#!/usr/bin/env python3
"""Write-time quality/decision checks; host readers are never loaded from files."""
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
import task_context as tc
import task_next as selection
import quality_policy as quality
import decision_host as human

_TEMPORARY = ContextVar('state_writer_temporary', default=None)


@contextmanager
def _writer_temporary(request, path, identity):
    """Expose only this writer's concrete temporary artifact to host readers."""
    token = _TEMPORARY.set((request.digest, path, *identity))
    try:
        yield
    finally:
        _TEMPORARY.reset(token)


@dataclass(frozen=True)
class TransitionRequest:
    root: str
    task_id: str
    source: str
    target: str
    before_digest: str
    after_digest: str
    read_set: tuple

    @property
    def digest(self):
        return 'state-sha256:' + quality.request_digest(asdict(self))


@dataclass(frozen=True)
class HumanDecisionInputs:
    record: dict
    read_current: object
    read_reply: object
    interpret: object
    grant: object


@dataclass(frozen=True)
class TransitionEvidence:
    """Actual host readbacks bound to one exact prepared state write.

    The callback must independently read repository/remote and provenance facts.
    A constructor or digest is not authentication. No JSON/CLI import exists.
    """
    request_digest: str
    quality_inputs: object = None
    human_decision: object = None


def requirements(task_id, target, fields):
    phase = None
    decision = False
    if task_id.startswith('ACCEPT-'):
        if target == 'WIP':
            phase = 'pre_accept'
        decision = target == 'DONE' or (target == 'RECORDING' and fields.get('Decision') != 'WAITING')
    if task_id.startswith('GATE-') and fields.get('To phase') == 'DONE' and target in {'WIP', 'RECORDING', 'DONE'}:
        phase = 'post_merge'
    return phase, decision


def require(ok, code):
    if not ok:
        raise tc.ContextError(code)


def verify(request, callback, records, fields, brief_body=None):
    try:
        return _verify(request, callback, records, fields, brief_body)
    except tc.ContextError:
        raise
    except Exception:
        raise tc.ContextError('STATE_EVIDENCE_INVALID') from None


def _verify(request, callback, records, fields, brief_body=None):
    """Recompute real policies, not an uploaded allowed flag or actor label."""
    phase, needs_decision = requirements(request.task_id, request.target, fields)
    if phase is None and not needs_decision:
        return
    require(callable(callback), 'STATE_EVIDENCE_REQUIRED')
    try:
        evidence = callback(request)
    except Exception:
        raise tc.ContextError('STATE_SOURCE_UNAVAILABLE') from None
    require(type(evidence) is TransitionEvidence and evidence.request_digest == request.digest,
            'STATE_EVIDENCE_BINDING_MISMATCH')
    if phase:
        inputs = evidence.quality_inputs
        require(type(inputs) is selection.QualityInputs and inputs.task_id == request.task_id
                and inputs.source_ref == request.digest, 'STATE_QUALITY_UNVERIFIED')
        feature = inputs.feature
        require(type(feature) is tc.ValidatedFeature and Path(feature.documents.root).resolve() == Path(request.root),
                'STATE_FEATURE_MISMATCH')
        require(request.task_id in records and set(feature.records) == set(records), 'STATE_PLAN_MISMATCH')
        for key, record in records.items():
            observed = feature.records[key]
            require(isinstance(observed, dict) and all(observed.get(k) == record.get(k) for k in ('type', 'state', 'dependencies')),
                    'STATE_PLAN_MISMATCH')
        # Intent cannot be supplied from a different/old feature while approving
        # this write. Transitional STATUS/detail edits are bound by request.digest
        # and must be independently reconciled by the host, not ignored as dirty.
        sources = dict(request.read_set)
        for name in ('REQUIREMENT.md', 'SOLUTION.md'):
            require(name in feature.documents.records and sources.get(name) == feature.documents.records[name].content_digest,
                    'STATE_INTENT_CHANGED')
        require(isinstance(inputs.request, dict) and inputs.request.get('phase') == phase, 'STATE_QUALITY_PHASE_MISMATCH')
        result = quality.assess_quality(feature, inputs.request, observed=inputs.observations,
            report_evidence=inputs.report_evidence, decision_sources=inputs.decision_sources)
        require(result['allowed'] is True, result['reason_codes'][0] if result['reason_codes'] else 'QUALITY_NOT_ELIGIBLE')
    if needs_decision:
        inputs = evidence.human_decision
        require(type(inputs) is HumanDecisionInputs, 'HUMAN_SOURCE_UNVERIFIED')
        raw = inputs.record
        require(isinstance(raw, dict) and raw.get('decision_kind') == 'acceptance'
                and raw.get('feature') == Path(request.root).name
                and raw.get('outcome') == fields.get('Decision')
                and raw.get('actor') == fields.get('Decided by'), 'ACCEPTANCE_DECISION_MISMATCH')
        require(isinstance(brief_body, str) and raw.get('approved_body') == brief_body, 'ACCEPTANCE_BRIEF_MISMATCH')
        # The exact approved brief must name this candidate, not merely quote an
        # arbitrary SHA somewhere in an unrelated paragraph or fenced example.
        from review_resume import _markdown
        versions = [line for kind, _, line in _markdown(brief_body)
                    if kind == 'line' and re.match(r'^(?:Target version|目标版本)[:：]', line)]
        require(len(versions) == 1 and re.fullmatch(r'(?:Target version|目标版本)[:：]\s*`?'
            + re.escape(fields.get('Target SHA', '')) + r'`?\s*', versions[0]), 'ACCEPTANCE_TARGET_MISMATCH')
        def read_current():
            current = inputs.read_current()
            require(isinstance(current, dict) and current.get('body') == brief_body, 'ACCEPTANCE_BRIEF_MISMATCH')
            return current
        result = human.inspect_decision(raw, read_current=read_current, read_reply=inputs.read_reply,
            interpret=inputs.interpret, grant=inputs.grant)
        require(result['applicable'] is True and result['source_verified'] is True,
                result['reason_codes'][0] if result['reason_codes'] else 'HUMAN_SOURCE_UNVERIFIED')
