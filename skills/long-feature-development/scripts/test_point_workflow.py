#!/usr/bin/env python3
"""Business point workflow on real Git; human transport is synthetic."""
from dataclasses import replace
import unittest
from unittest.mock import patch
import point_workflow as workflow
import decision_apply as apply
import decision_status as status
import test_decision_apply as fixture
from test_decision_point import evidence
from test_task_context import git


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.PointApplyTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root, self.pm = self.case.root, self.case.pm

    def run_workflow(self):
        c = self.case
        return workflow.run_point(self.root, self.pm, c.point, c.case.record, **c.case.options)

    def test_first_run_records_two_commits_and_reentry_is_read_only(self):
        base = git(self.pm, "rev-parse", "HEAD")
        result = self.run_workflow()
        self.assertTrue(result["complete"])
        self.assertEqual(result["phase"], "RECORDED")
        self.assertEqual(git(self.pm, "rev-list", "--count", base + "..HEAD"), "2")
        self.assertFalse(result["merge_authorized"])
        self.case.case.options["read_reply"] = lambda ref: self.fail("completed readback must not request new decision")
        head = git(self.pm, "rev-parse", "HEAD")
        self.assertEqual(self.run_workflow(), result)
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), head)

    def test_resumes_applied_decision_without_reapplication(self):
        applied = apply.apply_point(self.case.prepare())
        with patch.object(workflow, "apply_point", side_effect=AssertionError("must not reapply")):
            result = self.run_workflow()
        self.assertTrue(result["complete"])
        self.assertEqual(result["decision_commit"], applied["commit"])

    def test_unknown_point_dispatch_does_not_start_status_or_retry(self):
        real = apply.git
        def lost(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "update-ref":
                raise status.CommitError("POINT_GIT_UNAVAILABLE")
            return result
        with patch.object(apply, "git", side_effect=lost):
            result = self.run_workflow()
        self.assertEqual(result["phase"], "DISPATCHED_UNCONFIRMED")
        with patch.object(workflow, "apply_point", side_effect=AssertionError("must not retry")):
            self.assertEqual(self.run_workflow(), result)
        self.assertIsNone(result["status_commit"])

    def test_assigned_consumer_handoff_names_exact_task_without_changes(self):
        c = self.case
        c.point = "SOL-001"
        c.case.record = evidence((self.root / "SOLUTION.md").read_text(encoding="utf-8"), c.point, "REOPENED")
        c.case.record["target_ref"].update(source_key="pm:solution", version=c.base)
        c.case.grant = replace(c.case.grant, exact_scope=(c.point,))
        c.case.reply = replace(c.case.reply, text=c.case.record["original_reply"])
        result = self.run_workflow()
        self.assertEqual(result["phase"], "DEPENDENCY_COORDINATION_REQUIRED")
        self.assertIn(dict(task_id="DEV-02", state="WIP", dependency="SOL-001"), result["blockers"])
        self.assertFalse(result["complete"])
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), c.base)
        self.assertEqual(git(self.pm, "for-each-ref", "--format=%(refname)", "refs/lfd/"), "")
        self.assertEqual(git(self.pm, "status", "--porcelain"), "")

    def test_unknown_status_dispatch_is_observed_without_retry(self):
        real = status.git
        def lost(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "update-ref" and args[1].startswith("refs/lfd/point-status-applications/"):
                raise status.CommitError("POINT_GIT_UNAVAILABLE")
            return result
        with patch.object(status, "git", side_effect=lost):
            result = self.run_workflow()
        self.assertEqual(result["phase"], "STATUS_DISPATCHED_UNCONFIRMED")
        with patch.object(workflow, "PointStatus", side_effect=AssertionError("must not dispatch again")):
            self.assertEqual(self.run_workflow(), result)
        self.assertFalse(result["complete"])

    def test_missing_human_grant_cannot_apply_point(self):
        self.case.case.grant = None
        with self.assertRaisesRegex(status.CommitError, "HUMAN_AUTHORITY_UNVERIFIED"):
            self.run_workflow()
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.case.base)
        self.assertEqual(git(self.pm, "for-each-ref", "--format=%(refname)", "refs/lfd/"), "")

    def test_revocation_between_legs_preserves_decision_then_resumes(self):
        real = workflow.apply_point
        saved = self.case.case.grant
        def revoke(operation):
            result = real(operation)
            self.case.case.grant = None
            return result
        with patch.object(workflow, "apply_point", side_effect=revoke):
            with self.assertRaisesRegex(status.CommitError, "HUMAN_AUTHORITY_UNVERIFIED"):
                self.run_workflow()
        decision = git(self.pm, "rev-parse", "HEAD")
        self.assertNotEqual(decision, self.case.base)
        self.case.case.grant = saved
        result = self.run_workflow()
        self.assertTrue(result["complete"])
        self.assertEqual(result["decision_commit"], decision)


if __name__ == "__main__":
    unittest.main(verbosity=2)
