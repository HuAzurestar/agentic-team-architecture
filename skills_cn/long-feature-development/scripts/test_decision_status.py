#!/usr/bin/env python3
"""Real Git status followups; host authorization is explicitly synthetic."""
import unittest
from unittest.mock import patch
from dataclasses import replace
import decision_apply as apply
import decision_status as status
from decision_evidence import decision_digest
import task_context as tc
import test_decision_apply as fixture
from test_task_context import git
from test_decision_point import evidence


class PointStatusTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.PointApplyTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root, self.pm = self.case.root, self.case.pm
        self.point = self.case.point
        self.digest = decision_digest(self.case.case.record)
        self.applied = apply.apply_point(self.case.prepare())

    def prepare(self):
        return status.PointStatus(self.root, self.pm, self.point, self.digest,
                                  **self.case.case.options)

    def test_reopened_leaf_status_records_actual_decision_sha(self):
        result = self.prepare().apply()
        self.assertEqual(result["status"], "STATUS_RECORDED")
        self.assertTrue(result["task_status_recorded"])
        self.assertFalse(result["merge_authorized"])
        self.assertEqual(git(self.pm, "show", "-s", "--format=%P", "HEAD"), self.applied["commit"])
        records = tc.task_records(tc.read_utf8(self.root / "TASKS.md"))
        self.assertEqual(records[self.point]["state"], "WIP")
        detail = tc.read_utf8(self.root / ("tasks/" + self.point + ".md"))
        self.assertIn(self.applied["commit"], detail)
        self.assertEqual(git(self.pm, "status", "--porcelain"), "")
        recovered = status.observe_status(self.root, self.pm, self.point, self.digest,
                                         self.case.case.options["repo_overrides"])
        self.assertEqual(recovered, result)

    def observe(self):
        return status.observe_status(self.root, self.pm, self.point, self.digest,
                                     self.case.case.options["repo_overrides"])

    def test_lost_merge_response_is_read_back_without_repeating(self):
        operation = self.prepare()
        real, merges = status.git, []
        def lost(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "merge":
                merges.append(args)
                raise status.CommitError("POINT_GIT_UNAVAILABLE")
            return result
        with patch.object(status, "git", side_effect=lost):
            result = operation.apply()
        self.assertEqual(result["status"], "STATUS_RECORDED")
        self.assertEqual(len(merges), 1)

    def test_unknown_dispatch_is_not_retried_on_reentry(self):
        operation = self.prepare()
        real = status.git
        def lost(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "update-ref" and args[1] == operation.dispatch:
                raise status.CommitError("POINT_GIT_UNAVAILABLE")
            if args[0] == "merge":
                self.fail("unknown dispatch must not launch merge")
            return result
        with patch.object(status, "git", side_effect=lost):
            result = operation.apply()
        self.assertEqual(result["status"], "STATUS_DISPATCHED_UNCONFIRMED")
        with patch.object(status, "git", side_effect=lost):
            again = self.prepare().apply()
        self.assertEqual(again, result)
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.applied["commit"])

    def test_revoked_grant_cannot_write_status(self):
        operation = self.prepare()
        self.case.case.grant = None
        with self.assertRaisesRegex(status.CommitError, "HUMAN_AUTHORITY_UNVERIFIED"):
            operation.apply()
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.applied["commit"])
        self.assertIsNone(status.read_ref(self.pm, operation.retained))

    def test_forged_otherwise_valid_task_metadata_is_not_recorded(self):
        operation = self.prepare()
        operation.apply()
        path = self.root / ("tasks/" + self.point + ".md")
        path.write_text(path.read_text(encoding="utf-8") + "\nUnrelated injected change.\n", encoding="utf-8")
        git(self.pm, "add", str(path))
        git(self.pm, "commit", "--amend", "--no-edit")
        changed = git(self.pm, "rev-parse", "HEAD")
        git(self.pm, "update-ref", operation.retained, changed)
        git(self.pm, "update-ref", operation.dispatch, changed)
        with self.assertRaisesRegex(status.CommitError, "STATUS_CONTENT_MISMATCH"):
            self.observe()
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), changed)

    def test_forged_commit_message_is_not_recorded(self):
        operation = self.prepare()
        operation.apply()
        git(self.pm, "commit", "--amend", "-m", "unbound task status")
        changed = git(self.pm, "rev-parse", "HEAD")
        git(self.pm, "update-ref", operation.retained, changed)
        git(self.pm, "update-ref", operation.dispatch, changed)
        with self.assertRaisesRegex(status.CommitError, "STATUS_REF_CONFLICT"):
            self.observe()

    def complete_again(self, outcome):
        self.prepare().apply()
        c = self.case.case
        c.record = evidence(tc.read_utf8(self.root / "SOLUTION.md"), self.point, outcome)
        c.record["decision_id"] = "decision-2"
        c.record["target_ref"].update(source_key="pm:solution", version=git(self.pm, "rev-parse", "HEAD"))
        c.grant = replace(c.grant, outcomes=(outcome,))
        c.reply = replace(c.reply, text=c.record["original_reply"])
        self.digest = decision_digest(c.record)
        self.applied = apply.apply_point(self.case.prepare())
        result = self.prepare().apply()
        self.assertEqual(result["status"], "STATUS_RECORDED")
        record = tc.task_records(tc.read_utf8(self.root / "TASKS.md"))[self.point]
        self.assertEqual(record["state"], "DONE")
        detail, refs = tc.task_detail(self.root, record)
        pm = next(item for item in refs if item["repository"] == "pm")
        self.assertEqual(pm["completion_sha"], self.applied["commit"])
        self.assertIn('"transitions":["RECORDING","DONE"]', detail)
        self.assertEqual(detail.count("### Point status history"), 2)

    def test_reconfirmed_point_completes_with_exact_decision_sha(self):
        self.complete_again("CONFIRMED")

    def test_rejected_point_also_completes_without_quality_or_merge_claim(self):
        self.complete_again("REJECTED")

    def test_late_foreign_edit_is_preserved_and_not_committed(self):
        operation = self.prepare()
        path = self.root / ("tasks/" + self.point + ".md")
        original = path.read_text(encoding="utf-8")
        changed = original + "\nExternal author note.\n"
        path.write_text(changed, encoding="utf-8")
        with self.assertRaisesRegex(status.CommitError, "POINT_SOURCE_CHANGED"):
            operation.apply()
        self.assertEqual(path.read_text(encoding="utf-8"), changed)
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.applied["commit"])

    def test_retained_candidate_reentry_reuses_exact_commit(self):
        first = self.prepare()
        sha = first._candidate()
        second = self.prepare()
        self.assertEqual(second._candidate(), sha)
        result = second.apply()
        self.assertEqual(result["status_commit"], sha)
        self.assertEqual(result["status"], "STATUS_RECORDED")


if __name__ == "__main__":
    unittest.main()
