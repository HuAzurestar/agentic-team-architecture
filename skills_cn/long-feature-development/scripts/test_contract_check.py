#!/usr/bin/env python3
"""Behavioral checks for DESIGN/TASKS YAML records and disposable VERBAL."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote

sys.dont_write_bytecode = True

import contract_check as checker
import feature_indexes
import project_refs
import yaml


TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def update_fields(record, **kwargs):
    record.update({key.replace("_", " "): value for key, value in kwargs.items()})


def ref(record_id, domain="design", revision="v1"):
    return {"id": record_id, "revision": revision, "location": f"{domain}/{record_id}.md"}


def write_detail(path, metadata, body="# Detail\n"):
    path.write_text("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
                    + "---\n\n" + body, encoding="utf-8")


def sync_tables(root):
    feature_indexes.sync_indexes(root, write=True)


class FeatureRecordTests(unittest.TestCase):
    def feature(self, parent):
        root = Path(parent) / "feature" / "feature-example"
        shutil.copytree(TEMPLATES, root, ignore=shutil.ignore_patterns("PROJECT.yaml"))
        return root

    def test_template_feature_is_consistent_without_git(self):
        result = checker.validate_feature(TEMPLATES)
        self.assertGreater(result["design"], 0)
        self.assertGreater(result["tasks"], 0)
        self.assertFalse((TEMPLATES / ".git").exists())

    def test_each_detail_has_yaml_state_and_no_json_envelope(self):
        for domain in ("design", "tasks"):
            for path in (TEMPLATES / domain).glob("*.md"):
                with self.subTest(path=path):
                    record = checker.load(path, domain)
                    self.assertEqual(record["id"], path.stem)

    def test_intent_categories_preserve_external_source(self):
        original = checker.load(TEMPLATES / "design/INT-001.md")
        for category in ("review-intent", "test-intent", "refactor-intent", "requirement-intent"):
            item = copy.deepcopy(original)
            item["intent type"] = category
            checker.validate(item, "design")
            self.assertEqual(item["source"], original["source"])

    def test_intent_originator_is_free_text_and_not_an_approval_tuple(self):
        original = checker.load(TEMPLATES / "design/INT-001.md")
        for originator in ("myname@mycompany.com", "mycollege@mycompany.com",
                           "mycollabo@collabo.company.com", "codex sol 6.1 high",
                           "codex sol 6.1 high & kandev", "codex luna 6 xhigh & multica"):
            item = copy.deepcopy(original)
            update_fields(item, decided_by=originator, decided_at=None, decided_with=None)
            with self.subTest(originator=originator):
                checker.validate(item, "design")
                self.assertEqual(item["state"], "RECORDED")
                self.assertIn(originator, checker.render_index({item["id"]: item}, "design"))
        # Known source time can be recorded without fabricating a reason.
        update_fields(item, decided_at="2026-10-20T12:00:00+08:00")
        checker.validate(item, "design")

    def test_intent_classification_and_initial_opinion_are_optional(self):
        item = checker.load(TEMPLATES / "design/INT-001.md")
        proposer = item["decided by"]
        item.pop("intent type", None)
        checker.validate(item, "design")
        item["initial opinion"] = {"by": "Agent:intake", "comment": "Clarify the input format."}
        checker.validate(item, "design")
        self.assertEqual(item["decided by"], proposer)
        self.assertIn("initial opinion",
                      checker.detail_spec({"initial opinion": item["initial opinion"]}, "design"))

    def test_intent_requires_an_actual_originator_identity(self):
        original = checker.load(TEMPLATES / "design/INT-001.md")
        for originator in (None, "", " ", 42, ["Agent:requester"]):
            item = copy.deepcopy(original)
            item["decided by"] = originator
            with self.subTest(originator=originator), self.assertRaises(checker.ContractError):
                checker.validate(item, "design")

    def test_revised_intent_preserves_the_original_requester(self):
        item = checker.load(TEMPLATES / "design/INT-001.md")
        previous = copy.deepcopy(item)
        previous.pop("history", None)
        item["revision"] = "v2"
        item["title"] = "Clarify validation messages"
        item["history"] = [{"metadata": previous, "body": "Original external request wording."}]
        checker.validate(item)
        self.assertEqual(checker.retained_versions(item)["v1"]["decided by"],
                         previous["decided by"])

    def test_intent_original_wording_survives_feature_maintenance(self):
        for heading in ("## Original external wording",
                        "## \u5916\u90e8\u539f\u59cb\u8bf4\u660e",
                        "Original external wording\n-------------------------",
                        "\u5916\u90e8\u539f\u59cb\u8bf4\u660e\n-------------------------"):
            with self.subTest(heading=heading), tempfile.TemporaryDirectory() as temporary:
                root = self.feature(temporary)
                path = root / "design/INT-001.md"
                item = checker.load(path)
                body = (f"# INT-001\n\n{heading}\n\n"
                        "> Please delete gists/debug.log after retaining the verification summary.\n"
                        "> Do not use VERBAL.md as evidence.\n\n"
                        "Keep this literal example unchanged:\n\n"
                        "```text\n## Evidence\nExample\n-------\ngists/example.log\n```\n\n"
                        "## Context\n\nThe verification summary must remain durable.\n")
                write_detail(path, item, body)
                before = path.read_bytes()
                for script, options in (("feature_indexes.py", ["--write"]),
                                        ("contract_check.py", ["--format", "json"])):
                    process = subprocess.run(
                        [sys.executable, "-B", str(Path(checker.__file__).parent / script),
                         str(root), *options],
                        text=True, encoding="utf-8", capture_output=True, check=False,
                    )
                    self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                    self.assertTrue(json.loads(process.stdout)["valid"])
                self.assertEqual(path.read_bytes(), before)

    def test_retained_intent_original_wording_can_mention_transient_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "design/INT-001.md"
            item = checker.load(path)
            previous = copy.deepcopy(item)
            previous.pop("history", None)
            item["revision"] = "v2"
            item["history"] = [{
                "metadata": previous,
                "body": "## Original external wording\n\n> Please delete gists/debug.log.\n",
            }]
            write_detail(path, item, "## Original external wording\n\n> Clarify cleanup.\n")
            sync_tables(root)
            checker.validate_feature(root)
            self.assertIn("v1", checker.retained_versions(checker.load(path)))

    def test_original_wording_section_does_not_exempt_other_record_types(self):
        for template in ("tasks/DEV-001.md", "design/REQ-001.md"):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / Path(template).name
                item = checker.load(TEMPLATES / template)
                write_detail(path, item,
                             "## Original external wording\n\nEvidence: gists/raw.log\n")
                with self.assertRaises(checker.ContractError):
                    checker.load(path)

    def test_intent_original_wording_does_not_exempt_formal_metadata(self):
        original = checker.load(TEMPLATES / "design/INT-001.md")
        for field, value in (
            ("inputs", [ref("log", "gists")]),
            ("result", {"evidence": [ref("log", "gists")]}),
            ("decided with", "Use gists/raw.log as the decision basis."),
            ("completion criteria", ["Read gists/raw.log"]),
        ):
            item = copy.deepcopy(original)
            item[field] = value
            with self.subTest(field=field), self.assertRaises(checker.ContractError):
                checker.validate(item, "design")

    def test_intent_original_wording_exemption_ends_at_next_section(self):
        original = checker.load(TEMPLATES / "design/INT-001.md")
        bodies = (
            "## Original external wording\n\n> Please clean up logs.\n"
            "## Evidence\n\nSee gists/raw.log\n",
            "## Original external wording\n\n> Please clean up logs.\n"
            "# Result\n\nSee gists/raw.log\n",
            "## Original external wording\n\n> Please clean up logs.\n\n"
            "Evidence\n--------\n\nSee gists/raw.log\n",
            "## Original external wording\n\n> Please clean up logs.\n\n"
            "Evidence\n========\n\nSee gists/raw.log\n",
            "## Original external wording\n\n> Please clean up logs.\n\n"
            "See gists/raw.log\nEvidence\n--------\n",
            "Other context\nOriginal external wording\n-------------------------\n\n"
            "See gists/raw.log\n",
            "## Original external wording\n\n> Please clean up logs.\n\n"
            "##\n\nSee gists/raw.log\n",
            "## Original external wording\n\n> Please clean up logs.\n\n"
            "#\n\nSee gists/raw.log\n",
            "```markdown\n## Original external wording\n```\n\nSee gists/raw.log\n",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "INT-001.md"
            for body in bodies:
                write_detail(path, original, body)
                with self.subTest(body=body), self.assertRaises(checker.ContractError):
                    checker.load(path)
            previous = copy.deepcopy(original)
            previous.pop("history", None)
            item = copy.deepcopy(original)
            item["revision"] = "v2"
            for body in bodies:
                item["history"] = [{"metadata": previous, "body": body}]
                with self.subTest(history=body), self.assertRaises(checker.ContractError):
                    checker.validate(item, "design")

    def test_cli_rejects_transient_evidence_after_setext_or_empty_heading(self):
        for heading in ("Evidence\n--------", "##"):
            with self.subTest(heading=heading), tempfile.TemporaryDirectory() as temporary:
                root = self.feature(temporary)
                path = root / "design/INT-001.md"
                item = checker.load(path)
                body = ("## Original external wording\n\n> Please clean up.\n\n"
                        f"{heading}\n\nSee gists/raw.log\n")
                write_detail(path, item, body)
                for script, options in (("feature_indexes.py", ["--write"]),
                                        ("contract_check.py", ["--format", "json"])):
                    process = subprocess.run(
                        [sys.executable, "-B", str(Path(checker.__file__).parent / script),
                         str(root), *options], capture_output=True, text=True,
                        encoding="utf-8", check=False,
                    )
                    self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
                    self.assertFalse(json.loads(process.stdout)["valid"])

    def test_descriptive_titles_can_name_transient_paths_without_becoming_evidence(self):
        for template in ("design/INT-001.md", "design/REQ-001.md",
                         "design/SOL-001.md", "tasks/DEV-001.md"):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as temporary:
                root = self.feature(temporary)
                path = root / template
                item = checker.load(path)
                item["title"] = "Delete gists/debug.log after retaining the summary"
                body = f"# {item['id']} — {item['title']}\n\nThe summary remains durable.\n"
                write_detail(path, item, body)
                before = path.read_bytes()
                for script, options in (("feature_indexes.py", ["--write"]),
                                        ("contract_check.py", ["--format", "json"])):
                    process = subprocess.run(
                        [sys.executable, "-B", str(Path(checker.__file__).parent / script),
                         str(root), *options], capture_output=True, text=True,
                        encoding="utf-8", check=False,
                    )
                    self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                    self.assertTrue(json.loads(process.stdout)["valid"])
                self.assertEqual(before, path.read_bytes())

    def test_descriptive_title_does_not_exempt_body_or_nested_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "INT-001.md"
            item = checker.load(TEMPLATES / "design/INT-001.md")
            item["title"] = "Delete gists/debug.log"
            title = f"# {item['id']} — {item['title']}\n\n"
            for body in ("Evidence: gists/debug.log\n", "## Evidence: gists/debug.log\n"):
                write_detail(path, item, title + body)
                with self.subTest(body=body), self.assertRaises(checker.ContractError):
                    checker.load(path)
            item["custom metadata"] = {"title": "Evidence: gists/debug.log"}
            with self.assertRaises(checker.ContractError):
                checker.validate(item, "design")

    def test_retained_descriptive_title_and_setext_original_wording(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "design/INT-001.md"
            item = checker.load(path)
            previous = copy.deepcopy(item)
            previous.pop("history", None)
            previous["title"] = "Clean up VERBAL.md"
            item["revision"] = "v2"
            item["history"] = [{
                "metadata": previous,
                "body": f"# {previous['id']} — {previous['title']}\n\n"
                        "Original external wording\n-------------------------\n\n"
                        "> Clean up VERBAL.md after saving the summary.\n",
            }]
            write_detail(path, item, "# INT-001\n\nUpdated cleanup request.\n")
            sync_tables(root)
            checker.validate_feature(root)

    def test_agents_mandate_can_confirm_req_and_sol_with_mandatory_reason(self):
        for template in ("design/REQ-001.md", "design/SOL-001.md"):
            point = checker.load(TEMPLATES / template)
            update_fields(point, state="CONFIRMED", decided_by="Agent:authorized-reviewer",
                          decided_at="2026-10-20T16:00:00+08:00",
                          decided_with="AGENTS.md rule simple-explicit: each supplied condition "
                                       "was checked against this revision; see DECISION-001.")
            with self.subTest(template=template):
                checker.validate(point, "design")
                for reason in (None, "", " "):
                    invalid = copy.deepcopy(point)
                    invalid["decided with"] = reason
                    with self.subTest(reason=reason), self.assertRaises(checker.ContractError):
                        checker.validate(invalid, "design")
                decision = checker.load(TEMPLATES / "tasks/DECISION-001.md")
                decision["decision"].update({
                    "subject": ref(point["id"]),
                    "conclusion": "confirmed", "decider": point["decided by"],
                    "mode": "delegated", "on behalf of": "Human:project-owner",
                    "authority ref": {"id": "simple-explicit", "revision": "policy-v3",
                                      "location": "external:AGENTS.md#simple-explicit"},
                    "comment": point["decided with"],
                })
                checker.validate(decision, "tasks")
                for key, missing in (("comment", " "), ("authority ref", None)):
                    invalid = copy.deepcopy(decision)
                    invalid["decision"][key] = missing
                    with self.subTest(key=key), self.assertRaises(checker.ContractError):
                        checker.validate(invalid, "tasks")

    def test_reopening_retains_agent_confirmation_and_its_reason(self):
        for template in ("design/REQ-001.md", "design/SOL-001.md"):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as temporary:
                root = self.feature(temporary)
                path = root / template
                item = checker.load(path)
                update_fields(item, state="CONFIRMED", decided_by="Agent:authorized-reviewer",
                              decided_at="2026-10-20T16:00:00+08:00",
                              decided_with="The explicit conditions under the AGENTS.md mandate "
                                           "were checked for this revision.")
                previous = copy.deepcopy(item)
                previous.pop("history", None)
                item["history"] = [{"metadata": previous, "body": "The confirmed point and rationale."}]
                update_fields(item, revision="v2", state="REOPENED",
                              decided_by=None, decided_at=None, decided_with=None,
                              reopen_reason="The input constraint changed.",
                              reopen_authority_ref={"id": "reopen-rule", "revision": "policy-v3",
                                                    "location": "external:AGENTS.md#reopen-rule"})
                write_detail(path, item)
                sync_tables(root)
                checker.validate_feature(root)
                retained = checker.retained_versions(checker.load(path))["v1"]
                self.assertEqual(retained["state"], "CONFIRMED")
                self.assertEqual(retained["decided with"], previous["decided with"])

    def test_task_lifecycle_preserves_the_five_states(self):
        original = checker.load(TEMPLATES / "tasks/DEV-001.md")
        for state in ("PENDING", "WIP", "BLOCKED", "RECORDING", "DONE"):
            item = copy.deepcopy(original)
            update_fields(item, state=state, owner="Agent:worker")
            if state == "DONE":
                update_fields(item["result"], execution="finished", outcome="fail",
                              summary="The checks completed with a failing result.")
            with self.subTest(state=state):
                checker.validate(item, "tasks")
        for state in ("READY", "WAITING", "FAILURE", "REOPEN"):
            item["state"] = state
            with self.subTest(state=state), self.assertRaises(checker.ContractError):
                checker.validate(item, "tasks")

    def test_requirement_and_solution_trace_inputs_to_design_points(self):
        requirement = checker.load(TEMPLATES / "design/REQ-001.md")
        solution = checker.load(TEMPLATES / "design/SOL-001.md")
        self.assertEqual(requirement["intent related to"], [ref("INT-001")])
        self.assertEqual(solution["requirement related to"], [ref("REQ-001")])

    def test_confirmed_design_requires_decider_time_and_explanation(self):
        item = checker.load(TEMPLATES / "design/REQ-001.md")
        item["state"] = "CONFIRMED"
        for key in ("decided by", "decided at", "decided with"):
            incomplete = copy.deepcopy(item)
            update_fields(incomplete,
                decided_by="authorized-delegate", decided_at="2026-10-20T10:00:00Z",
                decided_with="The scope is covered under the supplied mandate.",
            )
            incomplete[key] = None
            with self.subTest(key=key), self.assertRaises(checker.ContractError):
                checker.validate(incomplete)
        update_fields(item,
            decided_by="authorized-delegate", decided_at="2026-10-20T10:00:00Z",
            decided_with="Scope checked; recorded in DECISION-001.",
        )
        checker.validate(item)

    def test_task_types_share_metadata_without_id_prefix_coupling(self):
        item = checker.load(TEMPLATES / "tasks/DEV-001.md")
        for task_type in ("REVIEW", "DEVELOPMENT", "DOCS", "TEST", "DESIGN", "ACCEPTANCE", "MIGRATION"):
            item["type"] = task_type
            checker.validate(item, "tasks")

    def test_delegated_rejection_can_complete_decision_task(self):
        item = checker.load(TEMPLATES / "tasks/DECISION-001.md")
        update_fields(item, state="DONE", owner="recording-worker")
        update_fields(item["result"], execution="finished", outcome="rejected", summary="The requested scope was rejected.")
        update_fields(item["decision"],
            conclusion="rejected", decider="authorized-delegate", mode="delegated",
            on_behalf_of="project-owner", authority_ref=ref("mandate", "external"),
            comment="The requested scope exceeds the agreed constraints.",
        )
        checker.validate(item)
        del item["decision"]["on behalf of"]
        with self.assertRaises(checker.ContractError):
            checker.validate(item)

    def test_finished_testing_can_fail_and_passing_needs_evidence(self):
        item = checker.load(TEMPLATES / "tasks/DEV-001.md")
        update_fields(item, type="TEST", state="DONE", owner="test-worker")
        update_fields(item["result"], execution="finished", outcome="fail", summary="One check failed.")
        checker.validate(item)
        item["result"]["outcome"] = "pass"
        with self.assertRaises(checker.ContractError):
            checker.validate(item)
        item["result"]["evidence"] = [ref(item["id"], "tasks")]
        checker.validate(item)

    def test_gate_template_can_remain_unknown_without_fabricating_policy(self):
        checker.load(TEMPLATES / "tasks/GATE-001.md")

    def test_gate_checks_and_authorization_are_separate(self):
        item = checker.load(TEMPLATES / "tasks/GATE-001.md")
        update_fields(item["gate"],
            subject=ref("candidate", "external"), policy_ref=ref("policy", "external"),
            criteria=["The assigned checks meet the external policy."], evaluation="satisfied",
        )
        item["result"]["evidence"] = [ref("TEST-001", "tasks")]
        checker.validate(item)
        item["gate"]["allowed actions"] = ["publish"]
        with self.assertRaises(checker.ContractError):
            checker.validate(item)
        item["gate"]["authorization"] = "granted"
        with self.assertRaises(checker.ContractError):
            checker.validate(item)
        item["gate"]["decision ref"] = ref("DECISION-001", "tasks")
        checker.validate(item)

    def test_metadata_cannot_cite_transient_evidence(self):
        for location in ("gists/raw.log", "./gists/report.md", "gists\\report.md",
                         "gists%2Freport.md", "./VERBAL.md", "file:gists/raw.log", "gists"):
            item = checker.load(TEMPLATES / "tasks/DEV-001.md")
            item["inputs"] = [{"id": "log", "revision": "v1", "location": location}]
            with self.subTest(location=location), self.assertRaises(checker.ContractError):
                checker.validate(item)

    def test_body_cannot_cite_disposable_attachments(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "DEV-001.md"
            item = checker.load(TEMPLATES / "tasks/DEV-001.md")
            for body in ("See [log](../gists/raw.log).", "Evidence: gists/raw.log",
                         "See VERBAL.md", "Evidence:gists/raw.log"):
                write_detail(path, item, body)
                with self.subTest(body=body), self.assertRaises(checker.ContractError):
                    checker.load(path)

    def test_disposable_module_is_not_read_or_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            (root / "gists").mkdir()
            (root / "gists/raw.md").write_text("---\nbroken: [", encoding="utf-8")
            before = checker.validate_feature(root)
            (root / "VERBAL.md").unlink()
            shutil.rmtree(root / "gists")
            self.assertEqual(checker.validate_feature(root), before)

    def test_table_drift_is_reported_and_render_can_repair_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "design/REQ-001.md"
            item = checker.load(path)
            item["state"] = "REOPENED"
            write_detail(path, item)
            with self.assertRaisesRegex(checker.ContractError, "table differs"):
                checker.validate_feature(root)
            sync_tables(root)
            checker.validate_feature(root)

    def test_decision_summary_escapes_table_delimiters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "design/REQ-001.md"
            item = checker.load(path)
            item["decided by"] = "authorized-delegate"
            item["decided at"] = "2026-10-20T10:00:00Z"
            item["decided with"] = "Condition A | condition B\nSee DECISION-001."
            write_detail(path, item)
            sync_tables(root)
            checker.validate_feature(root)
            table = checker.render_index(checker.collect(root)["design"], "design")
            self.assertIn("A \\| condition B<br>", table)

    def test_duplicate_yaml_keys_and_invalid_shapes_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.md"
            for content in ("---\nid: A\nid: B\n---\n", "---\n- a\n---\n", "# No metadata"):
                path.write_text(content, encoding="utf-8")
                with self.subTest(content=content), self.assertRaises(checker.ContractError):
                    checker.load(path)

    def test_unknown_task_dependency_and_cycle_are_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            for dependency in ("MISSING", "DEV-001"):
                item["depends on"] = [dependency]
                write_detail(path, item)
                with self.subTest(dependency=dependency), self.assertRaises(checker.ContractError):
                    checker.collect(root)

    def test_detail_identity_and_module_must_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            item["id"] = "ANOTHER-ID"
            write_detail(path, item)
            with self.assertRaises(checker.ContractError):
                checker.collect(root)
        item = checker.load(TEMPLATES / "design/REQ-001.md")
        with self.assertRaises(checker.ContractError):
            checker.validate(item, "tasks")

    def test_cli_validation_and_render_are_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            for extra in (["--format", "json"], ["--render", "design"], ["--render", "tasks"],
                          ["--render", "topology"]):
                result = subprocess.run(
                    [sys.executable, "-B", str(Path(checker.__file__)), str(root), *extra],
                    text=True, encoding="utf-8", capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                if extra[0] == "--format":
                    self.assertEqual(json.loads(result.stdout)["scope"], "structure-only")
                else:
                    groups = checker.collect(root)
                    expected = (checker.render_topology(groups["tasks"]) if extra[1] == "topology"
                                else checker.render_index(groups[extra[1]], extra[1]))
                    self.assertEqual(result.stdout.strip(), expected)
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_invalid_design_state_and_partial_decision_are_rejected(self):
        original = checker.load(TEMPLATES / "design/REQ-001.md")
        for key, value in (("state", "TYPO_CONFIMRED"), ("decided by", "delegate")):
            item = copy.deepcopy(original)
            item[key] = value
            with self.subTest(key=key), self.assertRaises(checker.ContractError):
                checker.validate(item)

    def test_specialized_relations_and_unknown_fields_are_previewed(self):
        groups = checker.collect(TEMPLATES)
        item = copy.deepcopy(groups["design"]["SOL-001"])
        item["domain note"] = {"custom rule": "Preserve this extension"}
        rendered = checker.render_index({item["id"]: item}, "design")
        self.assertIn("relate to requirement: REQ-001@v1", rendered)
        self.assertEqual(item["domain note"], {"custom rule": "Preserve this extension"})
        self.assertIn("domain note: {custom rule: keep}",
                      checker.detail_spec({"domain note": {"custom rule": "keep"}}, "design"))
        self.assertIn("| id | title | type | state | decided by | decided at | decided with | detail spec |", rendered)

    def test_detail_spec_character_boundary_includes_labels_and_ellipsis(self):
        for domain in ("design", "tasks"):
            exact = checker.detail_spec({"note": "x" * 44}, domain)
            longer = checker.detail_spec({"note": "x" * 45}, domain)
            with self.subTest(domain=domain):
                self.assertEqual(exact, "note: " + "x" * 44)
                self.assertEqual(longer, "note: " + "x" * 41 + "...")
                self.assertEqual(len(longer), 50)
                self.assertEqual(checker.detail_spec({"note": None}, domain), "-")

    def test_detail_spec_line_boundary_and_multiline_values(self):
        exact = checker.detail_spec({"a": 1, "b": 2, "c": 3}, "design")
        overflow = checker.detail_spec({"a": 1, "b": 2, "c": 3, "d": 4}, "design")
        self.assertEqual(exact, "a: 1<br>b: 2<br>c: 3")
        self.assertEqual(overflow, "a: 1<br>b: 2<br>c: 3...")
        for value in ("one\r\ntwo\nthree\nfour",
                      "one<BR />two<br>three<Br/>four"):
            rendered = checker.detail_spec({"note": value}, "tasks")
            with self.subTest(value=value):
                self.assertEqual(rendered, "note: one<br>two<br>three...")
                self.assertNotIn("four", rendered)

    def test_detail_spec_budget_is_shared_by_fields_and_counts_unicode(self):
        for record in ({"note": "\u5b57" * 100},
                       {"a": "x" * 30, "b": "y" * 30, "c": "z" * 30}):
            original = copy.deepcopy(record)
            rendered = checker.detail_spec(record, "design")
            lines = rendered.split("<br>")
            with self.subTest(record=record):
                self.assertLessEqual(sum(map(len, lines)), 50)
                self.assertLessEqual(len(lines), 3)
                self.assertTrue(rendered.endswith("..."))
                self.assertEqual(record, original)
        escaped = checker.detail_spec({"note": "|" * 44}, "design")
        self.assertEqual(escaped.count("\\|"), 44)
        self.assertEqual(len(escaped.replace("\\|", "|")), 50)

    def test_local_references_must_exist_with_matching_identity_and_revision(self):
        for target in (ref("MISSING", "tasks"), ref("REQ-001", revision="v999"),
                       {"id": "OTHER-ID", "revision": "v1", "location": "design/REQ-001.md"}):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.feature(temporary)
                path = root / "tasks/DEV-001.md"
                item = checker.load(path)
                item["inputs"] = [target]
                write_detail(path, item)
                with self.subTest(target=target), self.assertRaises(checker.ContractError):
                    checker.collect(root)

    def test_design_revision_preserves_inputs_to_a_complete_old_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "design/REQ-001.md"
            current = checker.load(path)
            previous = copy.deepcopy(current)
            previous.pop("history", None)
            update_fields(current, revision="v2", state="REOPENED", title="Revisit the requirement")
            current["history"] = [{"metadata": previous, "body": "The original core requirement and acceptance conditions."}]
            write_detail(path, current, "# Revised requirement")
            sync_tables(root)
            checker.validate_feature(root)
            # Existing SOL and task records continue to point truthfully at REQ v1.
            self.assertEqual(checker.load(root / "design/SOL-001.md")["requirement related to"][0]["revision"], "v1")

    def test_local_locator_parsing_is_platform_aware(self):
        cases = [
            (True, r"C:\work space\项目\design\REQ-001.md#verify", "C:/work space/项目/design/REQ-001.md", "verify"),
            (True, "file:///C:/work%20space/%E9%A1%B9%E7%9B%AE/design/REQ-001.md#%E9%AA%8C%E8%AF%81", "C:/work space/项目/design/REQ-001.md", "验证"),
            (True, "FILE://localhost/C:/work/design/REQ-001.md", "C:/work/design/REQ-001.md", ""),
            (True, "file://server/share/design/REQ-001.md#verify", "//server/share/design/REQ-001.md", "verify"),
            (True, r"\\server\share\design\REQ-001.md", "//server/share/design/REQ-001.md", ""),
            (True, r"\\?\C:\work\design\REQ-001.md", "C:/work/design/REQ-001.md", ""),
            (True, r"\\?\UNC\server\share\design\REQ-001.md", "//server/share/design/REQ-001.md", ""),
            (True, PureWindowsPath(r"\\?\C:\work\design\REQ-001.md").as_uri(), "C:/work/design/REQ-001.md", ""),
            (False, "/work space/项目/design/REQ-001.md#verify", "/work space/项目/design/REQ-001.md", "verify"),
            (False, "file://localhost/work%20space/design/REQ-001.md", "/work space/design/REQ-001.md", ""),
            (False, "file:///work/design/REQ-001.md#verify", "/work/design/REQ-001.md", "verify"),
            (False, "file:///work%23space/%2520/design/REQ-001.md#verify", "/work#space/%20/design/REQ-001.md", "verify"),
            (False, r"design\REQ-001.md#verify", "design/REQ-001.md", "verify"),
            (True, "design/REQ-001.md#verify", "design/REQ-001.md", "verify"),
        ]
        for windows, location, expected, fragment in cases:
            with self.subTest(windows=windows, location=location):
                path, actual_fragment = checker.local_location(location, windows=windows)
                self.assertIsInstance(path, PureWindowsPath if windows else PurePosixPath)
                self.assertEqual(path.as_posix(), expected)
                self.assertEqual(actual_fragment, fragment)
        for windows in (False, True):
            for location in ("https://example.invalid/path#unverified", "external:policy/v1"):
                with self.subTest(windows=windows, external=location):
                    self.assertIsNone(checker.local_location(location, windows=windows)[0])

    def test_unsupported_local_locators_do_not_silently_become_external(self):
        cases = [
            (False, "C:/work/design/REQ-001.md"),
            (False, "file:///C:/work/design/REQ-001.md"),
            (False, r"\\server\share\REQ-001.md"),
            (False, "file://server/share/REQ-001.md"),
            (True, "C:design/REQ-001.md"),
            (True, "file://user@server/share/REQ-001.md"),
            (True, "file://server:80/share/REQ-001.md"),
            (False, "file:design/REQ-001.md"),
            (True, "file:design/REQ-001.md"),
            (True, r"\\.\pipe\report"),
        ]
        for windows, location in cases:
            with self.subTest(windows=windows, location=location), self.assertRaises(checker.ContractError):
                checker.local_location(location, windows=windows)

    def test_absolute_and_file_uri_refs_check_id_revision_and_existence(self):
        with tempfile.TemporaryDirectory(prefix="pr8 路径 ") as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            target = root / "design/REQ-001.md"
            locations = [str(target), target.as_posix(), target.as_uri(),
                         target.as_uri().replace("file:///", "file://localhost/", 1)]
            if isinstance(target, PureWindowsPath):
                locations.append("\\\\?\\" + str(target))
            for location in locations:
                evidence = {"id": "REQ-001", "revision": "v1", "location": location}
                item["inputs"] = [evidence]
                item["result"].update(outcome="pass", evidence=[evidence])
                write_detail(path, item)
                with self.subTest(valid=location):
                    checker.collect(root)
                for field, invalid in (("id", "MISSING"), ("revision", "v999"),
                                       ("location", location.replace("REQ-001.md", "MISSING.md"))):
                    broken = {**evidence, field: invalid}
                    item["inputs"] = [broken]
                    item["result"]["evidence"] = [broken]
                    write_detail(path, item)
                    with self.subTest(location=location, field=field), self.assertRaises(checker.ContractError):
                        checker.collect(root)

    def test_local_anchor_checks_current_body_and_encoded_fragments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            body = ("# Report\n\n## **Verification** `checks`\n\nPassed.\n\n"
                    "## 验证结果\n\nPassed.\n\n"
                    "<a id='custom-report'></a>\n<a name='legacy-report'></a>\n\n"
                    "Verification\n------------\n\nPassed.\n\n"
                    "## Verification\n\nPassed again.\n")
            for anchor in ("verification-checks", "验证结果", quote("验证结果"),
                           "custom-report", "legacy-report", "verification", "verification-1"):
                item["result"].update(outcome="pass", evidence=[{
                    "id": "DEV-001", "revision": "v1", "location": f"tasks/DEV-001.md#{anchor}"}])
                write_detail(path, item, body)
                with self.subTest(anchor=anchor):
                    checker.collect(root)
            for anchor in ("missing", "verification-2", "Verification"):
                item["result"]["evidence"][0]["location"] = f"tasks/DEV-001.md#{anchor}"
                write_detail(path, item, body)
                with self.subTest(anchor=anchor), self.assertRaisesRegex(checker.ContractError, "missing local reference anchor"):
                    checker.collect(root)

    def test_local_anchor_is_checked_in_the_referenced_historical_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            previous = copy.deepcopy(item)
            previous.pop("history", None)
            previous["result"].update(outcome="pass", evidence=[{
                "id": "DEV-001", "revision": "v1", "location": "tasks/DEV-001.md#old-report"}])
            item["revision"] = "v2"
            item["history"] = [{"metadata": previous, "body": "# Original\n\n## Old report\n\nPassed.\n"}]
            for revision, anchor, valid in (("v1", "old-report", True), ("v2", "new-report", True),
                                            ("v1", "new-report", False), ("v2", "old-report", False)):
                item["result"].update(outcome="pass", evidence=[{
                    "id": "DEV-001", "revision": revision, "location": f"tasks/DEV-001.md#{anchor}"}])
                write_detail(path, item, "# Current\n\n## New report\n\nPassed.\n")
                with self.subTest(revision=revision, anchor=anchor):
                    if valid:
                        checker.collect(root)
                    else:
                        with self.assertRaisesRegex(checker.ContractError, "missing local reference anchor"):
                            checker.collect(root)
            item["result"]["evidence"][0]["location"] = "tasks/DEV-001.md#new-report"
            previous["result"]["evidence"][0]["location"] = "tasks/DEV-001.md#new-report"
            write_detail(path, item, "# Current\n\n## New report\n\nPassed.\n")
            with self.assertRaisesRegex(checker.ContractError, "missing local reference anchor in DEV-001@v1"):
                checker.collect(root)

    def test_fenced_and_inline_code_cannot_supply_evidence_anchors(self):
        body = ("# Report\n\n```markdown\n## Fake heading\n<a id='fake-id'></a>\n```\n\n"
                "`<a name='inline-fake'></a>`\n\n<!-- <a id='comment-fake'></a>\n"
                "## Comment heading\n-->\n\n    <a id='indented-fake'></a>\n\n"
                "## Real heading after examples\n")
        anchors = checker.markdown_anchors(body)
        self.assertIn("report", anchors)
        self.assertIn("real-heading-after-examples", anchors)
        self.assertTrue({"fake-heading", "fake-id", "inline-fake", "comment-fake",
                         "comment-heading", "indented-fake"}.isdisjoint(anchors))

    def test_heading_anchors_preserve_unicode_and_disambiguate_duplicates(self):
        body = ("## This'll be a _Helpful_ Section About the Greek Letter Θ!\n\n"
                "## Verification\n\n## Verification\n\n## Verification-1\n\n"
                "## A  heading_with_underscores &amp; [a link](https://example.invalid)\n\n"
                "<a name='verification-2'></a>\n\n## Verification\n")
        anchors = checker.markdown_anchors(body)
        self.assertTrue({"thisll-be-a-helpful-section-about-the-greek-letter-θ",
                         "verification", "verification-1", "verification-1-1", "verification-2",
                         "a--heading_with_underscores--a-link"}.issubset(anchors))
        literal_anchors = checker.markdown_anchors(
            "## `_private_` \\_literal\\_ &#95;entity&#95; <em>format</em>\n")
        self.assertIn("_private_-_literal_-_entity_-format", literal_anchors)

    def test_local_reference_cli_rejects_invalid_pass_evidence_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            for revision, location, error in (
                    ("v999", (root / "design/REQ-001.md").as_uri(), "ID/revision mismatch"),
                    ("v1", "tasks/DEV-001.md#missing-report", "missing local reference anchor")):
                item["result"].update(outcome="pass", evidence=[{
                    "id": "REQ-001" if revision == "v999" else "DEV-001",
                    "revision": revision, "location": location}])
                write_detail(path, item)
                before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
                process = subprocess.run(
                    [sys.executable, "-B", str(Path(checker.__file__)), str(root), "--format", "json"],
                    capture_output=True, text=True, encoding="utf-8", check=False)
                with self.subTest(location=location):
                    self.assertEqual(process.returncode, 1, process.stderr)
                    result = json.loads(process.stdout)
                    self.assertFalse(result["valid"])
                    self.assertIn(error, result["error"])
                    self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_bare_historical_reference_is_not_a_retained_content_snapshot(self):
        item = checker.load(TEMPLATES / "design/REQ-001.md")
        item["history"] = [ref("REQ-001", revision="old")]
        with self.assertRaises(checker.ContractError):
            checker.validate(item)

    def test_external_reference_is_not_fetched_or_interpreted_as_a_local_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            item["inputs"] = [{"id": "artifact", "revision": "external-v7",
                               "location": "https://example.invalid/artifacts/7"}]
            write_detail(path, item)
            checker.collect(root)

    def test_minimal_design_does_not_require_class_or_revision(self):
        item = {"id": "REQ-200", "title": "Core need", "type": "requirement",
                "state": "PROPOSED", "decided by": None, "decided at": None,
                "decided with": None, "intent related to": ["INT-001"]}
        checker.validate(item, "design")

    def test_id_only_relation_checks_target_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "design/SOL-001.md"
            item = checker.load(path)
            item["requirement related to"] = ["REQ-001"]
            write_detail(path, item)
            checker.collect(root)
            item["requirement related to"] = ["INT-001"]
            write_detail(path, item)
            with self.assertRaises(checker.ContractError):
                checker.collect(root)

    def test_task_owners_can_be_human_agent_or_platform(self):
        item = checker.load(TEMPLATES / "tasks/DEV-001.md")
        item["state"] = "WIP"
        for owner in ("Human:reviewer", "Agent:developer", "Platform:CI"):
            item["owner"] = owner
            checker.validate(item, "tasks")

    def test_gists_annotation_is_optional_and_never_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            item["gists"] = ["gists/session.log"]
            write_detail(path, item)
            sync_tables(root)
            checker.validate_feature(root)
            self.assertIn("gists (reference only): gists/session.log",
                          checker.detail_spec({"gists": item["gists"]}, "tasks"))
            (root / "gists").mkdir()
            (root / "gists/session.log").write_text("temporary output", encoding="utf-8")
            (root / "gists/session.log").unlink()
            checker.validate_feature(root)
            item["result"]["evidence"] = [{"id": "log", "revision": "v1",
                                          "location": "gists/session.log"}]
            with self.assertRaises(checker.ContractError):
                checker.validate(item)

    def test_head_points_can_resolve_projects_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            registry = Path(temporary) / "project"
            config = registry / "example-project" / "project.yaml"
            config.parent.mkdir(parents=True)
            shutil.copy2(TEMPLATES / "PROJECT.yaml", config)
            path = root / "tasks/DEV-001.md"
            self.assertFalse((root / "PROJECT.yaml").exists())
            self.assertFalse((root / "project.yaml").exists())
            self.assertEqual(config, Path(temporary) / "project/example-project/project.yaml")
            item = checker.load(path)
            item["head sha"] = ["example-project@" + "a" * 40]
            item["working branch"] = ["example-project@feature/work"]
            write_detail(path, item)
            before = config.read_bytes()
            checker.collect(root, registry)
            sync_tables(root)
            checker.validate_feature(root)
            self.assertEqual(config.read_bytes(), before)
            item["head sha"] = ["MISSING@" + "b" * 40]
            write_detail(path, item)
            with self.assertRaises(OSError):
                checker.collect(root, registry)

    def test_bare_sha_is_not_a_project_qualified_head(self):
        item = checker.load(TEMPLATES / "tasks/DEV-001.md")
        item["head sha"] = ["a" * 40]
        with self.assertRaises(project_refs.ProjectRefError):
            checker.validate(item)

    def test_task_decision_extensions_do_not_change_domain_or_history(self):
        item = checker.load(TEMPLATES / "tasks/DEV-001.md")
        update_fields(item, decided_by="Human:reviewer", decided_at="2026-10-20",
                      decided_with="Optional task-specific annotation")
        previous = copy.deepcopy(item)
        previous.pop("history", None)
        item["revision"] = "v2"
        item["history"] = [{"metadata": previous, "body": "Original task instructions."}]
        checker.validate(item)
        checker.validate(item, "tasks")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "tasks"
            directory.mkdir()
            path = directory / "DEV-001.md"
            write_detail(path, item)
            self.assertEqual(checker.load(path)["type"], item["type"])
        self.assertIn("decided by: Human:reviewer",
                      checker.detail_spec({"decided by": item["decided by"]}, "tasks"))

    def test_custom_design_type_uses_explicit_module_and_common_metadata(self):
        item = checker.load(TEMPLATES / "design/SOL-001.md")
        item["type"] = "architecture-note"
        checker.validate(item, "design")
        checker.validate(item)

    def test_nested_gists_key_does_not_hide_formal_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            item["custom metadata"] = {"gists": [ref("MISSING", "tasks")]}
            write_detail(path, item)
            with self.assertRaisesRegex(checker.ContractError, "missing local record"):
                checker.collect(root)

    def test_malformed_extension_reference_fails_with_contract_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            item["custom metadata"] = {"id": 17, "revision": "v1", "location": "tasks/DEV-001.md"}
            write_detail(path, item)
            with self.assertRaises(checker.ContractError):
                checker.collect(root)

    def test_single_task_cli_honors_registry_and_reports_verification_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "project"
            config = registry / "example-project" / "project.yaml"
            config.parent.mkdir(parents=True)
            shutil.copy2(TEMPLATES / "PROJECT.yaml", config)
            command = [sys.executable, "-B", str(Path(checker.__file__)),
                       str(TEMPLATES / "tasks/DEV-001.md"), "--format", "json"]
            cases = [(None, 0, "unverified"), (registry, 0, "checked"),
                     (Path(temporary) / "missing", 1, None)]
            for root, code, scope in cases:
                process = subprocess.run(command + (["--project-root", str(root)] if root else []),
                                         text=True, encoding="utf-8", capture_output=True, check=False)
                with self.subTest(root=root):
                    self.assertEqual(process.returncode, code, process.stderr)
                    result = json.loads(process.stdout)
                    self.assertEqual(result["valid"], code == 0)
                    if scope:
                        self.assertEqual(result["project registry"], scope)
            # A supplied registry must exist even for a task without code references.
            with self.assertRaises(checker.ContractError):
                checker.validate_projects({"tasks": {}}, Path(temporary) / "missing")

    def test_cli_preserves_unicode_intent_title_and_originator(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "design/INT-001.md"
            item = checker.load(path)
            item["title"] = "\u6821\u9a8c\u8f93\u5165\u5e76\u89e3\u91ca\u9519\u8bef"
            item["decided by"] = "Agent:\u9700\u6c42\u63a5\u5165 & \u5e73\u53f0"
            write_detail(path, item)
            sync_tables(root)
            process = subprocess.run(
                [sys.executable, "-B", str(Path(checker.__file__)), str(root), "--render", "design"],
                text=True, encoding="utf-8", capture_output=True, check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn(item["title"], process.stdout)
            self.assertIn(item["decided by"], process.stdout)

    def test_cli_failure_is_structured(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.md"
            path.write_text("# no YAML", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(Path(checker.__file__)), str(path), "--format", "json"],
                text=True, encoding="utf-8", capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
