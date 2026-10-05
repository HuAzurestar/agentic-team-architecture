#!/usr/bin/env python3
"""Pure applicability checks; source authentication belongs to a trusted host."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
import sys
import time

sys.dont_write_bytecode = True
MAX_BYTES = 4 * 1024 * 1024
MAX_SCOPE = 1000
DIFF_CHARS = 4096
CPU_SECONDS = 2.0
OUTCOMES = {
    "point": {"CONFIRMED", "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE", "REOPENED"},
    "acceptance": {"CONFIRMED", "REJECTED", "REWORK"},
    "scope-exception": {"APPROVED", "REJECTED"},
}
FIELDS = {"schema", "decision_id", "feature", "human_source_ref", "actor", "received_at",
          "decision_kind", "target_ref", "exact_scope", "outcome", "original_reply", "approved_body"}
CURRENT_FIELDS = {"feature", "decision_kind", "target_ref", "exact_scope", "body"}
ID = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{0,255}\Z")
POINT = re.compile(r"(REQ|SOL)-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\Z")


@dataclass(frozen=True)
class VerifiedDecisionSource:
    """Host-only facts, NOT a deserializable credential or proof by type alone.

    Construct only after actual conversation/platform readback verifies the
    human actor, authority, exact interpretation, reply and approved material.
    The digest binds all recorded fields; tests constructing this object are
    synthetic, not human decisions. No Markdown/JSON import can mint one.
    """
    decision_digest: str
    human_source_ref: str
    actor: str
    received_at: str
    source_kind: str
    verification_ref: str


class Invalid(ValueError):
    pass


def line(value):
    return (isinstance(value, str) and 0 < len(value) <= 2048 and value.strip() == value
            and all(ord(char) >= 32 and ord(char) != 127 for char in value))


def validate_material(raw, *, current=False):
    expected = CURRENT_FIELDS if current else FIELDS
    if not isinstance(raw, dict) or len(raw) != len(expected) or set(raw) != expected:
        raise Invalid("INVALID_DECISION_SCHEMA")
    if not isinstance(raw["feature"], str) or not ID.fullmatch(raw["feature"]):
        raise Invalid("INVALID_DECISION_SCHEMA")
    kind = raw["decision_kind"]
    if not isinstance(kind, str) or kind not in OUTCOMES:
        raise Invalid("INVALID_DECISION_SCHEMA")
    target = raw["target_ref"]
    if (not isinstance(target, dict) or set(target) != {"source_key", "version_kind", "version"}
            or not line(target["source_key"]) or not line(target["version"])
            or target["version_kind"] not in ("git", "native")):
        raise Invalid("INVALID_DECISION_SCHEMA")
    if target["version_kind"] == "git" and re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", target["version"]) is None:
        raise Invalid("INVALID_DECISION_SCHEMA")
    scope = raw["exact_scope"]
    if (not isinstance(scope, list) or not 0 < len(scope) <= MAX_SCOPE
            or any(not isinstance(item, str) or not ID.fullmatch(item) for item in scope)
            or len(set(scope)) != len(scope)):
        raise Invalid("INVALID_DECISION_SCHEMA")
    # An enumerated multi-point reply is split into separately bound records.
    if kind == "point" and (len(scope) != 1 or POINT.fullmatch(scope[0]) is None):
        raise Invalid("INVALID_DECISION_SCHEMA")
    body = raw["body" if current else "approved_body"]
    if not isinstance(body, str) or not body.strip() or "\0" in body:
        raise Invalid("INVALID_DECISION_SCHEMA")
    if len(body) > MAX_BYTES:
        raise Invalid("RESOURCE_LIMIT")
    if current:
        return
    if raw["schema"] != "decision-evidence-v1":
        raise Invalid("INVALID_DECISION_SCHEMA")
    if not isinstance(raw["decision_id"], str) or not ID.fullmatch(raw["decision_id"]):
        raise Invalid("INVALID_DECISION_SCHEMA")
    if any(not line(raw[field]) for field in ("human_source_ref", "actor", "received_at")):
        raise Invalid("INVALID_DECISION_SCHEMA")
    if not isinstance(raw["outcome"], str) or raw["outcome"] not in OUTCOMES[kind]:
        raise Invalid("INVALID_DECISION_SCHEMA")
    if not isinstance(raw["original_reply"], str) or not raw["original_reply"].strip() or "\0" in raw["original_reply"]:
        raise Invalid("INVALID_DECISION_SCHEMA")
    if len(raw["original_reply"]) > MAX_BYTES:
        raise Invalid("RESOURCE_LIMIT")
    try:
        received = datetime.fromisoformat(raw["received_at"])
        if received.tzinfo is None or received.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise Invalid("INVALID_DECISION_SCHEMA") from None


def canonical(raw):
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def decision_digest(raw):
    """Content binding only, not a statement that the content is authorized."""
    validate_material(raw)
    encoded = canonical(raw)
    if len(encoded) > MAX_BYTES:
        raise Invalid("RESOURCE_LIMIT")
    return hashlib.sha256(encoded).hexdigest()


def changed_span(before, after):
    """Linear exact changed span, not a quadratic similarity alignment."""
    start, common = 0, min(len(before), len(after))
    while start < common and before[start] == after[start]:
        start += 1
    end = 0
    while end < common - start and before[len(before) - end - 1] == after[len(after) - end - 1]:
        end += 1
    old = before[start:len(before) - end if end else len(before)]
    new = after[start:len(after) - end if end else len(after)]
    return {"start_character": start, "before_length": len(old), "after_length": len(new),
            "before": old[:DIFF_CHARS], "after": new[:DIFF_CHARS],
            "truncated": len(old) > DIFF_CHARS or len(new) > DIFF_CHARS}


def check_decision(raw, current, *, verified=None):
    """Determine exact applicability without mutating a decision or its sources.

    Current material must be supplied from verified source reads, not from the
    decision itself. Applicability permits recording that particular outcome;
    even CONFIRMED does not establish review/test quality or merge authority.
    """
    started = time.process_time()
    result = dict(schema_valid=False, applicable=False, source_verified=False,
                  effect="NOT_APPLIED", merge_authorized=False, reason_codes=[], diff=None,
                  decision_id=None, outcome=None, exact_scope=[], evidence_refs=[])
    try:
        validate_material(raw)
        validate_material(current, current=True)
        encoded = canonical(raw)
        if len(encoded) + len(canonical(current)) > MAX_BYTES:
            raise Invalid("RESOURCE_LIMIT")
        digest = hashlib.sha256(encoded).hexdigest()
        result.update(schema_valid=True, decision_id=raw["decision_id"], outcome=raw["outcome"],
                      exact_scope=list(raw["exact_scope"]), decision_digest=digest)
        trusted = (type(verified) is VerifiedDecisionSource
                   and verified.decision_digest == digest
                   and verified.human_source_ref == raw["human_source_ref"]
                   and verified.actor == raw["actor"] and verified.received_at == raw["received_at"]
                   and verified.source_kind in ("conversation", "platform-readback")
                   and line(verified.verification_ref))
        if not trusted:
            result["reason_codes"].append("HUMAN_SOURCE_UNVERIFIED")
        else:
            result["source_verified"] = True
            result["evidence_refs"] = [raw["human_source_ref"], verified.verification_ref]
        if (raw["feature"] != current["feature"] or raw["decision_kind"] != current["decision_kind"]
                or set(raw["exact_scope"]) != set(current["exact_scope"])):
            result["reason_codes"].append("DECISION_SCOPE_MISMATCH")
        old_target, new_target = raw["target_ref"], current["target_ref"]
        if (old_target["source_key"] != new_target["source_key"]
                or old_target["version_kind"] != new_target["version_kind"]):
            result["reason_codes"].append("DECISION_TARGET_MISMATCH")
        if old_target["version"] != new_target["version"] or raw["approved_body"] != current["body"]:
            result["reason_codes"].append("DECISION_STALE")
            if raw["approved_body"] != current["body"]:
                result["diff"] = changed_span(raw["approved_body"], current["body"])
        if time.process_time() - started > CPU_SECONDS:
            raise Invalid("RESOURCE_LIMIT")
        result["applicable"] = not result["reason_codes"]
    except (Invalid, TypeError, ValueError, UnicodeError, RecursionError) as exc:
        code = str(exc) if isinstance(exc, Invalid) else "INVALID_DECISION_SCHEMA"
        result.update(schema_valid=False, applicable=False, source_verified=False, diff=None)
        result["reason_codes"] = [code]
    # No reply, body, difference text or actor data is included in event metadata.
    result["event"] = {"name": "decision.check", "decision_id": result["decision_id"],
                       "applicable": result["applicable"], "reason_codes": list(result["reason_codes"])}
    return result
