#!/usr/bin/env python3
"""review/v1 configuration and allowlisted context views, without task mutations."""

from __future__ import annotations

import copy
import hashlib
import re
import shlex
from pathlib import Path
from typing import Any


TOPICS = ("core", "api", "ui", "data", "auth", "recovery", "regression", "observe", "perf")
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_INPUTS = 1000


def parse_review_scope(value: str | None = None) -> dict[str, Any]:
    tokens = shlex.split(value or "review/v1")
    if not tokens or tokens[0] != "review/v1":
        raise ValueError("unsupported review protocol; expected review/v1")
    fields: dict[str, str] = {}
    for token in tokens[1:]:
        key, separator, content = token.partition("=")
        if not separator or key not in {"mode", "topics", "exclude", "focus"} or key in fields or not content:
            raise ValueError("invalid or duplicate review scope field")
        fields[key] = content
    mode = fields.get("mode", "strong")
    if mode not in {"strong", "weak"}:
        raise ValueError("review mode must be strong or weak")

    def topic_list(raw: str) -> list[str]:
        values = raw.split(",") if raw else []
        if len(values) != len(set(values)) or any(value not in TOPICS for value in values):
            raise ValueError("unknown or duplicate review topic")
        return values

    requested = list(TOPICS) if fields.get("topics", "all") == "all" else topic_list(fields["topics"])
    excluded = topic_list(fields.get("exclude", ""))
    focus = fields.get("focus", "").split(",") if "focus" in fields else []
    if any(not item for item in focus) or len(focus) != len(set(focus)):
        raise ValueError("empty or duplicate review focus")
    return {
        "protocol": "review/v1", "mode": mode,
        "topics": [topic for topic in TOPICS if topic in requested and topic not in excluded],
        "exclude": [topic for topic in TOPICS if topic in excluded], "focus": focus,
    }


def scope_lines(text: str) -> list[str]:
    return re.findall(r"^- (?:Review scope|审查范围)[:：][ \t]*(.+?)[ \t]*$", text, re.MULTILINE)


def configured_scope(solution: str, task_detail: str) -> dict[str, Any]:
    design_values, task_values = scope_lines(solution), scope_lines(task_detail)
    if len(design_values) > 1 or len(task_values) > 1:
        raise ValueError("Review scope must have one authoritative line and at most one task snapshot")
    configured = parse_review_scope(design_values[0] if design_values else None)
    if task_values and parse_review_scope(task_values[0]) != configured:
        raise ValueError("task Review scope snapshot differs from SOLUTION.md")
    return {**configured, "source": "SOLUTION.md" if design_values else "default", "snapshot": bool(task_values)}


