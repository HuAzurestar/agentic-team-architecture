#!/usr/bin/env python3
"""Calculate review/v1 scores from counts; never read a review ledger."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


WEIGHTS = {"P0": 100, "P1": 10, "P2": 2, "P3": 1}


def score_review(counts: dict[str, int], *, complete: bool) -> dict[str, Any]:
    if not isinstance(counts, dict) or set(counts) != set(WEIGHTS):
        raise ValueError("counts must contain exactly P0, P1, P2 and P3")
    if type(complete) is not bool:
        raise ValueError("complete must be a boolean")
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("counts must be nonnegative integers, not booleans")
    score = max(0, 100 - sum(WEIGHTS[key] * counts[key] for key in WEIGHTS)) if complete else None
    result = "INCOMPLETE" if not complete else "PASS" if counts["P0"] == 0 and score >= 60 else "FAIL"
    return {"protocol": "review/v1", "counts": dict(counts), "complete": complete, "score": score, "result": result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    completeness = parser.add_mutually_exclusive_group(required=True)
    completeness.add_argument("--complete", action="store_true")
    completeness.add_argument("--incomplete", action="store_true")
    for priority in WEIGHTS:
        parser.add_argument("--" + priority.lower(), type=int, default=0)
    args = parser.parse_args(argv)
    try:
        result = score_review({priority: getattr(args, priority.lower()) for priority in WEIGHTS}, complete=args.complete)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
