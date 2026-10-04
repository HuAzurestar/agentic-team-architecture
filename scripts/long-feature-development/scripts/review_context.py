#!/usr/bin/env python3
"""review/v1 configuration and allowlisted context views, without task mutations."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shlex
from pathlib import Path
from typing import Any


TOPICS = ("core", "api", "ui", "data", "auth", "recovery", "regression", "observe", "perf")
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_INPUTS = 1000


def parse_review_scope(value: str | None = None) -> dict[str, Any]:
    if value is not None and not value.strip():
        raise ValueError("Review scope is explicitly empty; omit the declaration to use defaults")
    tokens = shlex.split("review/v1" if value is None else value)
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
    return re.findall(r"^- (?:Review scope|审查范围)[:：]([^\r\n]*)\r?$", text, re.MULTILINE)


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


def candidate_references(
    repositories: dict[str, Any], repository_refs: list[dict[str, str]], feature: dict[str, Any]
) -> dict[str, Any]:
    """Bind every implementation checkout, plus literal task/intent source refs.

    Never bind a management checkout HEAD: committing the report itself advances it.
    Without a registry, task refs remain explicitly recorded-only evidence.
    """
    task_keys = ("branch", "head_sha", "baseline_history", "start_refs", "completion_sha")
    refs = {item["repository"]: {key: item[key] for key in task_keys} for item in repository_refs}
    for name, item in repositories.items():
        if item["role"] == "implementation":
            refs.setdefault(name, {}).update(
                branch=item["actual_branch"], head_sha=item["actual_head"], verification="observed"
            )
    for name, item in refs.items():
        item.setdefault("verification", "recorded-only")
        if name in repositories and repositories[name]["role"] != "implementation":
            continue
        item["integration_refs"] = [
            {"branch": row[1], "sha": row[2]}
            for row in feature["integration_opponents"]["rows"] if row[0] == name
        ]
        item["pr_refs"] = [
            {"source_branch": row[2], "source_sha": row[3], "target_branch": row[4], "target_sha": row[5]}
            for row in feature["pr_mr_objects"]["rows"] if row[1] == name
        ]
    return refs


def verify_blind_snapshot(
    path: str | None, declared: dict[str, Path], task_id: str, target: str | None,
    scope: dict[str, Any], candidate_refs: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    values = re.findall(r"^- Review refs:([^\r\n]*)\r?$", content, re.MULTILINE)
    if candidate_refs is None or len(values) != 1:
        raise ValueError("blind snapshot requires one Review refs line and current per-repository candidate refs")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("blind snapshot Review refs contains a duplicate JSON key")
            result[key] = value
        return result

    try:
        saved_refs = json.loads(values[0], object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise ValueError("blind snapshot Review refs must be valid JSON") from exc
    if saved_refs != candidate_refs:
        raise ValueError("blind snapshot Review refs differ from current per-repository candidate refs")
    return {"path": path, "sha256": hashlib.sha256(declared[path].read_bytes()).hexdigest(), "target_sha": target, "candidate_refs": candidate_refs}


def blind_context(context: dict[str, Any], scope: dict[str, Any], inputs: list[dict[str, str]]) -> dict[str, Any]:
    """Construct an allowlist; never serialize then try to redact old conclusions."""
    task = context["task"]
    safe_task_keys = ("id", "type", "state", "readiness", "owner", "depends_raw", "head_raw", "dependencies", "head_refs", "started_at", "completed_at")

    def task_metadata(record: dict[str, Any]) -> dict[str, Any]:
        return {key: copy.deepcopy(record[key]) for key in safe_task_keys if key in record}

    feature = context["feature"]
    allowed_summary = {"Phase", "阶段", "Condition", "条件", "Current task", "当前任务", "Current gate", "当前 gate", "Next transition", "下一流转"}
    summary = [{"item": row["item"], "value": row["value"], "note": "-"} for row in feature["summary"] if row["item"] in allowed_summary]

    def ref_table(kind: str, table: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "working_branches": {"Repository", "仓库", "Local path", "本地路径", "Working branch", "工作分支", "Working HEAD SHA", "工作 HEAD SHA", "Current task", "当前 task", "当前任务"},
            "integration_opponents": {"Repository", "仓库", "Integration branch", "Integration SHA"},
            "pr_mr_objects": {"Repository", "仓库", "Source branch", "Source SHA", "Target branch", "Target SHA"},
        }[kind]
        keep = [index for index, header in enumerate(table["header"]) if header in allowed]
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
    condition = conditions.get("Condition", conditions.get("条件"))
    blocked = task["state"] == "BLOCKED" or condition in {"BLOCKED", "WAITING_HUMAN", "WAITING_EXTERNAL"}
    boundaries = {}
    for key, labels in (("action_boundary", "Action boundary|行动边界"), ("release_condition", "Release condition|解除条件")):
        values = [
            value.strip() for packet in inputs
            for value in re.findall(rf"^- (?:{labels})[:：]([^\r\n]*)\r?$", packet["content"], re.MULTILINE)
        ]
        if len(values) > 1:
            raise ValueError("original review inputs repeat an action boundary or release condition")
        boundaries[key] = values[0] if values and values[0].casefold() not in {"", "-", "none", "n/a", "无", "无。"} else None
    if blocked:
        diagnostics.append(f"Existing action blocker: task={task['state']}, condition={condition}; do not resume blocked actions or infer authorization from review input readiness.")
        for key, value in boundaries.items():
            if value is None:
                diagnostics.append(f"Missing clean {key}: STATUS.md/task blocker prose is withheld because it may contain old findings; provide a separated original excerpt before proceeding.")
    return {
        "feature_directory": context["feature_directory"],
        "feature": {"summary": summary, **{key: ref_table(key, feature[key]) for key in ("working_branches", "integration_opponents", "pr_mr_objects")}},
        "repositories": {name: {key: item[key] for key in ("path", "actual_branch", "actual_head", "stable_branch", "integration_branch") if key in item} for name, item in context["repositories"].items()},
        "trace": copy.deepcopy(context["trace"]), "intent": intent,
        "task": task_metadata(task), "task_detail": f"# {task['id']} — Blind review\n\nManagement descriptions and previous conclusions withheld. Use the selected original input and current authorization.\n",
        "repository_refs": copy.deepcopy(context["repository_refs"]),
        "type_contract": {key: contract[key] for key in ("Target SHA", "Output SHA", "Result gist") if key in contract},
        "acceptance_brief": None,
        "dependencies": [{"task": task_metadata(item["task"]), "task_detail": "Historical task conclusions withheld.\n"} for item in context["dependencies"]],
        "topology": None, "gists": inputs,
        "review": {"phase": "blind", "scope": scope, "inputs_ready": bool(inputs) and bool(scope["topics"]) and not blocked,
                   "candidate_refs": candidate_references(context["repositories"], context["repository_refs"], feature),
                   "action_boundary": boundaries["action_boundary"], "release_condition": boundaries["release_condition"],
                   "completeness": "UNVERIFIED", "action_blocked": blocked, "diagnostics": diagnostics, "independence": "UNVERIFIED"},
    }
