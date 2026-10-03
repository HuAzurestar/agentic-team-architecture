#!/usr/bin/env python3
"""Recover an explicitly recorded local checkpoint; never infer remote success."""
from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
import task_checkpoint as cp
import task_context as tc
import task_reconcile as recovery

Error = recovery.RecoveryError
MAX_COMMITS = 1000


def interruption_point(name):
    """Test seam: production performs no action here."""


@contextmanager
def coordinator(root):
    path = root / ".operation.lock"
    marker = json.dumps({"coordinator_id": str(uuid.uuid4()), "owner_pid": os.getpid()}).encode()
    try:
        with path.open("xb") as stream:
            stream.write(marker)
    except FileExistsError:
        raise Error("COORDINATOR_BUSY") from None
    try:
        yield
    finally:
        if path.exists() and recovery.bounded_bytes(path, 1024) == marker:
            path.unlink()


def read_gist(root, relative):
    raw = recovery.bounded_bytes(recovery.safe_path(root, relative), recovery.MAX_PLAN_BYTES)
    return parse_gist(raw)


def parse_gist(raw):
    if len(raw) > recovery.MAX_PLAN_BYTES:
        raise Error('RESOURCE_LIMIT')
    text = recovery.decode(raw)
    blocks = list(re.finditer(r"^```json[ \t]*\n(.*?)^```[ \t]*$", text, re.M | re.S))
    if len(blocks) > 1:
        raise Error("AMBIGUOUS_OPERATION_GIST")
    data = json.loads(blocks[0][1]) if blocks else {"operations": []}
    if not isinstance(data, dict) or set(data) != {"operations"} or not isinstance(data["operations"], list):
        raise Error("INVALID_OPERATION_GIST")
    records = {}
    for item in data["operations"]:
        if item.get("operation_version") != "operation-v1" or item["operation_id"] in records:
            raise Error("INVALID_OPERATION_GIST")
        uuid.UUID(item["operation_id"])
        records[item["operation_id"]] = item
    if len(records) > 1000:
        raise Error("RESOURCE_LIMIT")
    return raw, text, blocks, records


def save(root, relative, record, expected):
    raw, text, blocks, records = read_gist(root, relative)
    if raw != expected:
        raise Error("CONTENT_CONFLICT", path=relative)
    after = render_gist(raw, record)
    path = recovery.safe_path(root, relative)
    if recovery.bounded_bytes(path, recovery.MAX_PLAN_BYTES) != raw:
        raise Error("CONTENT_CONFLICT", path=relative)
    if after != raw:
        recovery.atomic_replace(path, after)
    return after


def render_gist(raw, record):
    raw, text, blocks, records = parse_gist(raw)
    records[record["operation_id"]] = record
    if len(records) > 1000:
        raise Error("RESOURCE_LIMIT")
    block = "```json\n" + json.dumps({"operations": list(records.values())}, ensure_ascii=False, indent=2) + "\n```"
    text = text[:blocks[0].start()] + block + text[blocks[0].end():] if blocks else text.rstrip() + "\n\n" + block + "\n"
    after = recovery.encode(text, raw)
    if len(after) > recovery.MAX_PLAN_BYTES:
        raise Error("RESOURCE_LIMIT")
    return after


def raw_snapshot(raw):
    return {"bytes": base64.b64encode(raw).decode(), "digest": recovery.digest(raw)}


def original(snapshot):
    raw = base64.b64decode(snapshot["bytes"], validate=True)
    if recovery.digest(raw) != snapshot["digest"]:
        raise Error("INVALID_INTENT")
    try:
        recovery.decode(raw)
    except Error:
        raise Error("INVALID_INTENT") from None
    return raw


