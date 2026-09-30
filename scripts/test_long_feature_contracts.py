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

    def test_c3_context_different_from_source_is_rejected(self) -> None:
        self.rewrite_case("C3-01", lambda case: case["context"].update(intent={"unrelated": "different source"}))
        code, result = self.check_bundle()
        self.assertEqual(code, 3)
        self.assertEqual(result["failures"][0]["field"], "expected_result")

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
