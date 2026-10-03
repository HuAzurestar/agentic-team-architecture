#!/usr/bin/env python3
"""Bounded, read-only next-action selection. See references/selection.md.

Inputs are already validated, normalized facts supplied by the coordinator.
This module neither reads Markdown nor authenticates host permissions. In particular,
constructing an Authorization from a document that says "approved" is invalid.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import re
import time
from typing import Mapping
import quality_policy as quality

MAX_TASKS = 10_000
MAX_EDGES = 30_000
MAX_SECONDS = 2.0
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
STATES = {"PENDING", "WIP", "RECORDING", "BLOCKED", "DONE"}
OPERATIONS = {"work", "rework", "retest", "rereview", "accept", "gate", "merge", "publish"}
PRIORITY = {"rework", "retest", "rereview"}
CAPABILITY = {"merge": "merge", "publish": "publish", "accept": "request-acceptance"}
VERDICTS = {"ready", "wait-human", "wait-external", "repair-plan"}


@dataclass(frozen=True)
class Task:
    id: str
    state: str
    dependencies: tuple[str, ...] = ()
    kind: str = "Development"
    contract: Mapping[str, str] = field(default_factory=dict)
    release_condition: str = ""


@dataclass(frozen=True)
class ValidatedContext:
    # source_ref binds the full validated plan/read-set AND actual repository refs.
    source_ref: str
    current_task: str
    current_gate: str
    tasks: tuple[Task, ...]


@dataclass(frozen=True)
class Grant:
    # Explicit host classification: Development does NOT imply permission to merge.
    operation: str
    capabilities: frozenset[str]
    authority_ref: str
    outside_scope: bool = False


@dataclass(frozen=True)
class Authorization:
    source_ref: str
    grants: Mapping[str, Grant] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityInputs:
    """Host-only complete policy inputs, never parsed from a ready JSON claim.

    source_ref binds the selection read set. feature and observations must come
    from actual validated sources and separately verified host facts. The selector
    recomputes policy, not a caller-provided allowed flag. This is not authority.
    """
    source_ref: str
    task_id: str
    feature: object
    request: dict
    observations: object
    report_evidence: object = None
    decision_sources: object = None


@dataclass(frozen=True)
class GateEvidence:
    # ready means the host checked applicable quality, budget, external contracts
    # and target scope, not merely that dependencies were marked DONE.
    verdict: str
    evidence_refs: tuple[str, ...]
    target_sha: str = ""
    acceptance_task: str | None = None
    release_condition: str = ""
    release_satisfied: bool = False
    quality_inputs: QualityInputs | None = None


@dataclass(frozen=True)
class ObservedGateEvidence:
    source_ref: str
    tasks: Mapping[str, GateEvidence] = field(default_factory=dict)


@dataclass(frozen=True)
class NextAction:
    action: str
    task_id: str | None
    reason_code: str
    evidence_refs: tuple[str, ...] = ()
    required_authority: tuple[str, ...] = ()


class _Diagnostic(Exception):
    def __init__(self, code: str):
        self.code = code


def _check_time(start: float) -> None:
    if time.monotonic() - start >= MAX_SECONDS:
        raise _Diagnostic("RESOURCE_LIMIT")


def _refs(refs: tuple[str, ...]) -> bool:
    return (isinstance(refs, tuple) and 0 < len(refs) <= 32
            and all(isinstance(ref, str) and 0 < len(ref) <= 1024 for ref in refs))


def _graph(context: ValidatedContext, start: float):
    if not isinstance(context.tasks, tuple) or not context.tasks:
        raise _Diagnostic("INVALID_GRAPH")
    if len(context.tasks) > MAX_TASKS:
        raise _Diagnostic("RESOURCE_LIMIT")
    records = {}
    edge_count = 0
    for task in context.tasks:
        _check_time(start)
        if (not isinstance(task, Task) or not isinstance(task.id, str)
                or not ID.fullmatch(task.id) or task.id in records
                or task.state not in STATES or not isinstance(task.dependencies, tuple)):
            raise _Diagnostic("INVALID_GRAPH")
        edge_count += len(task.dependencies)
        if edge_count > MAX_EDGES:
            raise _Diagnostic("RESOURCE_LIMIT")
        if any(not isinstance(dep, str) or not ID.fullmatch(dep) for dep in task.dependencies):
            raise _Diagnostic("INVALID_GRAPH")
        if len(set(task.dependencies)) != len(task.dependencies):
            raise _Diagnostic("INVALID_GRAPH")
        records[task.id] = task
    if context.current_task not in records or context.current_gate not in records:
        raise _Diagnostic("INVALID_GRAPH")
    if records[context.current_gate].kind != "Gate":
        raise _Diagnostic("INVALID_GRAPH")
    dependents = {key: [] for key in records}
    degrees = {}
    for task in records.values():
        _check_time(start)
        degrees[task.id] = len(task.dependencies)
        for dep in task.dependencies:
            if dep not in records:
                raise _Diagnostic("INVALID_GRAPH")
            dependents[dep].append(task.id)
    queue = deque(key for key, degree in degrees.items() if degree == 0)
    visited = 0
    while queue:
        _check_time(start)
        key = queue.popleft()
        visited += 1
        for child in dependents[key]:
            degrees[child] -= 1
            if degrees[child] == 0:
                queue.append(child)
    if visited != len(records):
        raise _Diagnostic("INVALID_GRAPH")
    required = set()
    queue = deque([context.current_gate])
    while queue:
        _check_time(start)
        key = queue.popleft()
        if key not in required:
            required.add(key)
            queue.extend(records[key].dependencies)
    return records, required


def _contract_failure(task: Task) -> str | None:
    """A DONE process record is not a successful test/review/acceptance."""
    contract = task.contract
    if task.kind == "Acceptance":
        if contract.get("Decision") != "CONFIRMED":
            return "ACCEPTANCE_NOT_CONFIRMED"
    elif task.kind == "Test":
        # Unknown, skipped and zero executed checks cannot be inferred as passing.
        values = []
        for key in ("Executed", "Passed", "Failed", "Skipped", "Unknown"):
            value = contract.get(key, "")
            if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,9}", value):
                return "TEST_EVIDENCE_INCOMPLETE"
            values.append(int(value))
        executed, passed, failed, skipped, unknown = values
        if failed:
            return "TEST_FAILED"
        if not executed or passed != executed or skipped or unknown:
            return "TEST_EVIDENCE_INCOMPLETE"
    elif task.kind == "Review":
        if contract.get("Blocking findings") != "0":
            return "REVIEW_NOT_CLEAR"
    elif task.kind == "Gate":
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", contract.get("Decision ref", "")):
            return "GATE_EVIDENCE_MISSING"
    return None


def _quality_failure(task, operation, evidence, records, source_ref):
    phase = ('pre_accept' if operation == 'accept' else
             'pre_merge' if operation in {'merge', 'publish'} else
             'post_merge' if operation == 'gate' and task.contract.get('To phase') == 'DONE' else None)
    if phase is None:
        return None
    inputs = evidence.quality_inputs
    if inputs is None:
        return 'LEGACY_EVIDENCE_INCOMPLETE'
    if type(inputs) is not QualityInputs:
        return 'QUALITY_SOURCES_UNVERIFIED'
    if inputs.source_ref != source_ref or inputs.task_id != task.id:
        return 'STALE_QUALITY_INPUT'
    feature = inputs.feature
    if type(feature) is not quality.tc.ValidatedFeature:
        return 'VALIDATED_FEATURE_REQUIRED'
    # A valid report from another plan cannot be attached to this selection.
    if (not isinstance(feature.records, Mapping) or not isinstance(feature.type_contracts, Mapping)
            or set(feature.records) != set(records)):
        return 'QUALITY_PLAN_MISMATCH'
    for key, record in records.items():
        actual = feature.records[key]
        if not isinstance(actual, Mapping) or not isinstance(actual.get('dependencies', ()), (tuple, list)):
            return 'QUALITY_PLAN_MISMATCH'
        kind = {'TEST': 'Test', 'REVIEW': 'Review', 'REWORK': 'Rework',
                'ACCEPT': 'Acceptance', 'GATE': 'Gate'}.get(key.split('-')[0], actual.get('type'))
        if (actual.get('state') != record.state or kind != record.kind
                or tuple(actual.get('dependencies', ())) != record.dependencies
                or feature.type_contracts.get(key, {}) != record.contract):
            return 'QUALITY_PLAN_MISMATCH'
    if not isinstance(inputs.request, dict) or inputs.request.get('phase') != phase:
        return 'QUALITY_PHASE_MISMATCH'
    result = quality.assess_quality(feature, inputs.request, observed=inputs.observations,
        report_evidence=inputs.report_evidence, decision_sources=inputs.decision_sources)
    if result['allowed'] is not True:
        return result['reason_codes'][0] if result['reason_codes'] else 'QUALITY_NOT_ELIGIBLE'
    # Legacy single-target summary must at least identify an accepted source;
    # the policy above checks the complete vector and post-merge correspondence.
    if phase != 'pre_accept' and evidence.target_sha not in inputs.request['target_refs'].values():
        return 'QUALITY_TARGET_MISMATCH'
    return None


def _candidate(task, action, records, required, authorization, observations):
    grant = authorization.grants.get(task.id)
    if not isinstance(grant, Grant) or grant.operation not in OPERATIONS:
        return NextAction("wait-human", task.id, "AUTHORITY_MISSING",
                          required_authority=("classify-operation", "execute"))
    if not isinstance(grant.authority_ref, str) or not grant.authority_ref.strip():
        return NextAction("wait-human", task.id, "AUTHORITY_MISSING",
                          required_authority=("host-authority-reference",))
    if task.id not in required and grant.outside_scope is not True:
        return NextAction("stop-scope", task.id, "OUTSIDE_GATE_SCOPE")
    # An acceptance task only requests/presents a decision. No capability allows
    # the selector to manufacture a human decision or complete the task.
    expected = {"Acceptance": "accept", "Gate": "gate", "Rework": "rework"}.get(task.kind)
    if expected and grant.operation != expected:
        return NextAction("repair-plan", task.id, "OPERATION_KIND_MISMATCH")
    needed = ("execute", CAPABILITY[grant.operation]) if grant.operation in CAPABILITY else ("execute",)
    missing = tuple(key for key in needed if key not in grant.capabilities)
    if missing:
        return NextAction("wait-human", task.id, "AUTHORITY_MISSING",
                          (grant.authority_ref,), missing)
    evidence = observations.tasks.get(task.id)
    if (not isinstance(evidence, GateEvidence) or evidence.verdict not in VERDICTS
            or not _refs(evidence.evidence_refs)):
        return NextAction("wait-external", task.id, "EVIDENCE_MISSING")
    refs = (grant.authority_ref, *evidence.evidence_refs)
    if evidence.verdict != "ready":
        codes = {"wait-human": "HUMAN_REQUIRED", "wait-external": "EXTERNAL_REQUIRED",
                 "repair-plan": "PLAN_REPAIR_REQUIRED"}
        return NextAction(evidence.verdict, task.id, codes[evidence.verdict], refs)
    if task.state == "BLOCKED" and (
            not task.release_condition or evidence.release_satisfied is not True
            or evidence.release_condition != task.release_condition):
        return NextAction("wait-external", task.id, "RELEASE_UNPROVEN", refs)
    # A rework/retest/rereview may consume a negative result. It is not delivery.
    # Host evidence must independently assess transitive quality and applicability;
    # direct contradictions are never hidden by a positive summary.
    if grant.operation not in PRIORITY:
        for dep in task.dependencies:
            failure = _contract_failure(records[dep])
            if failure:
                return NextAction("wait-human", task.id, failure, refs)
    needs_acceptance = (grant.operation in {"merge", "publish"}
                        or (grant.operation == "gate" and task.contract.get("To phase") == "DONE"))
    if needs_acceptance:
        acceptance = records.get(evidence.acceptance_task)
        if acceptance is None or acceptance.kind != "Acceptance" or acceptance.id not in required:
            return NextAction("repair-plan", task.id, "ACCEPTANCE_TASK_MISSING", refs)
        if acceptance.state != "DONE" or _contract_failure(acceptance):
            return NextAction("wait-human", task.id, "ACCEPTANCE_NOT_CONFIRMED", refs)
        if (not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", evidence.target_sha)
                or acceptance.contract.get("Target SHA") != evidence.target_sha):
            return NextAction("wait-human", task.id, "ACCEPTANCE_TARGET_MISMATCH", refs)
    failure = _quality_failure(task, grant.operation, evidence, records, observations.source_ref)
    if failure:
        return NextAction('wait-external', task.id, failure, refs)
    return NextAction(action, task.id, "CURRENT_UNFINISHED" if action == "resume"
                      else "LEGAL_CANDIDATE", refs)


def _select(validated_context: ValidatedContext, authorization: Authorization,
            observed_gate_evidence: ObservedGateEvidence, start: float,
            metrics: list[int]) -> NextAction:
    """Return at most one suggestion, never permission or a task-state mutation.

    Whole-graph validation runs before choosing even the current task. Inputs must
    come from the strict reader and actual host authority/evidence, not arbitrary
    JSON with a 'validated' label. Callers must recheck the same source_ref before
    using the existing task_state writer. An action is NOT a merge/push command.
    """
    try:
        context = validated_context
        records, required = _graph(context, start)
        if (not isinstance(context.source_ref, str) or not context.source_ref
                or authorization.source_ref != context.source_ref
                or observed_gate_evidence.source_ref != context.source_ref):
            return NextAction("repair-plan", None, "STALE_INPUT")
        current = records[context.current_task]
        if current.state in {"WIP", "RECORDING", "BLOCKED"}:
            metrics[0] = 1
            if any(records[dep].state != "DONE" for dep in current.dependencies):
                return NextAction("repair-plan", current.id, "ACTIVE_DEPENDENCY_UNFINISHED")
            result = _candidate(current, "resume", records, required, authorization,
                                observed_gate_evidence)
            _check_time(start)
            return result
        # Do not silently replace some other assigned work by a new assignment.
        if any(task.state in {"WIP", "RECORDING"} and task.id in required
               for task in records.values()):
            return NextAction("repair-plan", None, "CURRENT_TASK_MISMATCH")
        priority, ordinary = [], []
        blocked = []
        for task in records.values():
            _check_time(start)
            grant = authorization.grants.get(task.id)
            if task.id not in required and not (isinstance(grant, Grant) and grant.outside_scope is True):
                continue
            if task.state == "BLOCKED":
                blocked.append(task)
            elif task.state == "PENDING" and all(records[dep].state == "DONE" for dep in task.dependencies):
                (priority if isinstance(grant, Grant) and grant.operation in PRIORITY
                 else ordinary).append(task)
        first_diagnostic = None
        metrics[0] = len(priority) + len(ordinary)
        for task in (*priority, *ordinary):
            _check_time(start)
            result = _candidate(task, "assign", records, required, authorization,
                                observed_gate_evidence)
            if result.action == "assign":
                _check_time(start)
                return result
            if first_diagnostic is None:
                first_diagnostic = result
        if first_diagnostic is not None:
            return first_diagnostic
        # BLOCKED is never reset by elapsed time or a status summary.
        for task in blocked:
            _check_time(start)
            if any(records[dep].state != "DONE" for dep in task.dependencies):
                continue
            metrics[0] += 1
            result = _candidate(task, "resume", records, required, authorization,
                                observed_gate_evidence)
            if result.action == "resume":
                return result
            if first_diagnostic is None:
                first_diagnostic = result
        _check_time(start)
        if first_diagnostic is not None:
            return first_diagnostic
        if all(records[key].state == "DONE" for key in required):
            # Scope exhaustion is NOT a declaration that a feature is accepted.
            gate_failure = _contract_failure(records[context.current_gate])
            if gate_failure:
                return NextAction("repair-plan", context.current_gate, gate_failure)
            return NextAction("stop-scope", None, "SCOPE_EXHAUSTED")
        return NextAction("repair-plan", None, "NO_LEGAL_CANDIDATE")
    except _Diagnostic as exc:
        return NextAction("repair-plan", None, exc.code)


def select_next(validated_context: ValidatedContext, authorization: Authorization,
                observed_gate_evidence: ObservedGateEvidence) -> NextAction:
    """Pure suggestion from validated records and separately supplied host facts."""
    return select_with_metrics(validated_context, authorization, observed_gate_evidence)[0]


def select_with_metrics(validated_context: ValidatedContext, authorization: Authorization,
                        observed_gate_evidence: ObservedGateEvidence) -> tuple[NextAction, int, float]:
    """Same single traversal, with candidate count and elapsed milliseconds for CLI events."""
    start = time.monotonic()
    metrics = [0]
    result = _select(validated_context, authorization, observed_gate_evidence, start, metrics)
    # Apply the deadline also to early diagnostic and blocked-resume exits.
    elapsed = time.monotonic() - start
    if elapsed >= MAX_SECONDS:
        result = NextAction("repair-plan", None, "RESOURCE_LIMIT")
    return result, metrics[0], round(elapsed * 1000, 3)


if __name__ == "__main__":
    import sys
    sys.dont_write_bytecode = True
    from selection_context import main
    raise SystemExit(main())
