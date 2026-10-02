#!/usr/bin/env python3
"""Validate and extract one task for long-feature-development."""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
import json
import re
import subprocess
import sys
import time
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
REPOSITORY_REGISTRY_HEADERS = (
    ("Repository", "Role", "Remote", "Path hints", "Stable branch", "Integration branch"),
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
ALLOWED_PHASES = {"PLANNING", "EXECUTING", "RELEASING", "DONE"}
ALLOWED_CONDITIONS = {"ACTIVE", "BLOCKED", "WAITING_HUMAN", "WAITING_EXTERNAL", "COMPLETE"}
QUALITY_CONTRACT_FIELDS = {
    "TEST": {
        "Target SHA", "Environment", "Planned checks", "Executed", "Passed",
        "Failed", "Skipped", "Unknown", "Result gist",
    },
    "REVIEW": {"Target SHA", "Blocking findings", "Deferred findings", "Result gist"},
    "REWORK": {"Source findings", "Target SHA", "Output SHA", "Result gist"},
    "ACCEPT": {"Target SHA", "Acceptance scope", "Decision", "Decided by"},
    "GATE": {"From phase", "To phase", "Required tasks", "Decision ref"},
}
ACCEPTANCE_BRIEF_HEADINGS = (
    ("What changed", "用户可见变化"),
    ("How to check", "如何检查"),
    ("Evidence", "验证证据"),
    ("Out of scope", "范围外内容"),
    ("Known limitations", "已知限制"),
    ("Decision options", "决定选项"),
)


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
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Override one repository location; repeat for multiple repositories",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "acceptance", "envelope"),
        default="markdown",
        help="Use acceptance for a short user-facing acceptance packet",
    )
    parser.add_argument("--context-schema", default="lfd-context-v1",
                        help="Structured context schema; unknown versions are rejected")
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

    dependents: dict[str, list[str]] = {key: [] for key in records}
    degrees = {key: len(record["dependencies"]) for key, record in records.items()}
    for key, record in records.items():
        for dependency in record["dependencies"]:
            dependents[dependency].append(key)
    queue = deque(key for key, degree in degrees.items() if degree == 0)
    visited = 0
    while queue:
        key = queue.popleft()
        visited += 1
        for child in dependents[key]:
            degrees[child] -= 1
            if degrees[child] == 0:
                queue.append(child)
    if visited != len(records):
        raise ContextError("task dependency cycle: " + ", ".join(key for key in records if degrees[key]))

    for task_id, record in records.items():
        if record["state"] != "PENDING":
            unfinished = [dep for dep in record["dependencies"] if records[dep]["state"] != "DONE"]
            if unfinished:
                raise ContextError(f"active task {task_id} has unfinished dependencies: {', '.join(unfinished)}")
        record["readiness"] = (
            "READY"
            if record["state"] == "PENDING"
            and all(records[dep]["state"] == "DONE" for dep in record["dependencies"])
            else "WAITING"
            if record["state"] == "PENDING"
            else "ACTIVE"
        )


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


def synchronized_topology(text: str) -> str:
    records = task_records(text)
    validate_dependency_graph(records)
    matches = list(TOPOLOGY_RE.finditer(text))
    if len(matches) != 1:
        raise ContextError("TASKS.md must contain exactly one generated task-topology block")
    replacement = "<!-- task-topology:start -->\n" + mermaid_topology(records) + "\n<!-- task-topology:end -->"
    return text[: matches[0].start()] + replacement + text[matches[0].end() :]


def sync_topology(path: Path) -> None:
    text = read_utf8(path)
    updated = synchronized_topology(text)
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


def task_detail(root: Path, record: dict[str, Any], *, text: str | None = None) -> tuple[str, list[dict[str, str]]]:
    task_id = record["id"]
    path = root / "tasks" / f"{task_id}.md"
    text = read_utf8(path) if text is None else text
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
    if record["state"] == "BLOCKED":
        for label in ("Blocker", "Impact", "Release condition"):
            matches = re.findall(
                rf"^- {re.escape(label)}[:：][ \t]*(.+?)[ \t]*$", text, re.MULTILINE
            )
            if len(matches) != 1 or matches[0].strip().casefold() in {
                "", "-", "none", "n/a", "无", "无。",
            }:
                raise ContextError(f"BLOCKED task {task_id} requires a non-empty {label}")
    return text, refs


def validate_task_files(root: Path, records: dict[str, dict[str, Any]], *, documents: Any = None) -> dict[str, tuple[str, list[dict[str, str]]]]:
    task_root = root / "tasks"
    if documents is None and not task_root.is_dir():
        raise ContextError("required directory is missing: tasks")
    indexed = {f"{task_id}.md" for task_id in records}
    actual = ({PurePosixPath(path).name for path in documents.task_paths} if documents is not None
              else {path.name for path in task_root.glob("*.md")})
    missing = sorted(indexed - actual)
    extra = sorted(actual - indexed)
    if missing:
        raise ContextError("tasks/ is missing detail files: " + ", ".join(missing))
    if extra:
        raise ContextError("tasks/ has detail files absent from TASKS.md: " + ", ".join(extra))
    return {task_id: task_detail(root, record, text=documents.read(f"tasks/{task_id}.md")
                                if documents is not None else None)
            for task_id, record in records.items()}


def h2_section(text: str, headings: tuple[str, ...]) -> str:
    patterns = [re.compile(rf"^##[ \t]+{re.escape(heading)}[ \t]*$", re.MULTILINE) for heading in headings]
    matches = [match for pattern in patterns for match in pattern.finditer(text)]
    if len(matches) != 1:
        raise ContextError(f"expected exactly one section named: {' or '.join(headings)}")
    next_heading = re.search(r"^##[ \t]+", text[matches[0].end() :], re.MULTILINE)
    end = matches[0].end() + next_heading.start() if next_heading else len(text)
    return text[matches[0].start() : end]


def metadata_value(section: str, keys: set[str], location: str) -> str:
    rows = unique_table(
        markdown_tables(section),
        (("Item", "Value"), ("Field", "Value"), ("项目", "值"), ("字段", "值")),
        f"{location} metadata",
    )
    values = [row[1] for row in rows if row[0] in keys]
    if len(values) != 1:
        raise ContextError(f"{location} must contain exactly one of: {', '.join(sorted(keys))}")
    return values[0]


