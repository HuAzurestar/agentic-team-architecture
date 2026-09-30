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
        self.assertEqual(code, 3)
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
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["path"], "c1.md")

    def test_duplicate_case_id_is_rejected(self) -> None:
        value = self.manifest()
        value["files"][-1]["case_id"] = "C3-08"
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertIn("duplicate", result["failures"][0]["observed"])

    def test_escape_path_is_rejected(self) -> None:
        value = self.manifest()
        value["files"][3]["path"] = "../outside.json"
        self.save_manifest(value)
        code, result = self.check_bundle()
        self.assertEqual(code, 2)
        self.assertIn("unsafe relative path", result["failures"][0]["observed"])


if __name__ == "__main__":
    unittest.main()
