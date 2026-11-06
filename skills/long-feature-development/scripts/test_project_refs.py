#!/usr/bin/env python3
"""Read-only project mapping and reference identity tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

import project_refs
import yaml


TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "PROJECT.yaml"


class ProjectReferenceTests(unittest.TestCase):
    def registry(self, parent):
        root = Path(parent) / "project"
        path = root / "example-project" / "project.yaml"
        path.parent.mkdir(parents=True)
        shutil.copy2(TEMPLATE, path)
        return root, path

    def test_point_uses_project_and_sha_without_branch(self):
        point = project_refs.parse_ref("AOPC-AI@" + "a" * 40)
        self.assertEqual(point["project key"], "AOPC-AI")
        self.assertEqual(point["sha"], "a" * 40)
        self.assertIsNone(point["branch"])
        self.assertFalse(point["abbreviated"])

    def test_full_spelling_normalizes_to_the_same_point(self):
        short = project_refs.parse_ref("AOPC-AI@" + "a" * 40)
        full = project_refs.parse_ref("AOPC-AI@feature/work@" + "a" * 40)
        self.assertEqual(short["canonical"], full["canonical"])
        self.assertEqual(full["branch"], "feature/work")

    def test_area_is_explicit_even_for_a_hexadecimal_branch_name(self):
        area = project_refs.parse_ref("AOPC-AI@deadbeef", "area")
        point = project_refs.parse_ref("AOPC-AI@deadbeef", "point")
        self.assertEqual(area["branch"], "deadbeef")
        self.assertNotIn("sha", area)
        self.assertTrue(point["abbreviated"])

    def test_project_qualifies_identical_branch_names(self):
        first = project_refs.parse_ref("AOPC-AI@main", "area")
        second = project_refs.parse_ref("SM-MD@main", "area")
        self.assertNotEqual(first["canonical"], second["canonical"])

    def test_branch_can_contain_the_separator(self):
        point = project_refs.parse_ref("AOPC-AI@team@review@" + "a" * 40)
        self.assertEqual(point["branch"], "team@review")
        self.assertEqual(project_refs.parse_ref("AOPC-AI@team@review", "area")["branch"], "team@review")

    def test_invalid_points_and_keys_are_rejected(self):
        for value in ("a" * 40, "AOPC-AI@main", "../bad@" + "a" * 40,
                      "AOPC-AI@@not-a-sha", "AOPC-AI@"):
            with self.subTest(value=value), self.assertRaises(project_refs.ProjectRefError):
                project_refs.parse_ref(value)

    def test_sha256_and_abbreviated_points_are_distinguished(self):
        self.assertFalse(project_refs.parse_ref("SM-MD@" + "b" * 64)["abbreviated"])
        self.assertTrue(project_refs.parse_ref("SM-MD@abcdef1")["abbreviated"])

    def test_resolver_returns_os_locations_without_changing_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, path = self.registry(temporary)
            before = path.read_bytes()
            result = project_refs.resolve_ref(root, "example-project@" + "a" * 40)
            self.assertIn("windows", result["project"]["local repository"])
            self.assertIn("linux", result["project"]["local repository"])
            self.assertEqual(result["scope"], "location-only")
            self.assertFalse(result["commit verified"])
            self.assertEqual(path.read_bytes(), before)

    def test_folder_and_project_key_must_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, path = self.registry(temporary)
            record = project_refs.load_project(path)
            record["project key"] = "OTHER"
            path.write_text(yaml.safe_dump(record), encoding="utf-8")
            with self.assertRaises(project_refs.ProjectRefError):
                project_refs.project_config(root, "example-project")

    def test_moving_task_state_is_not_stable_project_configuration(self):
        record = project_refs.load_project(TEMPLATE)
        for key in ("head sha", "working branch", "integration branch"):
            item = {**record, key: "example-project@main"}
            with self.subTest(key=key), self.assertRaises(project_refs.ProjectRefError):
                project_refs.validate_project(item)

    def test_duplicate_project_yaml_keys_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "project.yaml"
            path.write_text("project key: one\nproject key: two\n", encoding="utf-8")
            with self.assertRaises(project_refs.ProjectRefError):
                project_refs.load_project(path)

    def test_project_rule_dates_remain_strings_in_resolver_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, path = self.registry(temporary)
            content = path.read_text(encoding="utf-8").replace(
                "basic rules: []", "basic rules:\n  supported until: 2027-01-01")
            path.write_text(content, encoding="utf-8")
            process = subprocess.run(
                [sys.executable, "-B", str(Path(project_refs.__file__)), str(root),
                 "example-project@" + "a" * 40],
                text=True, encoding="utf-8", capture_output=True, check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout)["project"]["basic rules"]["supported until"],
                             "2027-01-01")

    def test_cli_reports_location_only_and_does_not_run_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, path = self.registry(temporary)
            before = path.read_bytes()
            process = subprocess.run(
                [sys.executable, "-B", str(Path(project_refs.__file__)), str(root),
                 "example-project@" + "a" * 40],
                text=True, encoding="utf-8", capture_output=True, check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertFalse(json.loads(process.stdout)["commit verified"])
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
