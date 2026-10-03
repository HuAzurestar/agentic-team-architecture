#!/usr/bin/env python3
"""Bounded single-point document drafts; no authority, I/O, commits or task writes."""
from __future__ import annotations
from dataclasses import dataclass
import html
import re
import sys
import time
sys.dont_write_bytecode = True
import task_context as context
from decision_evidence import MAX_BYTES, CPU_SECONDS, canonical, decision_digest
from decision_source import _point

TICK = chr(96)
POINT_TITLE = re.compile(r"(REQ|SOL)-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?:[ \t]+(?:—|–|-)[ \t]+.*)?")
DISPOSITION = {"Disposition records", "处置记录"}
DERIVED = {"Derived document state", "派生文档状态"}
HISTORY = {"Decision history", "决定历史"}


class DraftError(ValueError):
    """Safe diagnostic; never returns document/reply text."""


@dataclass(frozen=True)
class PointDraft:
    document: str
    point_id: str
    outcome: str
    decision_digest: str
    before: str
    after: str
    effect: str = "DRAFT_ONLY"


def headings(text):
    """Source offsets for non-quoted, non-fenced ATX headings."""
    result, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\n")
        marker = re.match(r"^ {0,3}(" + TICK + r"{3,}|~{3,})(.*)$", bare)
        if fence:
            if (marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence)
                    and not marker[2].strip()):
                fence = None
        elif marker and not (marker[1][0] == TICK and TICK in marker[2]):
            fence = marker[1]
        else:
            heading = re.fullmatch(r"(#{1,6})[ \t]+(.+?)[ \t]*", bare)
            if heading:
                result.append((len(heading[1]), heading[2], offset, offset + len(line)))
        offset += len(line)
    return result


def section(text, titles, level):
    found = [entry for entry in headings(text) if entry[0] == level and entry[1] in titles]
    if len(found) != 1:
        raise DraftError("POINT_LAYOUT_AMBIGUOUS")
    entry = found[0]
    end = next((item[2] for item in headings(text)
                if item[2] > entry[2] and item[0] <= level), len(text))
    return entry[2], end


def replace_row(text, keys, value):
    # Call only on the metadata prefix, never on a point statement/history.
    found = []
    for match in re.finditer(r"^\|([^\n]*)\|[ \t]*$", text, re.MULTILINE):
        cells = match[1].split("|")
        if len(cells) == 2 and cells[0].strip().strip(TICK) in keys:
            found.append(match)
    if len(found) != 1:
        raise DraftError("POINT_METADATA_AMBIGUOUS")
    match = found[0]
    key = match[1].split("|")[0]
    safe = html.escape(value, quote=True).replace("|", "&#124;").replace(TICK, "&#96;")
    return text[:match.start()] + "|" + key + "| " + safe + " |" + text[match.end():]


def validate_pair(requirement, solution):
    # Reuse the actual confirmation/dependency rules, without pretending that
    # this synthetic mapping supplies task state or any Git/host authority.
    records = {key: {"state": "PENDING"} for text, prefix in
               ((requirement, "REQ"), (solution, "SOL"))
               for key in context.point_sections(text, prefix)}
    context.validate_decision_mapping(records, requirement, solution)