def refs(root, record, overrides, git):
    status = recovery.decode(original(record["expected_source"]["documents"]["STATUS.md"]))
    repos = recovery.resolve_repositories(root, tc.repository_registry(status), overrides, git)
    target = record["target_identity"]
    repo = repos[target["repository"]]
    if (repo["actual_branch"] != target["branch"]
            or recovery.digest(repo["remote"].encode()) != target["remote_digest"]):
        raise Error("REF_MOVED")
    _, table = validate_record(root, record["intent_ref"], record)
    task_refs = [r for r in table if r["repository"] == target["repository"]]
    if len(task_refs) != 1:
        raise Error("INVALID_INTENT")
    previous = record["expected_source"]["head"]
    retained = tc.ref_tokens(task_refs[0]["start_refs"], ";") + tc.ref_tokens(task_refs[0]["baseline_history"], "<=")
    for _, sha in retained:
        if not git.commit_exists(Path(repo["path"]), sha):
            raise Error("MISSING_COMMIT")
        if not git.is_ancestor(Path(repo["path"]), sha, previous):
            raise Error("REF_MOVED")
    management = [Path(r["path"]) for r in repos.values() if r["role"] == "project-management"]
    management_sync = record['kind'] == 'review-master-sync' and target.get('role') == 'project-management'
    if (len(management) != 1 or repo['role'] != ('project-management' if management_sync else 'implementation')):
        raise Error("INVALID_REPOSITORY_SET")
    if management_sync:
        recorded_head = record['expected_source']['recorded_head']
        if not git.is_ancestor(Path(repo['path']), recorded_head, previous):
            raise Error('REF_MOVED')
    base = record["expected_source"]["management_head"]
    if not git.commit_exists(management[0], base) or not git.is_ancestor(management[0], base, git.run(management[0], "rev-parse", "HEAD")):
        raise Error("REF_MOVED")
    for relative, snapshot in record["expected_source"]["documents"].items():
        raw = original(snapshot)
        blob_path = recovery.safe_path(root, relative).relative_to(management[0]).as_posix()
        recorded = git.run(management[0], "show", f"{base}:{blob_path}")
        # Git may retain CRLF (-text) or normalize it via attributes. Compare
        # decoded text symmetrically; snapshots/CAS still use exact raw bytes.
        if recovery.decode(recorded.encode("utf-8")) != recovery.decode(raw).rstrip("\n"):
            raise Error("INVALID_INTENT", path=relative)
    allowed = {record["intent_ref"], ".operation.lock", *record["expected_source"]["documents"]}
    prefix = root.relative_to(management[0]).as_posix() + "/"
    for entry in git.run(management[0], "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0"):
        if management_sync:
            # The sync observer must inspect MERGE_HEAD before treating a
            # conflict as ordinary dirt; its own whole-repository guard follows.
            continue
        if not entry:
            continue
        if len(entry) < 4 or "R" in entry[:2] or "C" in entry[:2]:
            raise Error("UNOWNED_CHANGES")
        if entry[3:].startswith(prefix) and entry[3 + len(prefix):] not in allowed:
            raise Error("UNOWNED_CHANGES")
    gist_path = recovery.safe_path(root, record["intent_ref"]).relative_to(management[0]).as_posix()
    if git.run(management[0], "ls-files", "--error-unmatch", "--", gist_path, check=False) is None:
        raise Error("UNTRACKED_RECORD")
    return Path(repo["path"]), management[0]


