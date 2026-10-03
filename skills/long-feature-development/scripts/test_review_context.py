#!/usr/bin/env python3
"""Behavioral regression for blind context leakage, scope and reconciliation."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import review_context
import task_context
import test_task_context as fixtures
from test_task_context import DETAILS, STATUS, TASKS


class ReviewContextTests(unittest.TestCase):
    def make_review(self, parent: Path) -> Path:
        root = fixtures.TaskContextTests().make_feature(
            parent,
            status=STATUS.replace("DEV-02", "REVIEW-01"),
            tasks=TASKS.replace("DEV-02", "REVIEW-01").replace("| Development |", "| Review |"),
        )
        (root / "tasks/DEV-02.md").unlink()
        (root / "tasks/GATE-ACCEPT.md").write_text(DETAILS["GATE-ACCEPT"].replace("DEV-02", "REVIEW-01"), encoding="utf-8")
        detail = DETAILS["DEV-02"].replace("DEV-02", "REVIEW-01").replace(
            "- Gists: gists/parser.md", "- Gists: gists/parser.md, gists/review-input.md, gists/blind-01.md"
        )
        detail += "\n## Type contract\n\n| Field | Value |\n| --- | --- |\n| Target SHA | 4444444 |\n| Blocking findings | 1 |\n| Deferred findings | 0 |\n| Result gist | gists/blind-01.md |\n"
        (root / "tasks/REVIEW-01.md").write_text(detail, encoding="utf-8")
        (root / "gists/review-input.md").write_text(
            "- Evidence type: original\n\nCurrent normative requirement: reject invalid conditions.\nAuthorization: isolated fixture data only.\n", encoding="utf-8"
        )
        (root / "gists/blind-01.md").write_text(
            "- Review phase: blind\n- Review task: REVIEW-01\n- Target SHA: 4444444\n- Review scope: review/v1\n\nSaved current scan.\n", encoding="utf-8"
        )
        task_context.sync_topology(root / "TASKS.md")
        return root

    def test_blind_view_does_not_leak_history_through_markdown_or_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            marker = "HISTORICAL_FINDING_EXFILTRATION_921"
            (root / "REVIEW.md").write_text(marker, encoding="utf-8")
            (root / "gists/parser.md").write_text(marker, encoding="utf-8")
            for name in ("REQUIREMENT.md", "SOLUTION.md"):
                path = root / name
                path.write_text(path.read_text(encoding="utf-8").replace("## Disposition records", f"### Historical review\n\n{marker}\n\n## Disposition records"), encoding="utf-8")
            path = root / "tasks/REVIEW-01.md"
            path.write_text(path.read_text(encoding="utf-8").replace("Continue parser.", marker).replace("| Blocking findings | 1 |", f"| Blocking findings | {marker} |"), encoding="utf-8")
            path = root / "tasks/SOL-001.md"
            path.write_text(path.read_text(encoding="utf-8").replace("Confirm it.", marker), encoding="utf-8")
            path = root / "STATUS.md"
            path.write_text(path.read_text(encoding="utf-8").replace("| Blocker | None | - |", f"| Blocker | {marker} | {marker} |").replace("| final target |", f"| {marker} |"), encoding="utf-8")
            path = root / "TASKS.md"
            path.write_text(path.read_text(encoding="utf-8").replace("Implement parser", marker), encoding="utf-8")
            task_context.sync_topology(path)
            context = task_context.build_context(root, review_phase="blind", review_inputs=["gists/review-input.md"])
            self.assertNotIn(marker, json.dumps(context))
            self.assertNotIn(marker, task_context.render_markdown(context))
            self.assertIn("Current normative requirement", task_context.render_markdown(context))
            self.assertEqual(context["type_contract"]["Target SHA"], "4444444")
            self.assertEqual(context["intent"]["requirement"]["points"][0]["id"], "REQ-001")
            self.assertTrue(context["review"]["inputs_ready"])
            self.assertEqual(context["review"]["completeness"], "UNVERIFIED")
            self.assertEqual(context["review"]["independence"], "UNVERIFIED")
            self.assertIn("Completeness: UNVERIFIED", task_context.render_markdown(context))

    def test_candidate_target_binds_to_observed_git_head_not_a_stale_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "app"
            commits = fixtures.make_git_repo(repo, "https://example.invalid/app.git", 2)
            observed = fixtures.git(repo, "rev-parse", "HEAD")
            repositories = {"app": {"role": "implementation", "actual_head": observed}}
            review_context.validate_candidate_target(observed, repositories)
            review_context.validate_candidate_target(observed[:7], repositories)
            review_context.validate_candidate_target(observed.upper(), repositories)
            for target in (None, commits[0], "f" * 40):
                with self.subTest(target=target), self.assertRaisesRegex(ValueError, "candidate HEAD"):
                    review_context.validate_candidate_target(target, repositories)
            # Preserve old, unregistered feature recovery rather than inventing refs.
            review_context.validate_candidate_target("4444444", {})
            repositories["other"] = {"role": "implementation", "actual_head": observed[:7] + "0" * 33}
            with self.assertRaisesRegex(ValueError, "unambiguously"):
                review_context.validate_candidate_target(observed[:7], repositories)

    def test_missing_packet_is_explicitly_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            context = task_context.build_context(self.make_review(Path(temp)), review_phase="blind")
            self.assertFalse(context["review"]["inputs_ready"])
            self.assertEqual(context["gists"], [])
            self.assertIn("Do not claim PASS", " ".join(context["review"]["diagnostics"]))

    def test_original_packet_requires_declaration_and_exact_safe_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            for selected in (["../REVIEW.md"], ["gists/missing.md"], ["gists/blind-01.md"], ["gists/review-input.md"] * 2, ["gists/parser.md"]):
                with self.subTest(selected=selected), self.assertRaises(task_context.ContextError):
                    task_context.build_context(root, review_phase="blind", review_inputs=selected)

    def test_reconciliation_needs_snapshot_bound_to_task_target_and_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            (root / "REVIEW.md").write_text("HISTORICAL_LEDGER_AVAILABLE_AFTER_FREEZE", encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "requires --review-report"):
                task_context.build_context(root, review_phase="reconcile")
            path = root / "gists/blind-01.md"
            original = path.read_text(encoding="utf-8")
            for old, new in (("Target SHA: 4444444", "Target SHA: 1111111"), ("Review task: REVIEW-01", "Review task: REVIEW-02"), ("Review phase: blind", "Review phase: reconcile"), ("Review scope: review/v1", "Review scope: review/v1 exclude=ui")):
                path.write_text(original.replace(old, new), encoding="utf-8")
                with self.subTest(new=new), self.assertRaises(task_context.ContextError):
                    task_context.build_context(root, review_phase="reconcile", review_report="gists/blind-01.md")
            path.write_text(original, encoding="utf-8")
            context = task_context.build_context(root, review_phase="reconcile", review_report="gists/blind-01.md")
            self.assertIn("HISTORICAL_LEDGER", task_context.render_markdown(context))
            self.assertEqual(len(context["review"]["blind_snapshot"]["sha256"]), 64)

    def test_scope_is_recorded_and_task_snapshot_cannot_silently_override_design(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            configuration = "review/v1 mode=weak topics=core,api,ui exclude=ui focus=permissions"
            path = root / "SOLUTION.md"
            path.write_text(path.read_text(encoding="utf-8") + f"\n## Review scope\n\n- Review scope: {configuration}\n", encoding="utf-8")
            context = task_context.build_context(root, review_phase="blind")
            self.assertEqual(context["review"]["scope"]["topics"], ["core", "api"])
            self.assertEqual(context["review"]["scope"]["mode"], "weak")
            path = root / "tasks/REVIEW-01.md"
            path.write_text(path.read_text(encoding="utf-8") + "\n- Review scope: review/v1\n", encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "snapshot differs"):
                task_context.build_context(root, review_phase="blind")

    def test_scope_validation_and_empty_selection(self):
        for value in ("review/v2", "review/v1 ui=off", "review/v1 mode=medium", "review/v1 topics=unknown", "review/v1 exclude=ui,ui", "review/v1 mode=strong mode=weak", "review/v1 focus=x,,y"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review_context.parse_review_scope(value)
        self.assertEqual(review_context.parse_review_scope("review/v1 topics=ui exclude=ui")["topics"], [])
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            path = root / "SOLUTION.md"
            path.write_text(path.read_text(encoding="utf-8") + "\n- Review scope: review/v1 topics=ui exclude=ui\n", encoding="utf-8")
            self.assertFalse(task_context.build_context(root, review_phase="blind", review_inputs=["gists/review-input.md"])["review"]["inputs_ready"])

    def test_review_arguments_do_not_bypass_normal_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            path = root / "tasks/REVIEW-01.md"
            path.write_text(path.read_text(encoding="utf-8").replace("gists/parser.md", "gists/missing.md"), encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "declared gist is missing"):
                task_context.build_context(root, review_phase="blind")
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            for kwargs in ({"review_inputs": ["gists/review-input.md"]}, {"review_phase": "blind", "review_report": "gists/blind-01.md"}, {"review_phase": "unknown"}):
                with self.subTest(kwargs=kwargs), self.assertRaises(task_context.ContextError):
                    task_context.build_context(root, **kwargs)
            with self.assertRaisesRegex(task_context.ContextError, "requires a REVIEW task"):
                task_context.build_context(root, "SOL-001", review_phase="blind")

    def test_cli_json_does_not_reintroduce_old_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            marker = "OLD_LEDGER_SECRET_CONCLUSION"
            (root / "REVIEW.md").write_text(marker, encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = task_context.main([str(root), "--review-phase", "blind", "--review-input", "gists/review-input.md", "--format", "json"])
            self.assertEqual(result, 0)
            self.assertNotIn(marker, output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["review"]["phase"], "blind")

    def test_view_never_repairs_topology_and_missing_snapshot_precedes_history_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            path = root / "TASKS.md"
            previous = path.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(task_context.main([str(root), "--review-phase", "blind", "--sync-topology"]), 1)
            self.assertEqual(path.read_bytes(), previous)
            # Invalid UTF-8 history would fail if loaded before snapshot validation.
            (root / "gists/parser.md").write_bytes(b"\xff")
            with self.assertRaisesRegex(task_context.ContextError, "requires --review-report"):
                task_context.build_context(root, review_phase="reconcile")


if __name__ == "__main__":
    unittest.main()