def document_status_value(document_text: str, prefix: str) -> str:
    derived_matches = re.findall(
        r"^##[ \t]+(?:Derived document state|派生文档状态)[ \t]*$",
        document_text,
        re.MULTILINE,
    )
    if derived_matches:
        derived_section = h2_section(
            document_text, ("Derived document state", "派生文档状态")
        )
        return metadata_value(
            derived_section, {"Status", "状态"}, f"{prefix} document"
        )
    candidates = [
        row[1]
        for header, rows in markdown_tables(document_text)
        if tuple(header) in {("Item", "Current value"), ("项目", "当前值")}
        for row in rows
        if row[0] in {"Status", "状态"}
    ]
    if len(candidates) != 1:
        raise ContextError(
            f"{prefix} document must contain exactly one derived or legacy status value"
        )
    return candidates[0]


def section_table(text: str, headings: tuple[str, ...], location: str) -> dict[str, Any]:
    section = h2_section(text, headings)
    tables = markdown_tables(section)
    if len(tables) != 1:
        raise ContextError(f"{location} must contain exactly one Markdown table")
    header, rows = tables[0]
    return {"header": header, "rows": rows}


def repository_registry(status_text: str) -> dict[str, dict[str, str]]:
    """Parse the optional repository registry; absence keeps legacy records readable."""
    if not re.search(r"^##[ \t]+Repository registry[ \t]*$", status_text, re.MULTILINE):
        return {}
    rows = unique_table(
        markdown_tables(h2_section(status_text, ("Repository registry",))),
        REPOSITORY_REGISTRY_HEADERS,
        "repository-registry",
    )
    keys = ("repository", "role", "remote", "path_hints", "stable_branch", "integration_branch")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        item = dict(zip(keys, row))
        name = item["repository"]
        if not name or name == "-" or name in result:
            raise ContextError(f"repository registry has invalid or duplicate name: {name!r}")
        if item["role"] not in {"project-management", "implementation", "support"}:
            raise ContextError(f"repository {name} has invalid role: {item['role']!r}")
        if any(item[field] == "-" for field in ("remote", "path_hints", "stable_branch", "integration_branch")):
            raise ContextError(f"repository {name} has incomplete registry fields")
        result[name] = item
    if not result:
        raise ContextError("repository registry is empty")
    if sum(item["role"] == "project-management" for item in result.values()) != 1:
        raise ContextError("repository registry requires exactly one project-management repository")
    return result


def parse_repo_overrides(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ContextError(f"repository override must be NAME=PATH: {value!r}")
        name, raw_path = value.split("=", 1)
        if not name or not raw_path or name in result:
            raise ContextError(f"invalid or duplicate repository override: {value!r}")
        result[name] = Path(raw_path).expanduser().resolve()
    return result


def run_git(path: Path, *arguments: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(path), *arguments],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and process.returncode:
        message = process.stderr.strip() or process.stdout.strip() or "git command failed"
        raise ContextError(f"Git check failed for {path}: {message}")
    return process.stdout.strip() if process.returncode == 0 else ""


def git_succeeds(path: Path, *arguments: str) -> bool:
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(path), *arguments],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def git_root(path: Path) -> Path | None:
    output = run_git(path, "rev-parse", "--show-toplevel", check=False)
    return Path(output).resolve() if output else None


def normalize_remote(value: str) -> str:
    normalized = value.strip().replace("\\", "/").rstrip("/")
    if normalized.casefold().endswith(".git"):
        normalized = normalized[:-4]
    return normalized.casefold()


def repository_remotes(path: Path) -> set[str]:
    names = run_git(path, "remote").splitlines()
    return {
        normalize_remote(run_git(path, "remote", "get-url", name.strip()))
        for name in names
        if name.strip()
    }


