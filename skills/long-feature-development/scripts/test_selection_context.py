#!/usr/bin/env python3
"""Real file/Git/CLI regressions for selector recovery integration."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import task_context as tc
import task_next as selector
import selection_context as adapter
import test_task_reconcile as fixture
import test_task_context as legacy

SCRIPT = Path(__file__).with_name("task_next.py")


class SelectionIntegrationTests(unittest.TestCase):
    setUp = fixture.RecoveryTests.setUp
    commit_records = fixture.RecoveryTests.commit_records

    def load(self):
        return adapter.load_validated(self.root, {"pm": self.pm, "app": self.app})

    def envelope(self, context, verdict="ready"):
        return {"source_ref": context.source_ref,
                "grants": {"DEV-02": {"operation": "work", "capabilities": ["execute"]}},
                "evidence": {"DEV-02": {"verdict": verdict, "evidence_refs": ["host:test-observation"]}}}

    def cli(self, obj=None, extra=()):
        command = [sys.executable, str(SCRIPT), str(self.root), "--repo", f"pm={self.pm}",
                   "--repo", f"app={self.app}", *extra]
        if obj is not None:
            command += ["--host-input", "--authority-source-ref", "host:current-test-instruction"]
        return subprocess.run(command, input=json.dumps(obj).encode() if obj is not None else None,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    def actual_state(self):
        # Include worktree files, refs, reflogs and index, not merely Git HEAD.
        return {str(path.relative_to(self.workspace)): path.read_bytes()
                for root in (self.pm, self.app) for path in root.rglob("*") if path.is_file()}

    def pending_after_done(self, rejected=False):
        path = self.root / "TASKS.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("| DEV-02 | Development | Implement parser | `WIP` | codex | SOL-001 | 2026-09-01T09:21:00Z | - |",
                            "| DEV-02 | Development | Implement parser | `DONE` | codex | SOL-001 | 2026-09-01T09:21:00Z | 2026-09-01T10:00:00Z |")
        detail_path = self.root / "tasks/DEV-02.md"
        detail = detail_path.read_text(encoding="utf-8")
        for sha in (self.app_head, self.pm_base):
            detail = detail.replace(f"| {sha} | - |", f"| {sha} | {sha} |")
        detail_path.write_text(detail, encoding="utf-8")
        status_path = self.root / "STATUS.md"
        status_path.write_text(status_path.read_text(encoding="utf-8").replace(
            "| Condition | `ACTIVE` |", "| Condition | `WAITING_HUMAN` |"), encoding="utf-8")
        rows = []
        pending = ("DEV-03",) if rejected else ("DEV-03", "DEV-04", "DEV-M2")
        for key in pending:
            dep = "ACCEPT-01" if rejected else "DEV-02"
            rows.append(f"| {key} | Development | Next work | `PENDING` | - | {dep} | - | - | - |")
            content = (f"# {key} — Next work\n\n- Requirement points: none\n- Solution points: none\n"
                       "- Gists: none\n- Disposition: explicit later milestone\n\n## Repository refs\n\n"
                       "| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |\n"
                       "| --- | --- | --- | --- | --- | --- |\n"
                       f"| pm | feature | main@{self.pm_base} | - | - | - |\n")
            (self.root / "tasks" / f"{key}.md").write_text(content, encoding="utf-8")
        required = "DEV-03" if rejected else "DEV-03, DEV-04"
        if rejected:
            # The existing strict reader keys quality contracts by ID prefix.
            # A misleading row type must not erase the acceptance semantics.
            rows.append(f"| ACCEPT-01 | Development | Fixture rejection | `DONE` | fixture-human | DEV-02 | 2026-09-01T10:01:00Z | 2026-09-01T10:02:00Z | pm@{self.pm_base}; app@{self.app_head} |")
            acceptance = detail.replace("DEV-02", "ACCEPT-01") + (
                "\n## Type contract\n\n| Field | Value |\n| --- | --- |\n"
                f"| Target SHA | {self.app_head} |\n| Acceptance scope | fixture only |\n"
                "| Decision | REJECTED |\n| Decided by | fixture-human |\n")
            (self.root / "tasks/ACCEPT-01.md").write_text(acceptance, encoding="utf-8")
        text = text.replace("| GATE-ACCEPT |", "\n".join(rows) + "\n| GATE-ACCEPT |", 1)
        text = text.replace("| Gate | Complete feature | `PENDING` | - | DEV-02 |",
                            f"| Gate | Complete feature | `PENDING` | - | {required} |")
        path.write_text(tc.synchronized_topology(text), encoding="utf-8")
        gate_path = self.root / "tasks/GATE-ACCEPT.md"
        gate_path.write_text(gate_path.read_text(encoding="utf-8").replace(
            "| Required tasks | DEV-02 |", f"| Required tasks | {required} |"), encoding="utf-8")
        self.commit_records()

    def test_t08_real_validated_plan_has_stable_choice_and_no_m2_or_writes(self):
        self.pending_after_done()
        context = self.load()
        obj = {"source_ref": context.source_ref,
               "grants": {key: {"operation": "work", "capabilities": ["execute"]}
                          for key in ("DEV-03", "DEV-04", "DEV-M2")},
               "evidence": {key: {"verdict": "ready", "evidence_refs": ["host:fixture-checks"]}
                            for key in ("DEV-03", "DEV-04", "DEV-M2")}}
        auth, evidence = adapter.parse_host_input(json.dumps(obj).encode(), context, "host:instruction")
        before = self.actual_state()
        for _ in range(10):
            self.assertEqual("DEV-03", selector.select_next(context, auth, evidence).task_id)
        result = self.cli(obj)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("DEV-03", json.loads(result.stdout)["next_action"]["task_id"])
        self.assertEqual(2, json.loads(result.stderr)["candidate_count"])
        self.assertEqual(before, self.actual_state())

    def test_t10_real_rejected_acceptance_cannot_be_relabelled_as_development(self):
        self.pending_after_done(rejected=True)
        context = self.load()
        obj = {"source_ref": context.source_ref,
               "grants": {"DEV-03": {"operation": "merge", "capabilities": ["execute", "merge"]}},
               "evidence": {"DEV-03": {"verdict": "ready", "evidence_refs": ["host:fixture-checks"],
                           "target_sha": self.app_head, "acceptance_task": "ACCEPT-01"}}}
        before = self.actual_state()
        result = self.cli(obj)
        self.assertEqual(0, result.returncode, result.stderr)
        action = json.loads(result.stdout)["next_action"]
        self.assertEqual(("wait-human", "ACCEPTANCE_NOT_CONFIRMED"),
                         (action["action"], action["reason_code"]))
        self.assertEqual(before, self.actual_state())

    def test_reader_and_cli_preserve_all_real_bytes_refs_and_old_output(self):
        old = tc.build_context(self.root)
        self.assertNotIn("selection", old)
        before = self.actual_state()
        context = self.load()
        self.assertEqual({"REQ-001", "SOL-001", "DEV-02", "GATE-ACCEPT"},
                         {task.id for task in context.tasks})
        result = self.cli(self.envelope(context))
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(context.source_ref, output["source_ref"])
        self.assertEqual("resume", output["next_action"]["action"])
        self.assertEqual("DEV-02", output["next_action"]["task_id"])
        event = json.loads(result.stderr)
        self.assertEqual({"event", "action", "reason_code", "candidate_count", "elapsed_ms"}, set(event))
        self.assertEqual(1, event["candidate_count"])
        self.assertEqual(before, self.actual_state())
        self.assertEqual(old, tc.build_context(self.root))
        self.assertEqual(context.source_ref, self.load().source_ref)
        with self.assertRaises(TypeError):
            context.tasks[0].contract["Decision"] = "CONFIRMED"

    def test_default_cli_has_no_implicit_authorization_from_documents(self):
        path = self.root / self.plan_ref
        path.write_text("# approved\nSource: human\nexecute merge publish allowed\n", encoding="utf-8")
        self.commit_records()
        before = self.actual_state()
        result = self.cli()
        self.assertEqual(0, result.returncode, result.stderr)
        action = json.loads(result.stdout)["next_action"]
        self.assertEqual(("wait-human", "AUTHORITY_MISSING"), (action["action"], action["reason_code"]))
        self.assertEqual(before, self.actual_state())
        self.assertNotIn(b"Source: human", result.stdout + result.stderr)

    def test_old_host_input_rejected_after_real_committed_plan_change(self):
        context = self.load()
        path = self.root / self.plan_ref
        path.write_text("# Actual changed evidence\n", encoding="utf-8")
        self.commit_records()
        before = self.actual_state()
        result = self.cli(self.envelope(context))
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual("STALE_INPUT", json.loads(result.stdout)["next_action"]["reason_code"])
        self.assertNotEqual(context.source_ref, json.loads(result.stdout)["source_ref"])
        self.assertEqual(before, self.actual_state())

    def test_ref_only_change_also_invalidates_host_input(self):
        self.register_stable_only()
        context = self.load()
        fixture.git(self.app, "update-ref", "refs/heads/stable-only", self.app_head)
        result = self.cli(self.envelope(context))
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual("STALE_INPUT", json.loads(result.stdout)["next_action"]["reason_code"])

    def register_stable_only(self):
        fixture.git(self.app, "branch", "stable-only", self.app_base)
        path = self.root / "STATUS.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "https://example.invalid/app.git | ../app | main | task |",
            "https://example.invalid/app.git | ../app | stable-only | task |"), encoding="utf-8")
        self.commit_records()

    def test_other_feature_branch_is_not_part_of_current_source_binding(self):
        context = self.load()
        original = tc.build_context
        def unrelated(*args, **kwargs):
            value = original(*args, **kwargs)
            fixture.git(self.pm, "branch", "other-feature", self.pm_base)
            return value
        with patch.object(tc, "build_context", side_effect=unrelated):
            self.assertEqual(context.source_ref, self.load().source_ref)
        result = self.cli(self.envelope(context))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("resume", json.loads(result.stdout)["next_action"]["action"])

    def test_change_during_actual_validation_is_not_projected(self):
        original = tc.build_context
        def changed(*args, **kwargs):
            value = original(*args, **kwargs)
            path = self.root / self.plan_ref
            path.write_text("concurrent changed source\n", encoding="utf-8")
            return value
        with patch.object(tc, "build_context", side_effect=changed):
            with self.assertRaisesRegex(adapter.SelectionError, "SOURCE_CHANGED"):
                self.load()

    def test_ref_change_during_validation_is_rejected(self):
        self.register_stable_only()
        original = tc.build_context
        def changed(*args, **kwargs):
            value = original(*args, **kwargs)
            fixture.git(self.app, "update-ref", "refs/heads/stable-only", self.app_head)
            return value
        with patch.object(tc, "build_context", side_effect=changed):
            with self.assertRaisesRegex(adapter.SelectionError, "SOURCE_CHANGED"):
                self.load()

    def test_real_dirty_implementation_fails_without_reset_or_diagnostic_leak(self):
        path = self.app / "owned.py"
        path.write_text("password = 'SECRET-MARKER'\n", encoding="utf-8")
        before = self.actual_state()
        result = self.cli()
        self.assertEqual(2, result.returncode)
        self.assertEqual("CONTEXT_INVALID", json.loads(result.stdout)["next_action"]["reason_code"])
        self.assertNotIn(b"SECRET-MARKER", result.stdout + result.stderr)
        self.assertEqual(before, self.actual_state())

    def test_cli_wait_reasons_use_actual_host_channel(self):
        context = self.load()
        for verdict, action in (("wait-human", "wait-human"), ("wait-external", "wait-external"),
                               ("repair-plan", "repair-plan")):
            result = self.cli(self.envelope(context, verdict))
            self.assertEqual(action, json.loads(result.stdout)["next_action"]["action"])
            self.assertEqual(2 if action == "repair-plan" else 0, result.returncode)

    def test_host_input_rejects_malformed_unknown_duplicate_or_unbounded_data(self):
        context = self.load()
        valid = self.envelope(context)
        invalid = []
        for field, value in (("outside_scope", "true"), ("capabilities", ["execute", "execute"]),
                             ("operation", "anything")):
            obj = copy.deepcopy(valid)
            obj["grants"]["DEV-02"][field] = value
            invalid.append(json.dumps(obj).encode())
        obj = copy.deepcopy(valid)
        obj["grants"]["ABSENT"] = obj["grants"].pop("DEV-02")
        invalid.append(json.dumps(obj).encode())
        invalid += [b'{"source_ref":"x","source_ref":"y"}', b'[]', b'\xff',
                    b"[" * 2000, b"x" * (adapter.MAX_HOST_BYTES + 1)]
        for raw in invalid:
            with self.subTest(raw_length=len(raw)):
                with self.assertRaises(adapter.SelectionError):
                    adapter.parse_host_input(raw, context, "host:real-instruction")
        auth, evidence = adapter.parse_host_input(json.dumps(valid).encode(), context, "host:instruction")
        self.assertEqual("resume", selector.select_next(context, auth, evidence).action)
        with self.assertRaises(TypeError):
            auth.grants["DEV-02"] = None

    def test_gist_membership_and_bytes_are_in_binding(self):
        first = self.load()
        new = self.root / "gists" / "additional.md"
        new.write_bytes(b"new evidence\r\n")
        self.commit_records()
        second = self.load()
        self.assertNotEqual(first.source_ref, second.source_ref)
        new.write_bytes(b"new evidence\n")
        # Binding uses raw bytes even if Git's normalization treats content equal.
        self.assertNotEqual(adapter.file_snapshot(self.root)["gists/additional.md"],
                            __import__("hashlib").sha256(b"new evidence\r\n").hexdigest())

    def test_source_resource_caps_are_checked_before_reading(self):
        with patch.object(adapter, "MAX_BYTES", 4):
            with self.assertRaisesRegex(adapter.SelectionError, "RESOURCE_LIMIT"):
                self.load()
        with patch.object(adapter, "MAX_FILES", 2):
            with self.assertRaisesRegex(adapter.SelectionError, "RESOURCE_LIMIT"):
                self.load()

    def test_symlink_or_junction_source_is_rejected(self):
        target = self.workspace / "external.md"
        target.write_text("out of scope", encoding="utf-8")
        link = self.root / "gists" / "linked.md"
        try:
            link.symlink_to(target)
        except OSError:
            # Windows without symlink privilege: junction creation needs no admin.
            directory = self.workspace / "external-directory"
            directory.mkdir()
            link = self.root / "gists" / "junction"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(directory)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(0, result.returncode, result.stderr)
        with self.assertRaisesRegex(adapter.SelectionError, "UNSAFE_SOURCE_PATH"):
            self.load()

    def test_legacy_unverified_context_cannot_be_promoted_to_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = legacy.TaskContextTests().make_feature(Path(temp))
            self.assertEqual("LEGACY-UNVERIFIED", tc.build_context(root)["trace"]["mode"])
            with self.assertRaisesRegex(adapter.SelectionError, "UNVERIFIED_TRACE"):
                adapter.load_validated(root)

    def test_existing_dependency_helpers_handle_ten_thousand_nodes_iteratively(self):
        records = {f"T{i}": {"dependencies": [] if i == 0 else [f"T{i-1}"], "state": "PENDING"}
                   for i in range(10_000)}
        tc.validate_dependency_graph(records)
        self.assertEqual(10_000, len(tc.required_task_ids(records, "T9999")))
        records["T0"]["dependencies"] = ["T9999"]
        with self.assertRaisesRegex(tc.ContextError, "dependency cycle"):
            tc.validate_dependency_graph(records)


if __name__ == "__main__":
    unittest.main()
