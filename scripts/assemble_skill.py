#!/usr/bin/env python3
"""Combine one locale's content and its same-named shared runtime, without tests."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


LOCALES = {"en": "skills", "cn": "skills_cn"}
EXCLUDED = {"tests", "__pycache__", ".pytest_cache", ".git"}


def excluded(path: Path) -> bool:
    return any(part in EXCLUDED for part in path.parts) or path.name.startswith("test_") or path.suffix in {".pyc", ".pyo"}


def copy_ignore(directory: str, names: list[str]) -> list[str]:
    return [name for name in names if excluded(Path(name))]


def assemble_skill(repository: Path, name: str, locale: str, output: Path) -> Path:
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) is None or locale not in LOCALES:
        raise ValueError("expected a skill folder name and locale en/cn")
    repository = repository.resolve()
    content = repository / LOCALES[locale] / name
    shared = repository / "scripts" / name
    target = output.resolve() / name
    if not (content / "SKILL.md").is_file():
        raise ValueError("selected locale's SKILL.md is missing")
    if shared.exists() and not (shared / "scripts").is_dir():
        raise ValueError("shared payload must use scripts/<skill>/scripts; legacy applications are not assembled")
    if target.exists() or target.is_symlink():
        raise FileExistsError("destination already exists; choose a fresh output directory")
    if any(target.is_relative_to(repository / folder) for folder in (*LOCALES.values(), "scripts")):
        raise ValueError("output must not be inside source content, runtimes or tests")

    # Validate before writing, including file/directory collisions and external links.
    for tree in (content, shared):
        if not tree.exists():
            continue
        for path in (tree, *tree.rglob("*")):
            relative = path.relative_to(tree)
            if excluded(relative):
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(tree.resolve()):
                raise ValueError("package sources must not contain links outside their tree")
            if tree == shared and relative != Path("."):
                existing = content / relative
                if existing.exists() and not (path.is_dir() and existing.is_dir()):
                    raise ValueError(f"content/runtime collision: {relative.as_posix()}")
                if any((content / parent).is_file() for parent in relative.parents):
                    raise ValueError(f"content/runtime parent collision: {relative.as_posix()}")
    shutil.copytree(content, target, ignore=copy_ignore)
    if shared.exists():
        shutil.copytree(shared, target, dirs_exist_ok=True, ignore=copy_ignore)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--locale", choices=tuple(LOCALES), default="en")
    parser.add_argument("--output", type=Path, required=True, help="Fresh package parent; no existing skill is overwritten")
    args = parser.parse_args(argv)
    try:
        print(assemble_skill(Path(__file__).resolve().parents[1], args.skill, args.locale, args.output))
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
