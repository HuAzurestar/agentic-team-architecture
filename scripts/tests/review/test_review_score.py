#!/usr/bin/env python3
"""Exercise agreed score boundaries, completeness and rejected inputs."""

import contextlib
import io
import json
import unittest

from review_score import main, score_review


class ReviewScoreTests(unittest.TestCase):
    def test_agreed_boundaries(self):
        cases = [
            ((0, 0, 0, 0), 100, "PASS"), ((1, 0, 0, 0), 0, "FAIL"),
            ((0, 1, 0, 0), 90, "PASS"), ((0, 4, 0, 0), 60, "PASS"),
            ((0, 5, 0, 0), 50, "FAIL"), ((0, 0, 20, 0), 60, "PASS"),
            ((0, 0, 21, 0), 58, "FAIL"), ((0, 0, 0, 40), 60, "PASS"),
            ((0, 3, 4, 2), 60, "PASS"), ((4, 100, 100, 100), 0, "FAIL"),
        ]
        for values, expected, result in cases:
            with self.subTest(values=values):
                actual = score_review(dict(zip(("P0", "P1", "P2", "P3"), values)), complete=True)
                self.assertEqual((actual["score"], actual["result"]), (expected, result))

    def test_incomplete_never_scores_even_with_zero_discoveries(self):
        for p0 in (0, 1):
            actual = score_review({"P0": p0, "P1": 0, "P2": 0, "P3": 0}, complete=False)
            self.assertIsNone(actual["score"])
            self.assertEqual(actual["result"], "INCOMPLETE")
            self.assertEqual(actual["counts"]["P0"], p0)

    def test_rejects_invalid_counts(self):
        valid = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        for counts in (None, {}, {**valid, "P4": 0}, {**valid, "P0": -1}, {**valid, "P1": True}, {**valid, "P2": 1.5}, {**valid, "P3": "1"}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                score_review(counts, complete=True)
        with self.assertRaises(ValueError):
            score_review(valid, complete=1)

    def test_cli_requires_completeness_and_signals_bad_input(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as missing:
            main(["--p1", "1"])
        self.assertEqual(missing.exception.code, 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--complete", "--p2", "-1"]), 2)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--complete", "--p1", "3", "--p2", "4", "--p3", "2"]), 0)
        self.assertEqual(json.loads(output.getvalue())["score"], 60)


if __name__ == "__main__":
    unittest.main()
