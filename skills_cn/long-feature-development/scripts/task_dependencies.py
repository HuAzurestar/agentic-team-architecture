#!/usr/bin/env python3
"""Bounded, pure dependency preview. Persistence is a separate authorized step."""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
import task_context as tc
import task_reconcile as recovery

Error = recovery.RecoveryError
MAX_NODES = 10000
MAX_EDGES = 30000
MAX_BYTES = 4 * 1024 * 1024
CPU_SECONDS = 2.0


def plan_dependencies(index_bytes, detail_bytes, task_id, expected_index_digest, dependency_ids):
    """Build byte-exact before/after records; never write, dispatch or decide.

    IDs are deduplicated in caller order. The expected digest covers original
    bytes (including BOM/newlines), not normalized Markdown. A valid graph is
    necessary, not sufficient for acceptance or integration authorization.
    """
    started = time.process_time()

    def budget():
        if time.process_time() - started > CPU_SECONDS:
            raise Error("RESOURCE_LIMIT", resource="computation")

    if (not isinstance(index_bytes, bytes) or not isinstance(detail_bytes, bytes)
            or len(index_bytes) + len(detail_bytes) > MAX_BYTES):
        raise Error("RESOURCE_LIMIT", resource="document_bytes")
    if (not isinstance(task_id, str) or tc.TASK_ID_RE.fullmatch(task_id) is None
            or not isinstance(expected_index_digest, str)
            or re.fullmatch(r"[a-f0-9]{64}", expected_index_digest) is None):
        raise Error("INVALID_REQUEST")
    if recovery.digest(index_bytes) != expected_index_digest:
        raise Error("INDEX_CHANGED")
    if (not isinstance(dependency_ids, (list, tuple))
            or len(dependency_ids) > MAX_EDGES):
        raise Error("INVALID_DEPENDENCIES")
    dependencies = []
    seen = set()
    for value in dependency_ids:
        if not isinstance(value, str) or tc.TASK_ID_RE.fullmatch(value) is None:
            raise Error("INVALID_DEPENDENCIES")
        if value not in seen:
            seen.add(value)
            dependencies.append(value)
    if task_id in seen:
        raise Error("INVALID_DEPENDENCY_GRAPH")
    text = recovery.decode(index_bytes)
    detail = recovery.decode(detail_bytes)
    budget()
    try:
        records = tc.task_records(text)
        if len(records) > MAX_NODES:
            raise Error("RESOURCE_LIMIT", resource="nodes")
        edge_count = sum(len(row["dependencies"]) for row in records.values())
        if edge_count > MAX_EDGES:
            raise Error("RESOURCE_LIMIT", resource="edges")
        tc.validate_dependency_graph(records)
        tc.validate_topology(text, records)
    except tc.ContextError:
        raise Error("INVALID_DEPENDENCY_GRAPH") from None
    budget()
    if task_id not in records:
        raise Error("UNKNOWN_TASK")
    target = records[task_id]
    if target["state"] != "PENDING" or target["owner"] != "-":
        raise Error("TASK_ALREADY_STARTED")
    if any(value not in records for value in dependencies):
        raise Error("UNKNOWN_DEPENDENCY")
    try:
        tc.task_detail(Path("."), target, text=detail)
        tc.validate_type_contract(target, detail, records)
    except tc.ContextError:
        raise Error("INVALID_TASK_DETAIL") from None
    new_edge_count = edge_count - len(target["dependencies"]) + len(dependencies)
    if new_edge_count > MAX_EDGES:
        raise Error("RESOURCE_LIMIT", resource="edges")
    keys = ("id", "type", "name", "state", "owner", "depends_raw",
            "started_at", "completed_at", "head_raw")
    cells = [target[key] for key in keys]
    old_line = recovery.row_line(text, cells)
    updated = list(cells)
    updated[3] = "`PENDING`"
    updated[5] = ", ".join(dependencies) if dependencies else "-"
    candidate = recovery.replace_operations(text, [{
        "kind": "row", "old_value": old_line,
        "new_value": "| " + " | ".join(updated) + " |"}])
    try:
        candidate = tc.synchronized_topology(candidate)
        new_records = tc.task_records(candidate)
        tc.validate_dependency_graph(new_records)
        tc.validate_topology(candidate, new_records)
        if task_id.startswith("GATE-"):
            fields = tc.type_contract_fields(detail, task_id)
            old = recovery.row_line(detail, ["Required tasks", fields["Required tasks"]])
            detail = recovery.replace_operations(detail, [{
                "kind": "row", "old_value": old,
                "new_value": "| Required tasks | " + updated[5] + " |"}])
        tc.task_detail(Path("."), new_records[task_id], text=detail)
        tc.validate_type_contract(new_records[task_id], detail, new_records)
    except tc.ContextError:
        raise Error("INVALID_DEPENDENCY_GRAPH") from None
    before = {"TASKS.md": index_bytes, f"tasks/{task_id}.md": detail_bytes}
    after = {
        "TASKS.md": recovery.encode(candidate, index_bytes),
        f"tasks/{task_id}.md": recovery.encode(detail, detail_bytes),
    }
    if sum(map(len, after.values())) > MAX_BYTES:
        raise Error("RESOURCE_LIMIT", resource="document_bytes")
    # A no-op must not normalize user formatting or regenerate unchanged bytes.
    if dependencies == target["dependencies"]:
        after = dict(before)
    result = dict(task_id=task_id, old_dependencies=list(target["dependencies"]),
                  new_dependencies=dependencies, topology_digest=recovery.digest(
                      tc.mermaid_topology(new_records).encode()),
                  before=before, after=after,
                  changed_paths=[p for p in before if before[p] != after[p]],
                  expected_index_digest=expected_index_digest,
                  readiness=new_records[task_id]["readiness"], effect="NOT_APPLIED",
                  node_count=len(records), edge_count=new_edge_count,
                  quality_assessed=False)
    budget()
    return result

