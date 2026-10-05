#!/usr/bin/env python3
"""Observe owned save/record effects; never replay an editor or state writer."""
from __future__ import annotations

import copy
from pathlib import Path
import re
import uuid

import task_checkpoint as cp
import task_context as tc
import task_operation as op
import task_reconcile as recovery

Error = recovery.RecoveryError


def file_digest(path, remaining):
    if not path.exists():
        return None, 0
    raw = recovery.bounded_bytes(path, remaining)
    return recovery.digest(raw), len(raw)


def prepare(feature, gist, kind, repository, expected_after, authority_source_ref,
            overrides=None, *, authority=False):
    """Persist bounded intent BEFORE the host performs its authorized save."""
    if authority is not True:
        raise Error("AUTHORITY_REQUIRED")
    if kind not in {"save", "record"}:
        raise Error("INVALID_OPERATION_KIND")
    root = Path(feature).resolve()
    with op.coordinator(root):
        plan = recovery.inspect(root, overrides or {}, plan_gist=gist, _allowed_dirty=(".operation.lock",))
        if not plan["complete"] or plan["edits"]:
            raise Error("RECOVERY_REQUIRED", blockers=plan["blockers"])
        sources = {r["name"]: r for r in plan["repositories"]}
        if repository not in sources:
            raise Error("INVALID_REPOSITORY_SET")
        cp.safe_line(authority_source_ref, "authority source")
        if not isinstance(expected_after, dict) or not 0 < len(expected_after) <= recovery.MAX_FILES:
            raise Error("RESOURCE_LIMIT")
        record = dict(operation_version="operation-v1", operation_id=str(uuid.uuid4()), kind=kind,
                      feature=root.name, task=plan["task_id"], authority_source_ref=authority_source_ref,
                      target_identity={"repository": repository}, owned_paths=list(expected_after), intent_ref=gist,
                      expected_source={"files": {}, "read_set": plan["read_set"],
                                       "repositories": plan["repositories"], "comparisons": plan["comparisons"]},
                      observed_result={"status": "not-observed"}, recorded_fields=[])
        repo = Path(sources[repository]["resolved_path"])
        remaining = recovery.MAX_BYTES
        for relative, after in expected_after.items():
            cp.safe_include(relative)
            if after is not None and (not isinstance(after, str) or not re.fullmatch(r"[a-f0-9]{64}", after)):
                raise Error("INVALID_FILE_DIGEST")
            before, size = file_digest(recovery.safe_path(repo, relative), remaining)
            remaining -= size
            if before == after:
                raise Error("UNCHANGED_INTENT", path=relative)
            record["expected_source"]["files"][relative] = {"before_digest": before, "after_digest": after}
        # Validate scope and original observations before persisting any intent.
        observe(root, gist, record, overrides or {})
        raw, _, _, _ = op.read_gist(root, gist)
        op.save(root, gist, record, raw)
        return record


