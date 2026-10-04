#!/usr/bin/env python3
"""Regression tests for validate_policy.py."""

from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

import validate_policy


MODEL = {
    "schema_version": "1.0.0",
    "primary_types": [
        {"issue_type": "feature", "branch_prefix": "feature", "commit_type": "feat"},
        {"issue_type": "bug", "branch_prefix": "fix", "commit_type": "fix"},
        {"issue_type": "build", "branch_prefix": "build", "commit_type": "build"},
        {"issue_type": "maintenance", "branch_prefix": "chore", "commit_type": "chore"},
    ],
    "overrides": [
        {"name": "hotfix", "branch_prefix": "hotfix", "branch_pattern": "hotfix/<issue>-<summary>", "commit_type": "fix", "allowed_issue_types": ["bug"], "requires_issue": True, "issue_in_branch_name": True},
        {"name": "revert", "branch_prefix": "revert", "branch_pattern": "revert/<issue>-<summary>", "commit_type": "revert", "allowed_issue_types": ["bug", "maintenance"], "requires_issue": True, "issue_in_branch_name": True},
        {"name": "release", "branch_prefix": "release", "branch_pattern": "release/<version>", "commit_type": "chore", "allowed_issue_types": ["maintenance"], "requires_issue": True, "issue_in_branch_name": False},
    ],
    "exemptions": [
        {"name": "repository-bootstrap", "requires_issue": False, "require_documented_reason": True}
    ],
}


class ValidatePolicyTests(unittest.TestCase):
    def make_skill(self, parent: Path, name: str, model: dict = MODEL) -> Path:
        root = parent / name
        (root / "references").mkdir(parents=True)
        (root / "SKILL.md").write_text("# fixture\n", encoding="utf-8")
        (root / "references" / "policy-model.json").write_text(
            json.dumps(model), encoding="utf-8"
        )
        return root

    def test_valid_model(self) -> None:
        self.assertEqual(validate_policy.validate_model(copy.deepcopy(MODEL)), [])

    def test_duplicate_branch_prefix_fails(self) -> None:
        model = copy.deepcopy(MODEL)
        model["primary_types"][1]["branch_prefix"] = "feature"
        findings = validate_policy.validate_model(model)
        self.assertTrue(any("duplicate primary branch_prefix" in item for item in findings))

    def test_unknown_override_issue_type_fails(self) -> None:
        model = copy.deepcopy(MODEL)
        model["overrides"][0]["allowed_issue_types"] = ["security"]
        findings = validate_policy.validate_model(model)
        self.assertTrue(any("unknown issue types" in item for item in findings))

    def test_ruleset_regex_covers_build_and_revert(self) -> None:
        pattern = re.compile(validate_policy.ruleset_regex(MODEL))
        self.assertIsNotNone(pattern.match("#9 build: update package graph"))
        self.assertIsNotNone(pattern.match("#12 revert(core): restore stable parser"))
        self.assertIsNone(pattern.match("#0 feat: invalid issue"))
        self.assertIsNone(pattern.match("#4 unknown: invalid type"))

    def test_document_projection_detects_mapping_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_skill(Path(temp), "skill")
            rows = []
            patterns = []
            for entry in MODEL["primary_types"]:
                rows.append(
                    f"| `{entry['issue_type']}` | `{entry['branch_prefix']}/<issue>-...` | `{entry['commit_type']}` | purpose |"
                )
                patterns.append(f"{entry['branch_prefix']}/<issue>-<summary>")
            patterns.extend(entry["branch_pattern"] for entry in MODEL["overrides"])
            (root / "references" / "branches.md").write_text(
                "\n".join(patterns + rows), encoding="utf-8"
            )
            (root / "references" / "github.md").write_text(
                validate_policy.ruleset_regex(MODEL), encoding="utf-8"
            )
            self.assertEqual(validate_policy.validate_document_projection(root, MODEL), [])
            (root / "references" / "github.md").write_text("stale", encoding="utf-8")
            findings = validate_policy.validate_document_projection(root, MODEL)
            self.assertTrue(any("Ruleset regex differs" in item for item in findings))

    def test_counterpart_inventory_and_model_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            first = self.make_skill(parent, "first")
            second = self.make_skill(parent, "second")
            self.assertEqual(
                validate_policy.validate_counterpart(first, second, copy.deepcopy(MODEL)), []
            )
            (second / "extra.txt").write_text("extra", encoding="utf-8")
            findings = validate_policy.validate_counterpart(first, second, copy.deepcopy(MODEL))
            self.assertTrue(any("extra files" in item for item in findings))

    def test_counterpart_model_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            first = self.make_skill(parent, "first")
            changed = copy.deepcopy(MODEL)
            changed["primary_types"][0]["commit_type"] = "feature"
            second = self.make_skill(parent, "second", changed)
            findings = validate_policy.validate_counterpart(first, second, copy.deepcopy(MODEL))
            self.assertTrue(any("differs" in item for item in findings))

    def test_counterpart_local_link_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            first = self.make_skill(parent, "first")
            second = self.make_skill(parent, "second")
            (first / "SKILL.md").write_text(
                "See [model](references/policy-model.json).\n", encoding="utf-8"
            )
            findings = validate_policy.validate_counterpart(first, second, copy.deepcopy(MODEL))
            self.assertTrue(any("local link targets differ" in item for item in findings))

    def test_counterpart_script_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            first = self.make_skill(parent, "first")
            second = self.make_skill(parent, "second")
            for root, content in ((first, "one"), (second, "two")):
                (root / "scripts").mkdir()
                (root / "scripts" / "check.py").write_text(content, encoding="utf-8")
            findings = validate_policy.validate_counterpart(first, second, copy.deepcopy(MODEL))
            self.assertTrue(any("validation script differs" in item for item in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
