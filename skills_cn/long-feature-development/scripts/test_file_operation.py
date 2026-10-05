#!/usr/bin/env python3
"""Real files/Git prove saves and records are not mistaken for commits."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import file_operation as files
import task_operation as op
import test_task_reconcile as fixtures
from test_task_context import git


class FileOperationTests(unittest.TestCase):
    setUp = fixtures.RecoveryTests.setUp
    commit_records = fixtures.RecoveryTests.commit_records

    def prepare(self, changes=None, kind="save", repository="app"):
        expected = changes or {"owned.py": b"version = 2\n"}
        after = {p: files.recovery.digest(raw) if raw is not None else None for p, raw in expected.items()}
        return files.prepare(self.root, self.plan_ref, kind, repository, after, "session:actual-request",
                             {"pm": self.pm, "app": self.app}, authority=True)

    def observe(self, record, **kwargs):
        return op.reconcile(self.root, self.plan_ref, record["operation_id"],
                            {"pm": self.pm, "app": self.app}, **kwargs)

    def test_save_reentry_records_bytes_without_committing_or_resaving(self):
        record = self.prepare()
        self.assertEqual(self.observe(record)["observed_result"]["status"], "not-observed")
        (self.app / "owned.py").write_bytes(b"version = 2\n")
        result = self.observe(record, apply=True, authority=True)
        self.assertEqual(result["effect"], "APPLIED", result)
        self.assertEqual(result["observed_result"]["status"], "success")
        self.assertEqual(result["observed_result"]["evidence"], "current-bytes-not-commit")
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)
        with patch.object(files.recovery, "atomic_replace", side_effect=AssertionError("duplicate write")):
            repeated = self.observe(record, apply=True, authority=True)
        self.assertEqual(repeated["effect"], "UNCHANGED", repeated)

    def test_partial_save_only_reports_missing_side_without_replaying_it(self):
        record = self.prepare({"owned.py": b"new\n", "new.py": b"pending\n"})
        (self.app / "owned.py").write_bytes(b"new\n")
        result = self.observe(record, apply=True, authority=True)
        self.assertEqual(result["observed_result"]["status"], "partial", result)
        self.assertEqual(result["observed_result"]["pending_files"], ["new.py"])
        self.assertFalse((self.app / "new.py").exists())
        (self.app / "new.py").write_bytes(b"pending\n")
        self.assertEqual(self.observe(record)["observed_result"]["status"], "success")

    def test_record_observation_preserves_control_state_and_git_refs(self):
        detail = self.root / "tasks/DEV-02.md"
        text = detail.read_text(encoding="utf-8").replace("gists/parser.md", "gists/parser.md, gists/evidence.md")
        detail.write_text(text, encoding="utf-8")
        target = self.root / "gists/evidence.md"
        target.write_bytes(b"old evidence\n")
        self.commit_records()
        task_bytes = (self.root / "TASKS.md").read_bytes()
        pm_head = git(self.pm, "rev-parse", "HEAD")
        relative = target.relative_to(self.pm).as_posix()
        record = self.prepare({relative: b"new evidence\n"}, "record", "pm")
        target.write_bytes(b"new evidence\n")
        result = self.observe(record, apply=True, authority=True)
        self.assertEqual(result["observed_result"]["status"], "success", result)
        self.assertEqual((self.root / "TASKS.md").read_bytes(), task_bytes)
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), pm_head)
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)

    def test_third_file_value_is_preserved(self):
        record = self.prepare()
        (self.app / "owned.py").write_bytes(b"USER\n")
        result = self.observe(record, apply=True, authority=True)
        self.assertEqual(result["conflicts"][0]["code"], "CONTENT_CONFLICT")
        self.assertEqual((self.app / "owned.py").read_bytes(), b"USER\n")

    def test_extra_user_file_and_staged_content_are_rejected(self):
        record = self.prepare()
        (self.app / "owned.py").write_bytes(b"version = 2\n")
        user = self.app / "user.txt"
        user.write_bytes(b"USER")
        self.assertEqual(self.observe(record)["conflicts"][0]["code"], "UNOWNED_CHANGES")
        user.unlink()
        git(self.app, "add", "owned.py")
        self.assertEqual(self.observe(record)["conflicts"][0]["code"], "PRESTAGED_CHANGES")

    def test_commit_after_save_requires_separate_commit_reconciliation(self):
        record = self.prepare()
        (self.app / "owned.py").write_bytes(b"version = 2\n")
        git(self.app, "add", "owned.py")
        git(self.app, "commit", "-m", "saved and committed separately")
        self.assertEqual(self.observe(record)["conflicts"][0]["code"], "REF_MOVED")

    def test_absent_file_can_be_an_observed_deletion_not_an_action(self):
        record = self.prepare({"owned.py": None})
        (self.app / "owned.py").unlink()
        self.assertEqual(self.observe(record)["observed_result"]["status"], "success")
        self.assertFalse((self.app / "owned.py").exists())

    def test_authority_and_record_scope_are_explicit(self):
        with self.assertRaisesRegex(files.Error, "AUTHORITY_REQUIRED"):
            files.prepare(self.root, self.plan_ref, "save", "app", {}, "claimed")
        with self.assertRaisesRegex(files.Error, "INVALID_OPERATION_SCOPE"):
            self.prepare({"outside.md": b"not allowed"}, "record", "pm")
        record = self.prepare()
        self.assertEqual(self.observe(record, apply=True)["conflicts"][0]["code"], "AUTHORITY_REQUIRED")

    def test_changed_unowned_management_source_is_not_ignored(self):
        record = self.prepare()
        path = self.root / "SOLUTION.md"
        changed = path.read_bytes() + b"\nUSER\n"
        path.write_bytes(changed)
        self.assertEqual(self.observe(record)["conflicts"][0]["code"], "UNOWNED_CHANGES")
        self.assertEqual(path.read_bytes(), changed)

    def test_cli_reports_save_observation_without_rewriting_file(self):
        record = self.prepare()
        (self.app / "owned.py").write_bytes(b"version = 2\n")
        command = [sys.executable, str(Path(op.recovery.__file__)), str(self.root), "--plan-gist", self.plan_ref,
                   "--operation-id", record["operation_id"], "--repo", f"pm={self.pm}", "--repo", f"app={self.app}"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["observed_result"]["status"], "success")
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)


if __name__ == "__main__":
    unittest.main()