def resolve_repositories(
    feature_root: Path,
    registry: dict[str, dict[str, str]],
    overrides: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    if not registry:
        if overrides:
            raise ContextError("--repo cannot be used without a Repository registry")
        return {}
    unknown = sorted(set(overrides) - set(registry))
    if unknown:
        raise ContextError("repository overrides name unknown repositories: " + ", ".join(unknown))
    management_root = git_root(feature_root)
    if management_root is None:
        raise ContextError("feature directory is not inside the registered project-management Git repository")
    resolved: dict[str, dict[str, Any]] = {}
    for name, item in registry.items():
        candidates: list[Path] = []
        if name in overrides:
            candidates.append(overrides[name])
        else:
            for raw_hint in item["path_hints"].split(";"):
                hint = Path(raw_hint.strip())
                candidates.append((hint if hint.is_absolute() else management_root / hint).resolve())
            candidates.extend(
                child.resolve()
                for child in management_root.parent.iterdir()
                if child.is_dir() and child != management_root
            )
            if item["role"] == "project-management":
                candidates.insert(0, management_root)
        matches: dict[str, Path] = {}
        expected_remote = normalize_remote(item["remote"])
        for candidate in candidates:
            root = git_root(candidate) if candidate.exists() else None
            if root is None:
                continue
            try:
                remote_match = expected_remote in repository_remotes(root)
            except ContextError:
                remote_match = False
            if remote_match:
                matches[str(root).casefold()] = root
        if not matches:
            raise ContextError(f"repository {name} cannot be located with remote {item['remote']!r}")
        if len(matches) != 1:
            raise ContextError(f"repository {name} location is ambiguous: " + ", ".join(str(path) for path in matches.values()))
        path = next(iter(matches.values()))
        branch = run_git(path, "branch", "--show-current")
        head = run_git(path, "rev-parse", "HEAD").lower()
        for field in ("stable_branch", "integration_branch"):
            branch_name = item[field]
            if not run_git(path, "rev-parse", "--verify", f"refs/heads/{branch_name}", check=False):
                raise ContextError(f"repository {name} is missing local branch {branch_name!r}")
        resolved[name] = {**item, "path": str(path), "actual_branch": branch, "actual_head": head}
    return resolved


def validate_shared_records(feature_root: Path, resolved: dict[str, dict[str, Any]]) -> None:
    if not resolved:
        return
    management = [item for item in resolved.values() if item["role"] == "project-management"]
    if len(management) != 1:
        raise ContextError("resolved repositories require exactly one project-management repository")
    repository_root = Path(management[0]["path"])
    required = [feature_root / name for name in ("REQUIREMENT.md", "SOLUTION.md", "STATUS.md", "TASKS.md")]
    for directory_name in ("tasks", "gists"):
        directory = feature_root / directory_name
        if not directory.is_dir():
            raise ContextError(f"required shared directory is missing: {directory_name}")
        required.extend(path for path in directory.rglob("*") if path.is_file())
    for path in required:
        try:
            relative = path.resolve().relative_to(repository_root).as_posix()
        except ValueError as exc:
            raise ContextError(f"shared record is outside project-management repository: {path}") from exc
        if git_succeeds(repository_root, "check-ignore", "-q", "--", relative):
            raise ContextError(f"shared project-management record is ignored: {relative}")
        if not git_succeeds(repository_root, "ls-files", "--error-unmatch", relative):
            raise ContextError(f"shared project-management record is not tracked: {relative}")


def repository_changes(path: Path) -> list[str]:
    process = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return [line for line in process.stdout.splitlines() if line]


def validate_recovery_cleanliness(
    feature_root: Path, resolved: dict[str, dict[str, Any]]
) -> None:
    """Stop recovery before new work when a relevant repository has residue."""
    for name, item in resolved.items():
        path = Path(item["path"])
        changes = repository_changes(path)
        if item.get("role") == "project-management":
            relative_feature = feature_root.relative_to(path).as_posix().rstrip("/") + "/"
            changes = [
                line
                for line in changes
                if line[3:].replace("\\", "/").lstrip('"').startswith(relative_feature)
            ]
        if changes:
            preview = ", ".join(line[3:] for line in changes[:5])
            suffix = "" if len(changes) <= 5 else f" (+{len(changes) - 5} more)"
            raise ContextError(
                f"recovery required: repository {name} has uncheckpointed changes: "
                f"{preview}{suffix}"
            )


def commit_exists(path: Path, sha: str) -> bool:
    return bool(run_git(path, "rev-parse", "--verify", f"{sha}^{{commit}}", check=False))


def is_ancestor(path: Path, older: str, newer: str) -> bool:
    process = subprocess.run(
        ["git", "-C", str(path), "merge-base", "--is-ancestor", older, newer],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process.returncode == 0


def ref_tokens(raw: str, separator: str) -> list[tuple[str, str]]:
    if raw == "-":
        return []
    result: list[tuple[str, str]] = []
    for token in raw.split(separator):
        branch, sha = token.strip().strip("`").rsplit("@", 1)
        result.append((branch, sha.lower()))
    return result


def focused_status(status_text: str) -> dict[str, Any]:
    summary_rows = unique_table(
        markdown_tables(status_text),
        (("Item", "Current value", "Note"), ("项目", "当前值", "备注")),
        "status-summary",
    )
    return {
        "summary": [
            {"item": row[0], "value": row[1], "note": row[2]}
            for row in summary_rows
        ],
        "working_branches": section_table(
            status_text, ("Working branches", "工作分支"), "working-branches"
        ),
        "integration_opponents": section_table(
            status_text,
            ("Integration opponents", "日常汇入对手分支"),
            "integration-opponents",
        ),
        "pr_mr_objects": section_table(
            status_text, ("PR/MR objects", "PR/MR 对象"), "PR/MR-objects"
        ),
    }


def validate_status_repositories(
    status_text: str,
    status_path: Path,
    resolved: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    if not resolved:
        return []
    trace_edges: list[dict[str, str]] = []
    status = focused_status(status_text)
    working_rows = status["working_branches"]["rows"]
    working_names = [row[0] for row in working_rows]
    if len(working_names) != len(set(working_names)) or set(working_names) != set(resolved):
        raise ContextError("STATUS.md working branches must name every registered repository exactly once")
    for row in working_rows:
        name, recorded_path, branch, recorded_head = row[:4]
        repository = resolved[name]
        actual_path = Path(repository["path"])
        if Path(recorded_path).resolve() != actual_path:
            raise ContextError(f"STATUS.md working path for {name} is stale: {recorded_path}")
        if branch != repository["actual_branch"]:
            raise ContextError(f"STATUS.md working branch for {name} is stale: {branch}")
        if recorded_head == "DERIVED:HEAD":
            if repository["role"] != "project-management":
                raise ContextError(f"DERIVED:HEAD is only valid for the project-management repository: {name}")
            try:
                relative = status_path.resolve().relative_to(actual_path)
            except ValueError as exc:
                raise ContextError("STATUS.md is outside its project-management repository") from exc
            if not run_git(actual_path, "ls-files", "--error-unmatch", relative.as_posix(), check=False):
                raise ContextError("STATUS.md must be tracked before resolving DERIVED:HEAD")
            if run_git(actual_path, "status", "--porcelain", "--", relative.as_posix(), check=False):
                raise ContextError("STATUS.md must match HEAD before resolving DERIVED:HEAD")
            head = repository["actual_head"]
        else:
            head = validate_literal_sha(recorded_head, f"STATUS.md working HEAD for {name}")
            if head != repository["actual_head"]:
                raise ContextError(f"STATUS.md working HEAD for {name} is stale: {head}")
        trace_edges.append({"from": f"{name}:checkout", "to": f"{name}:{head}", "kind": "working-head"})

    integration_rows = status["integration_opponents"]["rows"]
    seen_integration: set[str] = set()
    for row in integration_rows:
        name, branch, sha = row[:3]
        if name not in resolved or name in seen_integration:
            raise ContextError(f"STATUS.md has invalid integration repository: {name!r}")
        seen_integration.add(name)
        sha = validate_literal_sha(sha, f"STATUS.md integration SHA for {name}")
        path = Path(resolved[name]["path"])
        branch_sha = run_git(path, "rev-parse", "--verify", f"refs/heads/{branch}", check=False).lower()
        if not branch_sha or branch_sha != sha:
            raise ContextError(f"STATUS.md integration ref for {name} is stale: {branch}@{sha}")
        trace_edges.append({"from": f"{name}:{sha}", "to": f"{name}:checkout", "kind": "integration-opponent"})

    for row in status["pr_mr_objects"]["rows"]:
        if len(row) < 6:
            raise ContextError("STATUS.md PR/MR row is incomplete")
        _, name, source_branch, source_sha, target_branch, target_sha = row[:6]
        if name not in resolved:
            raise ContextError(f"STATUS.md PR/MR names unknown repository: {name}")
        path = Path(resolved[name]["path"])
        source_sha = validate_literal_sha(source_sha, f"STATUS.md PR/MR source SHA for {name}")
        target_sha = validate_literal_sha(target_sha, f"STATUS.md PR/MR target SHA for {name}")
        actual_source = run_git(path, "rev-parse", "--verify", f"refs/heads/{source_branch}", check=False).lower()
        actual_target = run_git(path, "rev-parse", "--verify", f"refs/heads/{target_branch}", check=False).lower()
        if source_sha != actual_source or target_sha != actual_target:
            raise ContextError(f"STATUS.md PR/MR refs for {name} are stale")
        if not is_ancestor(path, target_sha, source_sha):
            raise ContextError(f"PR/MR source for {name} is not descended from target SHA")
        trace_edges.append({"from": f"{name}:{target_sha}", "to": f"{name}:{source_sha}", "kind": "pr-target-to-source"})
    return trace_edges


def required_task_ids(records: dict[str, dict[str, Any]], target: str) -> set[str]:
    required: set[str] = set()
    queue = deque([target])
    while queue:
        task_id = queue.popleft()
        if task_id not in required:
            required.add(task_id)
            queue.extend(records[task_id]["dependencies"])
    return required


def validate_trace_graph(
    status_text: str,
    records: dict[str, dict[str, Any]],
    details: dict[str, tuple[str, list[dict[str, str]]]],
    resolved: dict[str, dict[str, Any]],
    initial_edges: list[dict[str, str]],
    git_probe: Any = None,
) -> dict[str, Any]:
    if not resolved:
        return {"mode": "LEGACY-UNVERIFIED", "edges": [], "mermaid": ""}
    summary_rows = focused_status(status_text)["summary"]
    summary = {row["item"]: row["value"] for row in summary_rows}
    current_task = summary.get("Current task", summary.get("当前任务"))
    current_gate = summary.get("Current gate", summary.get("当前 gate"))
    if current_task not in records or current_gate not in records:
        raise ContextError("trace graph cannot resolve current task and gate")
    required = required_task_ids(records, current_gate)
    if current_task not in required:
        raise ContextError(f"current task {current_task} is disconnected from current gate {current_gate}")
    for task_id, record in records.items():
        if task_id in required or record["state"] != "PENDING":
            continue
        dispositions = re.findall(r"^- Disposition[:：][ \t]*(.+?)[ \t]*$", details[task_id][0], re.MULTILINE)
        if len(dispositions) != 1 or dispositions[0].strip().casefold() in {"", "-", "none", "n/a"}:
            raise ContextError(f"disconnected PENDING task {task_id} requires an explicit Disposition")

    edges = list(initial_edges)
    task_refs: dict[str, dict[str, dict[str, str]]] = {}
    exists_cache: dict[tuple[str, str], bool] = {}
    ancestry_cache: dict[tuple[str, str, str], bool] = {}

    def known_commit(name: str, path: Path, sha: str) -> bool:
        key = (name, sha)
        if key not in exists_cache:
            exists_cache[key] = (git_probe.commit_exists(path, sha) if git_probe else commit_exists(path, sha))
        return exists_cache[key]

    def ordered(name: str, path: Path, older: str, newer: str) -> bool:
        key = (name, older, newer)
        if key not in ancestry_cache:
            ancestry_cache[key] = (git_probe.is_ancestor(path, older, newer) if git_probe else is_ancestor(path, older, newer))
        return ancestry_cache[key]

    for task_id, (_, refs) in details.items():
        task_refs[task_id] = {}
        for item in refs:
            name = item["repository"]
            if name not in resolved:
                raise ContextError(f"task {task_id} references unregistered repository {name}")
            path = Path(resolved[name]["path"])
            baselines = ref_tokens(item["baseline_history"], "<=")
            starts = ref_tokens(item["start_refs"], ";")
            for _, sha in baselines + starts:
                if not known_commit(name, path, sha):
                    raise ContextError(f"task {task_id} references missing commit {name}@{sha}")
            for (_, older), (_, newer) in zip(baselines, baselines[1:]):
                if not ordered(name, path, older, newer):
                    raise ContextError(f"task {task_id} has unordered baseline history in {name}")
                edges.append({"from": f"{name}:{older}", "to": f"{name}:{newer}", "kind": "baseline"})
            for _, start in starts:
                if baselines and not any(ordered(name, path, baseline, start) for _, baseline in baselines):
                    raise ContextError(f"task {task_id} start ref is disconnected from its baselines in {name}")
                for _, baseline in baselines:
                    if ordered(name, path, baseline, start):
                        edges.append({"from": f"{name}:{baseline}", "to": f"{name}:{start}", "kind": "task-start"})
                        break
            head = item["head_sha"].lower()
            completion = item["completion_sha"].lower()
            if head != "-":
                if not known_commit(name, path, head):
                    raise ContextError(f"task {task_id} references missing HEAD {name}@{head}")
                if starts and not any(ordered(name, path, start, head) for _, start in starts):
                    raise ContextError(f"task {task_id} HEAD is disconnected from its start refs in {name}")
                for _, start in starts:
                    if ordered(name, path, start, head):
                        edges.append({"from": f"{name}:{start}", "to": f"{name}:{head}", "kind": "task-work"})
                        break
            if completion != "-":
                if completion != head:
                    raise ContextError(f"task {task_id} completion SHA must equal its final HEAD in {name}")
                edges.append({"from": f"{name}:{completion}", "to": f"task:{task_id}", "kind": "task-completion"})
            task_refs[task_id][name] = {"head": head, "completion": completion}

    for task_id, record in records.items():
        for dependency in record["dependencies"]:
            edges.append({"from": f"task:{dependency}", "to": f"task:{task_id}", "kind": "task-dependency"})
            for name in set(task_refs[task_id]) & set(task_refs[dependency]):
                prior = task_refs[dependency][name]["completion"]
                later = task_refs[task_id][name]["head"]
                if prior == "-" or later == "-":
                    continue
                path = Path(resolved[name]["path"])
                if not ordered(name, path, prior, later):
                    raise ContextError(f"task dependency {dependency} -> {task_id} is disconnected in {name}")

    node_names = sorted(
        {edge[side] for edge in edges for side in ("from", "to")}
        | {f"task:{task_id}" for task_id in required}
    )
    node_ids = {name: f"N{index}" for index, name in enumerate(node_names)}
    lines = ["```mermaid", "flowchart LR"]
    lines.extend(f'    {node_ids[name]}["{name}"]' for name in node_names)
    lines.extend(f"    {node_ids[edge['from']]} -->|{edge['kind']}| {node_ids[edge['to']]}" for edge in edges)
    lines.append("```")
    return {"mode": "VALIDATED", "required_tasks": sorted(required), "edges": edges, "mermaid": "\n".join(lines)}


def validate_feature_state(status_text: str, records: dict[str, dict[str, Any]]) -> None:
    rows = unique_table(
        markdown_tables(status_text),
        (("Item", "Current value", "Note"), ("项目", "当前值", "备注")),
        "status-summary",
    )
    values = {row[0]: row[1] for row in rows}

    def one_of(keys: tuple[str, ...], label: str) -> str:
        matches = [values[key] for key in keys if key in values]
        if len(matches) != 1:
            raise ContextError(f"STATUS.md must contain exactly one {label} row")
        return matches[0]

    phase = one_of(("Phase", "阶段"), "Phase")
    condition = one_of(("Condition", "条件"), "Condition")
    current_task = one_of(("Current task", "当前任务"), "Current task")
    current_gate = one_of(("Current gate", "当前 gate"), "Current gate")
    next_transition = one_of(("Next transition", "下一流转"), "Next transition")
    if phase not in ALLOWED_PHASES:
        raise ContextError(f"STATUS.md has invalid feature phase: {phase!r}")
    if condition not in ALLOWED_CONDITIONS:
        raise ContextError(f"STATUS.md has invalid feature condition: {condition!r}")
    if current_task not in records:
        raise ContextError(f"STATUS.md current task is absent from TASKS.md: {current_task}")
    if current_gate not in records or not current_gate.startswith("GATE-"):
        raise ContextError(f"STATUS.md current gate is not a GATE task: {current_gate}")
    if records[current_gate]["type"].casefold() != "gate":
        raise ContextError(f"STATUS.md current gate has non-Gate type: {current_gate}")
    if next_transition != current_gate:
        raise ContextError("STATUS.md Next transition and Current gate must name the same gate task")
    if phase == "DONE":
        if condition != "COMPLETE":
            raise ContextError("DONE feature requires condition COMPLETE")
        if current_task != current_gate or records[current_gate]["state"] != "DONE":
            raise ContextError("DONE feature requires its completed current gate as current task")
    else:
        if condition == "COMPLETE":
            raise ContextError("condition COMPLETE is valid only when feature phase is DONE")
        if condition == "ACTIVE" and records[current_task]["state"] not in {"WIP", "RECORDING"}:
            raise ContextError("ACTIVE feature requires the current task to be WIP or RECORDING")


def type_contract_fields(detail: str, task_id: str) -> dict[str, str]:
    section = h2_section(detail, ("Type contract", "类型合同"))
    rows = unique_table(
        markdown_tables(section),
        (("Field", "Value"), ("字段", "值")),
        f"{task_id} type-contract",
    )
    result: dict[str, str] = {}
    for field, value in rows:
        if field in result:
            raise ContextError(f"task {task_id} type contract repeats field: {field}")
        result[field] = value
    return result


def validate_type_contract(
    record: dict[str, Any], detail: str, records: dict[str, dict[str, Any]]
) -> dict[str, str] | None:
    task_id = record["id"]
    kind = next((prefix for prefix in QUALITY_CONTRACT_FIELDS if task_id.startswith(prefix + "-")), None)
    if kind is None:
        return None
    fields = type_contract_fields(detail, task_id)
    missing = sorted(QUALITY_CONTRACT_FIELDS[kind] - set(fields))
    if missing:
        raise ContextError(f"task {task_id} type contract is missing fields: {', '.join(missing)}")
    state = record["state"]
    if kind in {"TEST", "REVIEW", "REWORK", "ACCEPT"} and state != "PENDING":
        for field in ({"Target SHA"} | ({"Output SHA"} if kind == "REWORK" and state == "DONE" else set())):
            validate_literal_sha(fields[field], f"task {task_id} {field}")
    if kind == "TEST" and state == "DONE":
        for field in sorted(QUALITY_CONTRACT_FIELDS["TEST"]):
            if fields[field] in {"", "-"}:
                raise ContextError(f"DONE test task {task_id} has incomplete field: {field}")
    if kind in {"REVIEW", "REWORK"} and state == "DONE":
        for field in sorted(QUALITY_CONTRACT_FIELDS[kind]):
            if fields[field] in {"", "-"}:
                raise ContextError(f"DONE {kind.lower()} task {task_id} has incomplete field: {field}")
    if kind in {"TEST", "REVIEW", "REWORK"} and state == "DONE":
        result_gist = fields["Result gist"]
        if not result_gist.startswith("gists/"):
            raise ContextError(f"DONE task {task_id} must record a result gist under gists/")
    if kind == "ACCEPT":
        decision = fields["Decision"]
        if state == "DONE" and decision not in {"CONFIRMED", "REJECTED", "REWORK"}:
            raise ContextError(f"DONE acceptance task {task_id} has invalid Decision: {decision}")
        if state in {"PENDING", "WIP", "BLOCKED"} and decision != "WAITING":
            raise ContextError(f"unfinished acceptance task {task_id} must keep Decision as WAITING")
        if state == "RECORDING" and decision not in {"WAITING", "CONFIRMED", "REJECTED", "REWORK"}:
            raise ContextError(f"RECORDING acceptance task {task_id} has invalid Decision: {decision}")
        if state == "DONE" and fields["Decided by"].casefold() in {"-", "agent", "codex", "llm"}:
            raise ContextError(f"DONE acceptance task {task_id} requires a human Decided by value")
        if "Acceptance brief" in fields and state != "PENDING" and fields["Acceptance brief"] == "-":
            raise ContextError(f"active acceptance task {task_id} requires an Acceptance brief")
    if kind == "GATE":
        required = parse_dependencies(fields["Required tasks"], task_id)
        if set(required) != set(record["dependencies"]):
            raise ContextError(f"gate {task_id} Required tasks must match its direct dependencies")
        for field in ("From phase", "To phase"):
            if fields[field] not in ALLOWED_PHASES:
                raise ContextError(f"gate {task_id} has invalid {field}: {fields[field]}")
        decision_ref = fields["Decision ref"]
        if state == "DONE":
            validate_literal_sha(decision_ref, f"gate {task_id} Decision ref")
        elif decision_ref != "-":
            raise ContextError(f"unfinished gate {task_id} cannot have Decision ref")
    return fields


def point_selectors(detail: str, label: str, aliases: tuple[str, ...]) -> list[str]:
    names = "|".join(re.escape(alias) for alias in aliases)
    matches = re.findall(rf"^- (?:{names})[:：][ \t]*(.+?)[ \t]*$", detail, re.MULTILINE)
    if len(matches) != 1:
        raise ContextError(f"task detail must contain exactly one '- {label}:' declaration")
    raw = matches[0].strip()
    if raw.lower() == "none" or raw in {"无", "无。"}:
        return []
    values = [value.strip().strip("`") for value in raw.split(",")]
    if not values or any(TASK_ID_RE.fullmatch(value) is None for value in values):
        raise ContextError(f"{label} must be 'none' or a comma-separated point ID list")
    if len(set(values)) != len(values):
        raise ContextError(f"{label} contains a point more than once")
    return values


def focused_document(
    document_text: str,
    prefix: str,
    final_status: str,
    selected_ids: list[str],
) -> dict[str, Any]:
    states = validate_decision_document(document_text, prefix, final_status)
    sections = point_sections(document_text, prefix)
    selected: list[dict[str, str]] = []
    tables = markdown_tables(document_text)
    for point_id in selected_ids:
        heading_match = sections.get(point_id)
        table_matches = [
            (header, row)
            for header, rows in tables
            for row in rows
            if row and row[0] == point_id
        ]
        match_count = (1 if heading_match is not None else 0) + len(table_matches)
        if match_count == 0:
            raise ContextError(f"task detail selects unknown {prefix} points: {point_id}")
        if match_count != 1:
            raise ContextError(f"task detail selects ambiguous {prefix} point: {point_id}")
        if heading_match is not None:
            selected.append(
                {"id": point_id, "state": states[point_id], "content": heading_match}
            )
        else:
            header, row = table_matches[0]
            content = "\n".join(
                (
                    "| " + " | ".join(header) + " |",
                    "| " + " | ".join("---" for _ in header) + " |",
                    "| " + " | ".join(row) + " |",
                )
            )
            selected.append(
                {"id": point_id, "state": row[1] if len(row) > 1 else "UNKNOWN", "content": content}
            )
    return {
        "status": document_status_value(document_text, prefix),
        "points": selected,
    }


def point_sections(document_text: str, prefix: str) -> dict[str, str]:
    heading = re.compile(
        rf"^(##|###)[ \t]+`?({prefix}-[A-Za-z0-9][A-Za-z0-9._-]*)`?(?:[ \t]+(?:—|–|-)[ \t]+.*)?[ \t]*$",
        re.MULTILINE,
    )
    matches = list(heading.finditer(document_text))
    sections: dict[str, str] = {}
    for match in matches:
        level = len(match.group(1))
        point_id = match.group(2)
        if point_id in sections:
            raise ContextError(f"duplicate decision point in document: {point_id}")
        next_heading = re.search(
            rf"^#{{1,{level}}}[ \t]+", document_text[match.end() :], re.MULTILINE
        )
        end = match.end() + next_heading.start() if next_heading else len(document_text)
        sections[point_id] = document_text[match.start() : end]
    return sections


def validate_decision_document(document_text: str, prefix: str, final_status: str) -> dict[str, str]:
    sections = point_sections(document_text, prefix)
    if not sections:
        return {}
    document_status = document_status_value(document_text, prefix)
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


def declared_gist_names(detail: str) -> list[str]:
    declarations = re.findall(r"^- Gists[:：][ \t]*(.+?)[ \t]*$", detail, re.MULTILINE)
    if len(declarations) != 1:
        raise ContextError("task detail must contain exactly one '- Gists:' declaration")
    raw = declarations[0].strip()
    if raw.lower() == "none" or raw in {"无", "无。"}:
        return []
    values = [value.strip().strip("`") for value in raw.split(",")]
    if not values or any(not value for value in values):
        raise ContextError("Gists must be 'none' or a comma-separated path list")
    result: list[str] = []
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
        result.append(normalized)
    return result


def declared_gist_paths(detail: str, feature_root: Path, *, documents: Any = None) -> list[tuple[str, Path]]:
    result: list[tuple[str, Path]] = []
    gist_root = (feature_root / "gists").resolve() if documents is None else feature_root / "gists"
    for normalized in declared_gist_names(detail):
        relative = PurePosixPath(normalized)
        if documents is not None:
            if normalized not in documents.records:
                raise ContextError(f"declared gist is missing: {normalized}")
            result.append((normalized, feature_root / Path(*relative.parts)))
            continue
        path = (feature_root / Path(*relative.parts)).resolve()
        try:
            path.relative_to(gist_root)
        except ValueError as exc:
            raise ContextError(f"gist path escapes gists/: {normalized}") from exc
        if not path.is_file():
            raise ContextError(f"declared gist is missing: {normalized}")
        result.append((normalized, path))
    return result


def declared_gists(detail: str, feature_root: Path, *, documents: Any = None) -> list[dict[str, str]]:
    return [
        {"path": normalized, "content": documents.read(normalized) if documents is not None else read_utf8(path)}
        for normalized, path in declared_gist_paths(detail, feature_root, documents=documents)
    ]


def validate_acceptance_brief(text: str, path: str) -> None:
    for aliases in ACCEPTANCE_BRIEF_HEADINGS:
        section = h2_section(text, aliases)
        body = re.sub(r"^##[^\n]*\n", "", section, count=1).strip()
        if not body or body in {"-", "none", "None", "无", "无。"}:
            raise ContextError(f"acceptance brief {path} has an empty section: {aliases[0]}")


def validate_type_contracts(
    records: dict[str, dict[str, Any]],
    details: dict[str, tuple[str, list[dict[str, str]]]],
    root: Path,
    *, documents: Any = None,
) -> dict[str, dict[str, str]]:
    contracts: dict[str, dict[str, str]] = {}
    for task_id, record in records.items():
        contract = validate_type_contract(record, details[task_id][0], records)
        if contract is None:
            continue
        contracts[task_id] = contract
        declared_paths = {
            normalized for normalized, _ in declared_gist_paths(details[task_id][0], root, documents=documents)
        }
        if "Result gist" in contract:
            result_gist = contract["Result gist"]
            if result_gist != "none" and result_gist not in declared_paths:
                raise ContextError(
                    f"task {task_id} Result gist is not declared by its Gists field: {result_gist}"
                )
        if task_id.startswith("ACCEPT-") and "Acceptance brief" in contract:
            brief = contract["Acceptance brief"]
            if brief == "-":
                continue
            if brief not in declared_paths:
                raise ContextError(
                    f"task {task_id} Acceptance brief is not declared by its Gists field: {brief}"
                )
            validate_acceptance_brief(documents.read(brief) if documents is not None else read_utf8(root / brief), brief)
    return contracts


def reject_legacy_status_table(status_text: str) -> None:
    legacy = {
        ("Task", "Type", "State", "Pickup refs", "Completion refs", "Next action"),
        ("Task", "类型", "状态", "接取 refs", "完成 refs", "下一步"),
    }
    if any(tuple(header) in legacy for header, _ in markdown_tables(status_text)):
        raise ContextError("legacy task table found in STATUS.md; migrate it explicitly to TASKS.md and tasks/<id>.md")


@dataclass(frozen=True)
class ValidatedFeature:
    documents: Any
    records: dict[str, dict[str, Any]]
    details: dict[str, tuple[str, list[dict[str, str]]]]
    type_contracts: dict[str, dict[str, str]]
    repositories: dict[str, dict[str, Any]]
    trace: dict[str, Any]
    review_recovery: dict[str, Any]


class LocalGitProbe:
    """Host-selected local authority, never supplied by the document provider."""
    def __init__(self, root: Path, repo_overrides: dict[str, Path] | None = None):
        self.root = root.resolve()
        self.repo_overrides = repo_overrides or {}

    def validate(self, documents: Any, records: dict, details: dict) -> tuple[dict, dict, dict]:
        from context_loader import LocalMarkdownLoader, LoaderError, enumerate_tasks
        if self.root != documents.root:
            raise LoaderError("SOURCE_MISMATCH", "Git authority root differs from the document root")
        local = LocalMarkdownLoader(self.root)
        if set(enumerate_tasks(local)) != set(documents.task_paths):
            raise LoaderError("INCOMPLETE_CONTEXT", "local task membership differs from loaded documents")
        for name, record in documents.records.items():
            if local.read(name).content_digest != record.content_digest:
                raise LoaderError("SOURCE_MISMATCH", "loader content differs from the authoritative local checkout")
        status_text = documents.read("STATUS.md")
        registry = repository_registry(status_text)
        repositories = resolve_repositories(self.root, registry, self.repo_overrides)
        validate_shared_records(self.root, repositories)
        validate_recovery_cleanliness(self.root, repositories)
        status_edges = validate_status_repositories(status_text, self.root / "STATUS.md", repositories)
        trace = validate_trace_graph(status_text, records, details, repositories, status_edges)
        from review_resume import recover
        reviews = {}
        for task_id, (detail, _) in details.items():
            resumed = recover(documents, detail, records, repositories, commit_exists)
            if resumed is not None:
                reviews[task_id] = resumed
        local.finish()
        return repositories, trace, reviews


def validate_feature(documents: Any, git_probe: LocalGitProbe, *, include_selection: bool = False) -> ValidatedFeature:
    from context_loader import SCHEMA, MAX_COMPUTE_SECONDS, LoaderError
    if documents.context_schema != SCHEMA:
        raise LoaderError("UNSUPPORTED_SCHEMA", "unsupported context schema")
    if documents.read_set.complete is not True:
        raise LoaderError("INCOMPLETE_CONTEXT", "document read set is incomplete")
    start_cpu = time.process_time()
    root = documents.root
    requirement_text = documents.read("REQUIREMENT.md")
    solution_text = documents.read("SOLUTION.md")
    status_text = documents.read("STATUS.md")
    tasks_text = documents.read("TASKS.md")
    reject_legacy_status_table(status_text)
    records = task_records(tasks_text)
    if (len(records) > 10_000 or
            sum(len(record["dependencies"]) for record in records.values()) > 30_000):
        raise ContextError("RESOURCE_LIMIT: selection graph exceeds 10000 tasks or 30000 edges")
    try:
        validate_dependency_graph(records)
    except ContextError as exc:
        if include_selection:
            raise ContextError("INVALID_GRAPH: " + str(exc)) from exc
        raise
    validate_topology(tasks_text, records)
    details = validate_task_files(root, records, documents=documents)
    validate_decision_mapping(records, requirement_text, solution_text)
    validate_feature_state(status_text, records)
    # Check every declaration, not just the focused task or quality task subset.
    for detail, _ in details.values():
        declared_gist_paths(detail, root, documents=documents)
    type_contracts = validate_type_contracts(records, details, root, documents=documents)
    if time.process_time() - start_cpu > MAX_COMPUTE_SECONDS:
        raise LoaderError("RESOURCE_LIMIT", "document validation computation budget exceeded")
    repositories, trace, reviews = git_probe.validate(documents, records, details)
    return ValidatedFeature(documents, records, details, type_contracts, repositories, trace, reviews)


def focus_context(validated: ValidatedFeature, requested_task: str | None = None, *,
                  include_selection: bool = False, structured: bool = False) -> dict[str, Any]:
    """Project already validated documents without file, Git or network access."""
    documents = validated.documents
    root = documents.root
    requirement_text = documents.read("REQUIREMENT.md")
    solution_text = documents.read("SOLUTION.md")
    status_text = documents.read("STATUS.md")
    records, details = validated.records, validated.details
    type_contracts = validated.type_contracts
    repositories, trace = validated.repositories, validated.trace
    task_id = selected_task_id(status_text, requested_task)
    if task_id not in records:
        raise ContextError(f"TASKS.md must contain exactly one index row for {task_id}")
    detail, repository_refs = details[task_id]
    requirement_ids = point_selectors(
        detail, "Requirement points", ("Requirement points", "需求点")
    )
    solution_ids = point_selectors(
        detail, "Solution points", ("Solution points", "方案点")
    )
    gists = declared_gists(detail, root, documents=documents)
    selected_contract = type_contracts.get(task_id)
    acceptance_brief = None
    if selected_contract and selected_contract.get("Acceptance brief") not in {None, "-"}:
        brief_path = selected_contract["Acceptance brief"]
        acceptance_brief = {"path": brief_path, "content": documents.read(brief_path)}
    result = {
        "feature_directory": str(root),
        "feature": focused_status(status_text),
        "repositories": repositories,
        "trace": trace,
        "intent": {
            "requirement": focused_document(
                requirement_text, "REQ", "CONFIRMED", requirement_ids
            ),
            "solution": focused_document(
                solution_text, "SOL", "BASELINED", solution_ids
            ),
        },
        "task": records[task_id],
        "task_detail": detail,
        "repository_refs": repository_refs,
        "type_contract": selected_contract,
        "acceptance_brief": acceptance_brief,
        "dependencies": [
            {"task": records[dep], "task_detail": details[dep][0]}
            for dep in records[task_id]["dependencies"]
        ],
        "topology": mermaid_topology(records),
        "gists": gists,
    }
    if task_id in validated.review_recovery:
        result['review_recovery'] = validated.review_recovery[task_id]
    if include_selection:
        # Project the very records/contracts that passed the full validator above.
        # The adapter binds these to source bytes and actual refs; this label alone
        # is not a validation credential and the default output stays unchanged.
        summary = {row["item"]: row["value"] for row in result["feature"]["summary"]}
        result["selection"] = {
            "current_task": selected_task_id(status_text, None),
            "current_gate": summary.get("Current gate", summary.get("当前 gate")),
            "tasks": [{
                "id": key, "state": record["state"],
                "kind": {"TEST": "Test", "REVIEW": "Review", "REWORK": "Rework",
                         "ACCEPT": "Acceptance", "GATE": "Gate"}.get(key.split("-")[0], record["type"]),
                "dependencies": record["dependencies"],
                "contract": type_contracts.get(key, {}),
                "release_condition": next(iter(re.findall(
                    r"^- Release condition[:：][ \t]*(.+?)[ \t]*$", details[key][0], re.MULTILINE)), ""),
            } for key, record in records.items()],
        }
    if structured:
        included_tasks = {task_id, *records[task_id]["dependencies"]}
        included_documents = {"STATUS.md", "TASKS.md", "REQUIREMENT.md", "SOLUTION.md",
                              *(f"tasks/{key}.md" for key in included_tasks),
                              *(gist["path"] for gist in gists)}
        if acceptance_brief:
            included_documents.add(acceptance_brief["path"])
        result["context_schema"] = documents.context_schema
        result["disclosure"] = {
            "tasks": {"total": len(records), "included": len(included_tasks),
                      "omitted": len(records) - len(included_tasks)},
            "documents": {"total": len(documents.records), "included": len(included_documents),
                          "omitted": len(documents.records) - len(included_documents)},
            "total_bytes": documents.read_set.total_bytes,
            "complete_validation": True,
        }
    return result


def build_context(feature_directory: Path, requested_task: str | None = None,
                  repo_overrides: dict[str, Path] | None = None, *,
                  include_selection: bool = False, structured: bool = False) -> dict[str, Any]:
    from context_loader import LocalMarkdownLoader, LoaderError, load_feature
    root = feature_directory.resolve()
    if not root.is_dir():
        raise ContextError(f"feature directory not found: {root}")
    try:
        documents = load_feature(LocalMarkdownLoader(root))
        validated = validate_feature(documents, LocalGitProbe(root, repo_overrides),
                                     include_selection=include_selection)
        return focus_context(validated, requested_task, include_selection=include_selection,
                             structured=structured)
    except LoaderError as exc:
        error = ContextError(str(exc))
        error.code = exc.code
        raise error from exc


def render_table(table: dict[str, Any]) -> list[str]:
    header = table["header"]
    rows = table["rows"]
    return [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def render_markdown(context: dict[str, Any]) -> str:
    task = context["task"]
    feature = context["feature"]
    parts = [
        f"# Feature context: {task['id']}",
        "",
        "## Feature summary",
        "",
        *(
            f"- {row['item']}: {row['value']}"
            + (f" — {row['note']}" if row["note"] not in {"", "-"} else "")
            for row in feature["summary"]
        ),
        "",
        "### Working branches",
        "",
        *render_table(feature["working_branches"]),
        "",
        "### Integration opponents",
        "",
        *render_table(feature["integration_opponents"]),
        "",
        "### PR/MR objects",
        "",
        *render_table(feature["pr_mr_objects"]),
        "",
        "### Resolved repositories",
        "",
        *(
            f"- {name}: {item['path']} @ {item['actual_branch']}@{item['actual_head']}"
            for name, item in context["repositories"].items()
        ),
        "",
        f"- Trace mode: {context['trace']['mode']}",
        "",
        "## Focused intent",
        "",
        f"- Requirement document status: {context['intent']['requirement']['status']}",
        f"- Solution document status: {context['intent']['solution']['status']}",
        "",
        "## Selected task",
        "",
        f"- Type: {task['type']}",
        f"- State: {task['state']}",
        f"- Readiness: {task['readiness']}",
        f"- Owner: {task['owner']}",
        f"- Depends on: {task['depends_raw']}",
        f"- HEAD SHA: {task['head_raw']}",
        "",
        context["task_detail"].rstrip(),
    ]
    for kind in ("requirement", "solution"):
        for point in context["intent"][kind]["points"]:
            parts.extend(
                ("", f"## {kind.title()} point: {point['id']}", "", point["content"].rstrip())
            )
    for dependency in context["dependencies"]:
        parts.extend(
            (
                "",
                f"## Direct dependency: {dependency['task']['id']}",
                "",
                dependency["task_detail"].rstrip(),
            )
        )
    for gist in context["gists"]:
        parts.extend(("", f"## Gist: {gist['path']}", "", gist["content"].rstrip()))
    if 'review_recovery' in context:
        review = context['review_recovery']
        parts.extend(('', '## Review recovery', '',
                      f"- Current candidate: {json.dumps(review['target_refs'], sort_keys=True)}",
                      f"- Attempt: {review['attempt_id']}",
                      f"- Report: {review['report_ref']['path']}",
                      f"- Next action: {review['next_review_action']}",
                      '- Quality assessment: not performed; no acceptance or closure granted.'))
    return "\n".join(parts).rstrip() + "\n"


def render_acceptance(context: dict[str, Any]) -> str:
    if not context["task"]["id"].startswith("ACCEPT-"):
        raise ContextError("acceptance format requires an ACCEPT task")
    brief = context.get("acceptance_brief")
    if brief is None:
        raise ContextError("acceptance packet is not ready yet")
    return brief["content"].rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    args = parse_args(argv)
    root = Path(args.feature_directory).resolve()
    try:
        if args.context_schema != "lfd-context-v1":
            error = ContextError("unsupported context schema")
            error.code = "UNSUPPORTED_SCHEMA"
            raise error
        if args.sync_topology:
            sync_topology(root / "TASKS.md")
        context = build_context(root, args.task, parse_repo_overrides(args.repo),
                                structured=args.format == "envelope")
    except (ContextError, OSError) as exc:
        code = getattr(exc, 'code', 'INVALID_CONTEXT')
        if code in {'STALE_REVIEW', 'EVIDENCE_MISSING', 'REVIEW_SUMMARY_MISMATCH', 'INVALID_REVIEW_REFERENCE'}:
            print(json.dumps({'event': 'review.resume', 'error_code': code,
                              'elapsed_ms': round((time.monotonic() - started) * 1000)}), file=sys.stderr)
        if args.format == "envelope":
            code = getattr(exc, "code", "INVALID_CONTEXT")
            print(json.dumps({"ok": False, "code": code, "diagnostics": [{"code": code}],
                              "complete": False}, ensure_ascii=True))
            return 2
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if 'review_recovery' in context:
        review = context['review_recovery']
        print(json.dumps({'event': 'review.resume', 'source': review['report_ref']['sha256'],
                          'open_count': len(review['open_findings']), 'error_code': None,
                          'elapsed_ms': round((time.monotonic() - started) * 1000)}), file=sys.stderr)
    if args.format == "envelope":
        print(json.dumps({"ok": True, "code": "OK", "diagnostics": [], "complete": True,
                          "context": context}, ensure_ascii=False, indent=2))
    elif args.format == "json":
        print(json.dumps(context, ensure_ascii=False, indent=2))
    elif args.format == "acceptance":
        try:
            print(render_acceptance(context), end="")
        except ContextError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    else:
        print(render_markdown(context), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
