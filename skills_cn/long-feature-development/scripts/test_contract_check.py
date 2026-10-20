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
from pathlib import Path

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
        shutil.copytree(TEMPLATES, root)
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
        self.assertIn("initial opinion", checker.detail_spec(item, "design"))

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
        self.assertIn("domain note: {custom rule: Preserve this extension}", rendered)
        self.assertIn("| id | title | type | state | decided by | decided at | decided with | detail spec |", rendered)

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
                          (root / "TASKS.md").read_text(encoding="utf-8"))
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
            item = checker.load(path)
            item["head sha"] = ["example-project@" + "a" * 40]
            item["working branch"] = ["example-project@feature/work"]
            write_detail(path, item)
            before = config.read_bytes()
            checker.collect(root, registry)
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
        self.assertIn("decided by: Human:reviewer", checker.detail_spec(item, "tasks"))

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
