#!/usr/bin/env python3
"""Actual Git commits and interruption/reentry for operation-v1 checkpoints."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import task_checkpoint as cp
import task_context as tc
import task_operation as op
import test_task_reconcile as fixtures
from test_task_context import git


class OperationTests(unittest.TestCase):
    commit_records = fixtures.RecoveryTests.commit_records

    def setUp(self):
        fixtures.RecoveryTests.setUp(self)
        path = self.root / "tasks/DEV-02.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n## Attempt notes\n\n- Initial attempt.\n", encoding="utf-8")
        self.commit_records()

    def args(self, operation_id=None):
        values = [str(self.root), "DEV-02", "app", "--include", "owned.py",
                  "--summary", "durable work", "--resume-action", "Run focused verification",
                  "--repo", f"pm={self.pm}", "--repo", f"app={self.app}",
                  "--operation-gist", self.plan_ref, "--authority-source-ref", "session:test-user-request"]
        if operation_id:
            values += ["--operation-id", operation_id]
        return cp.parse_args(values)

    def change(self):
        (self.app / "owned.py").write_text("version = 2\n", encoding="utf-8")

    def record(self):
        return next(iter(op.read_gist(self.root, self.plan_ref)[3].values()))

    def recover(self, **kwargs):
        return op.reconcile(self.root, self.plan_ref, self.record()["operation_id"],
                            {"pm": self.pm, "app": self.app}, **kwargs)

    def interrupt(self, point):
        def fail(name):
            if name == point:
                raise OSError("injected " + point)
        with patch.object(op, "interruption_point", side_effect=fail):
            with self.assertRaises(tc.ContextError):
                cp.checkpoint(self.args())

    def test_success_updates_all_records_and_strict_context_recovers(self):
        self.change()
        sha = cp.checkpoint(self.args())
        self.assertNotEqual(sha, self.app_head)
        self.assertEqual(self.record()["observed_result"]["commit_sha"], sha)
        self.commit_records()
        self.assertEqual(tc.build_context(self.root)["task"]["head_refs"]["app"], sha)
        count = git(self.app, "rev-list", "--count", "HEAD")
        self.assertEqual(cp.checkpoint(self.args(self.record()["operation_id"])), sha)
        self.assertEqual(git(self.app, "rev-list", "--count", "HEAD"), count)

    def test_F03_T04_unowned_residue_is_not_absorbed(self):
        self.change()
        (self.app / "user.txt").write_bytes(b"PRIVATE USER CONTENT")
        before = (self.root / self.plan_ref).read_bytes()
        with self.assertRaisesRegex(tc.ContextError, "UNOWNED_CHANGES"):
            cp.checkpoint(self.args())
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)
        self.assertEqual((self.app / "user.txt").read_bytes(), b"PRIVATE USER CONTENT")
        self.assertEqual((self.root / self.plan_ref).read_bytes(), before)

    def test_before_commit_resumes_exact_intent_and_commits_once(self):
        self.change()
        self.interrupt("before-commit")
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)
        self.assertEqual(self.recover()["observed_result"]["status"], "not-observed")
        sha = cp.checkpoint(self.args(self.record()["operation_id"]))
        self.assertEqual(git(self.app, "rev-list", "--count", f"{self.app_head}..{sha}"), "1")
        self.assertEqual(self.recover(apply=True, authority=True)["effect"], "UNCHANGED")

    def test_F03_T05_after_commit_only_records_without_second_commit(self):
        self.change()
        detail = (self.root / "tasks/DEV-02.md").read_bytes()
        self.interrupt("after-commit")
        sha = git(self.app, "rev-parse", "HEAD")
        self.assertNotEqual(sha, self.app_head)
        self.assertEqual((self.root / "tasks/DEV-02.md").read_bytes(), detail)
        self.assertEqual(self.record()["observed_result"]["status"], "not-observed")
        inspected = self.recover()
        self.assertEqual(inspected["observed_result"]["commit_sha"], sha)
        self.assertEqual((self.root / "tasks/DEV-02.md").read_bytes(), detail)
        self.assertEqual(self.recover(apply=True, authority=True)["effect"], "APPLIED")
        self.assertEqual(self.recover(apply=True, authority=True)["effect"], "UNCHANGED")
        self.assertEqual(git(self.app, "rev-list", "--count", f"{self.app_head}..HEAD"), "1")

    def test_F03_T06_detail_written_index_missing_reenters(self):
        self.change()
        index = (self.root / "TASKS.md").read_bytes()
        self.interrupt("after-detail")
        self.assertEqual((self.root / "TASKS.md").read_bytes(), index)
        detail = (self.root / "tasks/DEV-02.md").read_bytes()
        result = self.recover(apply=True, authority=True)
        self.assertEqual(result["effect"], "APPLIED", result)
        self.assertNotIn("tasks/DEV-02.md", result["recorded_fields"])
        self.assertEqual((self.root / "tasks/DEV-02.md").read_bytes(), detail)
        self.commit_records()
        tc.build_context(self.root)

    def test_after_index_before_final_record_repairs_only_missing_side(self):
        self.change()
        self.interrupt("after-index")
        result = self.recover(apply=True, authority=True)
        self.assertIn("STATUS.md", result["recorded_fields"])
        self.assertNotIn("TASKS.md", result["recorded_fields"])
        self.assertEqual(self.recover(apply=True, authority=True)["effect"], "UNCHANGED")

    def test_F03_T06_third_value_is_preserved(self):
        self.change()
        self.interrupt("after-detail")
        path = self.root / "TASKS.md"
        changed = path.read_bytes() + b"\nUSER EDIT\n"
        path.write_bytes(changed)
        self.assertEqual(self.recover(apply=True, authority=True)["conflicts"][0]["code"], "CONTENT_CONFLICT")
        self.assertEqual(path.read_bytes(), changed)

    def test_authority_is_not_inferred_from_intent(self):
        self.change()
        self.interrupt("after-commit")
        before = (self.root / "TASKS.md").read_bytes()
        self.assertEqual(self.recover(apply=True)["conflicts"][0]["code"], "AUTHORITY_REQUIRED")
        self.assertEqual((self.root / "TASKS.md").read_bytes(), before)

    def test_moved_head_does_not_reuse_previous_success(self):
        self.change()
        self.interrupt("after-commit")
        git(self.app, "commit", "--allow-empty", "-m", "new work")
        self.assertEqual(self.recover(apply=True, authority=True)["conflicts"][0]["code"], "REF_MOVED")

    def test_changed_owned_source_before_commit_does_not_resume(self):
        self.change()
        self.interrupt("before-commit")
        (self.app / "owned.py").write_bytes(b"USER CHANGED IT\n")
        with self.assertRaisesRegex(tc.ContextError, "CONTENT_CONFLICT"):
            cp.checkpoint(self.args(self.record()["operation_id"]))
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)

    def test_forged_original_document_cannot_be_written_back(self):
        self.change()
        self.interrupt("after-commit")
        raw, _, _, records = op.read_gist(self.root, self.plan_ref)
        record = copy.deepcopy(self.record())
        snap = record["expected_source"]["documents"]["TASKS.md"]
        record["expected_source"]["documents"]["TASKS.md"] = op.raw_snapshot(op.original(snap) + b"\nFORGED\n")
        op.save(self.root, self.plan_ref, record, raw)
        result = self.recover(apply=True, authority=True)
        self.assertEqual(result["conflicts"][0]["code"], "INVALID_INTENT")
        self.assertNotIn(b"FORGED", (self.root / "TASKS.md").read_bytes())

    def test_repeat_reconciliation_performs_zero_atomic_writes(self):
        self.change()
        cp.checkpoint(self.args())
        with patch.object(op.recovery, "atomic_replace", side_effect=AssertionError("unexpected write")):
            self.assertEqual(self.recover(apply=True, authority=True)["effect"], "UNCHANGED")

    def test_unrelated_management_residue_blocks_before_commit(self):
        self.change()
        path = self.root / "unowned.md"
        path.write_bytes(b"USER")
        with self.assertRaisesRegex(tc.ContextError, "UNOWNED_CHANGES"):
            cp.checkpoint(self.args())
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)
        self.assertEqual(path.read_bytes(), b"USER")

    def test_missing_attempt_notes_is_rejected_before_commit(self):
        path = self.root / "tasks/DEV-02.md"
        path.write_text(path.read_text(encoding="utf-8").split("## Attempt notes")[0], encoding="utf-8")
        self.commit_records()
        self.change()
        with self.assertRaisesRegex(tc.ContextError, "Attempt notes"):
            cp.checkpoint(self.args())
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)

    def test_operation_cli_inspects_and_applies_the_same_commit(self):
        self.change()
        self.interrupt("after-commit")
        command = [sys.executable, str(Path(op.recovery.__file__)), str(self.root),
                   "--plan-gist", self.plan_ref, "--operation-id", self.record()["operation_id"],
                   "--repo", f"pm={self.pm}", "--repo", f"app={self.app}"]
        check = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)["next_check"], "authorized-record-only")
        applied = subprocess.run(command + ["--apply", "--authorized"], capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(json.loads(applied.stdout)["effect"], "APPLIED")

    def test_commit_search_limit_preserves_sources(self):
        self.change()
        self.interrupt("after-commit")
        before = (self.root / "TASKS.md").read_bytes()
        with patch.object(op, "MAX_COMMITS", 0):
            result = self.recover(apply=True, authority=True)
        self.assertEqual(result["conflicts"][0]["code"], "RESOURCE_LIMIT")
        self.assertEqual((self.root / "TASKS.md").read_bytes(), before)

    def test_third_party_staged_content_is_not_overwritten_on_resume(self):
        self.change()
        self.interrupt("before-commit")
        path = self.app / "owned.py"
        path.write_bytes(b"USER STAGED DIFFERENT CONTENT\n")
        git(self.app, "add", "owned.py")
        staged = git(self.app, "rev-parse", ":owned.py")
        self.change()
        with self.assertRaisesRegex(tc.ContextError, "CONTENT_CONFLICT"):
            cp.checkpoint(self.args(self.record()["operation_id"]))
        self.assertEqual(git(self.app, "rev-parse", ":owned.py"), staged)
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)

    def test_wrong_expected_tree_does_not_accept_matching_operation_trailer(self):
        self.change()
        self.interrupt("after-commit")
        raw, _, _, _ = op.read_gist(self.root, self.plan_ref)
        record = self.record()
        record["expected_source"]["tree"] = git(self.app, "rev-parse", self.app_head + "^{tree}")
        op.save(self.root, self.plan_ref, record, raw)
        self.assertEqual(self.recover(apply=True, authority=True)["conflicts"][0]["code"], "COMMIT_CONTENT_MISMATCH")

    def test_actual_process_exit_after_commit_keeps_inspectable_lock_and_intent(self):
        self.change()
        command = (
            "import sys, os; sys.dont_write_bytecode = True; "
            "sys.path.insert(0, " + repr(str(Path(op.__file__).parent)) + "); "
            "import task_checkpoint as cp, task_operation as op; "
            "op.interruption_point = lambda name: os._exit(70) if name == 'after-commit' else None; "
            "cp.checkpoint(cp.parse_args(sys.argv[1:]))"
        )
        values = [str(self.root), "DEV-02", "app", "--include", "owned.py",
                  "--summary", "durable work", "--resume-action", "Run focused verification",
                  "--repo", f"pm={self.pm}", "--repo", f"app={self.app}",
                  "--operation-gist", self.plan_ref, "--authority-source-ref", "session:test-user-request"]
        process = subprocess.Popen([sys.executable, "-c", command, *values], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(timeout=30)
        self.assertEqual(process.returncode, 70, (stdout, stderr))
        sha = git(self.app, "rev-parse", "HEAD")
        self.assertNotEqual(sha, self.app_head)
        lock = self.root / ".operation.lock"
        self.assertEqual(json.loads(lock.read_bytes())["owner_pid"], process.pid)
        self.assertEqual(self.recover(apply=True, authority=True)["conflicts"][0]["code"], "COORDINATOR_BUSY")
        # Explicit fixture-owner recovery only after the actual child is terminal.
        self.assertEqual(process.poll(), 70)
        lock.unlink()
        self.assertEqual(self.recover(apply=True, authority=True)["effect"], "APPLIED")
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), sha)
        self.assertEqual(self.recover(apply=True, authority=True)["effect"], "UNCHANGED")


if __name__ == "__main__":
    unittest.main()
