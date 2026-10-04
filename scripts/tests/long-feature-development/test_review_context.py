#!/usr/bin/env python3
"""Behavioral regression for blind context leakage, scope and reconciliation."""

import contextlib
import copy
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
        context = task_context.build_context(root, review_phase="blind")
        with (root / "gists/blind-01.md").open("a", encoding="utf-8") as report:
            report.write("\n- Review refs: " + json.dumps(context["review"]["candidate_refs"]) + "\n")
        return root

    def test_renamed_and_added_status_columns_cannot_leak_blind_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            path = root / "STATUS.md"
            original = path.read_text(encoding="utf-8")
            marker = "OLD_REVIEW_P0_SINGLE_EXPORT_BYPASSES_AUTH"
            for header in ("Review result", "Conclusion", "审查结论", "任意字段"):
                path.write_text(original.replace("| Integration SHA | Receives | Note |", f"| Integration SHA | Receives | {header} |").replace("| observed |", f"| {marker} |"), encoding="utf-8")
                context = task_context.build_context(root, review_phase="blind", review_inputs=["gists/review-input.md"])
                with self.subTest(header=header):
                    self.assertNotIn(marker, json.dumps(context))
                    self.assertNotIn(marker, task_context.render_markdown(context))
                    self.assertTrue(context["review"]["inputs_ready"])
            # Apply the same root-cause probe to every reference-table surface,
            # including locale aliases, rather than just this reported column.
            base = task_context.build_context(root)
            for kind in ("working_branches", "integration_opponents", "pr_mr_objects"):
                for locale in ("en", "cn"):
                    probe = copy.deepcopy(base)
                    table = probe["feature"][kind]
                    if locale == "cn":
                        table["header"] = [{"Repository": "仓库", "Local path": "本地路径", "Working branch": "工作分支", "Working HEAD SHA": "工作 HEAD SHA", "Current task": "当前 task"}.get(header, header) for header in table["header"]]
                    table["header"].append("Unexpected review conclusion")
                    for row in table["rows"]:
                        row.append(marker)
                    result = review_context.blind_context(probe, review_context.parse_review_scope(), [])
                    with self.subTest(kind=kind, locale=locale):
                        self.assertNotIn(marker, json.dumps(result))
                        self.assertNotIn(marker, task_context.render_markdown(result))
                        self.assertTrue(any(header in {"Repository", "仓库"} for header in result["feature"][kind]["header"]))

    def test_waiting_states_fail_closed_when_clean_action_boundaries_are_missing(self):
        for condition in ("WAITING_HUMAN", "WAITING_EXTERNAL", "BLOCKED"):
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as temp:
                root = self.make_review(Path(temp))
                path = root / "STATUS.md"
                marker = "USER_PAUSED_EXTERNAL_API_ACCESS_UNTIL_APPROVAL"
                path.write_text(path.read_text(encoding="utf-8").replace("| Condition | `ACTIVE` |", f"| Condition | `{condition}` |").replace("| Blocker | None | - |", f"| Blocker | {marker} | old findings mixed with permission |"), encoding="utf-8")
                context = task_context.build_context(root, review_phase="blind", review_inputs=["gists/review-input.md"])
                self.assertTrue(context["review"]["action_blocked"])
                self.assertFalse(context["review"]["inputs_ready"])
                self.assertIsNone(context["review"]["action_boundary"])
                self.assertNotIn(marker, json.dumps(context))
                rendered = task_context.render_markdown(context)
                self.assertIn("Missing clean action_boundary", rendered)
                self.assertIn("Missing clean release_condition", rendered)
                self.assertIn(condition, rendered)

    def test_clean_boundaries_survive_both_outputs_without_granting_permission(self):
        for labels in (("Action boundary", "Release condition"), ("行动边界", "解除条件")):
            with self.subTest(labels=labels), tempfile.TemporaryDirectory() as temp:
                root = self.make_review(Path(temp))
                path = root / "STATUS.md"
                path.write_text(path.read_text(encoding="utf-8").replace("`ACTIVE`", "`WAITING_HUMAN`"), encoding="utf-8")
                path = root / "gists/review-input.md"
                path.write_text(path.read_text(encoding="utf-8") + f"\n- {labels[0]}: Local isolated tests only; no external API access.\n- {labels[1]}: Explicit human authorization recorded before external access.\n", encoding="utf-8")
                context = task_context.build_context(root, review_phase="blind", review_inputs=["gists/review-input.md"])
                self.assertIn("no external API access", context["review"]["action_boundary"])
                self.assertIn("Explicit human authorization", task_context.render_markdown(context))
                self.assertFalse(context["review"]["inputs_ready"])
                self.assertTrue(context["review"]["action_blocked"])
                self.assertFalse(any("Missing clean" in value for value in context["review"]["diagnostics"]))

    def test_task_blocker_is_not_cleared_by_an_input_packet(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            path = root / "TASKS.md"
            path.write_text(path.read_text(encoding="utf-8").replace("`WIP`", "`BLOCKED`"), encoding="utf-8")
            task_context.sync_topology(path)
            path = root / "STATUS.md"
            path.write_text(path.read_text(encoding="utf-8").replace("`ACTIVE`", "`WAITING_HUMAN`"), encoding="utf-8")
            path = root / "tasks/REVIEW-01.md"
            path.write_text(path.read_text(encoding="utf-8").replace("- Blocker: none", "- Blocker: permission required").replace("- Impact: none", "- Impact: cannot access external API").replace("- Release condition: none", "- Release condition: explicit authorization"), encoding="utf-8")
            context = task_context.build_context(root, review_phase="blind", review_inputs=["gists/review-input.md"])
            self.assertTrue(context["review"]["action_blocked"])
            self.assertIn("task=BLOCKED", " ".join(context["review"]["diagnostics"]))

    def test_empty_or_conflicting_action_boundaries_do_not_appear_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            path = root / "STATUS.md"
            path.write_text(path.read_text(encoding="utf-8").replace("`ACTIVE`", "`WAITING_HUMAN`"), encoding="utf-8")
            path = root / "gists/review-input.md"
            original = path.read_text(encoding="utf-8")
            for missing in ("", "none", "无", "\t"):
                path.write_text(original + f"\n- Action boundary: No external access.\n- Release condition: {missing}\n", encoding="utf-8")
                context = task_context.build_context(root, review_phase="blind", review_inputs=["gists/review-input.md"])
                with self.subTest(missing=missing):
                    self.assertFalse(context["review"]["inputs_ready"])
                    self.assertIsNone(context["review"]["release_condition"])
                    self.assertIn("Missing clean release_condition", task_context.render_markdown(context))
            for duplicate in ("Action boundary", "Release condition", "行动边界", "解除条件"):
                path.write_text(original + "\n- Action boundary: No external access.\n- Release condition: Human authorization.\n" + f"- {duplicate}: Contradictory allowance.\n", encoding="utf-8")
                with self.subTest(duplicate=duplicate), self.assertRaisesRegex(task_context.ContextError, "repeat"):
                    task_context.build_context(root, review_phase="blind", review_inputs=["gists/review-input.md"])

    def test_empty_scope_is_rejected_in_design_task_and_snapshot(self):
        self.assertEqual(review_context.configured_scope("", "")["source"], "default")
        for empty in ("", " ", "\t", "\r"):
            with self.subTest(empty=empty), self.assertRaisesRegex(ValueError, "explicitly empty"):
                review_context.parse_review_scope(empty)
            for label in ("Review scope:", "审查范围："):
                line = f"- {label}{empty}\n"
                for design, task in ((line, ""), ("", line), (line + "- Review scope: review/v1\n", "")):
                    with self.subTest(line=line, design=bool(design)), self.assertRaises(ValueError):
                        review_context.configured_scope(design, task)
        for document in ("SOLUTION.md", "tasks/REVIEW-01.md", "gists/blind-01.md"):
            with self.subTest(document=document), tempfile.TemporaryDirectory() as temp:
                root = self.make_review(Path(temp))
                path = root / document
                content = path.read_text(encoding="utf-8")
                path.write_text(content.replace("- Review scope: review/v1", "- Review scope:") if document.startswith("gists") else content + "\n- Review scope:\n", encoding="utf-8")
                with self.assertRaises(task_context.ContextError):
                    task_context.build_context(root, review_phase="reconcile", review_report="gists/blind-01.md")

    def test_snapshot_binds_every_checkout_and_ref_before_history_is_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            repos = {}
            for name in ("app", "second"):
                repo = Path(temp) / name
                fixtures.make_git_repo(repo, f"https://example.invalid/{name}.git", 2)
                repos[name] = {"role": "implementation", "actual_branch": "main", "actual_head": fixtures.git(repo, "rev-parse", "HEAD")}
            current = task_context.build_context(root)
            scope = review_context.parse_review_scope()
            refs = review_context.candidate_references(repos, current["repository_refs"], current["feature"])
            target = repos["app"]["actual_head"]
            report = root / "gists/blind-01.md"
            original = f"- Review phase: blind\n- Review task: REVIEW-01\n- Target SHA: {target}\n- Review scope: review/v1\n- Review refs: {json.dumps(refs)}\n"
            report.write_text(original, encoding="utf-8")
            declared = {"gists/blind-01.md": report}
            review_context.verify_blind_snapshot("gists/blind-01.md", declared, "REVIEW-01", target, scope, refs)
            fixtures.git(Path(temp) / "second", "commit", "--allow-empty", "-m", "advance second candidate only")
            repos["second"]["actual_head"] = fixtures.git(Path(temp) / "second", "rev-parse", "HEAD")
            moved = review_context.candidate_references(repos, current["repository_refs"], current["feature"])
            review_context.validate_candidate_target(target, repos)
            with self.assertRaisesRegex(ValueError, "per-repository"):
                review_context.verify_blind_snapshot("gists/blind-01.md", declared, "REVIEW-01", target, scope, moved)
            for mutate in (
                lambda value: value.pop("second"),
                lambda value: value["second"].update(branch="other"),
                lambda value: value["app"].update(baseline_history="main@fffffff"),
                lambda value: value["app"]["integration_refs"][0].update(sha="f" * 40),
                lambda value: value["app"]["pr_refs"][0].update(target_sha="f" * 40),
                lambda value: value.update(extra={}),
            ):
                changed = copy.deepcopy(refs)
                mutate(changed)
                report.write_text(original.replace(json.dumps(refs), json.dumps(changed)), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "per-repository"):
                    review_context.verify_blind_snapshot("gists/blind-01.md", declared, "REVIEW-01", target, scope, refs)
            # End-to-end reconcile must reject stale refs before touching history.
            report.write_text("- Review phase: blind\n- Review task: REVIEW-01\n- Target SHA: 4444444\n- Review scope: review/v1\n- Review refs: {}\n", encoding="utf-8")
            (root / "gists/parser.md").write_bytes(b"\xff")
            with self.assertRaisesRegex(task_context.ContextError, "per-repository"):
                task_context.build_context(root, review_phase="reconcile", review_report="gists/blind-01.md")

    def test_report_commit_does_not_invalidate_unchanged_management_source_refs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            context = task_context.build_context(root)
            repositories = {"pm": {"role": "project-management", "actual_branch": "feature", "actual_head": "a" * 40}}
            before = review_context.candidate_references(repositories, context["repository_refs"], context["feature"])
            repositories["pm"]["actual_head"] = "b" * 40
            after = review_context.candidate_references(repositories, context["repository_refs"], context["feature"])
            self.assertEqual(before, after)
            self.assertEqual(after["pm"]["head_sha"], "3333333")
            context["repository_refs"][1]["head_sha"] = "ccccccc"
            self.assertNotEqual(after, review_context.candidate_references(repositories, context["repository_refs"], context["feature"]))

    def test_snapshot_rejects_missing_duplicate_or_invalid_refs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_review(Path(temp))
            context = task_context.build_context(root, review_phase="blind")
            refs = context["review"]["candidate_refs"]
            path = root / "gists/blind-01.md"
            prefix = "- Review phase: blind\n- Review task: REVIEW-01\n- Target SHA: 4444444\n- Review scope: review/v1\n"
            for suffix in ("", "- Review refs: invalid\n", '- Review refs: {"app": {}, "app": {}}\n', f"- Review refs: {json.dumps(refs)}\n- Review refs: {json.dumps(refs)}\n"):
                path.write_text(prefix + suffix, encoding="utf-8")
                with self.subTest(suffix=suffix), self.assertRaises(task_context.ContextError):
                    task_context.build_context(root, review_phase="reconcile", review_report="gists/blind-01.md")

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
