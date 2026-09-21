#!/usr/bin/env python3
"""Validate and extract one task for long-feature-development."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ALLOWED_STATES = {"PENDING", "WIP", "BLOCKED", "RECORDING", "DONE"}
TASK_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}\Z")
TABLE_SEPARATOR_RE = re.compile(r":?-{3,}:?\Z")
ACTIVE_POINT_STATES = {"PROPOSED", "REOPENED", "CONFIRMED"}
DISPOSITION_POINT_STATES = {"REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"}
DECIDED_POINT_STATES = {"CONFIRMED", *DISPOSITION_POINT_STATES}
TASK_TABLE_HEADERS = (
    ("ID", "Type", "Name", "State", "Owner", "Depends on", "Started at", "Completed at", "HEAD SHA"),
    ("ID", "类型", "名称", "状态", "负责人", "依赖", "开始时间", "完成时间", "HEAD SHA"),
)
REPO_TABLE_HEADERS = (
    ("Repository", "Branch", "Baseline history", "Start refs", "HEAD SHA", "Completion SHA"),
    ("仓库", "分支", "基线历史", "开始 refs", "HEAD SHA", "完成 SHA"),
)
TOPOLOGY_RE = re.compile(
    r"<!-- task-topology:start -->\s*(.*?)\s*<!-- task-topology:end -->",
    re.DOTALL,
)
STATE_STYLE = {
    "PENDING": "pending",
    "WIP": "wip",
    "BLOCKED": "blocked",
    "RECORDING": "recording",
    "DONE": "done",
}


class ContextError(ValueError):
    """Raised when persisted task context is ambiguous or incomplete."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a feature and print one task with its declared gists."
    )
    parser.add_argument(
        "feature_directory",
        help="Directory containing REQUIREMENT.md, SOLUTION.md, STATUS.md, TASKS.md, and tasks/",
    )
    parser.add_argument("--task", help="Explicit task ID; defaults to STATUS.md Current task")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument(
        "--sync-topology",
        action="store_true",
        help="Rewrite only the generated Mermaid block in TASKS.md before validation",
    )
    return parser.parse_args(argv)


