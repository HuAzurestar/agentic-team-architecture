#!/usr/bin/env python3
"""Test the committed distributable via actual fresh Git checkouts.

Use --source URL --target FULL_SHA for a published candidate on another OS.
The default tests this repository's HEAD, never uncommitted working files.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = str(ROOT)
TARGET = "HEAD"


class CheckoutTests(unittest.TestCase):
    def run_process(self, argv, cwd=None):
        env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def check_checkout(self, autocrlf):
        with tempfile.TemporaryDirectory(prefix="pirc31-checkout-") as temporary:
            checkout = Path(temporary) / "product"
            self.run_process(["git", "clone", "--no-local", "--no-checkout", SOURCE, str(checkout)])
            self.run_process(["git", "config", "core.autocrlf", autocrlf], cwd=checkout)
            self.run_process(["git", "checkout", "--detach", TARGET], cwd=checkout)
            sha = self.run_process(["git", "rev-parse", "HEAD"], cwd=checkout).strip()
            self.assertEqual(len(sha), 40)
            bundle = checkout / "examples/long-feature/contracts/v0.2-draft"
            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                raw = (bundle / entry["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"],
                                 f"autocrlf={autocrlf}: {entry['path']} at {sha}")
            self.run_process([sys.executable, "scripts/test_long_feature_contracts.py"], cwd=checkout)
            for locale in ("skills", "skills_cn"):
                scripts = checkout / locale / "long-feature-development" / "scripts"
                self.run_process([sys.executable, str(scripts / "test_context.py")], cwd=checkout)
                self.run_process([sys.executable, str(scripts / "test_installation.py")], cwd=checkout)
            self.assertEqual(self.run_process(["git", "status", "--porcelain"], cwd=checkout), "")

    def test_autocrlf_true_preserves_manifest_and_installed_behavior(self):
        self.check_checkout("true")

    def test_autocrlf_false_preserves_manifest_and_installed_behavior(self):
        self.check_checkout("false")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--target", default=TARGET)
    args, remaining = parser.parse_known_args()
    SOURCE, TARGET = args.source, args.target
    unittest.main(argv=[sys.argv[0], *remaining])
