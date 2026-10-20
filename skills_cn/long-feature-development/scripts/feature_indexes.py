#!/usr/bin/env python3
"""Generate Feature indexes from records/files; write only explicit marked regions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from urllib.parse import quote

sys.dont_write_bytecode = True

import contract_check as checker
from index_blocks import BlockError, replace_regions


def render_attachments(root):
    """List filesystem facts without reading attachment content or inventing metadata."""
    root = Path(root)
    directory = root / "gists"
    lines = ["| Attachment | Size (bytes) | Modified at (UTC) |",
             "| --- | --- | --- |"]
    if directory.is_symlink():
        raise BlockError("gists must not be a symlink to another attachment tree")
    if not directory.exists():
        return "\n".join(lines)
    if not directory.is_dir():
        raise BlockError("gists must be a directory")
    files = []
    def scan_error(error):
        raise error

    for parent, directories, names in os.walk(directory, followlinks=False, onerror=scan_error):
        directories[:] = sorted(name for name in directories
                                if not (Path(parent) / name).is_symlink())
        for name in names:
            path = Path(parent) / name
            if path.is_symlink() or not path.is_file():
                continue
            if not path.resolve().is_relative_to(directory.resolve()):
                raise BlockError("attachment escapes gists directory")
            files.append(path)
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        info = path.stat()
        modified = datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        label = checker.cell(relative).replace("[", "&#91;").replace("]", "&#93;")
        label = label.replace("<", "&lt;").replace(">", "&gt;").replace("`", "&#96;")
        lines.append(f"| [{label}]({quote(relative, safe='/')}) | {info.st_size} | {modified} |")
    return "\n".join(lines)


def plan_indexes(root, only="all"):
    """Prepare every target before writes; malformed final blocks cannot alter earlier files."""
    root = Path(root).resolve()
    if only not in ("all", "design", "tasks", "verbal"):
        raise BlockError("unknown index selection")
    groups = checker.collect(root) if only != "verbal" else None
    rendered = {}
    if only in ("all", "design"):
        rendered["DESIGN.md"] = {
            "design-preview-table": checker.render_index(groups["design"], "design")}
    if only in ("all", "tasks"):
        rendered["TASKS.md"] = {
            "tasks-preview-table": checker.render_index(groups["tasks"], "tasks"),
            "tasks-dependency-topology-mermaid": checker.render_topology(groups["tasks"])}
    if only == "verbal" or (only == "all" and (root / "VERBAL.md").exists()):
        rendered["VERBAL.md"] = {"verbal-preview-table": render_attachments(root)}
    plans = []
    for filename, regions in rendered.items():
        path = root / filename
        if path.is_symlink() or path.resolve().parent != root:
            raise BlockError(f"index target must be a direct non-symlink file: {filename}")
        original = path.read_bytes()
        content = original.decode("utf-8")
        updated = replace_regions(content, regions).encode("utf-8")
        plans.append((path, original, updated))
    return plans


def sync_indexes(root, only="all", write=False):
    plans = plan_indexes(root, only)
    changed = [path.name for path, original, updated in plans if original != updated]
    if write:
        # Per-file atomic replacement, not a cross-file transaction.
        for path, original, updated in plans:
            if path.read_bytes() != original:
                raise BlockError(f"concurrent index edit detected: {path.name}")
        for path, original, updated in plans:
            if original == updated:
                continue
            mode = stat.S_IMODE(path.stat().st_mode)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(prefix="." + path.name + ".",
                                                 suffix=".tmp", dir=path.parent,
                                                 delete=False) as output:
                    temporary = Path(output.name)
                    output.write(updated)
                os.chmod(temporary, mode)
                if path.read_bytes() != original:
                    raise BlockError(f"concurrent index edit detected: {path.name}")
                os.replace(temporary, path)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    return {"valid": write or not changed, "scope": "derived-indexes-only",
            "mode": "write" if write else "check", "changed": changed,
            "checked": [path.name for path, _, _ in plans]}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature", type=Path)
    parser.add_argument("--only", choices=("all", "design", "tasks", "verbal"), default="all")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Replace marked generated content only")
    mode.add_argument("--check", action="store_true", help="Check without writing (default)")
    args = parser.parse_args(argv)
    try:
        result = sync_indexes(args.feature, args.only, args.write)
    except (checker.ContractError, BlockError, OSError, ValueError, UnicodeError) as exc:
        result = {"valid": False, "scope": "derived-indexes-only", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
