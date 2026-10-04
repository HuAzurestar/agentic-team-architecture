"""Verify actual locale packages run and never include development tests."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from assemble_skill import assemble_skill


REPOSITORY = Path(__file__).resolve().parents[3]


class AssembleSkillTests(unittest.TestCase):
    def make_repository(self, parent):
        repo = parent / "repository"
        source = repo / "skills/example"
        (source / "references").mkdir(parents=True)
        (source / "SKILL.md").write_text("# Example\n", encoding="utf-8")
        (source / "references/detail.md").write_text("English detail", encoding="utf-8")
        runtime = repo / "scripts/example/scripts"
        runtime.mkdir(parents=True)
        (runtime / "helper.py").write_text("print('runtime')\n", encoding="utf-8")
        return repo, source, runtime

    def test_overlay_preserves_content_and_shared_runtime_without_tests(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, source, runtime = self.make_repository(Path(temp))
            (runtime / "test_leak.py").write_text("old test", encoding="utf-8")
            outside = repo / "scripts/tests/example"
            outside.mkdir(parents=True)
            (outside / "oracle.md").write_text("expected findings", encoding="utf-8")
            package = assemble_skill(repo, "example", "en", Path(temp) / "output")
            self.assertEqual((package / "references/detail.md").read_text(encoding="utf-8"), "English detail")
            self.assertEqual((package / "scripts/helper.py").read_bytes(), (runtime / "helper.py").read_bytes())
            self.assertEqual(sorted(path.name for path in package.rglob("*") if path.is_file()), ["SKILL.md", "detail.md", "helper.py"])

    def test_existing_destination_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _, _ = self.make_repository(Path(temp))
            destination = Path(temp) / "output"
            package = assemble_skill(repo, "example", "en", destination)
            with self.assertRaises(FileExistsError):
                assemble_skill(repo, "example", "en", destination)
            self.assertEqual((package / "SKILL.md").read_text(encoding="utf-8"), "# Example\n")

    def test_collision_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, source, _ = self.make_repository(Path(temp))
            (source / "scripts").mkdir()
            (source / "scripts/helper.py").write_text("different", encoding="utf-8")
            output = Path(temp) / "output"
            with self.assertRaisesRegex(ValueError, "collision"):
                assemble_skill(repo, "example", "en", output)
            self.assertFalse(output.exists())

    def test_invalid_names_missing_locale_and_source_destination_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _, _ = self.make_repository(Path(temp))
            for name, locale, output in (("../example", "en", Path(temp)), ("example", "unknown", Path(temp)), ("example", "cn", Path(temp)), ("example", "en", repo / "scripts/output")):
                with self.subTest(name=name, locale=locale), self.assertRaises(ValueError):
                    assemble_skill(repo, name, locale, output)

    def test_real_english_and_chinese_packages_have_identical_runtimes(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ("git-collaboration", "long-feature-development", "review"):
                packages = [assemble_skill(REPOSITORY, name, locale, Path(temp) / locale) for locale in ("en", "cn")]
                expected = {path.name: path.read_bytes() for path in (REPOSITORY / "scripts" / name / "scripts").glob("*.py")}
                self.assertTrue(expected)
                for package in packages:
                    actual = {path.name: path.read_bytes() for path in (package / "scripts").glob("*.py")}
                    self.assertEqual(actual, expected)
                    self.assertFalse(any(path.name.startswith("test_") or path.name == "tests" for path in package.rglob("*")))
                    self.assertTrue((package / "SKILL.md").is_file())

    def test_assembled_entrypoints_run_without_repository_pythonpath(self):
        commands = {
            "git-collaboration": ("validate_policy.py",),
            "long-feature-development": ("task_context.py", "task_state.py", "task_create.py", "task_checkpoint.py"),
            "review": ("review_score.py",),
        }
        with tempfile.TemporaryDirectory() as temp:
            for locale in ("en", "cn"):
                for name, filenames in commands.items():
                    package = assemble_skill(REPOSITORY, name, locale, Path(temp) / locale)
                    environment = os.environ.copy()
                    environment.pop("PYTHONPATH", None)
                    for filename in filenames:
                        with self.subTest(locale=locale, filename=filename):
                            result = subprocess.run([sys.executable, "-B", "-X", "utf8", str(package / "scripts" / filename), "--help"], cwd=temp, env=environment, capture_output=True, text=True)
                            self.assertEqual(result.returncode, 0, result.stderr)
                            self.assertIn("usage:", result.stdout)
                    if name == "review":
                        result = subprocess.run([sys.executable, "-B", str(package / "scripts/review_score.py"), "--complete", "--p1", "4"], cwd=temp, env=environment, capture_output=True, text=True, check=True)
                        self.assertEqual(json.loads(result.stdout)["score"], 60)


if __name__ == "__main__":
    unittest.main()
