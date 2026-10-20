#!/usr/bin/env python3
"""Generated indexes preserve unmanaged bytes and never write authoritative inputs."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True

import contract_check as checker
import feature_indexes as indexes
from index_blocks import BlockError, REGIONS, region_bounds, replace_regions
from test_contract_check import TEMPLATES, write_detail


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def unmanaged(content, filename):
    spans = [region_bounds(content, name) for name, (target, _) in REGIONS.items()
             if target == filename]
    for left, right in sorted(spans, reverse=True):
        content = content[:left] + "<GENERATED>" + content[right:]
    return content.encode("utf-8")


class GeneratedIndexTests(unittest.TestCase):
    def feature(self, parent):
        root = Path(parent) / "feature"
        shutil.copytree(TEMPLATES, root)
        return root

    def stale_task(self, root):
        path = root / "tasks/DEV-001.md"
        item = checker.load(path)
        item["title"] = "New task title"
        item["depends on"] = ["DECISION-001"]
        write_detail(path, item)
        return item

    def test_default_check_is_read_only_and_reports_stale_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            self.stale_task(root)
            before = snapshot(root)
            result = indexes.sync_indexes(root)
            self.assertFalse(result["valid"])
            self.assertIn("TASKS.md", result["changed"])
            self.assertEqual(snapshot(root), before)

    def test_write_preserves_all_unmanaged_bytes_bom_and_line_endings(self):
        for newline, bom in (("\n", ""), ("\r\n", "\ufeff")):
            with self.subTest(newline=repr(newline)), tempfile.TemporaryDirectory() as temporary:
                root = self.feature(temporary)
                for filename in ("DESIGN.md", "TASKS.md", "VERBAL.md"):
                    path = root / filename
                    content = path.read_text(encoding="utf-8")
                    content += "\n- 2026-10-20 — Keep this note and punctuation: | <> &.\n"
                    path.write_bytes((bom + content.replace("\n", newline)).encode("utf-8"))
                self.stale_task(root)
                (root / "gists").mkdir()
                (root / "gists/output.bin").write_bytes(b"\x00\xff")
                before = snapshot(root)
                result = indexes.sync_indexes(root, write=True)
                self.assertTrue(result["valid"])
                after = snapshot(root)
                self.assertEqual(set(before), set(after))
                for filename, original in before.items():
                    if filename in ("DESIGN.md", "TASKS.md", "VERBAL.md"):
                        self.assertEqual(unmanaged(original.decode("utf-8"), filename),
                                         unmanaged(after[filename].decode("utf-8"), filename))
                        if newline == "\r\n":
                            self.assertNotIn(b"\n", after[filename].replace(b"\r\n", b""))
                    else:
                        self.assertEqual(original, after[filename])
                checker.validate_feature(root)

    def test_generation_is_idempotent_and_does_not_rewrite_clean_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            self.stale_task(root)
            indexes.sync_indexes(root, write=True)
            before = snapshot(root)
            times = {p.name: p.stat().st_mtime_ns for p in root.glob("*.md")}
            self.assertEqual(indexes.sync_indexes(root, write=True)["changed"], [])
            self.assertEqual(snapshot(root), before)
            self.assertEqual({p.name: p.stat().st_mtime_ns for p in root.glob("*.md")}, times)

    def test_tasks_update_both_table_and_dependency_graph(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            self.stale_task(root)
            before = snapshot(root)
            result = indexes.sync_indexes(root, only="tasks", write=True)
            self.assertEqual(result["changed"], ["TASKS.md"])
            content = (root / "TASKS.md").read_text(encoding="utf-8")
            self.assertIn("New task title", content)
            self.assertIn("n0 --> n1", content)
            self.assertEqual((root / "DESIGN.md").read_bytes(), before["DESIGN.md"])
            checker.validate_feature(root)

    def test_topology_drift_is_a_formal_validation_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "TASKS.md"
            content = path.read_text(encoding="utf-8").replace("flowchart TD", "flowchart LR")
            path.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(checker.ContractError, "topology differs"):
                checker.validate_feature(root)

    def test_topology_has_isolated_nodes_and_escapes_labels(self):
        original = checker.load(TEMPLATES / "tasks/DEV-001.md")
        records = {}
        for record_id, dependencies in (("A", []), ("B", ["A"]), ("C", ["A"]), ("D", ["B", "C"]),
                                        ("ISOLATED", [])):
            item = copy.deepcopy(original)
            item.update({"id": record_id, "depends on": dependencies,
                         "title": 'Title "\n<unsafe> ` label'})
            records[record_id] = item
        rendered = checker.render_topology(records)
        self.assertEqual(rendered.count(" --> "), 4)
        self.assertIn("ISOLATED", rendered)
        self.assertIn("&quot;", rendered)
        self.assertIn("&lt;unsafe&gt;", rendered)
        self.assertNotIn("\n<unsafe>", rendered)
        self.assertEqual(rendered, checker.render_topology(dict(reversed(list(records.items())))))

    def test_attachments_use_metadata_not_contents_and_support_nested_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "gists/nested/log [one] # report.bin"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"\x00\xff\xfe")
            os.utime(path, (1609459200, 1609459200))
            indexes.sync_indexes(root, only="verbal", write=True)
            content = (root / "VERBAL.md").read_text(encoding="utf-8")
            self.assertIn("Size (bytes)", content)
            self.assertIn("2021-01-01T00:00:00Z", content)
            self.assertIn("log%20%5Bone%5D%20%23%20report.bin", content)
            self.assertIn("| 3 |", content)
            self.assertEqual(path.read_bytes(), b"\x00\xff\xfe")
            path.unlink()
            indexes.sync_indexes(root, only="verbal", write=True)
            self.assertNotIn("report.bin", (root / "VERBAL.md").read_text(encoding="utf-8"))
            checker.validate_feature(root)

    def test_optional_verbal_is_not_recreated_or_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            (root / "VERBAL.md").unlink()
            result = indexes.sync_indexes(root, write=True)
            self.assertNotIn("VERBAL.md", result["checked"])
            self.assertFalse((root / "VERBAL.md").exists())
            checker.validate_feature(root)
            with self.assertRaises(OSError):
                indexes.sync_indexes(root, only="verbal", write=True)

    def test_verbal_only_does_not_require_design_or_tasks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copy2(TEMPLATES / "VERBAL.md", root / "VERBAL.md")
            self.assertTrue(indexes.sync_indexes(root, only="verbal", write=True)["valid"])

    def test_malformed_final_target_prevents_every_write(self):
        for defect in ("missing", "duplicate", "reversed", "wrong section", "inline",
                       "cross section", "tab section", "indented section", "setext section"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temporary:
                root = self.feature(temporary)
                self.stale_task(root)
                path = root / "VERBAL.md"
                content = path.read_text(encoding="utf-8")
                start = "<!-- verbal-preview-table:start -->"
                end = "<!-- verbal-preview-table:end -->"
                if defect == "missing":
                    content = content.replace(end, "")
                elif defect == "duplicate":
                    content += "\n" + end + "\n"
                elif defect == "reversed":
                    content = content.replace(start, "TEMP").replace(end, start).replace("TEMP", end)
                elif defect == "wrong section":
                    content = content.replace("## preview-table", "## other")
                elif defect == "inline":
                    content = content.replace(start, "Text " + start)
                elif defect == "cross section":
                    content = content.replace(end, "## crossed\n" + end)
                elif defect == "tab section":
                    content = content.replace(end, "##\tNotes\n" + end)
                elif defect == "indented section":
                    content = content.replace(end, "  ## Notes\n" + end)
                else:
                    content = content.replace(end, "Notes\n-----\n" + end)
                path.write_text(content, encoding="utf-8")
                before = snapshot(root)
                with self.assertRaises(BlockError):
                    indexes.sync_indexes(root, write=True)
                self.assertEqual(snapshot(root), before)

    def test_incomplete_attachment_scan_fails_before_any_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            self.stale_task(root)
            (root / "gists").mkdir()
            before = snapshot(root)
            original_scan = indexes.os.scandir
            def scan(path):
                if Path(path) == root / "gists":
                    raise PermissionError("denied")
                return original_scan(path)
            with patch.object(indexes.os, "scandir", side_effect=scan):
                with self.assertRaises(PermissionError):
                    indexes.sync_indexes(root, write=True)
            self.assertEqual(snapshot(root), before)

    def test_record_text_cannot_inject_generated_markers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "tasks/DEV-001.md"
            item = checker.load(path)
            item["title"] = "Mention <!-- tasks-preview-table:end --> safely"
            write_detail(path, item)
            indexes.sync_indexes(root, write=True)
            content = (root / "TASKS.md").read_text(encoding="utf-8")
            self.assertEqual(content.count("<!-- tasks-preview-table:end -->"), 1)
            checker.validate_feature(root)

    def test_fenced_example_cannot_be_used_as_a_generated_section(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            path = root / "VERBAL.md"
            content = path.read_text(encoding="utf-8")
            path.write_text("```markdown\n" + content + "\n```\n", encoding="utf-8")
            before = snapshot(root)
            with self.assertRaises(BlockError):
                indexes.sync_indexes(root, write=True)
            self.assertEqual(snapshot(root), before)

    def test_invalid_authoritative_input_prevents_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            self.stale_task(root)
            (root / "design/SOL-001.md").write_text("Invalid YAML record", encoding="utf-8")
            before = snapshot(root)
            with self.assertRaises(checker.ContractError):
                indexes.sync_indexes(root, write=True)
            self.assertEqual(snapshot(root), before)

    def test_generated_tables_have_no_horizontal_rule_wrappers(self):
        groups = checker.collect(TEMPLATES)
        for domain in ("design", "tasks"):
            self.assertNotIn("---", checker.render_index(groups[domain], domain).splitlines())

    def test_cli_check_write_and_check_have_meaningful_exit_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.feature(temporary)
            self.stale_task(root)
            command = [sys.executable, "-B", str(Path(indexes.__file__)), str(root)]
            for options, code in (([], 1), (["--write"], 0), (["--check"], 0)):
                process = subprocess.run(command + options, capture_output=True,
                                         text=True, encoding="utf-8", check=False)
                self.assertEqual(process.returncode, code, process.stderr)
                self.assertEqual(json.loads(process.stdout)["valid"], code == 0)


if __name__ == "__main__":
    unittest.main()
