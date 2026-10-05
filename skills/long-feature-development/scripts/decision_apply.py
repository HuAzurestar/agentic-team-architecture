#!/usr/bin/env python3
"""Exact local point application with durable dispatch/readback, no task closure.

This is the point-document leg of the coordinator. It deliberately reports
APPLIED_PENDING_STATUS until a separate task-state/status commit is recorded.
"""
import hashlib
from copy import deepcopy
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from decision_commit import PointCommit, CommitError, git, require
from decision_evidence import canonical, ID, POINT
from context_loader import LocalMarkdownLoader
from quality_source import SHA
import task_context as tc


def references(feature, point_id, digest):
    require(isinstance(feature, str) and ID.fullmatch(feature)
            and isinstance(point_id, str) and POINT.fullmatch(point_id)
            and isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest),
            "INVALID_POINT_APPLICATION")
    key = hashlib.sha256(canonical(dict(feature=feature, point_id=point_id, decision_digest=digest))).hexdigest()
    return "refs/lfd/point-decisions/" + key, "refs/lfd/point-applications/" + key


def read_ref(repo, ref):
    code, raw = git(repo, "rev-parse", "--verify", "--quiet", ref, accepted=(0, 1))
    if code:
        return None
    sha = raw.decode("ascii").strip()
    require(SHA.fullmatch(sha), "POINT_REF_CONFLICT")
    return sha


def observe_application(root, repository, point_id, digest):
    """Read-only facts, usable after a new process starts or task recovery fails.

    The configured root/repository identify the actual local scope. A ref or
    commit body is NOT authentication or permission to complete a task.
    """
    root, repo = Path(root).resolve(strict=True), Path(repository).resolve(strict=True)
    require(root.is_relative_to(repo) and root != repo, "POINT_REPOSITORY_MISMATCH")
    actual = Path(git(repo, "rev-parse", "--show-toplevel")[1].decode("utf-8").strip()).resolve()
    require(actual == repo, "POINT_REPOSITORY_MISMATCH")
    retained, dispatch = references(root.name, point_id, digest)
    candidate, sent = read_ref(repo, retained), read_ref(repo, dispatch)
    result = dict(effect="NOT_APPLIED", status="NOT_PREPARED", commit=candidate,
                  task_status_recorded=False, merge_authorized=False, dispatch_ref=dispatch)
    if candidate is None:
        require(sent is None, "POINT_REF_CONFLICT")
        return result
    require(sent in (None, candidate), "POINT_REF_CONFLICT")
    parents = git(repo, "show", "-s", "--format=%P", candidate)[1].decode().split()
    require(len(parents) == 1 and SHA.fullmatch(parents[0]), "POINT_REF_CONFLICT")
    base = parents[0]
    message = git(repo, "show", "-s", "--format=%B", candidate)[1].decode("utf-8")
    require(re.match(re.escape(root.name + "/" + point_id) +
                     r": (CONFIRMED|REJECTED|OUT-OF-SCOPE|INFEASIBLE|REOPENED) record human decision\n", message)
            and ("Decision-Digest: " + digest) in message.splitlines()
            and ("Prepared-From: " + base) in message.splitlines(), "POINT_REF_CONFLICT")
    document = "REQUIREMENT.md" if point_id.startswith("REQ-") else "SOLUTION.md"
    relative = (root / document).relative_to(repo).as_posix()
    require(git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", base, candidate)[1]
            == relative.encode("utf-8") + b"\0", "POINT_COMMIT_SCOPE_MISMATCH")
    head = git(repo, "rev-parse", "HEAD")[1].decode().strip()
    result.update(base=base, head=head)
    if head == base:
        result["status"] = "DISPATCHED_UNCONFIRMED" if sent else "PREPARED"
        if sent:
            result["effect"] = "UNKNOWN"
        return result
    if git(repo, "merge-base", "--is-ancestor", candidate, head, accepted=(0, 1))[0]:
        result["status"] = "HEAD_DIVERGED"
        result["effect"] = "UNKNOWN"
        return result
    entry = git(repo, "ls-tree", "-z", candidate, "--", relative)[1]
    header, name = entry.rstrip(b"\0").split(b"\t")
    mode, kind, blob = header.split()
    require(mode in (b"100644", b"100755") and kind == b"blob" and name == relative.encode(), "UNSAFE_PATH")
    expected_index = mode + b" " + blob + b" 0\t" + name + b"\0"
    current_entry = git(repo, "ls-tree", "-z", head, "--", relative)[1]
    index = git(repo, "ls-files", "--stage", "-z", "--", relative)[1]
    flags = git(repo, "ls-files", "-v", "-z", "--", relative)[1]
    if current_entry != entry or index != expected_index or not flags.startswith(b"H "):
        result["status"] = "APPLICATION_CONFLICT"
        result["effect"] = "CONFLICT"
        return result
    loader = LocalMarkdownLoader(root)
    working, identity = loader._read_raw(document, 4 * 1024 * 1024)
    require(loader._path(document).stat().st_nlink == 1, "UNSAFE_PATH")
    committed = git(repo, "cat-file", "blob", blob.decode())[1]
    if working.replace(b"\r\n", b"\n") != committed.replace(b"\r\n", b"\n"):
        result["status"] = "APPLICATION_CONFLICT"
        result["effect"] = "CONFLICT"
        return result
    # Re-observe after reading; no cached success across moving source/refs.
    again, next_identity = loader._read_raw(document, len(working))
    require((again, next_identity) == (working, identity)
            and loader._path(document).stat().st_nlink == 1
            and git(repo, "rev-parse", "HEAD")[1].decode().strip() == head
            and git(repo, "ls-files", "--stage", "-z", "--", relative)[1] == index
            and git(repo, "ls-files", "-v", "-z", "--", relative)[1] == flags
            and read_ref(repo, retained) == candidate and read_ref(repo, dispatch) == sent,
            "POINT_SOURCE_CHANGED")
    result.update(effect="APPLIED", status="APPLIED_PENDING_STATUS")
    return result


