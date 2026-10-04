#!/usr/bin/env python3
"""Real Git/files exercise authorized dependency writes and interrupted reentry."""
import sys
sys.dont_write_bytecode = True
import unittest
import json
import os
import subprocess
from unittest.mock import patch

import task_dependencies as deps
import task_operation as op
import task_context as tc
import test_task_reconcile as fixtures
from test_task_context import git


class DependencyWriteTests(unittest.TestCase):
    setUp = fixtures.RecoveryTests.setUp
    commit_records = fixtures.RecoveryTests.commit_records

    def replace(self, **kw):
        return deps.replace_dependencies(
            self.root, "GATE-ACCEPT", deps.recovery.digest((self.root / "TASKS.md").read_bytes()),
            kw.pop("dependencies", ["DEV-02", "SOL-001"]),
            operation_gist=self.plan_ref, repo_overrides={"pm": self.pm, "app": self.app},
            authority_source_ref="session:actual-request", authority=kw.pop("authority", True), **kw)

    def reconcile(self, result, **kw):
        return op.reconcile(self.root, self.plan_ref, result["operation_id"],
                            {"pm": self.pm, "app": self.app}, **kw)

    def test_gate_write_has_intent_and_preserves_git_refs(self):
        head = git(self.pm, "rev-parse", "HEAD")
        result = self.replace()
        self.assertEqual(result["effect"], "APPLIED", result)
        self.assertEqual(result["changed_paths"], ["TASKS.md", "tasks/GATE-ACCEPT.md"])
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)
        record = op.read_gist(self.root, self.plan_ref)[3][result["operation_id"]]
        self.assertEqual(record["kind"], "dependency-rewire")
        self.assertEqual(self.reconcile(result)["observed_result"]["status"], "success")
        self.commit_records()
        tc.build_context(self.root, repo_overrides={"pm": self.pm, "app": self.app})

    def test_partial_write_readback_and_authorized_resume(self):
        def fail(name):
            if name == "after-TASKS.md":
                raise OSError("injected interruption")
        with patch.object(deps, "interruption_point", side_effect=fail):
            result = self.replace()
        self.assertEqual(result["effect"], "PARTIAL", result)
        self.assertEqual(result["changed_paths"], ["TASKS.md"])
        before = (self.root / "tasks/GATE-ACCEPT.md").read_bytes()
        observed = self.reconcile(result)
        self.assertEqual(observed["observed_result"]["status"], "partial", observed)
        self.assertEqual((self.root / "tasks/GATE-ACCEPT.md").read_bytes(), before)
        self.assertEqual(self.reconcile(result, apply=True)["conflicts"][0]["code"], "AUTHORITY_REQUIRED")
        resumed = self.reconcile(result, apply=True, authority=True)
        self.assertEqual(resumed["effect"], "APPLIED", resumed)
        self.assertEqual(resumed["changed_paths"], ["tasks/GATE-ACCEPT.md"])
        with patch.object(deps.recovery, "atomic_replace", side_effect=AssertionError("duplicate write")):
            self.assertEqual(self.reconcile(result, apply=True, authority=True)["effect"], "UNCHANGED")

    def test_authority_and_stale_digest_fail_before_intent(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        result = self.replace(authority=False)
        self.assertEqual(result["conflicts"][0]["code"], "AUTHORITY_REQUIRED")
        result = deps.replace_dependencies(self.root, "GATE-ACCEPT", "0" * 64, ["SOL-001"],
            operation_gist=self.plan_ref, authority=True, authority_source_ref="session:request",
            repo_overrides={"pm": self.pm, "app": self.app})
        self.assertEqual(result["conflicts"][0]["code"], "INDEX_CHANGED")
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_third_value_after_partial_write_is_not_overwritten(self):
        with patch.object(deps, "interruption_point", side_effect=OSError("stop")):
            result = self.replace()
        detail = self.root / "tasks/GATE-ACCEPT.md"
        user_bytes = detail.read_bytes() + b"\nUSER EDIT\n"
        detail.write_bytes(user_bytes)
        resumed = self.reconcile(result, apply=True, authority=True)
        self.assertEqual(resumed["conflicts"][0]["code"], "CONTENT_CONFLICT", resumed)
        self.assertEqual(detail.read_bytes(), user_bytes)

    def test_noop_does_not_record_an_operation(self):
        before = (self.root / self.plan_ref).read_bytes()
        result = self.replace(dependencies=["DEV-02"])
        self.assertEqual(result["effect"], "UNCHANGED", result)
        self.assertIsNone(result["operation_id"])
        self.assertEqual((self.root / self.plan_ref).read_bytes(), before)

    def test_started_target_refused_without_changing_attempt(self):
        before = (self.root / "TASKS.md").read_bytes()
        result = deps.replace_dependencies(self.root, "DEV-02", deps.recovery.digest(before), [],
            operation_gist=self.plan_ref, authority=True, authority_source_ref="session:request",
            repo_overrides={"pm": self.pm, "app": self.app})
        self.assertEqual(result["conflicts"][0]["code"], "TASK_ALREADY_STARTED", result)
        self.assertEqual((self.root / "TASKS.md").read_bytes(), before)

    def test_intent_is_durable_before_any_target_write(self):
        before = (self.root / "TASKS.md").read_bytes()
        def stop(name):
            if name == "after-intent":
                raise OSError("power interruption")
        with patch.object(deps, "interruption_point", side_effect=stop):
            result = self.replace()
        self.assertEqual(result["effect"], "PARTIAL", result)
        self.assertEqual(result["changed_paths"], [])
        self.assertEqual((self.root / "TASKS.md").read_bytes(), before)
        self.assertEqual(self.reconcile(result)["observed_result"]["status"], "not-observed")

    def test_staged_target_is_refused_on_resume(self):
        with patch.object(deps, "interruption_point", side_effect=OSError("stop after intent")):
            result = self.replace()
        git(self.pm, "add", "project/PIRC-23/gists/parser.md")
        resumed = self.reconcile(result, apply=True, authority=True)
        self.assertEqual(resumed["conflicts"][0]["code"], "PRESTAGED_CHANGES", resumed)

    def test_changed_source_between_writes_is_not_ignored(self):
        original = (self.root / "REQUIREMENT.md").read_bytes()
        def mutate(name):
            if name == "before-tasks/GATE-ACCEPT.md":
                (self.root / "REQUIREMENT.md").write_bytes(original + b"\nUSER\n")
        with patch.object(deps, "interruption_point", side_effect=mutate):
            result = self.replace()
        self.assertEqual(result["effect"], "PARTIAL", result)
        self.assertEqual(result["changed_paths"], ["TASKS.md"])
        self.assertEqual(result["conflicts"][0]["code"], "SOURCE_CHANGED", result)
        self.assertTrue((self.root / "REQUIREMENT.md").read_bytes().endswith(b"USER\n"))

    def test_hardlink_source_is_refused_before_writing_intent(self):
        original = self.root / "tasks/GATE-ACCEPT.md"
        os.link(original, self.workspace / "alias.md")
        result = self.replace()
        self.assertEqual(result["conflicts"][0]["code"], "UNSAFE_SOURCE", result)
        self.assertIsNone(result["operation_id"])

    def test_ref_move_after_intent_is_not_replayed(self):
        with patch.object(deps, "interruption_point", side_effect=OSError("stop after intent")):
            result = self.replace()
        git(self.app, "commit", "--allow-empty", "-m", "new candidate")
        observed = self.reconcile(result, apply=True, authority=True)
        self.assertTrue(observed["conflicts"], observed)
        self.assertEqual(observed["changed_paths"], [])

    def test_cli_preview_is_read_only_and_does_not_print_source_prose(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        env = dict(os.environ)
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        completed = subprocess.run([sys.executable, deps.__file__, str(self.root),
            "GATE-ACCEPT", "--depends-on", "DEV-02,SOL-001"], capture_output=True, env=env)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        output = json.loads(completed.stdout)
        self.assertEqual(output["effect"], "NOT_APPLIED")
        self.assertNotIn("before", output)
        self.assertNotIn("after", output)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_corrupted_original_snapshot_cannot_invent_a_replacement(self):
        with patch.object(deps, "interruption_point", side_effect=OSError("stop")):
            result = self.replace()
        raw, _, _, records = op.read_gist(self.root, self.plan_ref)
        record = records[result["operation_id"]]
        snapshots = record["expected_source"]["documents"]
        snapshots["tasks/GATE-ACCEPT.md"] = op.raw_snapshot(
            op.original(snapshots["tasks/GATE-ACCEPT.md"]) + b"\nInjected original\n")
        op.save(self.root, self.plan_ref, record, raw)
        observed = self.reconcile(result, apply=True, authority=True)
        self.assertEqual(observed["conflicts"][0]["code"], "INVALID_INTENT", observed)
        self.assertEqual(observed["changed_paths"], [])

    def test_intent_write_completed_but_response_failed_keeps_operation_id(self):
        save = op.save
        def lost_response(*args, **kwargs):
            save(*args, **kwargs)
            raise OSError("response lost after intent replacement")
        with patch.object(op, "save", side_effect=lost_response):
            result = self.replace()
        self.assertIsNotNone(result["operation_id"], result)
        self.assertEqual(result["effect"], "PARTIAL", result)
        self.assertEqual(self.reconcile(result)["observed_result"]["status"], "not-observed")

    def test_target_replacement_completed_but_response_failed_reports_actual_path(self):
        replace = deps.recovery.atomic_replace
        def lost_response(path, raw):
            replace(path, raw)
            if path.name == "TASKS.md":
                raise OSError("response lost after target replacement")
        with patch.object(deps.recovery, "atomic_replace", side_effect=lost_response):
            result = self.replace()
        self.assertEqual(result["effect"], "PARTIAL", result)
        self.assertEqual(result["changed_paths"], ["TASKS.md"], result)
        self.assertEqual(self.reconcile(result)["observed_result"]["status"], "partial")


if __name__ == "__main__":
    unittest.main(verbosity=2)
