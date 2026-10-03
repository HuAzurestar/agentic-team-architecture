#!/usr/bin/env python3
"""Real Git chain fixtures; synthetic reviewer claims never prove independence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
import task_context as tc
import task_create as create
import task_state as state
import task_checkpoint as checkpoint
import task_dependencies as deps
import task_operation as operation
import review_report as report
import test_task_reconcile as fixture
from test_task_context import git
from test_review_report import report as report_fixture, check, finding, key_of


class ReworkChainTests(unittest.TestCase):
    commit_records = fixture.RecoveryTests.commit_records

    def setUp(self):
        fixture.RecoveryTests.setUp(self)
        detail = self.root / "tasks/DEV-02.md"
        detail.write_text(detail.read_text(encoding="utf-8") + "\n## Attempt notes\n\n- Fixture coordinator.\n",
                          encoding="utf-8")
        self.commit_records()

    def brief(self):
        text = "# Synthetic acceptance brief\n\nTarget version: " + self.app_head + "\n"
        for title, body in (
            ("What changed", "Synthetic protocol fixture only."),
            ("How to check", "Inspect the fixture chain and unchanged original report."),
            ("Evidence", "Fixture tests; no real independent review."),
            ("Out of scope", "Actual product acceptance and merge."),
            ("Known limitations", "A real human decision is still missing."),
            ("Decision options", "Accept, request changes, or defer; no option has been selected.")):
            text += "\n## " + title + "\n\n" + body + "\n"
        (self.root / "gists/brief.md").write_text(text, encoding="utf-8")

    def make_task(self, kind, dependencies, contracts):
        args = [str(self.root), "--type", kind, "--name", "Synthetic " + kind,
                "--depends-on", ",".join(dependencies) or "-", "--goal", "Verify chain protocol",
                "--work", "Fixture only", "--completion-condition", "Fixture report delivered",
                "--resume-action", "Continue fixture", "--requirement-points", "REQ-001",
                "--solution-points", "SOL-001", "--repo-ref", f"app|task|main@{self.app_base}"]
        for field, value in contracts.items():
            args += ["--contract", field + "=" + value]
        task = create.create(self.root, create.parse_args(args))
        return task

    def fields(self, task, values):
        path = self.root / f"tasks/{task}.md"
        text = path.read_text(encoding="utf-8")
        fields = tc.type_contract_fields(text, task)
        for field, value in values.items():
            old = deps.recovery.row_line(text, [field, fields[field]])
            text = text.replace(old, "| " + field + " | " + value + " |")
        path.write_text(text, encoding="utf-8")

    def start(self, task):
        path = self.root / f"tasks/{task}.md"
        text = path.read_text(encoding="utf-8").replace(
            f"| app | task | main@{self.app_base} | - | - | - |",
            f"| app | task | main@{self.app_base} | task@{self.app_head} | {self.app_head} | - |")
        path.write_text(text, encoding="utf-8")
        state.update(self.root, state.parse_args([str(self.root), task, "--to", "WIP",
            "--owner", "fixture", "--started-at", "2026-10-03T01:00:00Z", "--head", "app@" + self.app_head]))

    def finish(self, task):
        state.update(self.root, state.parse_args([str(self.root), task, "--to", "RECORDING"]))
        path = self.root / f"tasks/{task}.md"
        record = tc.task_records((self.root / "TASKS.md").read_text(encoding="utf-8"))[task]
        sha = record["head_refs"]["app"]
        text = path.read_text(encoding="utf-8").replace("| " + sha + " | - |", "| " + sha + " | " + sha + " |")
        path.write_text(text, encoding="utf-8")
        state.update(self.root, state.parse_args([str(self.root), task, "--to", "DONE",
            "--completed-at", "2026-10-03T02:00:00Z"]))

    def rewire(self, task, dependencies):
        return deps.replace_dependencies(self.root, task,
            deps.recovery.digest((self.root / "TASKS.md").read_bytes()), dependencies,
            operation_gist=self.plan_ref, repo_overrides={"pm": self.pm, "app": self.app},
            authority=True, authority_source_ref="fixture:actual-caller-authorization")

    def report_value(self, task, identity, target, prior=None):
        value = report_fixture(identity, identity + "-attempt")
        evidence = "gists/observed-v1.md"
        ref = {"path": evidence, "sha256": hashlib.sha256((self.root / evidence).read_bytes()).hexdigest()}
        value.update(feature=self.root.name, review_task=task, target_refs={"app": target},
                     packet_id=identity + "-packet", checklist_ref=ref, evidence_refs=[ref])
        value["checks"] = [check(outcome="FAIL", findings=["F1"])]
        value["checks"][0]["evidence_refs"] = [ref]
        value["findings"] = [finding()]
        item = value["findings"][0]
        item["evidence_refs"] = [ref]
        if prior is not None:
            item.update(status="addressed", resolution_ref=ref, duplicate_of=key_of(prior, "F1"),
                        duplicate_reason="Same explicitly identified requirement failure", duplicate_evidence_refs=[ref])
        return value

    def store_report(self, task, path, value):
        (self.root / path).write_text("# Synthetic protocol fixture\n\n```report-v1\n" +
            json.dumps(value, indent=2) + "\n```\n", encoding="utf-8")
        detail = self.root / f"tasks/{task}.md"
        text = detail.read_text(encoding="utf-8").replace(
            "- Gists: " + path, "- Gists: " + path + ", gists/observed-v1.md")
        detail.write_text(text, encoding="utf-8")

    def test_F04_T04_T05_blocked_report_rework_new_target_and_immutable_old_report(self):
        (self.root / "gists/observed-v1.md").write_text("Synthetic finding on the original candidate.\n", encoding="utf-8")
        r1 = self.make_task("Review", ["SOL-001"], {
            "Target SHA": self.app_head, "Blocking findings": "1", "Deferred findings": "0",
            "Result gist": "gists/r1.md"})
        old_target = self.app_head
        original = self.report_value(r1, "report-r1", old_target)
        self.store_report(r1, "gists/r1.md", original)
        self.start(r1)
        self.finish(r1)
        counted = report.compute_report(original)
        self.assertTrue(counted["summary"]["valid"], counted)
        self.assertEqual(counted["counts"]["open_blockers"], 1)
        frozen_report = (self.root / "gists/r1.md").read_bytes()
        frozen_detail = (self.root / f"tasks/{r1}.md").read_bytes()
        w1 = self.make_task("Rework", [r1], {"Source findings": "report-r1#F1",
            "Target SHA": old_target, "Result gist": "gists/w1.md"})
        (self.root / "gists/w1.md").write_text("Synthetic repair evidence.\n", encoding="utf-8")
        t2 = self.make_task("Test", [w1], {"Target SHA": old_target,
            "Environment": "Synthetic protocol fixture", "Planned checks": "1", "Executed": "1",
            "Passed": "1", "Failed": "0", "Skipped": "0", "Unknown": "0", "Result gist": "gists/t2.md"})
        (self.root / "gists/t2.md").write_text("Synthetic test record, not independent product testing.\n", encoding="utf-8")
        r2 = self.make_task("Review", [t2], {"Target SHA": old_target, "Blocking findings": "1",
            "Deferred findings": "0", "Result gist": "gists/r2.md"})
        (self.root / "gists/r2.md").write_text("Pending synthetic report.\n", encoding="utf-8")
        acceptance = self.make_task("Acceptance", [r1], {"Target SHA": old_target,
            "Acceptance scope": "Synthetic fixture only", "Acceptance brief": "gists/brief.md"})
        self.brief()
        self.commit_records()
        result = self.rewire(acceptance, [r2])
        self.assertEqual(result["effect"], "APPLIED", result)
        self.commit_records()
        result = self.rewire("GATE-ACCEPT", ["DEV-02", acceptance])
        self.assertEqual(result["effect"], "APPLIED", result)
        self.commit_records()
        records = tc.task_records((self.root / "TASKS.md").read_text(encoding="utf-8"))
        tc.validate_dependency_graph(records)
        self.assertEqual(records[r1]["state"], "DONE")
        self.assertEqual(records[w1]["readiness"], "READY")
        self.assertEqual(records[acceptance]["readiness"], "WAITING")
        with self.assertRaisesRegex(tc.ContextError, "not READY"):
            state.update(self.root, state.parse_args([str(self.root), acceptance, "--to", "WIP",
                "--owner", "fixture", "--started-at", "now", "--head", "app@" + self.app_head]))
        self.start(w1)
        self.commit_records()
        (self.app / "owned.py").write_text("version = 2\n", encoding="utf-8")
        self.app_head = checkpoint.checkpoint(checkpoint.parse_args([str(self.root), "DEV-02", "app",
            "--include", "owned.py", "--summary", "fixture repair F1", "--resume-action", "Verify new candidate",
            "--repo", f"pm={self.pm}", "--repo", f"app={self.app}"]))
        self.assertNotEqual(self.app_head, old_target)
        status = self.root / "STATUS.md"
        status.write_text(status.read_text(encoding="utf-8").replace(
            "| task | " + old_target + " | DEV-02 |", "| task | " + self.app_head + " | DEV-02 |"),
            encoding="utf-8")
        detail = self.root / f"tasks/{w1}.md"
        detail.write_text(checkpoint.replace_detail_checkpoint(detail.read_text(encoding="utf-8"),
            "app", self.app_head, "Deliver repair evidence", "fixture repair"), encoding="utf-8")
        index = self.root / "TASKS.md"
        index.write_text(checkpoint.replace_task_head(index.read_text(encoding="utf-8"), w1,
            "app", self.app_head), encoding="utf-8")
        self.fields(w1, {"Output SHA": self.app_head})
        self.finish(w1)
        self.fields(t2, {"Target SHA": self.app_head})
        self.start(t2)
        self.finish(t2)
        self.fields(r2, {"Target SHA": self.app_head})
        newer = self.report_value(r2, "report-r2", self.app_head, original)
        self.store_report(r2, "gists/r2.md", newer)
        self.start(r2)
        self.finish(r2)
        self.commit_records()
        tc.build_context(self.root, repo_overrides={"pm": self.pm, "app": self.app})
        self.assertEqual((self.root / "gists/r1.md").read_bytes(), frozen_report)
        self.assertEqual((self.root / f"tasks/{r1}.md").read_bytes(), frozen_detail)
        result = report.compute_report(newer, related_reports=[original])
        self.assertTrue(result["summary"]["valid"], result)
        self.assertEqual(result["counts"]["open_blockers"], 1)
        self.assertFalse(result["quality_assessed"])
        authored_closure = copy.deepcopy(newer)
        authored_closure["findings"][0].update(status="closed",
            verified_by=authored_closure["context"]["implementation_author"],
            verified_ref=authored_closure["evidence_refs"][0], verified_target_refs=authored_closure["target_refs"])
        self.assertFalse(report.compute_report(authored_closure, related_reports=[original])["summary"]["valid"])
        decision = tc.type_contract_fields((self.root / f"tasks/{acceptance}.md").read_text(encoding="utf-8"), acceptance)
        self.assertEqual(decision["Decision"], "WAITING")

    def test_F04_T06_active_acceptance_refuses_rewire_without_faking_human_decision(self):
        acceptance = self.make_task("Acceptance", ["SOL-001"], {"Target SHA": self.app_head,
            "Acceptance scope": "Synthetic fixture only", "Acceptance brief": "gists/brief.md"})
        self.brief()
        review = self.make_task("Review", ["SOL-001"], {"Target SHA": self.app_head,
            "Result gist": "gists/review.md"})
        (self.root / "gists/review.md").write_text("Review not yet executed.\n", encoding="utf-8")
        self.start(acceptance)
        self.commit_records()
        result = self.rewire("GATE-ACCEPT", ["DEV-02", acceptance])
        self.assertEqual(result["effect"], "APPLIED", result)
        self.commit_records()
        for phase in ("WIP", "RECORDING"):
            if phase == "RECORDING":
                state.update(self.root, state.parse_args([str(self.root), acceptance, "--to", phase]))
                self.commit_records()
            before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
            result = self.rewire(acceptance, [review])
            self.assertEqual(result["conflicts"][0]["code"], "TASK_ALREADY_STARTED", result)
            hidden = self.rewire("GATE-ACCEPT", ["DEV-02", review])
            self.assertEqual(hidden["conflicts"][0]["code"], "ACTIVE_ATTEMPT_WOULD_BE_HIDDEN", hidden)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            fields = tc.type_contract_fields((self.root / f"tasks/{acceptance}.md").read_text(encoding="utf-8"), acceptance)
            self.assertEqual(fields["Decision"], "WAITING")
            self.assertEqual(fields["Decided by"], "-")

    def test_started_gate_cannot_be_rewired(self):
        gate = self.make_task("Gate", ["SOL-001"], {})
        self.start(gate)
        self.commit_records()
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        result = self.rewire(gate, ["DEV-02"])
        self.assertEqual(result["conflicts"][0]["code"], "TASK_ALREADY_STARTED", result)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_actual_process_exit_after_index_keeps_lock_and_partial_intent(self):
        command = ("import sys, os; sys.dont_write_bytecode=True; "
            "sys.path.insert(0, " + repr(str(Path(deps.__file__).parent)) + "); "
            "import task_dependencies as d; "
            "d.interruption_point=lambda name: os._exit(70) if name == 'after-TASKS.md' else None; "
            "raise SystemExit(d.main(sys.argv[1:]))")
        index_digest = deps.recovery.digest((self.root / "TASKS.md").read_bytes())
        completed = subprocess.run([sys.executable, "-c", command, str(self.root), "GATE-ACCEPT",
            "--depends-on", "DEV-02,SOL-001", "--expected-index-digest", index_digest,
            "--operation-gist", self.plan_ref, "--apply", "--authorized", "--authority-source-ref", "fixture:request",
            "--repo", f"pm={self.pm}", "--repo", f"app={self.app}"], capture_output=True, timeout=90)
        self.assertEqual(completed.returncode, 70, completed.stderr + completed.stdout)
        records = operation.read_gist(self.root, self.plan_ref)[3]
        self.assertEqual(len(records), 1)
        identity = next(iter(records))
        overrides = {"pm": self.pm, "app": self.app}
        self.assertEqual(operation.reconcile(self.root, self.plan_ref, identity, overrides)["observed_result"]["status"], "partial")
        self.assertEqual(operation.reconcile(self.root, self.plan_ref, identity, overrides,
            apply=True, authority=True)["conflicts"][0]["code"], "COORDINATOR_BUSY")
        # Only fixture-owner cleanup after subprocess.run confirmed terminal exit.
        (self.root / ".operation.lock").unlink()
        result = operation.reconcile(self.root, self.plan_ref, identity, overrides, apply=True, authority=True)
        self.assertEqual(result["effect"], "APPLIED", result)
        self.assertEqual(result["changed_paths"], ["tasks/GATE-ACCEPT.md"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