def read_bounded(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("review input missing or larger than 4 MiB")
    return path.read_text(encoding="utf-8")


def validate_candidate_target(target: str | None, repositories: dict[str, Any]) -> None:
    """Bind a literal (possibly abbreviated) SHA to one observed candidate head."""
    heads = {item["actual_head"] for item in repositories.values() if item["role"] == "implementation"}
    if heads and (not target or len({head for head in heads if head.startswith(target.lower())}) != 1):
        raise ValueError("review Target SHA must match a current implementation candidate HEAD unambiguously")


def original_inputs(paths: list[str], declared: dict[str, Path]) -> list[dict[str, str]]:
    if len(paths) > MAX_INPUTS or len(paths) != len(set(paths)):
        raise ValueError("too many or duplicate review inputs")
    selected: list[dict[str, str]] = []
    total = 0
    for value in paths:
        if value not in declared:
            raise ValueError("review input must be an exact declared gist path")
        path = declared[value]
        name = path.name.casefold()
        if name.startswith(("review", "blind")) and not name.startswith("review-input"):
            raise ValueError("historical review reports cannot be original inputs")
        content = read_bounded(path)
        markers = re.findall(r"^- Evidence type:[ \t]*(.+?)[ \t]*$", content, re.MULTILINE)
        if markers != ["original"]:
            raise ValueError("raw review input requires exactly one Evidence type: original declaration")
        total += path.stat().st_size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("review inputs exceed 64 MiB")
        selected.append({"path": value, "content": content})
    return selected


def verify_blind_snapshot(path: str | None, declared: dict[str, Path], task_id: str, target: str | None, scope: dict[str, Any]) -> dict[str, str]:
    if path is None or path not in declared:
        raise ValueError("reconcile requires --review-report naming a declared blind snapshot gist")
    content = read_bounded(declared[path])
    for name, expected in (("Review phase", "blind"), ("Review task", task_id), ("Target SHA", target)):
        values = re.findall(rf"^- {re.escape(name)}:[ \t]*(.+?)[ \t]*$", content, re.MULTILINE)
        if expected is None or values != [expected]:
            raise ValueError("blind snapshot must match review phase, task and current Target SHA")
    values = scope_lines(content)
    expected_scope = {key: scope[key] for key in ("protocol", "mode", "topics", "exclude", "focus")}
    if len(values) != 1 or parse_review_scope(values[0]) != expected_scope:
        raise ValueError("blind snapshot Review scope differs from current scope")
    return {"path": path, "sha256": hashlib.sha256(declared[path].read_bytes()).hexdigest(), "target_sha": target}


def blind_context(context: dict[str, Any], scope: dict[str, Any], inputs: list[dict[str, str]]) -> dict[str, Any]:
    """Construct an allowlist; never serialize then try to redact old conclusions."""
    task = context["task"]
    safe_task_keys = ("id", "type", "state", "readiness", "owner", "depends_raw", "head_raw", "dependencies", "head_refs", "started_at", "completed_at")

    def task_metadata(record: dict[str, Any]) -> dict[str, Any]:
        return {key: copy.deepcopy(record[key]) for key in safe_task_keys if key in record}

    feature = context["feature"]
    allowed_summary = {"Phase", "阶段", "Condition", "条件", "Current task", "当前任务", "Current gate", "当前 gate", "Next transition", "下一流转"}
    summary = [{"item": row["item"], "value": row["value"], "note": "-"} for row in feature["summary"] if row["item"] in allowed_summary]

    def ref_table(table: dict[str, Any]) -> dict[str, Any]:
        hidden = {"Note", "备注", "Receives", "接收", "Object", "对象"}
        keep = [index for index, header in enumerate(table["header"]) if header not in hidden]
        return {"header": [table["header"][index] for index in keep], "rows": [[row[index] for index in keep] for row in table["rows"]]}

    intent = {
        kind: {"status": item["status"], "source": "REQUIREMENT.md" if kind == "requirement" else "SOLUTION.md",
               "points": [{"id": point["id"], "state": point["state"], "content": "Normative excerpts must be provided in the original review input; management prose withheld."} for point in item["points"]]}
        for kind, item in context["intent"].items()
    }
    contract = context["type_contract"] or {}
    diagnostics = []
    if not inputs:
        diagnostics.append("Original input packet missing; normative intent, authorization and original evidence require clean excerpts. Do not claim PASS.")
    if not scope["topics"]:
        diagnostics.append("No review topics selected; do not claim PASS.")
    conditions = {row["item"]: row["value"] for row in summary}
    blocked = task["state"] == "BLOCKED" or conditions.get("Condition", conditions.get("条件")) == "BLOCKED"
    if blocked:
        diagnostics.append("An existing action blocker is active; retain its authorized action boundary in the original packet before proceeding.")
    return {
        "feature_directory": context["feature_directory"],
        "feature": {"summary": summary, **{key: ref_table(feature[key]) for key in ("working_branches", "integration_opponents", "pr_mr_objects")}},
        "repositories": {name: {key: item[key] for key in ("path", "actual_branch", "actual_head", "stable_branch", "integration_branch") if key in item} for name, item in context["repositories"].items()},
        "trace": copy.deepcopy(context["trace"]), "intent": intent,
        "task": task_metadata(task), "task_detail": f"# {task['id']} — Blind review\n\nManagement descriptions and previous conclusions withheld. Use the selected original input and current authorization.\n",
        "repository_refs": copy.deepcopy(context["repository_refs"]),
        "type_contract": {key: contract[key] for key in ("Target SHA", "Output SHA", "Result gist") if key in contract},
        "acceptance_brief": None,
        "dependencies": [{"task": task_metadata(item["task"]), "task_detail": "Historical task conclusions withheld.\n"} for item in context["dependencies"]],
        "topology": None, "gists": inputs,
        "review": {"phase": "blind", "scope": scope, "inputs_ready": bool(inputs) and bool(scope["topics"]) and not blocked,
                   "completeness": "UNVERIFIED", "action_blocked": blocked, "diagnostics": diagnostics, "independence": "UNVERIFIED"},
    }
