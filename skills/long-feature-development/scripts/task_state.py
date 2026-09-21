#!/usr/bin/env python3
"""Atomically update one TASKS.md row and its derived Mermaid topology."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

import task_context


TRANSITIONS = {
    ("PENDING", "WIP"),
    ("WIP", "BLOCKED"),
    ("BLOCKED", "WIP"),
    ("WIP", "RECORDING"),
    ("RECORDING", "WIP"),
    ("RECORDING", "DONE"),
    ("DONE", "WIP"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update one task state and regenerate the TASKS.md Mermaid block atomically."
    )
    parser.add_argument("feature_directory")
    parser.add_argument("task_id")
    parser.add_argument("--to", required=True, choices=sorted(task_context.ALLOWED_STATES))
    parser.add_argument("--owner")
    parser.add_argument("--started-at")
    parser.add_argument("--completed-at")
    parser.add_argument("--head", help="Semicolon-separated repository@SHA values")
    parser.add_argument("--reason", help="Required when reopening DONE to WIP")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def replace_task_row(text: str, task_id: str, values: list[str]) -> str:
    lines = text.splitlines(keepends=True)
    matches: list[int] = []
    for index, line in enumerate(lines):
        row = task_context.split_row(line)
        if row and task_context.clean_cell(row[0]) == task_id:
            matches.append(index)
    if len(matches) != 1:
        raise task_context.ContextError(
            f"TASKS.md must contain exactly one index row for {task_id}"
        )
    ending = "\r\n" if lines[matches[0]].endswith("\r\n") else "\n"
    lines[matches[0]] = "| " + " | ".join(values) + " |" + ending
    return "".join(lines)


def transition_text(text: str, args: argparse.Namespace) -> str:
    records = task_context.task_records(text)
    task_context.validate_dependency_graph(records)
    if args.task_id not in records:
        raise task_context.ContextError(f"unknown task: {args.task_id}")
    record = records[args.task_id]
    source = record["state"]
    target = args.to
    if (source, target) not in TRANSITIONS:
        raise task_context.ContextError(f"invalid task transition: {source} -> {target}")
    if source == "PENDING" and record["readiness"] != "READY":
        raise task_context.ContextError(
            f"task {args.task_id} is not READY; dependencies are unfinished"
        )
    if source == "DONE" and target == "WIP" and not args.reason:
        raise task_context.ContextError("DONE -> WIP requires --reason")

    owner = args.owner or record["owner"]
    started = args.started_at or record["started_at"]
    completed = args.completed_at or record["completed_at"]
    head = args.head or record["head_raw"]
    if source == "PENDING" and target == "WIP":
        if not args.owner or not args.started_at or not args.head:
            raise task_context.ContextError(
                "PENDING -> WIP requires --owner, --started-at, and --head"
            )
        completed = "-"
    elif target != "DONE":
        completed = "-"
    elif not args.completed_at:
        raise task_context.ContextError("RECORDING -> DONE requires --completed-at")

    values = [
        record["id"], record["type"], record["name"], f"`{target}`", owner,
        record["depends_raw"], started, completed, head,
    ]
    candidate = replace_task_row(text, args.task_id, values)
    return task_context.synchronized_topology(candidate)


def update(feature_directory: Path, args: argparse.Namespace) -> str:
    root = feature_directory.resolve()
    path = root / "TASKS.md"
    original = task_context.read_utf8(path)
    candidate = transition_text(original, args)
    records = task_context.task_records(candidate)
    task_context.validate_dependency_graph(records)
    task_context.validate_topology(candidate, records)
    details = task_context.validate_task_files(root, records)
    task_context.validate_type_contracts(records, details, root)
    if args.dry_run:
        return candidate
    handle, temp_name = tempfile.mkstemp(prefix="TASKS.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(candidate)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return candidate


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        update(Path(args.feature_directory), args)
    except (task_context.ContextError, OSError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
