"""Verify template packaging and the deliberately flawed presentation example."""

import re
import runpy
import tempfile
import unittest
from pathlib import Path

from assemble_skill import assemble_skill
from review_score import score_review


REPOSITORY = Path(__file__).resolve().parents[3]


class ReviewTemplateTests(unittest.TestCase):
    def test_all_three_templates_ship_in_each_locale_without_demo_answers(self):
        with tempfile.TemporaryDirectory() as temp:
            for locale, folder in (("en", "skills"), ("cn", "skills_cn")):
                package = assemble_skill(REPOSITORY, "code-review", locale, Path(temp) / locale)
                for name in ("REVIEW_INPUT.md", "REVIEW_REPORT.md", "REVIEW.md"):
                    with self.subTest(locale=locale, name=name):
                        self.assertEqual((package / "assets" / name).read_bytes(), (REPOSITORY / folder / "code-review/assets" / name).read_bytes())
                self.assertFalse(any(path.name == "examples" for path in package.rglob("*")))
                self.assertNotIn("template-demo-01", "\n".join(path.read_text(encoding="utf-8") for path in package.rglob("*.md")))

    def test_example_observations_and_score_match_actual_fixture_execution(self):
        candidate = runpy.run_path(str(Path(__file__).parent / "replay/original/candidate.py"))
        records = [{"id": "a", "amount": 100}, {"id": "b", "amount": 100}]
        self.assertEqual(candidate["cash_total"](records, {"a": ["b"], "b": ["a"]}), 0)
        self.assertEqual(candidate["cash_total"](records, {"a": ["b"]}), 100)
        self.assertEqual(candidate["cash_total"](records + [{"id": "c", "amount": 250}], {"a": ["b"], "b": ["a"]}), 250)
        score = score_review({"P0": 1, "P1": 0, "P2": 0, "P3": 0}, complete=True)
        report = (Path(__file__).parent / "examples/blind-01.md").read_text(encoding="utf-8")
        self.assertEqual(int(re.search(r"^\| Score \| (\d+) \|$", report, re.MULTILINE).group(1)), score["score"])
        self.assertEqual(score["result"], "FAIL")
        # These checks establish example integrity, not agent discovery quality.
        self.assertNotEqual(candidate["cash_total"](records, {"a": ["b"], "b": ["a"]}), 100)


if __name__ == "__main__":
    unittest.main()
