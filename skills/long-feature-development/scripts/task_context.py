#!/usr/bin/env python3
"""Extract and validate one task's local context for long-feature-development."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ALLOWED_STATES = {"TODO", "WIP", "BLOCKED", "DONE"}
TASK_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
TABLE_SEPARATOR_RE = re.compile(r":?-{3,}:?\Z")
ACTIVE_POINT_STATES = {"PROPOSED", "REOPENED", "CONFIRMED"}
DISPOSITION_POINT_STATES = {"REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"}
DECIDED_POINT_STATES = {"CONFIRMED", *DISPOSITION_POINT_STATES}
TASK_TABLE_HEADERS = (
    ("Task", "Type", "State", "Pickup refs", "Completion refs", "Next action"),
    ("Task", "类型", "状态", "接取 refs", "完成 refs", "下一步"),
)


class ContextError(ValueError):
    """Raised when persisted task context is ambiguous or incomplete."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print one validated task section and its declared gists."
    )
    parser.add_argument(
        "feature_directory",
        help="Directory containing REQUIREMENT.md, SOLUTION.md, STATUS.md, and TASKS.md",
    )
    parser.add_argument("--task", help="Explicit task ID; defaults to STATUS.md Current task")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args(argv)


def read_utf8(path: Path) -> str:
    if not path.is_file():
        raise ContextError(f"required file is missing: {path.name}")
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
        if (
            header
            and len(separator) == len(header)
            and all(TABLE_SEPARATOR_RE.fullmatch(cell) for cell in separator)
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


def task_records(status_text: str) -> dict[str, dict[str, str]]:
    rows = unique_table(markdown_tables(status_text), TASK_TABLE_HEADERS, "task-state")
    records: dict[str, dict[str, str]] = {}
    keys = ("id", "type", "state", "pickup_refs", "completion_refs", "next_action")
    for row in rows:
        task_id = row[0]
        if TASK_ID_RE.fullmatch(task_id) is None:
            raise ContextError(f"invalid task ID in STATUS.md: {task_id!r}")
        if task_id in records:
            raise ContextError(f"STATUS.md must contain exactly one task-state row for {task_id}")
        if row[2] not in ALLOWED_STATES:
            raise ContextError(f"task {task_id} has invalid state: {row[2]!r}")
        records[task_id] = dict(zip(keys, row))
    return records


def task_section_ids(tasks_text: str) -> list[str]:
    ids: list[str] = []
    for match in re.finditer(r"^##[ \t]+(.+?)[ \t]*$", tasks_text, re.MULTILINE):
        token = match.group(1).split(maxsplit=1)[0].strip("`")
        if TASK_ID_RE.fullmatch(token) is None:
            raise ContextError(f"invalid task section heading in TASKS.md: {match.group(1)!r}")
        ids.append(token)
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise ContextError(f"TASKS.md contains duplicate task sections: {', '.join(duplicates)}")
    return ids


def validate_task_mapping(records: dict[str, dict[str, str]], tasks_text: str) -> None:
    status_ids = set(records)
    section_ids = set(task_section_ids(tasks_text))
    missing = sorted(status_ids - section_ids)
    extra = sorted(section_ids - status_ids)
    if missing:
        raise ContextError(f"TASKS.md is missing task sections: {', '.join(missing)}")
    if extra:
        raise ContextError(f"TASKS.md has task sections absent from STATUS.md: {', '.join(extra)}")


def task_section(tasks_text: str, task_id: str) -> str:
    heading = re.compile(
        rf"^##[ \t]+`?{re.escape(task_id)}`?(?:[ \t]+(?:—|–|-)[ \t]+.*)?[ \t]*$",
        re.MULTILINE,
    )
    matches = list(heading.finditer(tasks_text))
    if len(matches) != 1:
        raise ContextError(f"TASKS.md must contain exactly one level-two section for {task_id}")
    start = matches[0].start()
    next_heading = re.search(r"^##[ \t]+", tasks_text[matches[0].end() :], re.MULTILINE)
    end = matches[0].end() + next_heading.start() if next_heading else len(tasks_text)
    return tasks_text[start:end].strip()


def h2_section(text: str, headings: tuple[str, ...]) -> str:
    patterns = [
        re.compile(rf"^##[ \t]+{re.escape(heading)}[ \t]*$", re.MULTILINE)
        for heading in headings
    ]
    matches = [match for pattern in patterns for match in pattern.finditer(text)]
    if len(matches) != 1:
        raise ContextError(f"expected exactly one section named: {' or '.join(headings)}")
    next_heading = re.search(r"^##[ \t]+", text[matches[0].end() :], re.MULTILINE)
    end = matches[0].end() + next_heading.start() if next_heading else len(text)
    return text[matches[0].start() : end]


def metadata_value(section: str, keys: set[str], location: str) -> str:
    rows = unique_table(
        markdown_tables(section),
        (("Item", "Value"), ("项目", "值")),
        f"{location} metadata",
    )
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


def validate_decision_document(
    document_text: str, prefix: str, final_status: str
) -> dict[str, str]:
    sections = point_sections(document_text, prefix)
    if not sections:
        return {}

    derived_section = h2_section(
        document_text, ("Derived document state", "派生文档状态")
    )
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
                raise ContextError(
                    f"disposition point {point_id} has invalid state: {point_state!r}"
                )
        else:
            raise ContextError(f"point {point_id} has invalid class: {point_class!r}")
        states[point_id] = point_state

    expected_status = (
        final_status
        if active_states and all(state == "CONFIRMED" for state in active_states)
        else "DRAFT"
    )
    if document_status != expected_status:
        raise ContextError(
            f"{prefix} document status must be {expected_status}, got {document_status}"
        )
    return states


def validate_decision_mapping(
    records: dict[str, dict[str, str]], requirement_text: str, solution_text: str
) -> None:
    requirement_states = validate_decision_document(
        requirement_text, "REQ", "CONFIRMED"
    )
    solution_states = validate_decision_document(solution_text, "SOL", "BASELINED")
    for prefix, states in (("REQ", requirement_states), ("SOL", solution_states)):
        task_ids = {task_id for task_id in records if task_id.startswith(prefix + "-")}
        if not states and not task_ids:
            continue
        point_ids = set(states)
        missing_tasks = sorted(point_ids - task_ids)
        missing_points = sorted(task_ids - point_ids)
        if missing_tasks:
            raise ContextError(
                f"{prefix} decision points are missing STATUS tasks: {', '.join(missing_tasks)}"
            )
        if missing_points:
            raise ContextError(
                f"{prefix} STATUS tasks are missing document points: {', '.join(missing_points)}"
            )
        for point_id, point_state in states.items():
            if records[point_id]["state"] == "DONE" and point_state not in DECIDED_POINT_STATES:
                raise ContextError(
                    f"DONE task {point_id} requires a decided point state, got {point_state}"
                )

    for point_id, section in point_sections(solution_text, "SOL").items():
        if solution_states[point_id] != "CONFIRMED":
            continue
        raw_refs = metadata_value(
            section,
            {"Requirement points", "需求点"},
            point_id,
        )
        refs = [value.strip().strip("`") for value in raw_refs.split(",")]
        if not refs or any(not value for value in refs):
            raise ContextError(f"confirmed solution point {point_id} has no requirement refs")
        invalid = sorted(
            ref for ref in refs if requirement_states.get(ref) != "CONFIRMED"
        )
        if invalid:
            raise ContextError(
                f"confirmed solution point {point_id} references unconfirmed requirements: "
                + ", ".join(invalid)
            )


def declared_gists(section: str, feature_root: Path) -> list[dict[str, str]]:
    declarations = re.findall(r"^- Gists[:：][ \t]*(.+?)[ \t]*$", section, re.MULTILINE)
    if len(declarations) != 1:
        raise ContextError("task section must contain exactly one '- Gists:' declaration")
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


def build_context(feature_directory: Path, requested_task: str | None = None) -> dict[str, Any]:
    root = feature_directory.resolve()
    if not root.is_dir():
        raise ContextError(f"feature directory not found: {root}")
    requirement_text = read_utf8(root / "REQUIREMENT.md")
    solution_text = read_utf8(root / "SOLUTION.md")
    status_text = read_utf8(root / "STATUS.md")
    tasks_text = read_utf8(root / "TASKS.md")
    records = task_records(status_text)
    validate_task_mapping(records, tasks_text)
    validate_decision_mapping(records, requirement_text, solution_text)
    task_id = selected_task_id(status_text, requested_task)
    if task_id not in records:
        raise ContextError(f"STATUS.md must contain exactly one task-state row for {task_id}")
    record = records[task_id]
    section = task_section(tasks_text, task_id)
    return {
        "feature_directory": str(root),
        "documents": {
            "requirement": requirement_text,
            "solution": solution_text,
            "status": status_text,
        },
        "task": record,
        "task_section": section,
        "gists": declared_gists(section, root),
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
        f"- Pickup refs: {task['pickup_refs']}",
        f"- Completion refs: {task['completion_refs']}",
        f"- Next action: {task['next_action']}",
        "",
        context["task_section"],
    ]
    for gist in context["gists"]:
        parts.extend(("", f"## Gist: {gist['path']}", "", gist["content"].rstrip()))
    return "\n".join(parts).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        context = build_context(Path(args.feature_directory), args.task)
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