def observe(root, gist, record, overrides):
    required = {"operation_version", "operation_id", "kind", "feature", "task", "authority_source_ref",
                "target_identity", "expected_source", "owned_paths", "intent_ref", "observed_result", "recorded_fields"}
    if (not required.issubset(record) or record["operation_version"] != "operation-v1"
            or record["kind"] not in {"save", "record"} or record["feature"] != root.name or record["intent_ref"] != gist):
        raise Error("INVALID_FILE_INTENT")
    source = record["expected_source"]
    paths = record["owned_paths"]
    if (not isinstance(paths, list) or not 0 < len(paths) <= recovery.MAX_FILES
            or len(set(paths)) != len(paths) or set(source["files"]) != set(paths)):
        raise Error("INVALID_FILE_INTENT")
    cp.safe_line(record["authority_source_ref"], "authority source")
    git = recovery.GitProbe()
    status = recovery.decode(recovery.bounded_bytes(recovery.safe_path(root, "STATUS.md")))
    registry = tc.repository_registry(status)
    repos = recovery.resolve_repositories(root, registry, overrides, git)
    target_name = record["target_identity"]["repository"]
    target = repos[target_name]
    repo = Path(target["path"])
    if (record["kind"] == "save" and target["role"] != "implementation"
            or record["kind"] == "record" and target["role"] != "project-management"):
        raise Error("INVALID_OPERATION_SCOPE")
    observations = copy.deepcopy(source["repositories"])
    if {r["name"] for r in observations} != set(repos):
        raise Error("INVALID_REPOSITORY_SET")
    for r in observations:
        current = repos[r["name"]]
        if recovery.digest(current["remote"].encode()) != r["remote_digest"]:
            raise Error("REPO_IDENTITY_MISMATCH")
        r["resolved_path"] = current["path"]
    recovery.verify_observations({"repositories": observations, "comparisons": source["comparisons"]}, git)
    task_path = f"tasks/{record['task']}.md"
    detail = recovery.decode(recovery.bounded_bytes(recovery.safe_path(root, task_path)))
    declared = dict(tc.declared_gist_paths(detail, root))
    if gist not in declared:
        raise Error("PLAN_NOT_DECLARED")
    management = [Path(r["path"]) for r in repos.values() if r["role"] == "project-management"]
    if len(management) != 1:
        raise Error("INVALID_REPOSITORY_SET")
    pm = management[0]
    prefix = root.relative_to(pm).as_posix()
    prefix = "" if prefix == "." else prefix + "/"
    allowed_records = {prefix + p for p in {"STATUS.md", "TASKS.md", task_path, *declared}}
    if record["kind"] == "record" and not set(paths).issubset(allowed_records - {prefix + gist}):
        raise Error("INVALID_OPERATION_SCOPE")
    if git.run(pm, "ls-files", "--error-unmatch", "--", prefix + gist, check=False) is None:
        raise Error("UNTRACKED_RECORD")
    for name, current in repos.items():
        allowed = set(paths) if name == target_name else set()
        if current["role"] == "project-management":
            allowed |= {prefix + gist, prefix + ".operation.lock"}
        for entry in git.run(Path(current["path"]), "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0"):
            if not entry:
                continue
            if len(entry) < 4 or "R" in entry[:2] or "C" in entry[:2]:
                raise Error("UNOWNED_CHANGES")
            if current["role"] == "project-management" and prefix and not entry[3:].startswith(prefix):
                continue
            if entry[3:] not in allowed:
                raise Error("UNOWNED_CHANGES")
            if entry[0] not in {" ", "?"}:
                raise Error("PRESTAGED_CHANGES")
    owned_metadata = {p[len(prefix):] for p in paths} if record["kind"] == "record" else set()
    if len(source["read_set"]) > recovery.MAX_FILES:
        raise Error("RESOURCE_LIMIT")
    remaining = recovery.MAX_BYTES
    for relative, expected in source["read_set"].items():
        if relative not in owned_metadata:
            content = recovery.bounded_bytes(recovery.safe_path(root, relative), remaining)
            remaining -= len(content)
            if recovery.digest(content) != expected:
                raise Error("SOURCE_CHANGED", path=relative)
    saved, pending, digests = [], [], {}
    for relative in paths:
        cp.safe_include(relative)
        states = source["files"][relative]
        if (set(states) != {"before_digest", "after_digest"} or states["before_digest"] == states["after_digest"]
                or any(v is not None and (not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}", v)) for v in states.values())):
            raise Error("INVALID_FILE_INTENT")
        observed, size = file_digest(recovery.safe_path(repo, relative), remaining)
        remaining -= size
        digests[relative] = observed
        if observed == states["after_digest"]:
            saved.append(relative)
        elif observed == states["before_digest"]:
            pending.append(relative)
        else:
            raise Error("CONTENT_CONFLICT", path=relative)
    git.remaining()
    return dict(status="success" if not pending else "partial" if saved else "not-observed",
                saved_files=saved, pending_files=pending, files=digests, evidence="current-bytes-not-commit")


def reconcile(root, gist, operation_id, overrides, write):
    raw, _, _, records = op.read_gist(root, gist)
    record = records[operation_id]
    observed = observe(root, gist, record, overrides)
    result = dict(operation_id=operation_id, observed_result=observed, effect="NOT_APPLIED", recorded_fields=[], conflicts=[],
                  next_check=("validate-owned-work-before-checkpoint" if record["kind"] == "save" else "validate-records-before-checkpoint")
                  if observed["status"] == "success" else "resume-authorized-" + record["kind"])
    if not write:
        return result
    if observe(root, gist, record, overrides) != observed:
        raise Error("SOURCE_CHANGED")
    record.setdefault("initial_observed_result", record["observed_result"])
    record["observed_result"] = observed
    record["recorded_fields"] = list(dict.fromkeys([*record["recorded_fields"], "observed_result"]))
    if op.save(root, gist, record, raw) != raw:
        result["effect"] = "APPLIED"
        result["recorded_fields"] = [gist + "#observed_result"]
    else:
        result["effect"] = "UNCHANGED"
    return result