def read_utf8(path: Path) -> str:
    if not path.is_file():
        raise ContextError(f"required file is missing: {path.relative_to(path.parent.parent) if path.parent.name == 'tasks' else path.name}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ContextError(f"{path.name} is not valid UTF-8: {exc}") from exc


def split_row(line: str) -> list[str]:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return []
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def clean_cell(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1].strip()
    return value


def markdown_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = text.splitlines()
    tables: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index + 1 < len(lines):
        header = split_row(lines[index])
        separator = split_row(lines[index + 1])
        if header and len(separator) == len(header) and all(
            TABLE_SEPARATOR_RE.fullmatch(cell) for cell in separator
        ):
            rows: list[list[str]] = []
            index += 2
            while index < len(lines):
                row = split_row(lines[index])
                if not row:
                    break
                if len(row) != len(header):
                    raise ContextError("Markdown table contains a row with the wrong column count")
                rows.append([clean_cell(cell) for cell in row])
                index += 1
            tables.append(([clean_cell(cell) for cell in header], rows))
            continue
        index += 1
    return tables


def unique_table(
    tables: list[tuple[list[str], list[list[str]]]],
    accepted_headers: tuple[tuple[str, ...], ...],
    table_name: str,
) -> list[list[str]]:
    matches = [rows for header, rows in tables if tuple(header) in accepted_headers]
    if len(matches) != 1:
        accepted = " or ".join(" | ".join(header) for header in accepted_headers)
        raise ContextError(f"expected exactly one {table_name} table with header: {accepted}")
    return matches[0]


def selected_task_id(status_text: str, requested: str | None) -> str:
    if requested is not None:
        task_id = requested.strip()
    else:
        summary_rows = unique_table(
            markdown_tables(status_text),
            (("Item", "Current value", "Note"), ("项目", "当前值", "备注")),
            "status-summary",
        )
        values = [row[1] for row in summary_rows if row[0] in {"Current task", "当前任务"}]
        if len(values) != 1:
            raise ContextError("STATUS.md must contain exactly one Current task row")
        task_id = values[0]
    if TASK_ID_RE.fullmatch(task_id) is None:
        raise ContextError(f"invalid task ID: {task_id!r}")
    return task_id


def parse_dependencies(raw: str, task_id: str) -> list[str]:
    if raw == "-":
        return []
    values = [value.strip().strip("`") for value in raw.split(",")]
    if not values or any(TASK_ID_RE.fullmatch(value) is None for value in values):
        raise ContextError(f"task {task_id} has invalid dependency list: {raw!r}")
    if len(set(values)) != len(values):
        raise ContextError(f"task {task_id} declares a dependency more than once")
    if task_id in values:
        raise ContextError(f"task {task_id} cannot depend on itself")
    return values


def parse_head_refs(raw: str, task_id: str) -> dict[str, str]:
    if raw == "-":
        return {}
    result: dict[str, str] = {}
    for token in (value.strip().strip("`") for value in raw.split(";")):
        if "@" not in token:
            raise ContextError(f"task {task_id} has invalid HEAD ref: {token!r}")
        repository, sha = token.rsplit("@", 1)
        if not repository or SHA_RE.fullmatch(sha) is None:
            raise ContextError(f"task {task_id} has invalid HEAD ref: {token!r}")
        if repository in result:
            raise ContextError(f"task {task_id} has duplicate HEAD repository: {repository}")
        result[repository] = sha.lower()
    return result


def task_records(tasks_text: str) -> dict[str, dict[str, Any]]:
    rows = unique_table(markdown_tables(tasks_text), TASK_TABLE_HEADERS, "task-index")
    records: dict[str, dict[str, Any]] = {}
    keys = ("id", "type", "name", "state", "owner", "depends_raw", "started_at", "completed_at", "head_raw")
    for row in rows:
        task_id = row[0]
        if TASK_ID_RE.fullmatch(task_id) is None:
            raise ContextError(f"invalid task ID in TASKS.md: {task_id!r}")
        if task_id in records:
            raise ContextError(f"TASKS.md must contain exactly one index row for {task_id}")
        record: dict[str, Any] = dict(zip(keys, row))
        if record["state"] not in ALLOWED_STATES:
            raise ContextError(f"task {task_id} has invalid state: {record['state']!r}")
        record["dependencies"] = parse_dependencies(record["depends_raw"], task_id)
        record["head_refs"] = parse_head_refs(record["head_raw"], task_id)
        state = record["state"]
        if state == "PENDING":
            if record["started_at"] != "-" or record["completed_at"] != "-" or record["head_refs"]:
                raise ContextError(f"PENDING task {task_id} cannot have start/completion time or HEAD SHA")
        else:
            if record["owner"] == "-" or record["started_at"] == "-":
                raise ContextError(f"{state} task {task_id} requires owner and start time")
            if not record["head_refs"]:
                raise ContextError(f"{state} task {task_id} requires HEAD SHA")
            if state == "DONE" and record["completed_at"] == "-":
                raise ContextError(f"DONE task {task_id} requires completion time")
            if state != "DONE" and record["completed_at"] != "-":
                raise ContextError(f"{state} task {task_id} cannot have completion time")
        records[task_id] = record
    if not records:
        raise ContextError("TASKS.md task index is empty")
    return records


def validate_dependency_graph(records: dict[str, dict[str, Any]]) -> None:
    for task_id, record in records.items():
        missing = [dep for dep in record["dependencies"] if dep not in records]
        if missing:
            raise ContextError(f"task {task_id} has unknown dependencies: {', '.join(missing)}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, trail: list[str]) -> None:
        if task_id in visiting:
            start = trail.index(task_id)
            raise ContextError("task dependency cycle: " + " -> ".join(trail[start:] + [task_id]))
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in records[task_id]["dependencies"]:
            visit(dependency, trail + [dependency])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in records:
        visit(task_id, [task_id])

    for task_id, record in records.items():
        if record["state"] != "PENDING":
            unfinished = [dep for dep in record["dependencies"] if records[dep]["state"] != "DONE"]
            if unfinished:
                raise ContextError(f"active task {task_id} has unfinished dependencies: {', '.join(unfinished)}")


def mermaid_topology(records: dict[str, dict[str, Any]]) -> str:
    ids = {task_id: f"T{index}" for index, task_id in enumerate(records)}
    lines = ["```mermaid", "flowchart LR"]
    for task_id, record in records.items():
        label = f"{task_id} · {record['name']}".replace('"', "'")
        lines.append(f'    {ids[task_id]}["{label}"]:::{STATE_STYLE[record["state"]]}')
    for task_id, record in records.items():
        for dependency in record["dependencies"]:
            lines.append(f"    {ids[dependency]} --> {ids[task_id]}")
    lines.extend(
        (
            "    classDef pending fill:#e5e7eb,stroke:#6b7280,color:#111827",
            "    classDef wip fill:#dbeafe,stroke:#2563eb,color:#111827",
            "    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#111827",
            "    classDef recording fill:#fef3c7,stroke:#d97706,color:#111827",
            "    classDef done fill:#dcfce7,stroke:#16a34a,color:#111827",
            "```",
        )
    )
    return "\n".join(lines)


def validate_topology(tasks_text: str, records: dict[str, dict[str, Any]]) -> None:
    matches = list(TOPOLOGY_RE.finditer(tasks_text))
    if len(matches) != 1:
        raise ContextError("TASKS.md must contain exactly one generated task-topology block")
    if matches[0].group(1).strip() != mermaid_topology(records):
        raise ContextError("TASKS.md topology is stale; run task_context.py <feature-directory> --sync-topology")


def sync_topology(path: Path) -> None:
    text = read_utf8(path)
    records = task_records(text)
    validate_dependency_graph(records)
    matches = list(TOPOLOGY_RE.finditer(text))
    if len(matches) != 1:
        raise ContextError("TASKS.md must contain exactly one generated task-topology block")
    replacement = "<!-- task-topology:start -->\n" + mermaid_topology(records) + "\n<!-- task-topology:end -->"
    updated = text[: matches[0].start()] + replacement + text[matches[0].end() :]
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def validate_literal_sha(value: str, location: str) -> str:
    if SHA_RE.fullmatch(value) is None:
        raise ContextError(f"{location} must be one literal 7-64 character hexadecimal SHA")
    return value.lower()


def validate_ref_list(raw: str, separator: str, location: str) -> None:
    if raw == "-":
        return
    tokens = [token.strip().strip("`") for token in raw.split(separator)]
    if any("@" not in token for token in tokens):
        raise ContextError(f"{location} must contain branch@SHA refs separated by {separator!r}")
    for token in tokens:
        branch, sha = token.rsplit("@", 1)
        if not branch or SHA_RE.fullmatch(sha) is None:
            raise ContextError(f"{location} has invalid ref: {token!r}")


def task_detail(root: Path, record: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    task_id = record["id"]
    path = root / "tasks" / f"{task_id}.md"
    text = read_utf8(path)
    title = re.findall(r"^#[ \t]+`?([^` \t]+)`?[ \t]+(?:—|–|-)[ \t]+(.+?)[ \t]*$", text, re.MULTILINE)
    if len(title) != 1 or title[0][0] != task_id:
        raise ContextError(f"tasks/{task_id}.md must have exactly one matching level-one task heading")
    rows = unique_table(markdown_tables(text), REPO_TABLE_HEADERS, f"{task_id} repository-refs")
    refs: list[dict[str, str]] = []
    repositories: set[str] = set()
    keys = ("repository", "branch", "baseline_history", "start_refs", "head_sha", "completion_sha")
    for row in rows:
        item = dict(zip(keys, row))
        repository = item["repository"]
        if not repository or repository == "-" or repository in repositories:
            raise ContextError(f"task {task_id} has invalid or duplicate repository: {repository!r}")
        repositories.add(repository)
        validate_ref_list(item["baseline_history"], "<=", f"task {task_id} baseline history")
        validate_ref_list(item["start_refs"], ";", f"task {task_id} start refs")
        state = record["state"]
        if state == "PENDING":
            if item["start_refs"] != "-" or item["head_sha"] != "-" or item["completion_sha"] != "-":
                raise ContextError(f"PENDING task {task_id} repository refs cannot contain start, HEAD, or completion SHA")
        else:
            if item["start_refs"] == "-":
                raise ContextError(f"{state} task {task_id} requires start refs for {repository}")
            head = validate_literal_sha(item["head_sha"], f"task {task_id} HEAD SHA for {repository}")
            if record["head_refs"].get(repository) != head:
                raise ContextError(f"task {task_id} HEAD SHA differs between TASKS.md and tasks/{task_id}.md for {repository}")
            if state == "DONE":
                validate_literal_sha(item["completion_sha"], f"task {task_id} completion SHA for {repository}")
            elif item["completion_sha"] != "-":
                raise ContextError(f"{state} task {task_id} cannot have completion SHA for {repository}")
        refs.append(item)
    if set(record["head_refs"]) != repositories and record["state"] != "PENDING":
        raise ContextError(f"task {task_id} repository set differs between TASKS.md and its detail")
    return text, refs


def validate_task_files(root: Path, records: dict[str, dict[str, Any]]) -> dict[str, tuple[str, list[dict[str, str]]]]:
    task_root = root / "tasks"
    if not task_root.is_dir():
        raise ContextError("required directory is missing: tasks")
    indexed = {f"{task_id}.md" for task_id in records}
    actual = {path.name for path in task_root.glob("*.md")}
    missing = sorted(indexed - actual)
    extra = sorted(actual - indexed)
    if missing:
        raise ContextError("tasks/ is missing detail files: " + ", ".join(missing))
    if extra:
        raise ContextError("tasks/ has detail files absent from TASKS.md: " + ", ".join(extra))
    return {task_id: task_detail(root, record) for task_id, record in records.items()}


def h2_section(text: str, headings: tuple[str, ...]) -> str:
    patterns = [re.compile(rf"^##[ \t]+{re.escape(heading)}[ \t]*$", re.MULTILINE) for heading in headings]
    matches = [match for pattern in patterns for match in pattern.finditer(text)]
    if len(matches) != 1:
        raise ContextError(f"expected exactly one section named: {' or '.join(headings)}")
    next_heading = re.search(r"^##[ \t]+", text[matches[0].end() :], re.MULTILINE)
    end = matches[0].end() + next_heading.start() if next_heading else len(text)
    return text[matches[0].start() : end]


def metadata_value(section: str, keys: set[str], location: str) -> str:
    rows = unique_table(markdown_tables(section), (("Item", "Value"), ("项目", "值")), f"{location} metadata")
    values = [row[1] for row in rows if row[0] in keys]
    if len(values) != 1:
        raise ContextError(f"{location} must contain exactly one of: {', '.join(sorted(keys))}")
    return values[0]


def point_sections(document_text: str, prefix: str) -> dict[str, str]:
    heading = re.compile(
        rf"^###[ \t]+`?({prefix}-[A-Za-z0-9][A-Za-z0-9._-]*)`?(?:[ \t]+(?:—|–|-)[ \t]+.*)?[ \t]*$",
        re.MULTILINE,
    )
    matches = list(heading.finditer(document_text))
    sections: dict[str, str] = {}
    for match in matches:
        point_id = match.group(1)
        if point_id in sections:
            raise ContextError(f"duplicate decision point in document: {point_id}")
        next_heading = re.search(r"^#{2,3}[ \t]+", document_text[match.end() :], re.MULTILINE)
        end = match.end() + next_heading.start() if next_heading else len(document_text)
        sections[point_id] = document_text[match.start() : end]
    return sections


def validate_decision_document(document_text: str, prefix: str, final_status: str) -> dict[str, str]:
    sections = point_sections(document_text, prefix)
    if not sections:
        return {}
    derived_section = h2_section(document_text, ("Derived document state", "派生文档状态"))
    document_status = metadata_value(derived_section, {"Status", "状态"}, f"{prefix} document")
    states: dict[str, str] = {}
    active_states: list[str] = []
    for point_id, section in sections.items():
        point_class = metadata_value(section, {"Class", "类别"}, point_id)
        point_state = metadata_value(section, {"State", "状态"}, point_id)
        if point_class == "ACTIVE":
            if point_state not in ACTIVE_POINT_STATES:
                raise ContextError(f"active point {point_id} has invalid state: {point_state!r}")
            active_states.append(point_state)
        elif point_class == "DISPOSITION":
            if point_state not in DISPOSITION_POINT_STATES:
                raise ContextError(f"disposition point {point_id} has invalid state: {point_state!r}")
        else:
            raise ContextError(f"point {point_id} has invalid class: {point_class!r}")
        states[point_id] = point_state
    expected = final_status if active_states and all(state == "CONFIRMED" for state in active_states) else "DRAFT"
    if document_status != expected:
        raise ContextError(f"{prefix} document status must be {expected}, got {document_status}")
    return states


def validate_decision_mapping(records: dict[str, dict[str, Any]], requirement_text: str, solution_text: str) -> None:
    requirement_states = validate_decision_document(requirement_text, "REQ", "CONFIRMED")
    solution_states = validate_decision_document(solution_text, "SOL", "BASELINED")
    for prefix, states in (("REQ", requirement_states), ("SOL", solution_states)):
        task_ids = {task_id for task_id in records if task_id.startswith(prefix + "-")}
        point_ids = set(states)
        missing_tasks = sorted(point_ids - task_ids)
        missing_points = sorted(task_ids - point_ids)
        if missing_tasks:
            raise ContextError(f"{prefix} decision points are missing TASKS tasks: {', '.join(missing_tasks)}")
        if missing_points:
            raise ContextError(f"{prefix} TASKS tasks are missing document points: {', '.join(missing_points)}")
        for point_id, point_state in states.items():
            if records[point_id]["state"] == "DONE" and point_state not in DECIDED_POINT_STATES:
                raise ContextError(f"DONE task {point_id} requires a decided point state, got {point_state}")
    for point_id, section in point_sections(solution_text, "SOL").items():
        if solution_states[point_id] != "CONFIRMED":
            continue
        raw_refs = metadata_value(section, {"Requirement points", "需求点"}, point_id)
        refs = [value.strip().strip("`") for value in raw_refs.split(",")]
        invalid = sorted(ref for ref in refs if requirement_states.get(ref) != "CONFIRMED")
        if not refs or any(not value for value in refs):
            raise ContextError(f"confirmed solution point {point_id} has no requirement refs")
        if invalid:
            raise ContextError(f"confirmed solution point {point_id} references unconfirmed requirements: " + ", ".join(invalid))


def declared_gists(detail: str, feature_root: Path) -> list[dict[str, str]]:
    declarations = re.findall(r"^- Gists[:：][ \t]*(.+?)[ \t]*$", detail, re.MULTILINE)
    if len(declarations) != 1:
        raise ContextError("task detail must contain exactly one '- Gists:' declaration")
    raw = declarations[0].strip()
    if raw.lower() == "none" or raw in {"无", "无。"}:
        return []
    values = [value.strip().strip("`") for value in raw.split(",")]
    if not values or any(not value for value in values):
        raise ContextError("Gists must be 'none' or a comma-separated path list")
    gist_root = (feature_root / "gists").resolve()
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        if "\\" in value:
            raise ContextError(f"gist path must use forward slashes: {value}")
        relative = PurePosixPath(value)
        if relative.is_absolute() or len(relative.parts) < 2 or relative.parts[0] != "gists":
            raise ContextError(f"gist path must be feature-relative under gists/: {value}")
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise ContextError(f"gist path contains an unsafe segment: {value}")
        normalized = relative.as_posix()
        if normalized in seen:
            raise ContextError(f"gist path is declared more than once: {normalized}")
        seen.add(normalized)
        path = (feature_root / Path(*relative.parts)).resolve()
        try:
            path.relative_to(gist_root)
        except ValueError as exc:
            raise ContextError(f"gist path escapes gists/: {value}") from exc
        if not path.is_file():
            raise ContextError(f"declared gist is missing: {normalized}")
        result.append({"path": normalized, "content": read_utf8(path)})
    return result


def reject_legacy_status_table(status_text: str) -> None:
    legacy = {
        ("Task", "Type", "State", "Pickup refs", "Completion refs", "Next action"),
        ("Task", "类型", "状态", "接取 refs", "完成 refs", "下一步"),
    }
    if any(tuple(header) in legacy for header, _ in markdown_tables(status_text)):
        raise ContextError("legacy task table found in STATUS.md; migrate it explicitly to TASKS.md and tasks/<id>.md")


def build_context(feature_directory: Path, requested_task: str | None = None) -> dict[str, Any]:
    root = feature_directory.resolve()
    if not root.is_dir():
        raise ContextError(f"feature directory not found: {root}")
    requirement_text = read_utf8(root / "REQUIREMENT.md")
    solution_text = read_utf8(root / "SOLUTION.md")
    status_text = read_utf8(root / "STATUS.md")
    tasks_text = read_utf8(root / "TASKS.md")
    reject_legacy_status_table(status_text)
    records = task_records(tasks_text)
    validate_dependency_graph(records)
    validate_topology(tasks_text, records)
    details = validate_task_files(root, records)
    validate_decision_mapping(records, requirement_text, solution_text)
    task_id = selected_task_id(status_text, requested_task)
    if task_id not in records:
        raise ContextError(f"TASKS.md must contain exactly one index row for {task_id}")
    detail, repository_refs = details[task_id]
    return {
        "feature_directory": str(root),
        "documents": {"requirement": requirement_text, "solution": solution_text, "status": status_text},
        "task": records[task_id],
        "task_detail": detail,
        "repository_refs": repository_refs,
        "dependencies": [records[dep] for dep in records[task_id]["dependencies"]],
        "topology": mermaid_topology(records),
        "gists": declared_gists(detail, root),
    }


def render_markdown(context: dict[str, Any]) -> str:
    task = context["task"]
    parts = [
        f"# Feature context: {task['id']}",
        "",
        "## REQUIREMENT.md",
        "",
        context["documents"]["requirement"].rstrip(),
        "",
        "## SOLUTION.md",
        "",
        context["documents"]["solution"].rstrip(),
        "",
        "## STATUS.md",
        "",
        context["documents"]["status"].rstrip(),
        "",
        "## Selected task",
        "",
        f"- Type: {task['type']}",
        f"- State: {task['state']}",
        f"- Owner: {task['owner']}",
        f"- Depends on: {task['depends_raw']}",
        f"- HEAD SHA: {task['head_raw']}",
        "",
        context["task_detail"].rstrip(),
    ]
    for gist in context["gists"]:
        parts.extend(("", f"## Gist: {gist['path']}", "", gist["content"].rstrip()))
    return "\n".join(parts).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.feature_directory).resolve()
    try:
        if args.sync_topology:
            sync_topology(root / "TASKS.md")
        context = build_context(root, args.task)
    except (ContextError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(context, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(context), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