def apply_point(operation):
    """Apply one freshly authorized candidate once; read back ambiguous outcomes.

    Normal Git fast-forward protects differing working files; no hard reset,
    checkout overwrite, autostash, push, general merge or task-state write occurs.
    Arbitrary concurrent external writers are not locked by this coordinator.
    A prior dispatch without a confirmed result is never automatically retried.
    """
    require(type(operation) is PointCommit, "INVALID_POINT_APPLICATION")
    # Refuse a transition whose following task-state write is already known to
    # violate dependency rules. Never silently alter assigned downstream tasks.
    records = deepcopy(operation.feature.records)
    records[operation.request.point_id]["state"] = (
        "WIP" if operation.record["outcome"] == "REOPENED" else "RECORDING")
    try:
        tc.validate_dependency_graph(records)
    except tc.ContextError:
        raise CommitError("POINT_TASK_GRAPH_RECONCILIATION_REQUIRED") from None
    prepared = operation.prepare_commit()
    root, repo, request = operation.root, operation.repo, operation.request
    def observe():
        return observe_application(root, repo, request.point_id, request.decision_digest)
    initial = observe()
    require(initial["commit"] == prepared["commit"], "POINT_REF_CONFLICT")
    if initial["status"] != "PREPARED":
        return initial
    operation._verify()
    dispatch = initial["dispatch_ref"]
    try:
        git(repo, "update-ref", dispatch, prepared["commit"], "0" * len(prepared["commit"]))
    except CommitError:
        # A competing coordinator or response loss may already have dispatched.
        # Only observation is allowed; never follow an uncertain marker write
        # with another application attempt.
        return observe()
    operation._verify()
    require(read_ref(repo, prepared["retained_ref"]) == prepared["commit"], "POINT_REF_CONFLICT")
    require(git(repo, "rev-parse", "HEAD")[1].decode().strip() == prepared["base"], "POINT_SOURCE_CHANGED")
    try:
        git(repo, "merge", "--ff-only", "--no-edit", "--no-stat", "--no-autostash", prepared["commit"])
    except CommitError:
        return observe()
    return observe()