def owned_state(repo, includes, git):
    entries = [e for e in git.run(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0") if e]
    if any(len(e) < 4 or "R" in e[:2] or "C" in e[:2] for e in entries):
        raise Error("UNOWNED_CHANGES")
    if {e[3:] for e in entries} != set(includes):
        raise Error("UNOWNED_CHANGES")
    return entries


def files_at_worktree(repo, includes, git):
    result = {}
    for name in includes:
        cp.safe_include(name)
        path = recovery.safe_path(repo, name)
        if path.is_dir():
            raise Error("UNSAFE_PATH")
        if not path.exists():
            result[name] = None
        else:
            result[name] = git.run(repo, "hash-object", "--path=" + name, "--", name)
    return result


def validate_record(root, gist, record):
    if (record["operation_version"] != "operation-v1" or record["kind"] not in {"commit", "review-master-sync"}
            or record["feature"] != root.name or record["intent_ref"] != gist):
        raise Error("INVALID_INTENT")
    documents = record["expected_source"]["documents"]
    status = recovery.decode(original(documents["STATUS.md"]))
    if tc.selected_task_id(status, None) != record["task"]:
        raise Error("INVALID_INTENT")
    detail_ref = f"tasks/{record['task']}.md"
    if set(documents) != {"STATUS.md", "TASKS.md", detail_ref}:
        raise Error("INVALID_INTENT")
    records = tc.task_records(recovery.decode(original(documents["TASKS.md"])))
    task = records[record["task"]]
    detail, table = tc.task_detail(root, task, text=recovery.decode(original(documents[detail_ref])))
    if task["state"] not in {"WIP", "RECORDING"} or gist not in dict(tc.declared_gist_paths(detail, root)):
        raise Error("INVALID_INTENT")
    repository = record["target_identity"]["repository"]
    management_sync = record['kind'] == 'review-master-sync' and record['target_identity'].get('role') == 'project-management'
    expected_head = record['expected_source']['recorded_head' if management_sync else 'head']
    if task["head_refs"].get(repository) != expected_head:
        raise Error("INVALID_INTENT")
    if record["kind"] == "review-master-sync":
        import review_sync
        review_sync.validate(record)
    elif len(record["owned_paths"]) != len(set(record["owned_paths"])) or not record["owned_paths"]:
        raise Error("INVALID_INTENT")
    if set(record["expected_source"]["files"]) != set(record["owned_paths"]):
        raise Error("INVALID_INTENT")
    for name in record["owned_paths"]:
        cp.safe_include(name)
    cp.safe_line(record["summary"], "summary")
    cp.safe_line(record["resume_action"], "resume action")
    cp.safe_line(record["authority_source_ref"], "authority source")
    cp.replace_detail_checkpoint(detail, repository, record["expected_source"]["head"], record["resume_action"], record["summary"])
    return detail_ref, table


def locate_commit(repo, record, git):
    if record["kind"] == "review-master-sync":
        import review_sync
        return review_sync.locate(repo, record, git)
    previous = record["expected_source"]["head"]
    head = git.run(repo, "rev-parse", "HEAD")
    if head == previous:
        return None
    if not git.is_ancestor(repo, previous, head):
        raise Error("REF_MOVED")
    commits = git.run(repo, "rev-list", f"--max-count={MAX_COMMITS + 1}", f"{previous}..{head}").splitlines()
    if len(commits) > MAX_COMMITS:
        raise Error("RESOURCE_LIMIT")
    trailer = "Operation-Id: " + record["operation_id"]
    matching = [sha for sha in commits if trailer in git.run(repo, "show", "-s", "--format=%B", sha).splitlines()]
    if len(matching) != 1 or matching[0] != head:
        raise Error("REF_MOVED")
    sha = matching[0]
    if (git.run(repo, "show", "-s", "--format=%P", sha) != previous
            or git.run(repo, "rev-parse", sha + "^{tree}") != record["expected_source"].get("tree")):
        raise Error("COMMIT_CONTENT_MISMATCH")
    changed = git.run(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", sha).split("\0")
    if {p for p in changed if p} != set(record["owned_paths"]):
        raise Error("COMMIT_CONTENT_MISMATCH")
    for name, blob in record["expected_source"]["files"].items():
        observed = git.run(repo, "rev-parse", "--verify", f"{sha}:{name}", check=False)
        if observed != blob:
            raise Error("COMMIT_CONTENT_MISMATCH")
    return sha


def desired(root, record, sha):
    repository, task = record["target_identity"]["repository"], record["task"]
    docs = record["expected_source"]["documents"]
    detail_ref = f"tasks/{task}.md"
    texts = {p: recovery.decode(original(s)) for p, s in docs.items()}
    detail = cp.replace_detail_checkpoint(texts[detail_ref], repository, sha, record["resume_action"], record["summary"])
    tasks = cp.replace_task_head(texts["TASKS.md"], task, repository, sha)
    rows = tc.focused_status(texts["STATUS.md"])["working_branches"]["rows"]
    rows = [row for row in rows if row[0] == repository]
    management_sync = record['kind'] == 'review-master-sync' and record['target_identity'].get('role') == 'project-management'
    expected_head = 'DERIVED:HEAD' if management_sync else record['expected_source']['head']
    if len(rows) != 1 or rows[0][3] != expected_head:
        raise Error("INVALID_INTENT")
    old = recovery.row_line(texts["STATUS.md"], rows[0])
    new = list(rows[0]); new[3] = 'DERIVED:HEAD' if management_sync else sha
    status = recovery.replace_operations(texts["STATUS.md"], [{"kind": "row", "old_value": old, "new_value": "| " + " | ".join(new) + " |"}])
    return {p: recovery.encode(text, original(docs[p])) for p, text in
            [(detail_ref, detail), ("TASKS.md", tasks), ("STATUS.md", status)]}


def reconcile(root, gist, operation_id, overrides=None, *, apply=False, authority=False, remote_reader=None):
    root = Path(root).resolve()
    result = dict(operation_id=operation_id, observed_result={"status": "unknown"},
                  next_check="inspect-conflicts", effect="NOT_APPLIED", recorded_fields=[], conflicts=[])
    try:
        if apply and authority is not True:
            raise Error("AUTHORITY_REQUIRED")
        _, _, _, records = read_gist(root, gist)
        if records[operation_id]['kind'] == 'review-publish':
            import review_publish
            if apply:
                with coordinator(root):
                    return review_publish.reconcile(root, gist, operation_id, overrides or {}, True)
            return review_publish.reconcile(root, gist, operation_id, overrides or {}, False)
        if records[operation_id]["kind"] == "dependency-rewire":
            import task_dependencies
            if apply:
                with coordinator(root):
                    return task_dependencies._reconcile_dependencies(root, gist, operation_id, overrides or {}, True)
            return task_dependencies._reconcile_dependencies(root, gist, operation_id, overrides or {}, False)
        if records[operation_id]["kind"] in {"save", "record"}:
            import file_operation
            if apply:
                with coordinator(root):
                    return file_operation.reconcile(root, gist, operation_id, overrides or {}, True)
            return file_operation.reconcile(root, gist, operation_id, overrides or {}, False)
        if records[operation_id]["kind"] == "remote-write":
            if apply:
                with coordinator(root):
                    return reconcile_remote(root, gist, operation_id, overrides or {}, remote_reader, True)
            return reconcile_remote(root, gist, operation_id, overrides or {}, remote_reader, False)
        if apply:
            with coordinator(root):
                return reconcile_locked(root, gist, operation_id, overrides or {}, result, True)
        return reconcile_locked(root, gist, operation_id, overrides or {}, result, False)
    except (Error, tc.ContextError, KeyError, ValueError, TypeError, OSError) as exc:
        result["conflicts"] = [exc.diagnostic if isinstance(exc, Error) else {"code": "INVALID_OPERATION_OR_IO"}]
        if result["recorded_fields"]:
            result["effect"] = "PARTIAL"
        return result


def reconcile_remote(root, gist, operation_id, overrides, reader, write):
    from remote_lookup import inspect_remote
    raw, _, _, records = read_gist(root, gist)
    record = records[operation_id]
    required = {"operation_version", "operation_id", "kind", "feature", "task", "authority_source_ref",
                "target_identity", "expected_source", "owned_paths", "intent_ref", "observed_result", "recorded_fields"}
    if (not required.issubset(record) or record["feature"] != root.name or record["intent_ref"] != gist
            or record["kind"] != "remote-write" or record["owned_paths"]):
        raise Error("INVALID_REMOTE_INTENT")
    cp.safe_line(record["authority_source_ref"], "authority source")
    plan = recovery.inspect(root, overrides, plan_gist=gist, _allowed_dirty=(".operation.lock",))
    if not plan["complete"] or plan["edits"] or plan["task_id"] != record["task"]:
        raise Error("RECOVERY_REQUIRED", blockers=plan["blockers"])
    result = inspect_remote(record, reader)
    if result["conflicts"] or not write:
        return result
    for relative, expected in plan["read_set"].items():
        if recovery.digest(recovery.bounded_bytes(recovery.safe_path(root, relative))) != expected:
            raise Error("SOURCE_CHANGED", path=relative)
    recovery.verify_observations(plan, recovery.GitProbe())
    # This records current readback, never an invented receipt of the old call.
    record.setdefault("initial_observed_result", record["observed_result"])
    record["observed_result"] = result["observed_result"]
    record["recorded_fields"] = list(dict.fromkeys([*record["recorded_fields"], "observed_result"]))
    if save(root, gist, record, raw) != raw:
        result["effect"] = "APPLIED"
        result["recorded_fields"] = [gist + "#observed_result"]
    else:
        result["effect"] = "UNCHANGED"
    result["next_check"] = "commit-management-then-task-context"
    return result


def reconcile_locked(root, gist, operation_id, overrides, result, write):
    raw, _, _, records = read_gist(root, gist)
    record = records[operation_id]
    detail_ref, _ = validate_record(root, gist, record)
    git = recovery.GitProbe()
    repo, pm = refs(root, record, overrides, git)
    sha = locate_commit(repo, record, git)
    if sha is None:
        if record['kind'] == 'review-master-sync':
            result.update(observed_result={"status": "unknown" if record['dispatched'] else "not-observed"},
                          next_check="inspect-git-no-replay" if record['dispatched'] else "resume-authorized-review-sync")
            return result
        result.update(observed_result={"status": "not-observed"}, next_check="resume-authorized-checkpoint")
        return result
    management_sync = record['kind'] == 'review-master-sync' and record['target_identity'].get('role') == 'project-management'
    observed_head = git.run(repo, 'rev-parse', 'HEAD')
    if management_sync:
        import review_sync_management as management
        management.clean(root, repo, record, metadata=True, journal=True)
    elif git.run(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise Error("UNOWNED_CHANGES")
    result["observed_result"] = {"status": "success", "commit_sha": sha}
    targets = desired(root, record, sha)
    for path, target in targets.items():
        current = recovery.bounded_bytes(recovery.safe_path(root, path))
        if current not in (original(record["expected_source"]["documents"][path]), target):
            raise Error("CONTENT_CONFLICT", path=path)
    if not write:
        result["next_check"] = "authorized-record-only"
        return result
    record["observed_result"] = result["observed_result"]
    updated = save(root, gist, record, raw)
    if updated != raw:
        result["recorded_fields"].append(gist + "#observed_result")
    raw = updated
    for index, (relative, target) in enumerate(targets.items()):
        path = recovery.safe_path(root, relative)
        current = recovery.bounded_bytes(path)
        if current != target:
            if current != original(record["expected_source"]["documents"][relative]):
                raise Error("CONTENT_CONFLICT", path=relative)
            recovery.atomic_replace(path, target)
            result["recorded_fields"].append(relative)
        interruption_point("after-detail" if index == 0 else "after-index" if index == 1 else "after-status")
    if git.run(repo, "rev-parse", "HEAD") != (observed_head if management_sync else sha):
        raise Error("REF_MOVED")
    record["recorded_fields"] = list(targets)
    if save(root, gist, record, raw) != raw:
        result["recorded_fields"].append(gist + "#recorded_fields")
    git.remaining()
    result.update(effect="APPLIED" if result["recorded_fields"] else "UNCHANGED", next_check="commit-management-then-task-context")
    if record['kind'] == 'review-master-sync':
        result['next_check'] = 'commit-management-then-recheck-review-source-and-target-samples'
    return result


def checkpoint(args):
    root = Path(args.feature_directory).resolve()
    gist = args.operation_gist
    overrides = tc.parse_repo_overrides(args.repo)
    authority = cp.safe_line(args.authority_source_ref or "", "authority source")
    try:
        with coordinator(root):
            return checkpoint_locked(root, gist, overrides, args, authority)
    except subprocess.SubprocessError:
        raise tc.ContextError("CHECKPOINT_GIT_OUTCOME_REQUIRES_RECONCILIATION") from None
    except (Error, KeyError, ValueError, TypeError, OSError) as exc:
        raise tc.ContextError(str(exc)) from None


def checkpoint_locked(root, gist, overrides, args, authority):
    raw, _, _, records = read_gist(root, gist)
    git = recovery.GitProbe()
    if args.operation_id:
        record = records[args.operation_id]
        validate_record(root, gist, record)
        if (record["task"] != args.task_id or record["target_identity"]["repository"] != args.repository
                or record["owned_paths"] != args.include or record["summary"] != args.summary
                or record["resume_action"] != args.resume_action):
            raise Error("INTENT_MISMATCH")
        repo, _ = refs(root, record, overrides, git)
        if locate_commit(repo, record, git):
            result = dict(recorded_fields=[])
            reconcile_locked(root, gist, record["operation_id"], overrides, result, True)
            return result["observed_result"]["commit_sha"]
    else:
        status_raw = recovery.bounded_bytes(recovery.safe_path(root, "STATUS.md"))
        resolved = recovery.resolve_repositories(root, tc.repository_registry(recovery.decode(status_raw)), overrides, git)
        target = resolved[args.repository]
        if any(recovery.public_remote(r["remote"]) != r["remote"] for r in resolved.values()):
            raise Error("CREDENTIAL_BEARING_SOURCE")
        repo = Path(target["path"])
        management = [Path(r["path"]) for r in resolved.values() if r["role"] == "project-management"]
        if len(management) != 1 or target["role"] != "implementation":
            raise Error("INVALID_REPOSITORY_SET")
        pm = management[0]
        documents = {p: raw_snapshot(recovery.bounded_bytes(recovery.safe_path(root, p))) for p in
                     ("STATUS.md", "TASKS.md", f"tasks/{args.task_id}.md")}
        record = dict(operation_version="operation-v1", operation_id=str(uuid.uuid4()), kind="commit",
                      feature=root.name, task=args.task_id, authority_source_ref=authority,
                      target_identity=dict(repository=args.repository, branch=target["actual_branch"], remote_digest=recovery.digest(target["remote"].encode())),
                      expected_source=dict(head=git.run(repo, "rev-parse", "HEAD"), management_head=git.run(pm, "rev-parse", "HEAD"), documents=documents),
                      owned_paths=args.include, intent_ref=gist, summary=cp.safe_line(args.summary, "summary"),
                      resume_action=cp.safe_line(args.resume_action, "resume action"), observed_result={"status": "not-observed"}, recorded_fields=[])
        record["expected_source"]["files"] = files_at_worktree(repo, args.include, git)
        validate_record(root, gist, record)
        desired(root, record, record["expected_source"]["head"])
        refs(root, record, overrides, git)
        if any(e[0] not in {" ", "?"} for e in owned_state(repo, args.include, git)):
            raise Error("PRESTAGED_CHANGES")
        gist_path = recovery.safe_path(root, gist).relative_to(pm).as_posix()
        if git.run(pm, "ls-files", "--error-unmatch", "--", gist_path, check=False) is None:
            raise Error("UNTRACKED_RECORD")
        raw = save(root, gist, record, raw)
    owned_state(repo, args.include, git)
    if files_at_worktree(repo, args.include, git) != record["expected_source"]["files"]:
        raise Error("CONTENT_CONFLICT")
    staged = [p for p in git.run(repo, "diff", "--cached", "--name-only", "-z").split("\0") if p]
    for name in staged:
        if name not in record["expected_source"]["files"]:
            raise Error("UNOWNED_CHANGES")
        blob = git.run(repo, "rev-parse", "--verify", ":" + name, check=False)
        if blob != record["expected_source"]["files"][name]:
            raise Error("CONTENT_CONFLICT")
    if record["expected_source"].get("tree"):
        index_tree = git.run(repo, "write-tree")
        old_tree = git.run(repo, "rev-parse", record["expected_source"]["head"] + "^{tree}")
        if index_tree not in {old_tree, record["expected_source"]["tree"]}:
            raise Error("CONTENT_CONFLICT")
    subprocess.run(["git", "-C", str(repo), "add", "--", *args.include], check=True, capture_output=True, timeout=10)
    tree = git.run(repo, "write-tree")
    if record["expected_source"].get("tree", tree) != tree:
        raise Error("CONTENT_CONFLICT")
    record["expected_source"]["tree"] = tree
    raw = save(root, gist, record, raw)
    interruption_point("before-commit")
    message = f"{root.name}/{args.task_id}: checkpoint {record['summary']}\n\nOperation-Id: {record['operation_id']}"
    subprocess.run(["git", "-C", str(repo), "commit", "-m", message], check=True, capture_output=True, timeout=10)
    interruption_point("after-commit")
    result = dict(recorded_fields=[])
    reconcile_locked(root, gist, record["operation_id"], overrides, result, True)
    return result["observed_result"]["commit_sha"]
