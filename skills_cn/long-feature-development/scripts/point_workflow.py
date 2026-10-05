#!/usr/bin/env python3
"""Host point workflow: exact decision commit, status followup and readback.

No provider callbacks are deserialized; the real host supplies them. This API
does not grant push/merge authority, rewrite dependencies or resolve conflicts.
"""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from decision_commit import PointCommit, require
from decision_apply import apply_point, observe_application, read_ref
from decision_status import PointStatus, observe_status, status_refs
from decision_evidence import canonical, decision_digest


def envelope(point, status=None):
    completed = status is not None and status["status"] == "STATUS_RECORDED"
    if completed:
        phase, action = "RECORDED", "NONE"
    elif status is not None:
        phase, action = status["status"], "INSPECT_STATUS_RESULT"
    elif point["status"] == "APPLIED_PENDING_STATUS":
        phase, action = "APPLIED_PENDING_STATUS", "RECORD_POINT_STATUS"
    else:
        phase, action = point["status"], "INSPECT_POINT_RESULT"
    return dict(phase=phase, complete=completed, required_next_action=action,
                decision_commit=point.get("commit"), status_commit=(status or {}).get("status_commit"),
                point_observation=point, status_observation=status, blockers=[],
                merge_authorized=False, publication_performed=False)


def run_point(root, repository, point_id, record, *, source_key, read_reply,
              interpret, read_grant, repo_overrides=None, next_status=None, recorded_at=None):
    """Apply/continue one explicitly requested decision; never retry unknown effects.

    A completed operation returns freshly checked local facts without re-reading
    a human reply: it performs no new write. Every actual write uses the existing
    fresh source/grant checks. A caller still supplies its own authorization.
    """
    digest = decision_digest(record)
    record = json.loads(canonical(record))
    root, repo = Path(root).resolve(strict=True), Path(repository).resolve(strict=True)
    require(record["feature"] == root.name and record["decision_kind"] == "point"
            and record["exact_scope"] == [point_id], "POINT_SCOPE_MISMATCH")
    require(record["target_ref"]["source_key"] == source_key
            and record["target_ref"]["version_kind"] == "git", "POINT_SOURCE_MISMATCH")
    options = dict(source_key=source_key, read_reply=read_reply, interpret=interpret,
                   read_grant=read_grant, repo_overrides=repo_overrides)
    point = observe_application(root, repo, point_id, digest)
    retained, dispatched = status_refs(root.name, point_id, digest)
    status_candidate, status_sent = read_ref(repo, retained), read_ref(repo, dispatched)
    if point["status"] in {"NOT_PREPARED", "PREPARED"}:
        require(status_candidate is None and status_sent is None, "STATUS_WITHOUT_APPLIED_POINT")
        operation = PointCommit(root, point_id, record, **options)
        require(operation.repo == repo, "POINT_REPOSITORY_MISMATCH")
        # Refuse before either commit is applied; do not silently reset/rewrite
        # assigned consumers or transfer their old completion to a new attempt.
        blockers = []
        if record["outcome"] == "REOPENED":
            blockers = [dict(task_id=key, state=value["state"], dependency=point_id)
                        for key, value in operation.feature.records.items()
                        if point_id in value["dependencies"] and value["state"] != "PENDING"]
        if blockers:
            result = envelope(point)
            result.update(phase="DEPENDENCY_COORDINATION_REQUIRED",
                          required_next_action="RESOLVE_ASSIGNED_CONSUMER_ATTEMPTS",
                          blockers=sorted(blockers, key=lambda item: item["task_id"]))
            return result
        point = apply_point(operation)
    if point["status"] != "APPLIED_PENDING_STATUS":
        return envelope(point)
    # Refresh refs after application. Their presence never proves human authority.
    status_candidate, status_sent = read_ref(repo, retained), read_ref(repo, dispatched)
    require(status_candidate is not None or status_sent is None, "STATUS_REF_CONFLICT")
    if status_candidate is not None:
        observed = observe_status(root, repo, point_id, digest, repo_overrides)
        if observed["status"] != "STATUS_PREPARED":
            return envelope(point, observed)
    operation = PointStatus(root, repo, point_id, digest, **options,
                            next_status=next_status, recorded_at=recorded_at)
    status = operation.apply()
    return envelope(observe_application(root, repo, point_id, digest), status)
