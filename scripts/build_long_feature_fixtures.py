"""Materialize the reviewed PIRC-31 static case data and hash manifest."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


SHA_A = "a" * 40
SHA_B = "b" * 40


def c1_base(case_id: str) -> dict:
    finding = {
        "finding_id": "F-1", "severity": "P1", "closed_for_candidate": False,
        "description": "blocking discrepancy", "affected_scope": "BEACON-1/DEV-01",
        "evidence": "review/attempt-1.md#finding-1", "resolution": "open; rework required",
    }
    return {
        "case_id": case_id,
        "feature": "BEACON-1",
        "source_scope": {"environment": "staging", "project": "BEACON-1", "document_ref": "beacon-api@" + SHA_A + ":project/BEACON-1"},
        "points": [
            {"id": "REQ-001", "class": "ACTIVE", "text": "Review before acceptance", "state": "CONFIRMED", "decided_by": "project owner", "decided_at": "2026-09-29", "decision_history": ["approved at source ref"]},
            {"id": "SOL-001", "class": "ACTIVE", "text": "Record evidence per check", "state": "PROPOSED", "decision_history": []},
        ],
        "tasks": [
            {"id": "DEV-01", "type": "Development", "state": "DONE", "depends_on": [], "detail_ref": "tasks/DEV-01.md", "owner": "developer", "started_at": "2026-09-28", "completed_at": "2026-09-29", "repository_refs": ["beacon-api@" + SHA_A], "point_selectors": {"requirements": ["REQ-001"], "solutions": ["SOL-001"]}},
            {"id": "REVIEW-01", "type": "Review", "state": "DONE", "depends_on": ["DEV-01"], "detail_ref": "tasks/REVIEW-01.md", "owner": "independent reviewer", "started_at": "2026-09-29", "completed_at": "2026-09-29", "repository_refs": ["beacon-api@" + SHA_A], "point_selectors": {"requirements": ["REQ-001"], "solutions": ["SOL-001"]}},
        ],
        "declared_evidence": ["review/attempt-1.md"],
        "available_evidence": ["review/attempt-1.md"],
        "candidate_sha": SHA_A,
        "review": {
            "report_id": "R-1", "attempt": "1", "reviewer": "independent reviewer",
            "independent_context": "separate read-only review session against source refs",
            "target_repo": "beacon-api", "scope": "BEACON-1 F01",
            "source_refs": ["beacon-api@" + SHA_A],
            "target_sha": SHA_A,
            "report_done": True,
            "checks": [
                {"check_id": "CHK-1", "requirement_or_case": "REQ-001", "result": "PASS", "evidence": ["review/attempt-1.md#check-1"], "finding_ids": [], "reason": ""},
                {"check_id": "CHK-2", "requirement_or_case": "SOL-001", "result": "FAIL", "evidence": ["review/attempt-1.md#check-2"], "finding_ids": ["F-1"], "reason": "open finding"},
            ],
            "findings": [finding, copy.deepcopy(finding)],
        },
        "expected_counts": {"all": 2, "pass": 1, "findings_total": 1, "open_by_severity": {"P0": 0, "P1": 1, "P2": 0}},
        "request_acceptance": True,
        "request_rework": True,
    }


def c2_base(case_id: str, operation: str = "update") -> dict:
    return {
        "case_id": case_id,
        "operation": operation,
        "ref": "beacon-binding:DOC-01",
        "conditional_write": True,
        "expected_source_key": "route:A",
        "current_source_key": "route:A",
        "expected_content": "one\n",
        "current_content": "one\n",
        "expected_selection": "one",
        "current_selection": "one",
        "preview_id": "preview:BEACON-1:1",
        "preview_alive": True,
        "parent_ref": "beacon-api:project/BEACON-1",
        "target_id": "DOC-01",
        "target_exists": False,
        "expected_index": "index:rev-1",
    }


def c3_base(case_id: str) -> dict:
    case = {
        "case_id": case_id,
        "stage": "execution",
        "valid": True,
        "authoritative_source_ref": "beacon-api@" + SHA_A + ":BEACON-1",
        "checkout_source_ref": "beacon-api@" + SHA_A + ":BEACON-1",
        "profile_matches": True,
        "recorded_sha": SHA_A,
        "actual_sha": SHA_A,
        "service_available": True,
        "sources": ["BEACON-1/STATUS.md", "BEACON-1/TASKS.md"],
        "context": {
            "feature": {"id": "BEACON-1", "phase": "EXECUTING"},
            "task": {"id": "DEV-01", "state": "WIP"},
            "task_detail": {"blocker": "none", "resume_action": "continue"},
            "intent": {
                "requirements": [{"id": "REQ-001", "original_text": "Review before acceptance", "state": "CONFIRMED", "decided_by": "project owner", "decided_at": "2026-09-29", "decision_history": ["approved at source ref"]}],
                "solutions": [{"id": "SOL-001", "original_text": "Record evidence per check", "state": "CONFIRMED", "decided_by": "project owner", "decided_at": "2026-09-29", "decision_history": ["approved at source ref"]}],
            },
            "repositories": [{"id": "beacon-api", "sha": SHA_A}],
            "refs": ["beacon-api@" + SHA_A],
            "dependencies": ["GATE-START"],
            "trace": "VALIDATED",
            "gists": ["evidence.md"],
            "type_contract": {"kind": "development"},
            "acceptance_brief": {"status": "not-applicable"},
        },
    }
    case["source_facts"] = copy.deepcopy(case["context"])
    case["source_facts"]["sources"] = copy.deepcopy(case["sources"])
    return case


def cases() -> list[tuple[str, dict, str]]:
    rows: list[tuple[str, dict, str]] = []
    c1 = c1_base("C1-01")
    rows.append(("c1", c1, "REWORK_READY_ACCEPT_BLOCKED"))
    c1 = c1_base("C1-02")
    duplicate = copy.deepcopy(c1["tasks"][0])
    duplicate["state"] = "WIP"
    duplicate.pop("completed_at")
    c1["tasks"].append(duplicate)
    rows.append(("c1", c1, "INVALID_DOCUMENT"))
    c1 = c1_base("C1-03")
    c1["available_evidence"] = []
    rows.append(("c1", c1, "MISSING_EVIDENCE"))
    c1 = c1_base("C1-04")
    c1["candidate_sha"] = SHA_B
    rows.append(("c1", c1, "STALE_EVIDENCE"))

    c2 = c2_base("C2-01")
    c2["current_source_key"] = "route:B"
    rows.append(("c2", c2, "SOURCE_CHANGED"))
    c2 = c2_base("C2-02", "config_write")
    c2.update(expected_config="old", current_config="new")
    rows.append(("c2", c2, "CONFIG_CONFLICT"))
    c2 = c2_base("C2-03")
    c2.update(rebind_during_write=True, lock_serialized=True)
    rows.append(("c2", c2, "SAVED"))
    c2 = c2_base("C2-04")
    c2["response_lost"] = True
    rows.append(("c2", c2, "UNKNOWN"))
    c2 = c2_base("C2-05", "preview_apply")
    c2["current_content"] = "one\nchanged outside selection\n"
    rows.append(("c2", c2, "SAVED"))
    c2 = c2_base("C2-06", "preview_apply")
    c2["preview_alive"] = False
    rows.append(("c2", c2, "PREVIEW_EXPIRED"))
    c2 = c2_base("C2-07")
    c2["conditional_write"] = False
    rows.append(("c2", c2, "READ_ONLY"))
    c2 = c2_base("C2-08")
    c2["current_source_key"] = "remapped:other-document"
    rows.append(("c2", c2, "SOURCE_CHANGED"))
    c2 = c2_base("C2-09", "create")
    c2["known_partial"] = True
    c2["known_effects"] = ["file_created", "index_update_failed"]
    rows.append(("c2", c2, "PARTIAL"))
    c2 = c2_base("C2-10", "list")
    c2["mapping_changed"] = True
    rows.append(("c2", c2, "CURSOR_INVALID"))

    c3 = c3_base("C3-01")
    c3["display_extension"] = {"accent": "blue"}
    rows.append(("c3", c3, "VALID"))
    c3 = c3_base("C3-02")
    del c3["context"]["task_detail"]["blocker"]
    rows.append(("c3", c3, "MISSING_FIELD"))
    c3 = c3_base("C3-03")
    c3["actual_sha"] = SHA_B
    rows.append(("c3", c3, "STALE_REF"))
    c3 = c3_base("C3-04")
    c3["source_changed"] = True
    rows.append(("c3", c3, "SOURCE_SET_CHANGED"))
    c3 = c3_base("C3-05")
    c3["required_features"] = ["unknown-required"]
    rows.append(("c3", c3, "UNSUPPORTED_FEATURE"))
    c3 = c3_base("C3-06")
    c3["context"] = None
    c3["sources"] = []
    rows.append(("c3", c3, "INVALID_ENVELOPE"))
    c3 = c3_base("C3-07")
    c3["stage"] = "source"
    c3["valid"] = False
    rows.append(("c3", c3, "SOURCE_ONLY"))
    c3 = c3_base("C3-08")
    c3["checkout_source_ref"] = "other-checkout@" + SHA_B + ":BEACON-1"
    rows.append(("c3", c3, "SOURCE_CHECKOUT_MISMATCH"))
    c3 = c3_base("C3-09")
    c3["service_available"] = False
    c3["fallback_same_source"] = True
    rows.append(("c3", c3, "VALID_FALLBACK"))
    return rows


def build(bundle: Path) -> None:
    fixture_dir = bundle / "cases"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for name in ("c1", "c2", "c3"):
        path = bundle / f"{name}.md"
        if not path.is_file():
            raise FileNotFoundError(path)
        entries.append({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "contract": name, "case_id": None, "expected_result": None})
    for name, data, expected in cases():
        path = fixture_dir / f"{data['case_id'].lower()}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        entries.append({"path": "cases/" + path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "contract": name, "case_id": data["case_id"], "expected_result": expected})
    manifest = {"schema_version": "contract-fixtures/0.1", "contracts": {"c1": "c1/0.1", "c2": "c2/0.1", "c3": "c3/0.1"}, "required_features": ["c1", "c2", "c3"], "files": entries}
    (bundle / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    build(parser.parse_args().bundle)


if __name__ == "__main__":
    main()
