#!/usr/bin/env python3
"""Host readback gateway; configured transports, never uploaded authority claims."""
from __future__ import annotations
from dataclasses import dataclass
import json
import sys
import time
sys.dont_write_bytecode = True
from decision_evidence import (CPU_SECONDS, MAX_BYTES, Invalid, VerifiedDecisionSource, canonical,
                               check_decision, decision_digest, line, validate_material)


@dataclass(frozen=True)
class HumanReply:
    """Facts from an authenticated transport, not a Markdown/JSON constructor."""
    source_ref: str
    actor: str
    actor_kind: str
    received_at: str
    text: str
    source_kind: str
    source_version: str
    verification_ref: str


@dataclass(frozen=True)
class HumanGrant:
    """Host policy for one exact actor/feature/kind/source/scope and outcomes."""
    actor: str
    feature: str
    decision_kind: str
    source_key: str
    exact_scope: tuple[str, ...]
    outcomes: tuple[str, ...]


@dataclass(frozen=True)
class HumanInterpretation:
    """Coordinator's exact interpretation of the actual reply and quoted material.

    A digest is only a binding, not semantic understanding or authentication.
    The host must resolve ambiguity before returning this object.
    """
    decision_digest: str
    basis_ref: str


class HostFailure(ValueError):
    pass


def inspect_decision(raw, *, read_current=None, read_reply=None, interpret=None, grant=None):
    """Read twice and check, without applying a decision or writing any source.

    read_current() must independently read the configured current target.
    read_reply(ref) must use an authenticated, allowlisted host transport.
    interpret(reply, record) maps the actual human reply to exact quoted scope.
    All adapters and the grant are supplied by trusted host code, never loaded
    from the evidence document. Missing adapters fail closed. Tests are synthetic.
    """
    started = time.process_time()
    result = dict(applicable=False, source_verified=False, effect='NOT_APPLIED',
                  merge_authorized=False, reason_codes=[], diff=None, decision_id=None)
    try:
        digest = decision_digest(raw)
        # Snapshot bounded input; callbacks cannot rewrite the original record.
        record = json.loads(canonical(raw))
        result['decision_id'] = record['decision_id']
        if not all(callable(value) for value in (read_current, read_reply, interpret)):
            raise HostFailure('HUMAN_SOURCE_UNAVAILABLE')
        if (type(grant) is not HumanGrant or grant.actor != record['actor']
                or grant.feature != record['feature'] or grant.decision_kind != record['decision_kind']
                or grant.source_key != record['target_ref']['source_key']
                or type(grant.exact_scope) is not tuple or len(grant.exact_scope) != len(record['exact_scope'])
                or any(not isinstance(item, str) for item in grant.exact_scope)
                or set(grant.exact_scope) != set(record['exact_scope'])
                or type(grant.outcomes) is not tuple or len(grant.outcomes) > 5
                or record['outcome'] not in grant.outcomes):
            raise HostFailure('HUMAN_AUTHORITY_UNVERIFIED')
        current = read_current()
        validate_material(current, current=True)
        current_bytes = canonical(current)
        if len(current_bytes) + len(canonical(record)) > MAX_BYTES:
            raise HostFailure('RESOURCE_LIMIT')
        current = json.loads(current_bytes)
        reply = read_reply(record['human_source_ref'])
        if (type(reply) is not HumanReply or reply.actor_kind != 'human'
                or reply.source_kind not in ('conversation', 'platform-readback')
                or not line(reply.source_version) or not line(reply.verification_ref)
                or reply.source_ref != record['human_source_ref'] or reply.actor != record['actor']
                or reply.received_at != record['received_at'] or reply.text != record['original_reply']):
            raise HostFailure('HUMAN_SOURCE_MISMATCH')
        mapped = interpret(reply, json.loads(canonical(record)))
        if (type(mapped) is not HumanInterpretation or mapped.decision_digest != digest
                or not line(mapped.basis_ref)):
            raise HostFailure('HUMAN_INTERPRETATION_UNVERIFIED')
        # Re-observe instead of treating a cached file/earlier claim as freshness.
        if read_reply(record['human_source_ref']) != reply:
            raise HostFailure('HUMAN_SOURCE_CHANGED')
        again = read_current()
        validate_material(again, current=True)
        if canonical(again) != canonical(current):
            raise HostFailure('DECISION_SOURCE_CHANGED')
        verified = VerifiedDecisionSource(digest, reply.source_ref, reply.actor, reply.received_at,
                                          reply.source_kind, reply.verification_ref)
        result = check_decision(record, current, verified=verified)
        result['interpretation_ref'] = mapped.basis_ref
        result['human_source_version'] = reply.source_version
        if time.process_time() - started > CPU_SECONDS:
            raise HostFailure('RESOURCE_LIMIT')
    except (HostFailure, Invalid) as exc:
        result.update(applicable=False, source_verified=False, reason_codes=[str(exc)], diff=None)
    except Exception:
        # Adapters may raise provider errors containing tokens or reply bodies.
        # Never expose their message or reinterpret a failure as absent evidence.
        result.update(applicable=False, source_verified=False, reason_codes=['SOURCE_UNAVAILABLE'], diff=None)
    result['event'] = dict(name='decision.check', decision_id=result['decision_id'],
                           applicable=result['applicable'], reason_codes=list(result['reason_codes']))
    return result