def render_decision(requirement, solution, record):
    """Propose exactly one point's transition, preserving old statement/history.

    A writer MUST independently authenticate and re-read the human decision and
    current Git/native material. This function's result is never an authorization
    or proof of freshness, and cannot complete a point task.
    """
    started = time.process_time()
    try:
        digest = decision_digest(record)
        if record["decision_kind"] != "point":
            raise DraftError("POINT_DECISION_REQUIRED")
        if (not isinstance(requirement, str) or not isinstance(solution, str)
                or "\r" in requirement or "\r" in solution):
            raise DraftError("POINT_SOURCE_ENCODING")
        if (len(requirement) + len(solution) > MAX_BYTES
                or len(requirement.encode("utf-8")) + len(solution.encode("utf-8")) + len(canonical(record)) > MAX_BYTES):
            raise DraftError("RESOURCE_LIMIT")
        validate_pair(requirement, solution)
        point_id, outcome = record["exact_scope"][0], record["outcome"]
        before = requirement if point_id.startswith("REQ-") else solution
        original = _point(before, point_id)
        if original != record["approved_body"]:
            raise DraftError("DECISION_STALE")
        entries = headings(before)
        point_entry = [item for item in entries if item[0] == 2
                       and re.split(r"[ \t]+", item[1])[0].strip(TICK) == point_id]
        if len(point_entry) != 1:
            raise DraftError("POINT_LAYOUT_AMBIGUOUS")
        start = point_entry[0][2]
        if before[start:start + len(original)] != original:
            raise DraftError("POINT_LAYOUT_AMBIGUOUS")
        disposition_start, _ = section(before, DISPOSITION, 2)
        disposition_end = next((item[2] for item in entries
                                if item[2] > disposition_start and item[0] <= 2
                                and not (item[0] == 2 and POINT_TITLE.fullmatch(item[1].replace(TICK, "")))),
                               len(before))
        state = context.metadata_value(original, {"State", "状态"}, point_id)
        point_class = context.metadata_value(original, {"Class", "类别"}, point_id)
        if ((point_class == "DISPOSITION") != (disposition_start < start < disposition_end)
                or (point_class == "ACTIVE" and start > disposition_start)):
            raise DraftError("POINT_LOCATION_MISMATCH")
        allowed = ({"CONFIRMED", "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"}
                   if state in {"PROPOSED", "REOPENED"} else {"REOPENED"})
        if outcome not in allowed:
            raise DraftError("POINT_TRANSITION_INVALID")
        new_class = "DISPOSITION" if outcome in {"REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"} else "ACTIVE"
        prefix_end = next((item[2] for item in headings(original) if item[0] >= 3), len(original))
        prefix = original[:prefix_end]
        for keys, value in (({"Class", "类别"}, new_class), ({"State", "状态"}, outcome),
                            ({"Decided by", "决定人"}, record["actor"]),
                            ({"Decided at", "决定时间"}, record["received_at"])):
            prefix = replace_row(prefix, keys, value)
        revised = prefix + original[prefix_end:]
        _, history_end = section(revised, HISTORY, 3)
        # One JSON line cannot inject headings or terminate the tilde fence.
        history = "\n~~~json\n" + canonical(record).decode("utf-8") + "\n~~~\n\n"
        revised = revised[:history_end] + history + revised[history_end:]
        after = before[:start] + revised + before[start + len(original):]
        if new_class != point_class:
            without = before[:start] + before[start + len(original):]
            disposition_start, _ = section(without, DISPOSITION, 2)
            if new_class == "ACTIVE":
                insertion = disposition_start
            else:
                # H2 points inside the disposition region are not its end.
                insertion = next((item[2] for item in headings(without)
                                  if item[2] > disposition_start and item[0] <= 2
                                  and not (item[0] == 2 and POINT_TITLE.fullmatch(item[1].replace(TICK, "")))),
                                 len(without))
            after = without[:insertion] + revised + without[insertion:]
        active = [context.metadata_value(body, {"State", "状态"}, key)
                  for key, body in context.point_sections(after, point_id[:3]).items()
                  if context.metadata_value(body, {"Class", "类别"}, key) == "ACTIVE"]
        derived = ("CONFIRMED" if point_id.startswith("REQ-") else "BASELINED") if (
            active and all(value == "CONFIRMED" for value in active)) else "DRAFT"
        dstart, dend = section(after, DERIVED, 2)
        after = after[:dstart] + replace_row(after[dstart:dend], {"Status", "状态"}, derived) + after[dend:]
        validate_pair(after if point_id.startswith("REQ-") else requirement,
                      after if point_id.startswith("SOL-") else solution)
        if len(after.encode("utf-8")) + len(before.encode("utf-8")) > MAX_BYTES or time.process_time() - started > CPU_SECONDS:
            raise DraftError("RESOURCE_LIMIT")
        return PointDraft("REQUIREMENT.md" if point_id.startswith("REQ-") else "SOLUTION.md",
                          point_id, outcome, digest, before, after)
    except DraftError:
        raise
    except Exception:
        raise DraftError("POINT_DOCUMENT_INVALID") from None
