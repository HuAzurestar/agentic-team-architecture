"""Regression checks for the versioned PIRC-31 static package validator."""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import check_long_feature_contracts as checker


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "examples/long-feature/contracts/v0.2-draft"
CHECKER = ROOT / "scripts/check_long_feature_contracts.py"


class BundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bundle = Path(self.temp.name) / "bundle"
        shutil.copytree(BUNDLE, self.bundle)

    def check_bundle(self) -> tuple[int, dict]:
        run = subprocess.run(
            [sys.executable, str(CHECKER), "--bundle", str(self.bundle), "--format", "json"],
            capture_output=True, text=True, check=False,
        )
        self.assertFalse(run.stderr, run.stderr)
        return run.returncode, json.loads(run.stdout)

    def manifest(self) -> dict:
        return json.loads((self.bundle / "manifest.json").read_text(encoding="utf-8"))

    def save_manifest(self, value: dict) -> None:
        (self.bundle / "manifest.json").write_text(json.dumps(value), encoding="utf-8")

    def rewrite_case(self, case_id: str, change) -> None:
        target = self.bundle / "cases" / f"{case_id.lower()}.json"
        case = json.loads(target.read_text(encoding="utf-8"))
        change(case)
        target.write_text(json.dumps(case), encoding="utf-8")
        value = self.manifest()
        entry = next(item for item in value["files"] if item["case_id"] == case_id)
        entry["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        self.save_manifest(value)

    def test_all_23_cases_pass(self) -> None:
        code, result = self.check_bundle()
        self.assertEqual(code, 0)
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked_cases"], 23)

    def test_file_tamper_is_reported(self) -> None:
        target = self.bundle / "cases/c1-01.json"
        target.write_bytes(target.read_bytes() + b" ")
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertEqual(result["failures"][0]["field"], "sha256")

    def test_unsupported_version_is_rejected(self) -> None:
        value = self.manifest()
        value["contracts"]["c2"] = "c2/9.0"
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 4)
        self.assertFalse(result["valid"])

    def test_changed_condition_with_valid_hash_is_semantic_failure(self) -> None:
        self.rewrite_case("C2-01", lambda case: case.update(current_source_key=case["expected_source_key"]))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["field"], "expected_result")

    def test_c1_check_without_evidence_is_rejected(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["review"]["checks"][0].pop("evidence", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["field"], "expected_result")

    def test_c1_dependency_cycle_is_rejected(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["tasks"][0].update(depends_on=["REVIEW-01"]))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["field"], "expected_result")

    def test_c1_incomplete_report_cannot_allow_acceptance(self) -> None:
        def change(case: dict) -> None:
            case["points"][1].update(state="CONFIRMED", decided_by="owner", decided_at="2026-09-30", decision_history=["approved"])
            case["review"].update(report_done=False, findings=[])
            case["review"]["checks"][1].update(result="PASS", finding_ids=[], reason="")
            case["expected_counts"] = {"all": 2, "pass": 2, "findings_total": 0, "open_by_severity": {"P0": 0, "P1": 0, "P2": 0}}
            case["request_rework"] = False
        self.rewrite_case("C1-01", change)
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "ACCEPT_BLOCKED")

    def test_c1_closure_without_current_candidate_recheck_is_rejected(self) -> None:
        def change(case: dict) -> None:
            case["points"][1].update(state="CONFIRMED", decided_by="owner", decided_at="2026-09-30", decision_history=["approved"])
            for finding in case["review"]["findings"]:
                finding["closed_for_candidate"] = True
            case["expected_counts"]["open_by_severity"]["P1"] = 0
        self.rewrite_case("C1-01", change)
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "MISSING_EVIDENCE")

    def test_c1_current_candidate_recheck_can_close_finding(self) -> None:
        def change(case: dict) -> None:
            case["points"][1].update(state="CONFIRMED", decided_by="owner", decided_at="2026-09-30", decision_history=["approved"])
            for finding in case["review"]["findings"]:
                finding.update(closed_for_candidate=True, resolution="fixed", recheck_ref="review/attempt-1.md#recheck-1", recheck_sha=case["candidate_sha"])
            case["expected_counts"]["open_by_severity"]["P1"] = 0
            case["review"]["checks"][1].update(result="PASS", reason="current candidate rechecked")
            case["expected_counts"]["pass"] = 2
        self.rewrite_case("C1-01", change)
        manifest = self.manifest()
        next(item for item in manifest["files"] if item["case_id"] == "C1-01")["expected_result"] = "VALID"
        self.save_manifest(manifest)
        code, result = self.check_bundle()
        self.assertEqual(code, 0)
        self.assertTrue(result["valid"])

    def test_c1_unknown_check_cannot_allow_acceptance(self) -> None:
        def change(case: dict) -> None:
            case["points"][1].update(state="CONFIRMED", decided_by="owner", decided_at="2026-09-30", decision_history=["approved"])
            case["review"]["findings"] = []
            case["review"]["checks"] = [{"check_id": "CHK-1", "requirement_or_case": "REQ-001", "result": "UNKNOWN", "evidence": ["review/attempt-1.md#check-1"], "finding_ids": [], "reason": "not verified"}]
            case["expected_counts"] = {"all": 1, "pass": 0, "findings_total": 0, "open_by_severity": {"P0": 0, "P1": 0, "P2": 0}}
            case["request_rework"] = False
        self.rewrite_case("C1-01", change)
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "ACCEPT_BLOCKED")

    def test_c1_review_requires_independent_context(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["review"].pop("independent_context", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "INVALID_DOCUMENT")

    def test_c1_positive_requires_point_class(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["points"][0].pop("class", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "INVALID_DOCUMENT")

    def test_c1_positive_requires_task_type(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["tasks"][0].pop("type", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "INVALID_DOCUMENT")

    def test_c1_positive_requires_task_owner(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["tasks"][0].pop("owner", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "INVALID_DOCUMENT")

    def test_c1_positive_requires_task_repository_refs(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["tasks"][0].pop("repository_refs", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "INVALID_DOCUMENT")

    def test_c1_positive_requires_task_point_selectors(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["tasks"][0].pop("point_selectors", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "INVALID_DOCUMENT")

    def test_c2_missing_config_condition_is_rejected(self) -> None:
        self.rewrite_case("C2-02", lambda case: (case.pop("expected_config", None), case.pop("current_config", None)))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "MISSING_CONDITION")

    def test_c2_missing_source_or_content_condition_is_rejected(self) -> None:
        self.rewrite_case("C2-03", lambda case: (case.pop("expected_source_key", None), case.pop("current_source_key", None), case.pop("expected_content", None), case.pop("current_content", None)))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "MISSING_CONDITION")

    def test_c2_create_requires_observed_absence(self) -> None:
        self.rewrite_case("C2-09", lambda case: case.pop("target_exists", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "MISSING_CONDITION")

    def test_c2_update_requires_document_ref(self) -> None:
        self.rewrite_case("C2-03", lambda case: case.pop("ref", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "MISSING_CONDITION")

    def test_c2_preview_apply_requires_document_ref(self) -> None:
        self.rewrite_case("C2-05", lambda case: case.pop("ref", None))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "MISSING_CONDITION")

    def test_c3_context_different_from_source_is_rejected(self) -> None:
        self.rewrite_case("C3-01", lambda case: case["context"].update(intent={"unrelated": "different source"}))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["field"], "expected_result")

    def test_c3_execution_intent_requires_originals_and_decisions(self) -> None:
        def change(case: dict) -> None:
            case["context"]["intent"] = {"requirement": "REQ-001", "solution": "SOL-001"}
            case["source_facts"]["intent"] = dict(case["context"]["intent"])
        self.rewrite_case("C3-01", change)
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "MISSING_FIELD")

    def test_c3_source_stage_cannot_claim_execution_valid(self) -> None:
        self.rewrite_case("C3-07", lambda case: case.update(valid=True))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "INVALID_ENVELOPE")

    def test_spec_hash_failure_identifies_path(self) -> None:
        target = self.bundle / "c1.md"
        target.write_bytes(target.read_bytes() + b" ")
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertEqual(result["failures"][0]["path"], "c1.md")

    def test_manifest_contracts_wrong_type_is_controlled_input_error(self) -> None:
        value = self.manifest()
        value["contracts"] = []
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertFalse(result["valid"])
        self.assertIn("contracts", result["failures"][0]["observed"])

    def test_manifest_required_feature_wrong_type_is_controlled(self) -> None:
        value = self.manifest()
        value["required_features"] = [{}]
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertFalse(result["valid"])
        self.assertIn("required_features", result["failures"][0]["observed"])

    def test_unhashable_task_id_returns_json_input_error(self) -> None:
        self.rewrite_case("C1-01", lambda case: case["tasks"][0].update(id=[]))
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertFalse(result["valid"])
        self.assertIn("tasks[0].id", result["failures"][0]["observed"])

    def test_c2_non_boolean_observations_cannot_certify_write(self) -> None:
        fields = ("conditional_write", "mapping_changed", "rebind_during_write",
                  "lock_serialized", "target_exists", "preview_alive",
                  "known_partial", "response_lost")
        for field in fields:
            for value in ("false", "true", 0, 1, [], {}, None):
                with self.subTest(field=field, value=value):
                    # Always start from the original positive, not another mutation.
                    shutil.copytree(BUNDLE, self.bundle, dirs_exist_ok=True)
                    self.rewrite_case("C2-03", lambda case: case.update({field: value}))
                    code, result = self.check_bundle()
                    self.assertEqual(code, 2)
                    self.assertFalse(result["valid"])
                    self.assertIn(field, result["failures"][0]["observed"])

    def test_c2_config_write_checks_rebind_serialization(self) -> None:
        def unsafe(case: dict) -> None:
            case.update(current_config=case["expected_config"],
                        rebind_during_write=True, lock_serialized=False)
        self.rewrite_case("C2-02", unsafe)
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["observed"], "UNSAFE_INTERLEAVING")

    def test_c2_serialized_config_write_can_match_declared_success(self) -> None:
        def safe(case: dict) -> None:
            case.update(current_config=case["expected_config"],
                        rebind_during_write=True, lock_serialized=True)
        self.rewrite_case("C2-02", safe)
        manifest = self.manifest()
        next(item for item in manifest["files"] if item["case_id"] == "C2-02")["expected_result"] = "SAVED"
        self.save_manifest(manifest)
        code, result = self.check_bundle()
        self.assertEqual(code, 0)
        self.assertTrue(result["valid"])

    def test_duplicate_case_id_is_rejected(self) -> None:
        value = self.manifest()
        value["files"][-1]["case_id"] = "C3-08"
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertIn("duplicate", result["failures"][0]["observed"])

    def test_spec_contract_label_is_validated_without_case_id(self) -> None:
        value = self.manifest()
        value["files"][0]["contract"] = "unknown-contract"
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 4)
        self.assertFalse(result["valid"])
        self.assertTrue(result["unsupported_versions"])

    def test_spec_cannot_be_relabelled_as_another_supported_contract(self) -> None:
        value = self.manifest()
        value["files"][0]["contract"] = "c2"
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertFalse(result["valid"])

    def test_file_entry_required_features_are_not_silently_ignored(self) -> None:
        for index in (0, 3):
            with self.subTest(index=index):
                value = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
                value["files"][index]["required_features"] = ["unknown-required-semantic"]
                self.save_manifest(value)
                code, result = self.check_bundle()
                self.assertEqual(code, 4)
                self.assertFalse(result["valid"])

    def test_extra_contract_version_declaration_is_rejected(self) -> None:
        value = self.manifest()
        value["contracts"]["c9"] = "c9/0.1"
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 4)
        self.assertFalse(result["valid"])

    def test_required_semantics_are_not_ignored_by_c1_or_c2(self) -> None:
        for case_id in ("C1-01", "C2-03"):
            with self.subTest(case_id=case_id):
                shutil.copytree(BUNDLE, self.bundle, dirs_exist_ok=True)
                self.rewrite_case(case_id, lambda case: case.update(required_features=["unknown-required-semantic"]))
                code, result = self.check_bundle()
                self.assertEqual(code, 3)
                self.assertEqual(result["failures"][0]["observed"], "UNSUPPORTED_FEATURE")

    def test_escape_path_is_rejected(self) -> None:
        value = self.manifest()
        value["files"][3]["path"] = "../outside.json"
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertIn("unsafe relative path", result["failures"][0]["observed"])


