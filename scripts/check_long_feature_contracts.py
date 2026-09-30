"""Read-only validation of the PIRC-31 C1/C2/C3 fixture bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath


SCHEMA = "contract-fixtures/0.1"
VERSIONS = {"c1": "c1/0.1", "c2": "c2/0.1", "c3": "c3/0.1"}
MAX_MANIFEST = 1 << 20
MAX_FILE = 4 << 20
MAX_TOTAL = 64 << 20
MAX_FILES = 1000
REQUIRED_CONTEXT = (
    "feature", "task", "task_detail", "intent", "repositories", "refs",
    "dependencies", "trace", "gists", "type_contract", "acceptance_brief",
)
FULL_REPO_REF = re.compile(r"^[^@\s]+@[0-9a-f]{40}(?::[^\s]+)?$")


class BundleError(Exception):
    pass


def fail(case_id: str | None, field: str, expected: object, observed: object, path: str | None = None) -> dict:
    result = {"case_id": case_id, "field": field, "expected": expected, "observed": observed}
    if path is not None:
        result["path"] = path
    return result


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_intent(intent: object) -> bool:
    if not isinstance(intent, dict):
        return False
    for group in ("requirements", "solutions"):
        points = intent.get(group)
        if not isinstance(points, list) or not points:
            return False
        for point in points:
            if not isinstance(point, dict) or any(not nonempty_string(point.get(key)) for key in ("id", "original_text", "state")):
                return False
            if point["state"] not in {"PROPOSED", "REOPENED", "CONFIRMED", "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"}:
                return False
            if point["state"] not in {"PROPOSED", "REOPENED"} and any(not point.get(key) for key in ("decided_by", "decided_at", "decision_history")):
                return False
    return True


def safe_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise BundleError(f"unsafe relative path: {relative!r}")
    part = PurePosixPath(relative)
    if part.is_absolute() or any(p in {"", ".", ".."} for p in part.parts):
        raise BundleError(f"unsafe relative path: {relative!r}")
    target = root
    for component in part.parts:
        target = target / component
        if target.is_symlink():
            raise BundleError(f"symlink in bundle path: {relative}")
    if not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
        raise BundleError(f"missing or escaped bundle file: {relative}")
    return target


def digest(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            size += len(block)
            if size > MAX_FILE:
                raise BundleError(f"file exceeds 4 MiB: {path.name}")
            h.update(block)
    return h.hexdigest(), size


def evaluate_c1(case: dict) -> str:
    scope = case.get("source_scope")
    if not isinstance(scope, dict) or any(not scope.get(key) for key in ("environment", "project", "document_ref")):
        return "INVALID_DOCUMENT"
    points = case.get("points")
    if not isinstance(points, list) or not points:
        return "INVALID_DOCUMENT"
    point_ids = [point.get("id") for point in points if isinstance(point, dict)]
    if len(point_ids) != len(points) or len(set(point_ids)) != len(points):
        return "INVALID_DOCUMENT"
    for point in points:
        if not nonempty_string(point.get("text")) or point.get("class") not in {"ACTIVE", "DEFERRED"} or point.get("state") not in {"PROPOSED", "REOPENED", "CONFIRMED", "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"}:
            return "INVALID_DOCUMENT"
        if point["state"] not in {"PROPOSED", "REOPENED"} and any(not point.get(key) for key in ("decided_by", "decided_at", "decision_history")):
            return "INVALID_DOCUMENT"
    tasks = case.get("tasks", [])
    ids = [task.get("id") for task in tasks if isinstance(task, dict)]
    if not ids or len(ids) != len(tasks) or len(ids) != len(set(ids)):
        return "INVALID_DOCUMENT"
    task_index = {task["id"]: task for task in tasks}
    if any(task.get("state") not in {"PENDING", "WIP", "BLOCKED", "RECORDING", "DONE"} or not isinstance(task.get("depends_on"), list) for task in tasks):
        return "INVALID_DOCUMENT"
    for task in tasks:
        if not nonempty_string(task.get("type")) or not nonempty_string(task.get("detail_ref")):
            return "INVALID_DOCUMENT"
        if task["state"] != "PENDING" and any(not nonempty_string(task.get(key)) for key in ("owner", "started_at")):
            return "INVALID_DOCUMENT"
        if task["state"] == "DONE" and not nonempty_string(task.get("completed_at")):
            return "INVALID_DOCUMENT"
        refs = task.get("repository_refs")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or FULL_REPO_REF.fullmatch(ref) is None for ref in refs):
            return "INVALID_DOCUMENT"
        selectors = task.get("point_selectors")
        if not isinstance(selectors, dict) or set(selectors) != {"requirements", "solutions"}:
            return "INVALID_DOCUMENT"
        for group, prefix in (("requirements", "REQ-"), ("solutions", "SOL-")):
            selected = selectors[group]
            if not isinstance(selected, list) or any(not isinstance(point_id, str) or not point_id.startswith(prefix) or point_id not in point_ids for point_id in selected):
                return "INVALID_DOCUMENT"
    if any(dependency not in task_index for task in tasks for dependency in task["depends_on"]):
        return "INVALID_DOCUMENT"
    remaining = {task_id: set(task_index[task_id]["depends_on"]) for task_id in ids}
    dependents: dict[str, list[str]] = {task_id: [] for task_id in ids}
    for task_id, dependencies in remaining.items():
        for dependency in dependencies:
            dependents[dependency].append(task_id)
    ready = [task_id for task_id, dependencies in remaining.items() if not dependencies]
    resolved = 0
    while ready:
        completed = ready.pop()
        resolved += 1
        for dependent in dependents[completed]:
            remaining[dependent].remove(completed)
            if not remaining[dependent]:
                ready.append(dependent)
    if resolved != len(ids):
        return "INVALID_DOCUMENT"
    available = case.get("available_evidence", [])
    if any(ref not in available for ref in case.get("declared_evidence", [])):
        return "MISSING_EVIDENCE"
    review = case.get("review", {})
    if not isinstance(review, dict) or any(not nonempty_string(review.get(key)) for key in ("report_id", "attempt", "reviewer", "independent_context", "target_repo", "scope")) or not review.get("source_refs"):
        return "INVALID_DOCUMENT"
    if not isinstance(review.get("report_done"), bool) or not isinstance(case.get("request_acceptance"), bool) or not isinstance(case.get("request_rework"), bool):
        return "INVALID_DOCUMENT"
    if review.get("target_sha") != case.get("candidate_sha"):
        return "STALE_EVIDENCE"
    findings = review.get("findings", [])
    if not isinstance(findings, list):
        return "INVALID_DOCUMENT"
    unique_findings: dict[str, dict] = {}
    for item in findings:
        if not isinstance(item, dict) or not item.get("finding_id") or item.get("severity") not in {"P0", "P1", "P2"}:
            return "INVALID_DOCUMENT"
        if not item.get("description") or not item.get("affected_scope") or not item.get("evidence") or not nonempty_string(item.get("resolution")):
            return "MISSING_EVIDENCE"
        prior = unique_findings.setdefault(item["finding_id"], item)
        if prior != item:
            return "INVALID_DOCUMENT"
        if item["evidence"].split("#", 1)[0] not in available:
            return "MISSING_EVIDENCE"
        if item.get("closed_for_candidate"):
            recheck_ref = item.get("recheck_ref")
            if not nonempty_string(recheck_ref) or recheck_ref.split("#", 1)[0] not in available or item.get("recheck_sha") != case.get("candidate_sha"):
                return "MISSING_EVIDENCE"
    checks = review.get("checks", [])
    if not isinstance(checks, list) or not checks or any(not isinstance(item, dict) for item in checks):
        return "INVALID_DOCUMENT"
    if len({item.get("check_id") for item in checks}) != len(checks):
        return "INVALID_DOCUMENT"
    if any(not item.get("check_id") or not item.get("requirement_or_case") or item.get("result") not in {"PASS", "FAIL", "UNKNOWN", "NOT-RUN", "N/A"} for item in checks):
        return "INVALID_DOCUMENT"
    if any(item.get("result") == "N/A" and not item.get("reason") for item in checks):
        return "INVALID_DOCUMENT"
    for item in checks:
        if item["result"] != "N/A":
            refs = item.get("evidence")
            if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref.split("#", 1)[0] not in available for ref in refs):
                return "MISSING_EVIDENCE"
        if item["result"] == "FAIL" and not item.get("finding_ids"):
            return "INVALID_DOCUMENT"
        if any(finding_id not in unique_findings for finding_id in item.get("finding_ids", [])):
            return "INVALID_DOCUMENT"
    if not any(item.get("result") != "N/A" for item in checks):
        return "INVALID_DOCUMENT"
    counts = {
        "all": sum(item["result"] != "N/A" for item in checks),
        "pass": sum(item["result"] == "PASS" for item in checks),
        "findings_total": len(unique_findings),
        "open_by_severity": {level: sum(f["severity"] == level and not f.get("closed_for_candidate", False) for f in unique_findings.values()) for level in ("P0", "P1", "P2")},
    }
    if case.get("expected_counts") != counts:
        return "COUNT_MISMATCH"
    blocking = any(f.get("severity") in {"P0", "P1"} and not f.get("closed_for_candidate", False) for f in unique_findings.values())
    if case.get("request_acceptance") and not review.get("report_done"):
        return "ACCEPT_BLOCKED"
    if case.get("request_rework") and review.get("report_done") and case.get("request_acceptance") and blocking:
        return "REWORK_READY_ACCEPT_BLOCKED"
    if case.get("request_acceptance") and any(point["state"] != "CONFIRMED" for point in points):
        return "ACCEPT_BLOCKED"
    if case.get("request_acceptance") and blocking:
        return "ACCEPT_BLOCKED"
    if case.get("request_acceptance") and any(item["result"] not in {"PASS", "N/A"} for item in checks):
        return "ACCEPT_BLOCKED"
    if case.get("request_rework") and not review.get("report_done"):
        return "REWORK_WAITING_REPORT"
    return "VALID"


def evaluate_c2(case: dict) -> str:
    operation = case.get("operation")
    if operation == "list":
        return "CURSOR_INVALID" if case.get("mapping_changed") else "VALID"
    if operation == "config_write":
        if "expected_config" not in case or "current_config" not in case or not isinstance(case["expected_config"], (dict, str)) or not isinstance(case["current_config"], (dict, str)):
            return "MISSING_CONDITION"
        return "CONFIG_CONFLICT" if case.get("expected_config") != case.get("current_config") else "SAVED"
    if operation not in {"update", "create", "preview_apply"}:
        return "UNSUPPORTED_OPERATION"
    if not case.get("conditional_write"):
        return "READ_ONLY"
    if any(not nonempty_string(case.get(key)) for key in ("expected_source_key", "current_source_key")):
        return "MISSING_CONDITION"
    if operation in {"update", "preview_apply"} and not nonempty_string(case.get("ref")):
        return "MISSING_CONDITION"
    if operation == "update" and any(key not in case or not isinstance(case[key], str) for key in ("expected_content", "current_content")):
        return "MISSING_CONDITION"
    if operation == "create" and (any(not nonempty_string(case.get(key)) for key in ("parent_ref", "target_id", "expected_index")) or not isinstance(case.get("target_exists"), bool)):
        return "MISSING_CONDITION"
    if operation == "preview_apply" and (not nonempty_string(case.get("preview_id")) or any(not isinstance(case.get(key), str) for key in ("expected_selection", "current_selection"))):
        return "MISSING_CONDITION"
    if case.get("expected_source_key") != case.get("current_source_key"):
        return "SOURCE_CHANGED"
    if case.get("rebind_during_write") and not case.get("lock_serialized"):
        return "UNSAFE_INTERLEAVING"
    if operation == "create" and case.get("target_exists"):
        return "ALREADY_EXISTS"
    if operation == "update" and case.get("expected_content") != case.get("current_content"):
        return "CONTENT_CONFLICT"
    if operation == "preview_apply":
        if not case.get("preview_alive"):
            return "PREVIEW_EXPIRED"
        if case.get("expected_selection") != case.get("current_selection"):
            return "CONTENT_CONFLICT"
    if case.get("known_partial"):
        return "PARTIAL" if case.get("known_effects") else "INVALID_ENVELOPE"
    if case.get("response_lost"):
        return "UNKNOWN"
    return "SAVED"


def evaluate_c3(case: dict) -> str:
    if case.get("required_features") and not set(case["required_features"]).issubset({"source", "execution"}):
        return "UNSUPPORTED_FEATURE"
    if case.get("display_extension") and not isinstance(case["display_extension"], dict):
        return "INVALID_ENVELOPE"
    if case.get("source_changed"):
        return "SOURCE_SET_CHANGED"
    if case.get("recorded_sha") != case.get("actual_sha"):
        return "STALE_REF"
    if not case.get("authoritative_source_ref") or case.get("authoritative_source_ref") != case.get("checkout_source_ref"):
        return "SOURCE_CHECKOUT_MISMATCH"
    if case.get("stage") == "source":
        return "SOURCE_ONLY" if case.get("valid") is False else "INVALID_ENVELOPE"
    if case.get("stage") != "execution" or case.get("valid") is not True:
        return "INVALID_ENVELOPE"
    if not case.get("service_available", True) and not case.get("fallback_same_source"):
        return "SOURCE_UNAVAILABLE"
    context = case.get("context")
    if not isinstance(context, dict) or not case.get("sources"):
        return "INVALID_ENVELOPE"
    if any(key not in context or context[key] in (None, "", [], {}) for key in REQUIRED_CONTEXT):
        return "MISSING_FIELD"
    if not valid_intent(context.get("intent")):
        return "MISSING_FIELD"
    if not isinstance(context.get("task_detail"), dict) or "blocker" not in context["task_detail"]:
        return "MISSING_FIELD"
    if context.get("trace") != "VALIDATED":
        return "INVALID_ENVELOPE"
    source_facts = case.get("source_facts")
    if not isinstance(source_facts, dict) or any(key not in source_facts for key in REQUIRED_CONTEXT) or source_facts.get("sources") != case["sources"] or not valid_intent(source_facts.get("intent")):
        return "MISSING_FIELD"
    if any(context[key] != source_facts[key] for key in REQUIRED_CONTEXT) or not case.get("profile_matches", True):
        return "PROFILE_PROJECTION_MISMATCH"
    return "VALID_FALLBACK" if not case.get("service_available", True) else "VALID"


def validate(root: Path) -> tuple[dict, int]:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.stat().st_size > MAX_MANIFEST:
        raise BundleError("manifest missing or exceeds 1 MiB")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise BundleError("manifest must be an object")
    unsupported = []
    if manifest.get("schema_version") != SCHEMA:
        unsupported.append(str(manifest.get("schema_version")))
    for name, version in VERSIONS.items():
        if manifest.get("contracts", {}).get(name) != version:
            unsupported.append(f"{name}:{manifest.get('contracts', {}).get(name)}")
    required = manifest.get("required_features", [])
    if not isinstance(required, list) or set(required) != set(VERSIONS) or len(required) != len(VERSIONS):
        unsupported.append("required_features")
    if unsupported:
        return {"valid": False, "checked_cases": 0, "failures": [], "unsupported_versions": unsupported}, 4
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) > MAX_FILES:
        raise BundleError("files must be an array of at most 1000 entries")
    seen_paths: set[str] = set()
    seen_cases: set[str] = set()
    failures: list[dict] = []
    checked = 0
    total = 0
    for entry in files:
        if not isinstance(entry, dict):
            raise BundleError("file entry must be an object")
        relative = entry.get("path")
        path = safe_file(root, relative)
        if relative in seen_paths:
            raise BundleError(f"duplicate path: {relative}")
        seen_paths.add(relative)
        actual_hash, size = digest(path)
        total += size
        if total > MAX_TOTAL:
            raise BundleError("bundle exceeds 64 MiB")
        if entry.get("sha256") != actual_hash:
            failures.append(fail(entry.get("case_id"), "sha256", entry.get("sha256"), actual_hash, relative))
            continue
        case_id = entry.get("case_id")
        if case_id is None:
            continue
        if not isinstance(case_id, str) or case_id in seen_cases:
            raise BundleError(f"duplicate or invalid case_id: {case_id}")
        seen_cases.add(case_id)
        contract = entry.get("contract")
        if contract not in VERSIONS or not case_id.startswith(contract.upper() + "-"):
            raise BundleError(f"contract/case mismatch: {case_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("case_id") != case_id:
            failures.append(fail(case_id, "case_id", case_id, data.get("case_id") if isinstance(data, dict) else None, relative))
            continue
        observed = {"c1": evaluate_c1, "c2": evaluate_c2, "c3": evaluate_c3}[contract](data)
        expected = entry.get("expected_result")
        checked += 1
        if observed != expected:
            failures.append(fail(case_id, "expected_result", expected, observed, relative))
    if len(seen_cases) != 23 or any(not {f"{name.upper()}-{i:02}" for i in range(1, count + 1)}.issubset(seen_cases) for name, count in (("c1", 4), ("c2", 10), ("c3", 9))):
        failures.append(fail(None, "case_ids", "C1-01..04, C2-01..10, C3-01..09", sorted(seen_cases)))
    for name in VERSIONS:
        if f"{name}.md" not in seen_paths:
            failures.append(fail(None, "contract_file", f"{name}.md", "missing"))
    return {"valid": not failures, "checked_cases": checked, "failures": failures, "unsupported_versions": []}, 0 if not failures else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--format", choices=("json",), default="json")
    args = parser.parse_args()
    try:
        result, code = validate(args.bundle)
    except (BundleError, OSError, ValueError, json.JSONDecodeError) as exc:
        result, code = {"valid": False, "checked_cases": 0, "failures": [fail(None, "bundle", "valid input", str(exc))], "unsupported_versions": []}, 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
