#!/usr/bin/env python3
"""Run shared suites in isolated processes, keeping tests out of installed skills."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent
    scripts = root.parent
    suites = sorted(path.name for path in root.iterdir() if path.is_dir() and any(path.glob("test_*.py")))
    parser = argparse.ArgumentParser(description=__doc__)
    if not suites:
        parser.error("no shared test suites found")
    parser.add_argument("--skill", choices=suites, help="Omit to run all shared suites")
    args = parser.parse_args(argv)
    failed = False
    for name in ([args.skill] if args.skill else suites):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join([
            str(scripts / name / "scripts"), str(scripts), str(root / name),
            environment.get("PYTHONPATH", ""),
        ])
        print(f"Suite: {name}", flush=True)
        result = subprocess.run([
            sys.executable, "-B", "-X", "utf8", "-m", "unittest", "discover",
            "-s", str(root / name), "-p", "test_*.py",
        ], cwd=scripts.parent, env=environment, check=False)
        failed |= result.returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
