#!/usr/bin/env python3
"""Create one validated PENDING task and update TASKS.md atomically per file."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

import task_context


TYPE_PREFIX = {
    "Requirement": "REQ",
    "Solution": "SOL",
    "Development": "DEV",
    "Documentation": "DEV",
    "Test": "TEST",
    "Review": "REVIEW",
    "Rework": "REWORK",
    "Acceptance": "ACCEPT",
    "Gate": "GATE",
    "Correction": "CORR",
}
QUALITY_DEFAULTS = {
    "TEST": {
        "Target SHA": "-", "Environment": "-", "Planned checks": "-",
        "Executed": "-", "Passed": "-", "Failed": "-", "Skipped": "-",
        "Unknown": "-", "Result gist": "none",
    },
    "REVIEW": {
        "Target SHA": "-", "Blocking findings": "-", "Deferred findings": "-",
        "Result gist": "none",
    },
    "REWORK": {
        "Source findings": "-", "Target SHA": "-", "Output SHA": "-",
        "Result gist": "none",
    },
    "ACCEPT": {
        "Target SHA": "-", "Acceptance scope": "-", "Decision": "WAITING",
        "Decided by": "-", "Acceptance brief": "-",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Allocate an internal task ID and create its validated records."
    )
    parser.add_argument("feature_directory")
    parser.add_argument("--type", required=True, choices=tuple(TYPE_PREFIX))
    parser.add_argument("--name", required=True)
    parser.add_argument("--depends-on", default="-")
    parser.add_argument("--requirement-points", default="none")
    parser.add_argument("--solution-points", default="none")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--inputs")
    parser.add_argument("--work", required=True)
    parser.add_argument("--completion-condition", required=True)
    parser.add_argument("--resume-action", required=True)
    parser.add_argument(
        "--repo-ref",
        action="append",
        required=True,
        metavar="REPOSITORY|BRANCH|BASELINE_HISTORY",
    )
    parser.add_argument("--contract", action="append", default=[], metavar="FIELD=VALUE")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def safe_cell(value: str, label: str) -> str:
    value = value.strip()
    if not value or "\n" in value or "\r" in value or "|" in value:
        raise task_context.ContextError(f"{label} must be one non-empty Markdown-safe line")
    return value


def parse_id_list(raw: str, label: str) -> list[str]:
    raw = raw.strip()
    if raw in {"-", "none", "None", "无", "无。"}:
        return []
    values = [value.strip().strip("`") for value in raw.split(",")]
    if not values or any(task_context.TASK_ID_RE.fullmatch(value) is None for value in values):
        raise task_context.ContextError(f"{label} must be a comma-separated ID list")
    if len(set(values)) != len(values):
        raise task_context.ContextError(f"{label} contains a duplicate ID")
    return values


def allocate_task_id(records: dict[str, dict[str, object]], prefix: str) -> str:
    numbers: list[tuple[int, int]] = []
    pattern = re.compile(rf"{re.escape(prefix)}-(\d+)\Z")
    for task_id in records:
        match = pattern.fullmatch(task_id)
        if match:
            numbers.append((int(match.group(1)), len(match.group(1))))
    default_width = 3 if prefix in {"REQ", "SOL"} else 2
    width = max([default_width, *(item[1] for item in numbers)])
    number = max([0, *(item[0] for item in numbers)]) + 1
    return f"{prefix}-{number:0{width}d}"


def parse_repo_refs(values: list[str], registry: dict[str, dict[str, str]]) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for raw in values:
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) != 3:
            raise task_context.ContextError(
                "--repo-ref must be REPOSITORY|BRANCH|BASELINE_HISTORY"
            )
        repository, branch, baseline = parts
        if repository not in registry:
            raise task_context.ContextError(f"unknown repository in --repo-ref: {repository}")
        if repository in seen:
            raise task_context.ContextError(f"duplicate --repo-ref repository: {repository}")
        seen.add(repository)
        safe_cell(branch, "repository branch")
        task_context.validate_ref_list(baseline, "<=", "repository baseline history")
        result.append((repository, branch, baseline))
    return result


def parse_contract(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise task_context.ContextError("--contract must be FIELD=VALUE")
        field, value = (item.strip() for item in raw.split("=", 1))
        safe_cell(field, "contract field")
        safe_cell(value, "contract value")
        if field in result:
            raise task_context.ContextError(f"duplicate contract field: {field}")
        result[field] = value
    return result


def contract_for(prefix: str, dependencies: list[str], overrides: dict[str, str]) -> dict[str, str]:
    if prefix == "GATE":
        fields = {
            "From phase": "EXECUTING", "To phase": "DONE",
            "Required tasks": ", ".join(dependencies) if dependencies else "-",
            "Decision ref": "-",
        }
    else:
        fields = dict(QUALITY_DEFAULTS.get(prefix, {}))
    unknown = set(overrides) - set(fields)
    if unknown:
        raise task_context.ContextError(
            "unknown contract fields for task type: " + ", ".join(sorted(unknown))
        )
    fields.update(overrides)
    return fields


def render_detail(
    task_id: str,
    args: argparse.Namespace,
    dependencies: list[str],
    requirement_points: list[str],
    solution_points: list[str],
    repo_refs: list[tuple[str, str, str]],
    contract: dict[str, str],
) -> str:
    gist_values = []
    for field in ("Result gist", "Acceptance brief"):
        value = contract.get(field)
        if value and value not in {"-", "none"} and value not in gist_values:
            gist_values.append(value)
    gists = ", ".join(gist_values) if gist_values else "none"
    inputs = args.inputs or (", ".join(dependencies) if dependencies else "feature intent")
    lines = [
        f"# {task_id} — {safe_cell(args.name, 'task name')}", "",
        f"- Goal: {safe_cell(args.goal, 'goal')}",
        f"- Inputs: {safe_cell(inputs, 'inputs')}",
        "- Requirement points: " + (", ".join(requirement_points) if requirement_points else "none"),
        "- Solution points: " + (", ".join(solution_points) if solution_points else "none"),
        f"- Work: {safe_cell(args.work, 'work')}",
        f"- Completion condition: {safe_cell(args.completion_condition, 'completion condition')}",
        f"- Resume action: {safe_cell(args.resume_action, 'resume action')}",
        "- Blocker: none", "- Impact: none", "- Release condition: none",
        "- Reopen reason: none", "- Disposition: required", f"- Gists: {gists}", "",
        "## Repository refs", "",
        "| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |",
        "| --- | --- | --- | --- | --- | --- |",
        *(f"| {repo} | {branch} | {baseline} | - | - | - |" for repo, branch, baseline in repo_refs),
        "", "## Attempt notes", "", "- PENDING; created by the Agent-owned task planner.",
    ]
    if contract:
        lines.extend(("", "## Type contract", "", "| Field | Value |", "| --- | --- |"))
        lines.extend(f"| {field} | {value} |" for field, value in contract.items())
    return "\n".join(lines).rstrip() + "\n"


def insert_task_row(text: str, values: list[str]) -> str:
    lines = text.splitlines(keepends=True)
    header_index = -1
    for index, line in enumerate(lines):
        if tuple(task_context.clean_cell(cell) for cell in task_context.split_row(line)) in task_context.TASK_TABLE_HEADERS:
            header_index = index
            break
    if header_index < 0:
        raise task_context.ContextError("TASKS.md is missing the task index")
    insert_at = header_index + 2
    while insert_at < len(lines) and task_context.split_row(lines[insert_at]):
        insert_at += 1
    ending = "\r\n" if lines[header_index].endswith("\r\n") else "\n"
    lines.insert(insert_at, "| " + " | ".join(values) + " |" + ending)
    return "".join(lines)


def atomic_write(path: Path, text: str) -> None:
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def create(feature_directory: Path, args: argparse.Namespace) -> str:
    root = feature_directory.resolve()
    tasks_path = root / "TASKS.md"
    original = task_context.read_utf8(tasks_path)
    records = task_context.task_records(original)
    dependencies = parse_id_list(args.depends_on, "dependencies")
    missing = sorted(set(dependencies) - set(records))
    if missing:
        raise task_context.ContextError("unknown dependencies: " + ", ".join(missing))
    requirement_points = parse_id_list(args.requirement_points, "requirement points")
    solution_points = parse_id_list(args.solution_points, "solution points")
    requirement_text = task_context.read_utf8(root / "REQUIREMENT.md")
    solution_text = task_context.read_utf8(root / "SOLUTION.md")
    task_context.focused_document(requirement_text, "REQ", "CONFIRMED", requirement_points)
    task_context.focused_document(solution_text, "SOL", "BASELINED", solution_points)
    status_text = task_context.read_utf8(root / "STATUS.md")
    repo_refs = parse_repo_refs(args.repo_ref, task_context.repository_registry(status_text))
    prefix = TYPE_PREFIX[args.type]
    task_id = allocate_task_id(records, prefix)
    contract = contract_for(prefix, dependencies, parse_contract(args.contract))
    detail = render_detail(
        task_id, args, dependencies, requirement_points, solution_points, repo_refs, contract
    )
    row = [
        task_id, args.type, safe_cell(args.name, "task name"), "`PENDING`", "-",
        ", ".join(dependencies) if dependencies else "-", "-", "-", "-",
    ]
    candidate = task_context.synchronized_topology(insert_task_row(original, row))
    candidate_records = task_context.task_records(candidate)
    task_context.validate_dependency_graph(candidate_records)
    task_context.validate_topology(candidate, candidate_records)
    task_context.validate_type_contract(candidate_records[task_id], detail, candidate_records)
    if args.dry_run:
        print(detail, end="")
        return task_id
    detail_path = root / "tasks" / f"{task_id}.md"
    if detail_path.exists():
        raise task_context.ContextError(f"task detail already exists: tasks/{task_id}.md")
    try:
        atomic_write(detail_path, detail)
        atomic_write(tasks_path, candidate)
    except BaseException:
        if detail_path.exists():
            detail_path.unlink()
        atomic_write(tasks_path, original)
        raise
    return task_id


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        task_id = create(Path(args.feature_directory), args)
    except (task_context.ContextError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(task_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
