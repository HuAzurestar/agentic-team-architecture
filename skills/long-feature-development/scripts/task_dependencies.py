#!/usr/bin/env python3
"""Bounded dependency preview, authorized per-file writes and F03 reconciliation."""
from __future__ import annotations

import re
import argparse
import json
import stat
import sys
import time
import uuid
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
    def ancestors(seeds):
        reached, pending = set(), list(seeds)
        while pending:
            key = pending.pop()
            if key not in reached:
                reached.add(key)
                pending.extend(records[key]["dependencies"])
        return reached
    removed = ancestors(target["dependencies"]) - ancestors(dependencies)
    if any(key.startswith(("ACCEPT-", "GATE-")) and records[key]["state"] in
           {"WIP", "BLOCKED", "RECORDING"} for key in removed):
        raise Error("ACTIVE_ATTEMPT_WOULD_BE_HIDDEN")
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
        # The only index edit is the validated dependency cell above. Reuse
        # the parsed records instead of parsing a 10k-row document three times.
        new_records = {key: dict(row) for key, row in records.items()}
        new_records[task_id]["dependencies"] = list(dependencies)
        new_records[task_id]["depends_raw"] = updated[5]
        tc.validate_dependency_graph(new_records)
        topology = tc.mermaid_topology(new_records)
        matches = list(tc.TOPOLOGY_RE.finditer(candidate))
        if len(matches) != 1:
            raise Error("INVALID_DEPENDENCY_GRAPH")
        block = "<!-- task-topology:start -->\n" + topology + "\n<!-- task-topology:end -->"
        candidate = candidate[:matches[0].start()] + block + candidate[matches[0].end():]
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
                      topology.encode()),
                  before=before, after=after,
                  changed_paths=[p for p in before if before[p] != after[p]],
                  expected_index_digest=expected_index_digest,
                  readiness=new_records[task_id]["readiness"], effect="NOT_APPLIED",
                  node_count=len(records), edge_count=new_edge_count,
                  quality_assessed=False)
    budget()
    return result


def interruption_point(name):
    """Failure-injection seam; production does nothing."""


def public_plan(plan):
    return {key: value for key, value in plan.items() if key not in {"before", "after"}}


def read_source(root, relative):
    path = recovery.safe_path(root, relative)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise Error("UNSAFE_SOURCE", path=relative)
    raw = recovery.bounded_bytes(path, MAX_BYTES)
    after = path.stat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                              value.st_mtime_ns, value.st_ctime_ns, value.st_nlink, value.st_mode)
    if identity(after) != identity(info):
        raise Error("SOURCE_CHANGED", path=relative)
    return raw


