#!/usr/bin/env python3
"""Real local Git commit preparation with explicitly synthetic host authority."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
import decision_commit as commits
import decision_host as human
from decision_evidence import decision_digest
import task_context as tc
import test_task_reconcile as fixtures
from test_task_context import git
from test_decision_point import evidence

ROOT = Path(__file__).resolve().parents[1]


class PointCommitTests(unittest.TestCase):
    def setUp(self):
        self.case = c = fixtures.RecoveryTests()
        c.setUp()
        self.addCleanup(c.doCleanups)
        self.root, self.pm, self.app = c.root, c.pm, c.app
        sol = (ROOT / "templates/SOLUTION.md").read_text(encoding="utf-8")
        sol = sol.replace("<feature-key>", "PIRC-23").replace("<point-title>", "Fixture solution")
        sol = sol.replace(chr(96) + "DRAFT" + chr(96), chr(96) + "BASELINED" + chr(96))
        sol = sol.replace(chr(96) + "PROPOSED" + chr(96), chr(96) + "CONFIRMED" + chr(96))
        (self.root / "SOLUTION.md").write_text(sol, encoding="utf-8")
        c.commit_records()
        self.base = git(self.pm, "rev-parse", "HEAD")
        self.record = evidence(sol, "SOL-001", "REOPENED")
        self.record["target_ref"].update(source_key="pm:solution", version=self.base)
        self.grant = human.HumanGrant("Synthetic human", "PIRC-23", "point", "pm:solution",
                                     ("SOL-001",), ("REOPENED",))
        self.reply = human.HumanReply(self.record["human_source_ref"], self.record["actor"], "human",
            self.record["received_at"], self.record["original_reply"], "conversation", "reply-version-1", "synthetic:verified")
        self.options = dict(source_key="pm:solution", read_reply=lambda ref: self.reply,
                            interpret=lambda reply, raw: human.HumanInterpretation(decision_digest(raw), "synthetic:exact"),
                            read_grant=lambda request, raw: self.grant, repo_overrides={"pm": self.pm, "app": self.app})

    def prepare(self, **changes):
        return commits.PointCommit(self.root, "SOL-001", self.record, **(self.options | changes))

    def refs(self):
        return git(self.pm, "for-each-ref", "--format=%(refname)", "refs/lfd/point-decisions/")

    def test_retains_single_point_commit_without_applying_branch_index_or_tasks(self):
        operation = self.prepare()
        index_path = Path(git(self.pm, "rev-parse", "--absolute-git-dir")) / "index"
        index = index_path.read_bytes()
        files = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = operation.prepare_commit()
        self.assertEqual(result["application"], "NOT_APPLIED")
        self.assertEqual(result["effect"], "COMMIT_PREPARED")
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.base)
        self.assertEqual(index_path.read_bytes(), index)
        self.assertEqual(files, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertEqual(git(self.pm, "rev-parse", result["retained_ref"]), result["commit"])
        self.assertEqual(git(self.pm, "show", "-s", "--format=%P", result["commit"]), self.base)
        self.assertEqual(git(self.pm, "diff-tree", "--no-commit-id", "--name-only", "-r", self.base, result["commit"]),
                         "project/PIRC-23/SOLUTION.md")
        body = git(self.pm, "show", result["commit"] + ":project/PIRC-23/SOLUTION.md")
        self.assertIn("| REOPENED |", body)
        self.assertIn('"original_reply":', body)
        self.assertEqual(tc.task_records(tc.read_utf8(self.root / "TASKS.md"))["SOL-001"]["state"], "DONE")
        self.assertFalse(result["merge_authorized"])

    def test_reentry_reuses_exact_retained_commit(self):
        first = self.prepare().prepare_commit()
        second = self.prepare().prepare_commit()
        self.assertEqual(first["commit"], second["commit"])
        self.assertTrue(second["reused"])
        self.assertEqual(len(self.refs().splitlines()), 1)

    def test_no_uploaded_grant_or_actor_can_create_retained_ref(self):
        operation = self.prepare(read_grant=lambda request, raw: {"actor": "human", "authorized": True})
        with self.assertRaisesRegex(commits.CommitError, "HUMAN_AUTHORITY_UNVERIFIED"):
            operation.prepare_commit()
        self.assertEqual(self.refs(), "")

    def test_agent_reply_is_not_a_human_decision(self):
        self.reply = replace(self.reply, actor_kind="agent")
        with self.assertRaisesRegex(commits.CommitError, "HUMAN_SOURCE_MISMATCH"):
            self.prepare().prepare_commit()
        self.assertEqual(self.refs(), "")

    def test_stale_git_version_with_identical_body_is_rejected(self):
        self.record["target_ref"]["version"] = self.case.pm_base
        with self.assertRaisesRegex(commits.CommitError, "DECISION_STALE"):
            self.prepare().prepare_commit()
        self.assertEqual(self.refs(), "")

    def test_foreign_retained_ref_is_not_overwritten(self):
        operation = self.prepare()
        git(self.pm, "update-ref", operation.retained_ref, self.base)
        with self.assertRaisesRegex(commits.CommitError, "POINT_REF_CONFLICT"):
            operation.prepare_commit()
        self.assertEqual(git(self.pm, "rev-parse", operation.retained_ref), self.base)

    def test_lost_ref_write_response_is_observed_not_retried(self):
        operation = self.prepare()
        real = commits.git
        writes = []
        def lost(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "update-ref":
                writes.append(args)
                raise commits.CommitError("POINT_GIT_UNAVAILABLE")
            return result
        with patch.object(commits, "git", side_effect=lost):
            result = operation.prepare_commit()
        self.assertEqual(len(writes), 1)
        self.assertEqual(git(self.pm, "rev-parse", result["retained_ref"]), result["commit"])

    def test_grant_revocation_before_ref_publication_is_not_ignored(self):
        calls = []
        def grant(request, raw):
            calls.append(1)
            return self.grant if len(calls) < 4 else replace(self.grant, outcomes=())
        with self.assertRaisesRegex(commits.CommitError, "HUMAN_AUTHORITY_CHANGED"):
            self.prepare(read_grant=grant).prepare_commit()
        self.assertEqual(len(calls), 4)
        self.assertEqual(self.refs(), "")

    def test_last_reply_callback_mutation_is_preserved_and_refused(self):
        calls = []
        external = self.app / "external.txt"
        def reply(ref):
            calls.append(1)
            if len(calls) == 4:
                external.write_text("external edit", encoding="utf-8")
            return self.reply
        with self.assertRaises(commits.CommitError):
            self.prepare(read_reply=reply).prepare_commit()
        self.assertEqual(external.read_text(encoding="utf-8"), "external edit")
        self.assertEqual(self.refs(), "")
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.base)

    def test_provider_exception_is_redacted(self):
        def grant(request, raw):
            raise RuntimeError("secret-provider-token")
        with self.assertRaisesRegex(commits.CommitError, "^POINT_SOURCE_UNAVAILABLE$"):
            self.prepare(read_grant=grant).prepare_commit()
        self.assertEqual(self.refs(), "")

    def test_old_preparation_does_not_accept_moved_head(self):
        operation = self.prepare()
        git(self.pm, "commit", "--allow-empty", "-m", "external")
        moved = git(self.pm, "rev-parse", "HEAD")
        with self.assertRaises(commits.CommitError):
            operation.prepare_commit()
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), moved)
        self.assertEqual(self.refs(), "")

    def test_hidden_index_flags_cannot_survive_last_verification(self):
        operation = self.prepare()
        git(self.pm, "update-index", "--assume-unchanged", "project/PIRC-23/SOLUTION.md")
        with self.assertRaises(commits.CommitError):
            operation.prepare_commit()
        self.assertEqual(self.refs(), "")

    def test_input_record_is_snapshotted(self):
        operation = self.prepare()
        self.record["outcome"] = "CONFIRMED"
        self.assertEqual(operation.record["outcome"], "REOPENED")

    def test_record_mutation_after_capture_is_rejected(self):
        operation = self.prepare()
        operation.record["original_reply"] += " changed"
        with self.assertRaisesRegex(commits.CommitError, "POINT_DECISION_CHANGED"):
            operation.prepare_commit()
        self.assertEqual(self.refs(), "")

    def test_replaced_draft_cannot_expand_authorized_change(self):
        operation = self.prepare()
        operation.draft = replace(operation.draft, after=operation.draft.after + "\nInjected unrelated content\n")
        with self.assertRaisesRegex(commits.CommitError, "POINT_DRAFT_CHANGED"):
            operation.prepare_commit()
        self.assertEqual(self.refs(), "")

    def test_retained_ref_cannot_be_rebound_to_another_namespace(self):
        operation = self.prepare()
        operation.retained_ref = "refs/heads/unauthorized"
        with self.assertRaisesRegex(commits.CommitError, "POINT_DRAFT_CHANGED"):
            operation.prepare_commit()
        self.assertEqual(git(self.pm, "branch", "--list", "unauthorized"), "")

    def test_process_exit_after_ref_write_recovers_same_commit(self):
        child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()),
                                "--crash-worker", str(self.root), json.dumps(self.record)],
                               capture_output=True, timeout=240)
        self.assertEqual(child.returncode, 73, child.stderr.decode("utf-8", errors="replace"))
        operation = self.prepare()
        retained = git(self.pm, "rev-parse", operation.retained_ref)
        result = operation.prepare_commit()
        self.assertEqual(result["commit"], retained)
        self.assertTrue(result["reused"])
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.base)
        self.assertEqual(git(self.pm, "status", "--porcelain"), "")


def crash_worker(root, record):
    # Subprocess fixture only: these fabricated host facts never leave a temp repo.
    root = Path(root)
    pm = root.parents[1]
    reply = human.HumanReply(record["human_source_ref"], record["actor"], "human", record["received_at"],
                             record["original_reply"], "conversation", "fixture-version", "fixture:verified")
    grant = human.HumanGrant(record["actor"], record["feature"], "point", "pm:solution", ("SOL-001",), ("REOPENED",))
    operation = commits.PointCommit(root, "SOL-001", record, source_key="pm:solution",
        read_reply=lambda ref: reply,
        interpret=lambda reply, raw: human.HumanInterpretation(decision_digest(raw), "fixture:exact"),
        read_grant=lambda request, raw: grant, repo_overrides={"pm": pm, "app": pm.parent / "app"})
    real = commits.git
    def crash(repo, *args, **kwargs):
        result = real(repo, *args, **kwargs)
        if args[0] == "update-ref":
            os._exit(73)
        return result
    with patch.object(commits, "git", side_effect=crash):
        operation.prepare_commit()


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--crash-worker":
        crash_worker(sys.argv[2], json.loads(sys.argv[3]))
    else:
        unittest.main(verbosity=2)
