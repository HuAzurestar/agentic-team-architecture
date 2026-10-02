#!/usr/bin/env python3
"""Exercise directory installation and lifecycle using isolated real files."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
SKILL = Path(__file__).resolve().parent.parent


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "external-project"
        self.project.mkdir()
        for name in ("STATUS.md", "BACKGROUND.md", "credentials.local"):
            (self.project / name).write_bytes(("USER-DATA:" + name).encode())
        self.before = self.digests()
        self.install = self.root / "skills" / "long-feature-development"

    def digests(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.project.iterdir()}

    def copy(self, destination):
        # copytree's default rejects an existing destination, including old installs.
        shutil.copytree(SKILL, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def context(self, skill, *args):
        proc = subprocess.run([sys.executable, "-B", str(skill / "scripts" / "context.py"),
                               "--task-ref", str(self.project), "--purpose", "development", *args],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        return json.loads(proc.stdout)

    def test_clean_install_runs_without_service_or_original_checkout(self):
        self.copy(self.install)
        result = self.context(self.install)
        self.assertEqual(result["route"], "DIRECT")
        self.assertTrue(result["complete"])
        self.assertTrue((self.install / "SKILL.md").is_file())
        for source in result["source_refs"]:
            self.assertTrue(Path(source["path"]).is_relative_to(self.install))
        self.assertEqual(self.before, self.digests())

    def test_existing_install_is_not_overwritten(self):
        self.copy(self.install)
        marker = self.install / "local-marker"
        marker.write_bytes(b"KEEP")
        with self.assertRaises(FileExistsError):
            self.copy(self.install)
        self.assertEqual(marker.read_bytes(), b"KEEP")

    def test_fresh_process_reads_installed_background_selection(self):
        self.copy(self.install)
        background = self.root / "environment.md"
        shutil.copyfile(self.install / "templates" / "BACKGROUND.md", background)
        result = self.context(self.install, "--file", str(background),
                              "--environment-section", '["Example environment"]',
                              "--common-section", '["Common"]',
                              "--route-section", '["Example environment", "Route"]',
                              "--evidence-section", '["Example environment", "Evidence"]',
                              "--purpose-section", '["Example environment", "development"]')
        self.assertEqual(len(result["selected_sections"]), 4)
        self.assertTrue(result["complete"])

    def test_upgrade_exit_and_rollback_keep_external_data(self):
        self.copy(self.install)
        old_prompt = self.install / "references" / "prompts.md"
        original = old_prompt.read_bytes()
        # Different bytes model two program versions, not a real product acceptance.
        old_prompt.write_bytes(original.replace(b"## development\n", b"## development\n\nOLD_PROGRAM\n"))
        old_digest = hashlib.sha256(old_prompt.read_bytes()).hexdigest()
        new_install = self.root / "skills" / "long-feature-development-next"
        self.copy(new_install)
        self.assertNotIn("OLD_PROGRAM", json.dumps(self.context(new_install)))
        self.assertEqual(self.before, self.digests())
        # Exiting means stop selecting the new root. Rollback selects the old root.
        self.assertIn("OLD_PROGRAM", json.dumps(self.context(self.install)))
        self.assertEqual(hashlib.sha256(old_prompt.read_bytes()).hexdigest(), old_digest)
        self.assertEqual(self.before, self.digests())

    def test_exclusive_existing_backup_preserves_original_bytes(self):
        source = self.project / "BACKGROUND.md"
        backup = self.root / "background.backup"
        with backup.open("xb") as stream:
            stream.write(source.read_bytes())
        self.assertEqual(backup.read_bytes(), source.read_bytes())
        with self.assertRaises(FileExistsError):
            backup.open("xb")
        self.assertEqual(self.before, self.digests())


if __name__ == "__main__":
    unittest.main()