def checked_context(root, gist, overrides, originals=None, saved=None):
    """Reuse F03's full source/ref checks; no metadata repair is implicit."""
    kwargs = dict(plan_gist=gist, _allowed_dirty=(".operation.lock", *(originals or {})),
                  _originals=originals)
    if saved is not None:
        kwargs.update(_plan_id=saved["plan_id"], _observed_at=saved["observed_at"])
    checked = recovery.inspect(root, overrides, **kwargs)
    if not checked["complete"] or checked["edits"]:
        raise Error("RECOVERY_REQUIRED", blockers=checked["blockers"])
    if saved is not None and checked != saved:
        raise Error("SOURCE_CHANGED")
    for relative in {*checked["read_set"], gist}:
        read_source(root, relative)
    # F03 permits owned dirty paths to reconcile; ownership is not permission
    # to overwrite an already staged user change.
    git = recovery.GitProbe()
    for repo in checked["repositories"]:
        path = Path(repo["resolved_path"])
        prefix = root.relative_to(path).as_posix() + "/" if root.is_relative_to(path) else None
        for entry in git.run(path, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0"):
            if not entry:
                continue
            if prefix is not None and not entry[3:].startswith(prefix):
                continue
            if entry[0] not in {" ", "?"}:
                raise Error("PRESTAGED_CHANGES")
    return checked


def error_result(result, exc):
    result["conflicts"] = [exc.diagnostic if isinstance(exc, Error)
                           else {"code": "INVALID_DEPENDENCY_OPERATION_OR_IO"}]
    result["effect"] = "PARTIAL" if result["recorded_fields"] or result.get("effect_uncertain") else "NOT_APPLIED"
    result["next_check"] = "reconcile-operation" if result["operation_id"] else "inspect-conflicts"
    result["event"] = {"name": "dependency.partial" if result["effect"] == "PARTIAL" else "dependency.rewire",
                       "task_id": result.get("task_id"), "errors": [item["code"] for item in result["conflicts"]]}
    return result


def empty_result(operation_id=None):
    return dict(operation_id=operation_id, effect="NOT_APPLIED", changed_paths=[],
                recorded_fields=[], conflicts=[], observed_result={"status": "unknown"})


def guard_sources(root, gist, source, before, after, gist_bytes):
    """Cheap actual-byte/ref readback between individually atomic replacements."""
    if read_source(root, gist) != gist_bytes:
        raise Error("CONTENT_CONFLICT", path=gist)
    for relative, expected in source["read_set"].items():
        current = read_source(root, relative)
        if relative in before:
            if current not in (before[relative], after[relative]):
                raise Error("CONTENT_CONFLICT", path=relative)
        elif recovery.digest(current) != expected:
            raise Error("SOURCE_CHANGED", path=relative)
    git = recovery.GitProbe()
    recovery.verify_observations(source, git)
    registry = tc.repository_registry(recovery.decode(read_source(root, "STATUS.md")))
    for repo in source["repositories"]:
        path = Path(repo["resolved_path"])
        # A grant readback can hide a concurrent edit from ordinary status.
        # Use the strict recovery predicate; never clear flags or roll back.
        try:
            tc.validate_index_visibility(root, dict(path=path, role=registry[repo["name"]]["role"]))
        except tc.ContextError as exc:
            raise Error(str(exc), repository=repo["name"]) from None
        prefix = root.relative_to(path).as_posix() + "/" if root.is_relative_to(path) else None
        for entry in git.run(path, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0"):
            if not entry:
                continue
            if len(entry) < 4 or "R" in entry[:2] or "C" in entry[:2]:
                raise Error("UNOWNED_CHANGES")
            if prefix is not None and not entry[3:].startswith(prefix):
                continue
            if prefix is None or entry[3:][len(prefix):] not in {gist, ".operation.lock", *before}:
                raise Error("UNOWNED_CHANGES")
            if entry[0] not in {" ", "?"}:
                raise Error("PRESTAGED_CHANGES")


def write_authority(before_write, source_ref):
    """Trusted in-process grant readback; no callback can be loaded from JSON."""
    if before_write is not None:
        if not callable(before_write):
            raise Error('INVALID_WRITE_GUARD')
        source_ref = before_write()
        import task_operation as op
        op.cp.safe_line(source_ref, 'authority source')
    return source_ref


def replace_dependencies(feature, task_id, expected_index_digest, dependency_ids, *,
                         operation_gist, repo_overrides=None, authority=False,
                         authority_source_ref="", before_write=None):
    """Record intent then perform individually atomic writes; never commit."""
    import task_operation as op
    result = empty_result()
    root = Path(feature).resolve()
    overrides = repo_overrides or {}
    try:
        if authority is not True:
            raise Error("AUTHORITY_REQUIRED")
        op.cp.safe_line(authority_source_ref, "authority source")
        if not isinstance(task_id, str) or tc.TASK_ID_RE.fullmatch(task_id) is None:
            raise Error("INVALID_REQUEST")
        with op.coordinator(root):
            before = {"TASKS.md": read_source(root, "TASKS.md"),
                      f"tasks/{task_id}.md": read_source(root, f"tasks/{task_id}.md")}
            plan = plan_dependencies(before["TASKS.md"], before[f"tasks/{task_id}.md"],
                                     task_id, expected_index_digest, dependency_ids)
            result.update({k: v for k, v in public_plan(plan).items() if k != "changed_paths"})
            source = checked_context(root, operation_gist, overrides)
            # Validate the complete candidate too, including gate closure/trace.
            checked_context(root, operation_gist, overrides, plan["after"])
            if not plan["changed_paths"]:
                result.update(effect="UNCHANGED", observed_result={"status": "success"})
                return result
            record = dict(operation_version="operation-v1", operation_id=str(uuid.uuid4()),
                          kind="dependency-rewire", feature=root.name, task=source["task_id"],
                          target_task=task_id, intent_ref=operation_gist,
                          authority_source_ref=authority_source_ref,
                          dependency_ids=plan["new_dependencies"],
                          expected_source={"context": source,
                                           "documents": {p: op.raw_snapshot(raw) for p, raw in before.items()}},
                          owned_paths=plan["changed_paths"], observed_result={"status": "not-observed"},
                          recorded_fields=[])
            # Recheck all observations immediately before durable intent.
            raw, _, _, _ = op.read_gist(root, operation_gist)
            record['authority_source_ref'] = write_authority(before_write, authority_source_ref)
            guard_sources(root, operation_gist, source, before, plan["after"], raw)
            if any(read_source(root, p) != raw for p, raw in before.items()):
                raise Error("SOURCE_CHANGED")
            result["operation_id"] = record["operation_id"]
            op.save(root, operation_gist, record, raw)
            result["recorded_fields"] = [operation_gist + "#intent"]
            result["changed_paths"] = []
            interruption_point("after-intent")
            return _reconcile_dependencies(root, operation_gist, record["operation_id"], overrides, True,
                                          result=result, before_write=before_write)
    except (Error, tc.ContextError, OSError, ValueError, KeyError, TypeError) as exc:
        # An exception is not proof that replace() had no effect. Preserve the
        # UUID before attempting intent I/O, then read back without replay.
        if result["operation_id"] and not result["recorded_fields"]:
            try:
                if result["operation_id"] in op.read_gist(root, operation_gist)[3]:
                    result["recorded_fields"].append(operation_gist + "#intent")
                else:
                    result["operation_id"] = None
            except (Error, OSError, ValueError, KeyError, TypeError):
                result["effect_uncertain"] = True
        return error_result(result, exc)


def _reconcile_dependencies(root, gist, operation_id, overrides, write=False, *, result=None,
                            before_write=None):
    """Called under the shared coordinator for writes; reads never replay."""
    import task_operation as op
    root = Path(root).resolve()
    result = empty_result(operation_id) if result is None else result
    attempted, observer = [], None
    try:
        raw, _, _, records = op.read_gist(root, gist)
        record = records[operation_id]
        if (record["operation_version"] != "operation-v1" or record["kind"] != "dependency-rewire"
                or record["feature"] != root.name or record["intent_ref"] != gist
                or record["operation_id"] != operation_id):
            raise Error("INVALID_INTENT")
        uuid.UUID(operation_id)
        target = record["target_task"]
        if not isinstance(target, str) or tc.TASK_ID_RE.fullmatch(target) is None:
            raise Error("INVALID_INTENT")
        snapshots = record["expected_source"]["documents"]
        if set(snapshots) != {"TASKS.md", f"tasks/{target}.md"}:
            raise Error("INVALID_INTENT")
        before = {p: op.original(snapshot) for p, snapshot in snapshots.items()}
        plan = plan_dependencies(before["TASKS.md"], before[f"tasks/{target}.md"], target,
                                 recovery.digest(before["TASKS.md"]), record["dependency_ids"])
        if plan["changed_paths"] != record["owned_paths"] or not plan["changed_paths"]:
            raise Error("INVALID_INTENT")
        result.update({k: v for k, v in public_plan(plan).items()
                       if k not in {"effect", "changed_paths"}})
        source = record["expected_source"]["context"]
        if source["task_id"] != record["task"]:
            raise Error("INVALID_INTENT")
        # Snapshot claims must describe the original committed records, not
        # arbitrary user-provided replacement Markdown.
        management = [r for r in source["repositories"] if root.is_relative_to(Path(r["resolved_path"]))]
        if len(management) != 1:
            raise Error("INVALID_REPOSITORY_SET")
        pm = Path(management[0]["resolved_path"])
        git = recovery.GitProbe()
        for relative, content in before.items():
            blob = (root / relative).relative_to(pm).as_posix()
            committed = git.run(pm, "show", management[0]["observed_head"] + ":" + blob)
            if recovery.decode(committed.encode()) != recovery.decode(content).rstrip("\n"):
                raise Error("INVALID_INTENT")

        def observe():
            saved, pending = [], []
            for relative in plan["before"]:
                current = read_source(root, relative)
                if current == plan["after"][relative]:
                    if relative in plan["changed_paths"]:
                        saved.append(relative)
                elif current == plan["before"][relative]:
                    pending.append(relative)
                else:
                    raise Error("CONTENT_CONFLICT", path=relative)
            return dict(status="partial" if saved and pending else "not-observed" if pending else "success",
                        saved_files=saved, pending_files=pending, evidence="current-bytes-not-commit")

        observer = observe
        result["observed_result"] = observe()
        checked_context(root, gist, overrides, before, source)
        checked_context(root, gist, overrides, plan["after"])
        if not write:
            result["next_check"] = "authorized-resume-dependencies" if result["observed_result"]["pending_files"] else "commit-management-then-task-context"
            return result
        # Each file replacement has its own precondition. No all-file rollback.
        for relative in plan["changed_paths"]:
            interruption_point("before-" + relative)
            if relative in observe()['pending_files']:
                record['authority_source_ref'] = write_authority(before_write, record['authority_source_ref'])
            guard_sources(root, gist, source, before, plan["after"], raw)
            observed = observe()
            if relative in observed["pending_files"]:
                attempted.append(relative)
                recovery.atomic_replace(recovery.safe_path(root, relative), plan["after"][relative])
                result["changed_paths"].append(relative)
                result["recorded_fields"].append(relative)
            interruption_point("after-" + relative)
        result["observed_result"] = observe()
        guard_sources(root, gist, source, before, plan["after"], raw)
        record["observed_result"] = result["observed_result"]
        record["recorded_fields"] = list(plan["changed_paths"])
        record['authority_source_ref'] = write_authority(before_write, record['authority_source_ref'])
        guard_sources(root, gist, source, before, plan['after'], raw)
        if op.save(root, gist, record, raw) != raw:
            result["recorded_fields"].append(gist + "#observed_result")
        result.update(effect="APPLIED" if result["recorded_fields"] else "UNCHANGED",
                      next_check="commit-management-then-task-context",
                      event={"name": "dependency.rewire", "task_id": target,
                             "edge_count": plan["edge_count"], "topology_digest": plan["topology_digest"]})
        return result
    except (Error, tc.ContextError, OSError, ValueError, KeyError, TypeError) as exc:
        # Account for replacement succeeding just before an I/O response fails.
        for relative in attempted:
            try:
                if read_source(root, relative) == plan["after"][relative]:
                    if relative not in result["changed_paths"]:
                        result["changed_paths"].append(relative)
                    if relative not in result["recorded_fields"]:
                        result["recorded_fields"].append(relative)
            except (Error, OSError, ValueError, KeyError, TypeError):
                result["effect_uncertain"] = True
        if observer is not None:
            try:
                result["observed_result"] = observer()
            except (Error, OSError, ValueError, KeyError, TypeError):
                result["observed_result"] = {"status": "unknown"}
        return error_result(result, exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature_directory")
    parser.add_argument("task_id", nargs="?")
    parser.add_argument("--depends-on", default="-", help="Comma-separated IDs; '-' removes all")
    parser.add_argument("--expected-index-digest", help="Exact digest returned by preview; required for writes")
    parser.add_argument("--operation-gist", help="Existing tracked gist declared by the current task")
    parser.add_argument("--operation-id", help="Read actual effects or resume this exact recorded operation")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--authorized", action="store_true", help="Caller attests actual session authorization")
    parser.add_argument("--authority-source-ref", default="")
    args = parser.parse_args(argv)
    try:
        root = Path(args.feature_directory).resolve()
        overrides = tc.parse_repo_overrides(args.repo)
        if args.operation_id:
            if not args.operation_gist or args.task_id or args.expected_index_digest or args.depends_on != "-":
                raise Error("INVALID_REQUEST")
            import task_operation as op
            result = op.reconcile(root, args.operation_gist, args.operation_id, overrides,
                                  apply=args.apply, authority=args.authorized)
        else:
            if not args.task_id or tc.TASK_ID_RE.fullmatch(args.task_id) is None:
                raise Error("INVALID_REQUEST")
            dependencies = [] if args.depends_on == "-" else [v.strip() for v in args.depends_on.split(",")]
            if args.apply:
                if not args.expected_index_digest or not args.operation_gist:
                    raise Error("INVALID_REQUEST")
                result = replace_dependencies(root, args.task_id, args.expected_index_digest, dependencies,
                    operation_gist=args.operation_gist, repo_overrides=overrides, authority=args.authorized,
                    authority_source_ref=args.authority_source_ref)
            else:
                index = read_source(root, "TASKS.md")
                result = public_plan(plan_dependencies(index, read_source(root, f"tasks/{args.task_id}.md"),
                    args.task_id, args.expected_index_digest or recovery.digest(index), dependencies))
                result["conflicts"] = []
                result["next_check"] = "authorized-apply-with-returned-index-digest"
        print(json.dumps(result, ensure_ascii=False))
        return 2 if result.get("conflicts") else 0
    except (Error, tc.ContextError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(error_result(empty_result(), exc), ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