class ExecutionFactsTest(unittest.TestCase):
    def case(self, name="c3-01"):
        return json.loads((BUNDLE / "cases" / f"{name}.json").read_text(encoding="utf-8"))

    def test_c1_requires_complete_candidate_and_review_sha(self):
        for value in (None, "", "a" * 39, "g" * 40, False, []):
            with self.subTest(value=value):
                case = self.case("c1-01")
                case["candidate_sha"] = case["review"]["target_sha"] = value
                self.assertEqual(checker.evaluate_c1(case), "INVALID_DOCUMENT")
        case = self.case("c1-01")
        del case["candidate_sha"]
        del case["review"]["target_sha"]
        self.assertEqual(checker.evaluate_c1(case), "INVALID_DOCUMENT")

    def test_c3_requires_complete_execution_shas(self):
        for value in (None, "", "a" * 39, "g" * 40, False, []):
            with self.subTest(value=value):
                case = self.case()
                case["recorded_sha"] = case["actual_sha"] = value
                self.assertEqual(checker.evaluate_c3(case), "MISSING_FIELD")
        case = self.case()
        del case["recorded_sha"]
        del case["actual_sha"]
        self.assertEqual(checker.evaluate_c3(case), "MISSING_FIELD")

    def test_false_facts_cannot_validate_by_matching_each_other(self):
        for key in checker.REQUIRED_CONTEXT:
            with self.subTest(key=key):
                case = self.case()
                case["context"][key] = case["source_facts"][key] = False
                self.assertNotIn(checker.evaluate_c3(case), ("VALID", "VALID_FALLBACK"))

    def test_matching_but_invalid_nested_execution_identity_is_rejected(self):
        mutations = (
            lambda c: c["feature"].update(id=""),
            lambda c: c["task"].update(id=""),
            lambda c: c["task"].update(state="READY"),
            lambda c: c["repositories"][0].update(sha="short"),
            lambda c: c.update(refs=[False]),
            lambda c: c.update(dependencies=[{}]),
            lambda c: c.update(gists=[None]),
        )
        for i, change in enumerate(mutations):
            with self.subTest(mutation=i):
                case = self.case()
                change(case["context"])
                change(case["source_facts"])
                self.assertNotIn(checker.evaluate_c3(case), ("VALID", "VALID_FALLBACK"))

    def test_sources_are_a_nonempty_string_array(self):
        for sources in ("STATUS.md", False, {}, [], [False], [""]):
            with self.subTest(sources=sources):
                case = self.case()
                case["sources"] = case["source_facts"]["sources"] = sources
                self.assertEqual(checker.evaluate_c3(case), "INVALID_ENVELOPE")

    def test_known_empty_dependency_and_gist_sets_are_valid(self):
        for keys in (("dependencies",), ("gists",), ("dependencies", "gists")):
            case = self.case()
            for key in keys:
                case["context"][key] = case["source_facts"][key] = []
            self.assertEqual(checker.evaluate_c3(case), "VALID")
        case["context"].pop("dependencies")
        self.assertEqual(checker.evaluate_c3(case), "MISSING_FIELD")

    def test_all_evaluators_reject_malformed_required_feature_arrays(self):
        for name, evaluate in (("c1-01", checker.evaluate_c1),
                               ("c2-03", checker.evaluate_c2),
                               ("c3-01", checker.evaluate_c3)):
            for value in ("execution", [{}], [False], None):
                with self.subTest(name=name, value=value):
                    case = self.case(name)
                    case["required_features"] = value
                    with self.assertRaises(checker.BundleError):
                        evaluate(case)

    def acceptance_case(self, severity="P2"):
        case = self.case("c1-01")
        case["points"][1].update(state="CONFIRMED", decided_by="owner",
                                  decided_at="2026-10-03", decision_history=["approved"])
        for check in case["review"]["checks"]:
            check.update(result="PASS", reason="verified")
        for finding in case["review"]["findings"]:
            finding["severity"] = severity
        case["expected_counts"]["pass"] = 2
        case["expected_counts"]["open_by_severity"] = {
            level: int(level == severity) for level in ("P0", "P1", "P2")}
        case["request_rework"] = False
        return case

    def test_explicit_p2_blocker_prevents_acceptance_but_allows_rework(self):
        case = self.acceptance_case()
        for finding in case["review"]["findings"]:
            finding["blocking"] = True
        self.assertEqual(checker.evaluate_c1(case), "ACCEPT_BLOCKED")
        case["request_rework"] = True
        self.assertEqual(checker.evaluate_c1(case), "REWORK_READY_ACCEPT_BLOCKED")
        case["request_acceptance"] = False
        self.assertEqual(checker.evaluate_c1(case), "VALID")

    def test_nonblocking_p2_and_current_candidate_closure_allow_acceptance(self):
        case = self.acceptance_case()
        self.assertEqual(checker.evaluate_c1(case), "VALID")
        for finding in case["review"]["findings"]:
            finding["blocking"] = False
        self.assertEqual(checker.evaluate_c1(case), "VALID")
        for finding in case["review"]["findings"]:
            finding.update(blocking=True, closed_for_candidate=True, resolution="fixed",
                           recheck_ref="review/attempt-1.md#recheck-1",
                           recheck_sha=case["candidate_sha"])
        case["expected_counts"]["open_by_severity"]["P2"] = 0
        self.assertEqual(checker.evaluate_c1(case), "VALID")
        for finding in case["review"]["findings"]:
            finding["recheck_sha"] = "b" * 40
        self.assertEqual(checker.evaluate_c1(case), "MISSING_EVIDENCE")

    def test_false_blocking_flag_cannot_downgrade_p0_or_p1(self):
        for severity in ("P0", "P1"):
            case = self.acceptance_case(severity)
            for finding in case["review"]["findings"]:
                finding["blocking"] = False
            self.assertEqual(checker.evaluate_c1(case), "ACCEPT_BLOCKED")

    def test_blocking_flag_requires_boolean(self):
        for value in ("false", "true", 0, 1, None, [], {}):
            with self.subTest(value=value):
                case = self.acceptance_case()
                for finding in case["review"]["findings"]:
                    finding["blocking"] = value
                with self.assertRaises(checker.BundleError):
                    checker.evaluate_c1(case)

    def test_c1_nested_wrong_types_are_controlled(self):
        mutations = (
            lambda c: c.update(tasks=False),
            lambda c: c["tasks"][0].update(id=[]),
            lambda c: c["tasks"][0].update(state={}),
            lambda c: c["tasks"][0].update(depends_on=[{}]),
            lambda c: c["points"][0].update(id=[]),
            lambda c: c["points"][0].update(state=[]),
            lambda c: c["points"][0].update(decided_by=True),
            lambda c: c["source_scope"].update(project=False),
            lambda c: c.update(available_evidence=True),
            lambda c: c["review"].update(source_refs="not-an-array"),
            lambda c: c["review"]["findings"][0].update(finding_id=[]),
            lambda c: c["review"]["findings"][0].update(evidence=["reference"]),
            lambda c: c["review"]["findings"][0].update(closed_for_candidate="false"),
            lambda c: c["review"]["checks"][0].update(check_id={}),
            lambda c: c["review"]["checks"][0].update(finding_ids=[{}]),
            lambda c: c["expected_counts"].update(findings_total=True),
        )
        for i, change in enumerate(mutations):
            with self.subTest(mutation=i):
                case = self.case("c1-01")
                change(case)
                with self.assertRaises(checker.BundleError):
                    checker.evaluate_c1(case)


if __name__ == "__main__":
    unittest.main()
