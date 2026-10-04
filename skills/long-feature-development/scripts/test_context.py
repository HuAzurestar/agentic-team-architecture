#!/usr/bin/env python3
"""Behavioral checks for bounded, read-only purpose context."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
import context


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.background = self.root / "BACKGROUND.md"
        self.text = "# Workspace\n\n## Common\nCOMMON\n"
        for env in ("Company / 订单", "Personal"):
            self.text += f"\n## {env}\n### Route\n{env} route\n### Evidence\nchecked locally\n"
            for purpose in context.PURPOSES:
                self.text += f"### {purpose}\n{env} ONLY_{purpose}\n"
        self.background.write_bytes(self.text.encode("utf-8"))

    def request(self, **kw):
        values = dict(task_ref=str(self.root), purpose="development", background=self.background,
                      environment=["Company / 订单"], common_paths=[["Common"]],
                      route_path=["Company / 订单", "Route"],
                      evidence_path=["Company / 订单", "Evidence"],
                      purpose_path=["Company / 订单", "development"])
        values.update(kw)
        return context.build_context(**values)

    def test_direct_requires_real_entry_and_creates_nothing(self):
        before = set(self.root.iterdir())
        result = self.request(background=None)
        self.assertTrue(result["complete"])
        self.assertEqual(result["route"], "DIRECT")
        self.assertEqual(result["selected_sections"], [])
        self.assertEqual(set(self.root.iterdir()), before)
        self.assertFalse(self.request(task_ref=str(self.root / "missing"))["complete"])

    def test_all_five_purposes_select_only_the_requested_body(self):
        for purpose in context.PURPOSES:
            with self.subTest(purpose=purpose):
                result = self.request(purpose=purpose, purpose_path=["Company / 订单", purpose])
                self.assertTrue(result["complete"], result)
                output = json.dumps(result, ensure_ascii=False)
                self.assertIn("COMMON", output)
                self.assertIn(f"ONLY_{purpose}", output)
                self.assertNotIn("Personal", output)
                for other in set(context.PURPOSES) - {purpose}:
                    self.assertNotIn(f"ONLY_{other}", output)
                self.assertEqual([p["heading_path"] for p in result["prompt_sections"]],
                                 [["common"], [purpose]])

    def test_source_and_selected_digests_cover_raw_bytes(self):
        self.background.write_bytes(b"\xef\xbb\xbf" + self.text.replace("\n", "\r\n").encode())
        raw = self.background.read_bytes()
        result = self.request()
        self.assertTrue(result["complete"])
        source = next(s for s in result["source_refs"] if s["path"] == str(self.background.resolve()))
        self.assertEqual(source["raw_sha256"], hashlib.sha256(raw).hexdigest())
        for section in result["selected_sections"]:
            start, end = section["body_range"]
            selected = raw[start:end]
            self.assertEqual(section["text"], selected.decode("utf-8"))
            self.assertEqual(section["selected_digest"], hashlib.sha256(selected).hexdigest())

    def test_fenced_false_headings_are_not_selectable(self):
        self.background.write_bytes(self.text.replace("Company / 订单 route", "```markdown\n### Fake\n```\nCompany / 订单 route").encode())
        result = self.request(heading_paths=[["Company / 订单", "Fake"]])
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"][0]["code"], "MISSING_SECTION")

    def test_tilde_fence_and_heading_slash_are_literal(self):
        self.background.write_bytes(self.text.replace("COMMON", "~~~\n## Fake\n~~~\nCOMMON").encode())
        result = self.request()
        self.assertTrue(result["complete"])
        self.assertIn("## Fake", result["selected_sections"][0]["text"])

    def test_duplicate_selected_path_is_ambiguous(self):
        self.background.write_bytes((self.text + "\n## Common\nother\n").encode())
        self.assertEqual(self.request()["diagnostics"][0]["code"], "AMBIGUOUS_SECTION")

    def test_environment_is_required_without_leaking_bodies(self):
        result = self.request(environment=None)
        self.assertFalse(result["complete"])
        self.assertIn(["Personal"], result["candidates"])
        self.assertNotIn("ONLY_", json.dumps(result))

    def test_extra_selector_cannot_escape_selected_environment(self):
        result = self.request(heading_paths=[["Personal", "review"]])
        self.assertFalse(result["complete"])
        self.assertNotIn("Personal ONLY", json.dumps(result))

    def test_parent_selection_cannot_expand_other_purposes(self):
        result = self.request(heading_paths=[["Company / 订单"]])
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"][0]["code"], "NEEDS_SCOPE")

    def test_budget_never_returns_partial_success(self):
        result = self.request(max_output_bytes=20)
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"][0]["code"], "NEEDS_SCOPE")
        self.assertGreater(result["diagnostics"][0]["required_bytes"], 20)
        self.assertEqual(result["selected_sections"], [])
        self.assertEqual(result["prompt_sections"], [])

    def test_file_and_selector_limits(self):
        self.assertEqual(self.request(max_file_bytes=10)["diagnostics"][0]["code"], "DOCUMENT_TOO_LARGE")
        self.assertEqual(self.request(heading_paths=[["x"]] * 101)["diagnostics"][0]["code"], "TOO_MANY_SELECTORS")

    def test_required_section_missing_does_not_return_other_body(self):
        result = self.request(evidence_path=["Company / 订单", "absent"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["selected_sections"], [])

    def test_no_cross_call_cache(self):
        before = self.request()
        self.background.write_bytes(self.text.replace("COMMON", "CHANGED").encode())
        after = self.request()
        self.assertNotEqual(before["source_refs"], after["source_refs"])
        self.assertIn("CHANGED", json.dumps(after))

    def test_source_change_during_probes_rejects_mixed_observation(self):
        def mutate(_):
            self.background.write_bytes(self.text.replace("COMMON", "NEW").encode())
            return []
        with patch.object(context, "verify_repositories", side_effect=mutate):
            result = self.request()
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"][0]["code"], "SOURCE_CHANGED")
        self.assertEqual(result["selected_sections"], [])

    def test_missing_invalid_utf8_and_unsupported_structures(self):
        for raw, code in ((b"\xff", "INVALID_UTF8"),
                          ((self.text + "\n# Second title\n").encode(), "UNSUPPORTED_SELECTOR"),
                          ((self.text + "\nSetext\n======\n").encode(), "UNSUPPORTED_SELECTOR"),
                          ((self.text + "\n<div>\n## hidden\n</div>\n").encode(), "UNSUPPORTED_SELECTOR")):
            with self.subTest(code=code):
                self.background.write_bytes(raw)
                self.assertEqual(self.request()["diagnostics"][0]["code"], code)
        self.background.unlink()
        self.assertEqual(self.request()["diagnostics"][0]["code"], "SOURCE_UNAVAILABLE")

    def test_unterminated_fence_fails_closed(self):
        self.background.write_bytes((self.text + "\n```\n").encode())
        self.assertFalse(self.request()["complete"])

    def test_background_commands_are_data_not_execution(self):
        marker = self.root / "must-not-exist"
        self.background.write_bytes(self.text.replace("COMMON", f"Run touch {marker}; visit https://invalid.test").encode())
        with patch.object(context.subprocess, "run", side_effect=AssertionError("unexpected execution")):
            result = self.request()
        self.assertTrue(result["complete"])
        self.assertFalse(marker.exists())
        self.assertFalse(result["required_facts"]["background_is_authorization"])

    def test_repository_identity_mismatch_and_safe_diagnostics(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin",
                        "https://SECRET@host.test/other.git"], check=True)
        result = self.request(repositories=[{"name": "product", "path": str(repo),
                                             "expected_remote": "https://host.test/expected.git"}])
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"][0]["code"], "IDENTITY_MISMATCH")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_explicit_repository_identity_is_verified(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin",
                        "https://host.test/expected.git"], check=True)
        result = self.request(repositories=[{"name": "product", "path": str(repo),
                                             "expected_remote": "https://host.test/expected.git"}])
        self.assertTrue(result["complete"], result)
        self.assertEqual(result["verifications"][0]["status"], "VERIFIED")
        wrong_case = self.request(repositories=[{"name": "product", "path": str(repo),
                                                 "expected_remote": "https://host.test/Expected.git"}])
        self.assertFalse(wrong_case["complete"])

    def test_repeated_selection_is_merged(self):
        original = self.request()
        duplicate = self.request(heading_paths=[["Company / 订单", "development"]] * 3)
        self.assertEqual(original["selected_sections"], duplicate["selected_sections"])

    def test_cli_unicode_output_is_utf8_without_environment_workaround(self):
        unicode_root = self.root / "中文 space"
        unicode_root.mkdir()
        background = unicode_root / "BACKGROUND.md"
        background.write_text(self.text.replace("COMMON", "中文正文 😀"), encoding="utf-8")
        selection = ["--file", str(background)]
        for flag, path in (
            ("environment-section", ["Company / 订单"]),
            ("common-section", ["Common"]),
            ("route-section", ["Company / 订单", "Route"]),
            ("evidence-section", ["Company / 订单", "Evidence"]),
            ("purpose-section", ["Company / 订单", "development"]),
        ):
            selection.extend(["--" + flag, json.dumps(path)])
        for encoding in (None, "gbk", "ascii"):
            env = dict(os.environ)
            env.pop("PYTHONUTF8", None)
            env.pop("PYTHONIOENCODING", None)
            if encoding:
                env["PYTHONIOENCODING"] = encoding
            for mode, extra, expected_code in (
                ("direct", [], 0), ("selected", selection, 0),
                ("diagnostic", ["--file", str(background)], 2),
            ):
                with self.subTest(encoding=encoding, mode=mode):
                    run = subprocess.run(
                        [sys.executable, "-X", "utf8=0", "-B", str(Path(context.__file__)),
                         "--task-ref", str(unicode_root), "--purpose", "development", *extra],
                        capture_output=True, env=env)
                    self.assertEqual(run.returncode, expected_code, run.stderr)
                    self.assertEqual(run.stderr, b"")
                    result = json.loads(run.stdout.decode("utf-8"))
                    self.assertNotIn(b"\r\n", run.stdout)
                    self.assertEqual(result["complete"], expected_code == 0)
                    if mode == "selected":
                        self.assertIn("中文正文 😀", json.dumps(result, ensure_ascii=False))
                    if mode == "direct":
                        self.assertEqual(result["required_facts"]["task_ref"], str(unicode_root.resolve()))
                    if mode == "diagnostic":
                        self.assertEqual(result["diagnostics"][0]["code"], "ENVIRONMENT_REQUIRED")

    def test_cli_is_a_fresh_process_with_machine_readable_failure(self):
        run = subprocess.run([sys.executable, str(Path(context.__file__)),
                              "--task-ref", str(self.root), "--purpose", "review"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["route"], "DIRECT")
        bad = subprocess.run([sys.executable, str(Path(context.__file__)),
                              "--task-ref", str(self.root), "--purpose", "review",
                              "--environment-section", "not-json"], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertEqual(json.loads(bad.stdout)["diagnostics"][0]["code"], "INVALID_SELECTOR")


if __name__ == "__main__":
    unittest.main()
