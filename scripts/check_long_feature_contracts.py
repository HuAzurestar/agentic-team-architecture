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
C1_SHAPE = {
    "source_scope": {"environment": str, "project": str, "document_ref": str},
    "points": [{"id": str, "text": str, "class": str, "state": str,
                "decided_by": str, "decided_at": str, "decision_history": [str]}],
    "tasks": [{"id": str, "state": str, "type": str, "detail_ref": str,
               "owner": str, "started_at": str, "completed_at": str,
               "depends_on": [str], "repository_refs": [str],
               "point_selectors": {"requirements": [str], "solutions": [str]}}],
    "available_evidence": [str], "declared_evidence": [str],
    "request_acceptance": bool, "request_rework": bool,
    "review": {
        "report_id": str, "attempt": str, "reviewer": str,
        "independent_context": str, "target_repo": str, "scope": str,
        "source_refs": [str], "report_done": bool,
        "findings": [{"finding_id": str, "severity": str, "description": str,
                      "affected_scope": str, "evidence": str, "resolution": str,
                      "closed_for_candidate": bool, "recheck_ref": str}],
        "checks": [{"check_id": str, "requirement_or_case": str, "result": str,
                    "reason": str, "evidence": [str], "finding_ids": [str]}],
    },
    "expected_counts": {"all": int, "pass": int, "findings_total": int,
                        "open_by_severity": {"P0": int, "P1": int, "P2": int}},
}


class BundleError(Exception):
    pass


def validate_shape(value: object, shape: object, field: str) -> None:
    """Check present known fields before collection/key operations.

    Missing facts are classified by the contract evaluator. Wrong JSON types
    are input errors, with field-only diagnostics rather than source contents.
    Unknown optional display fields are not interpreted here.
    """
    expected = dict if isinstance(shape, dict) else list if isinstance(shape, list) else shape
    if type(value) is not expected:
        raise BundleError(f"{field} must be {expected.__name__}")
    if isinstance(shape, dict):
        for key, child in shape.items():
            if key in value:
                validate_shape(value[key], child, f"{field}.{key}")
    elif isinstance(shape, list):
        for index, child in enumerate(value):
            validate_shape(child, shape[0], f"{field}[{index}]")


def fail(case_id: str | None, field: str, expected: object, observed: object, path: str | None = None) -> dict:
    result = {"case_id": case_id, "field": field, "expected": expected, "observed": observed}
    if path is not None:
        result["path"] = path
    return result


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def full_sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def string_array(value: object, *, allow_empty: bool = False) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(nonempty_string(item) for item in value)


def supported_features(case: dict, supported: frozenset[str] = frozenset()) -> bool:
    required = case.get("required_features", [])
    if not string_array(required, allow_empty=True):
        raise BundleError("required_features must be an array of nonempty strings")
    return set(required).issubset(supported)


def execution_facts(context: object) -> bool:
    """Validate captured facts before comparing a projection to its source.

    Empty dependency/gist sets are facts; missing fields and false scalars are
    not. This is structural validation, not a replacement for a real Git probe.
    """
    if not isinstance(context, dict) or any(key not in context for key in REQUIRED_CONTEXT):
        return False
    for key in ("feature", "task", "task_detail", "type_contract", "acceptance_brief"):
        if not isinstance(context[key], dict) or not context[key]:
            return False
    if any(not nonempty_string(context["feature"].get(key)) for key in ("id", "phase")):
        return False
    task = context["task"]
    if not nonempty_string(task.get("id")) or not nonempty_string(task.get("state")) or task["state"] not in {"PENDING", "WIP", "BLOCKED", "RECORDING", "DONE"}:
        return False
    if not nonempty_string(context["task_detail"].get("blocker")):
        return False
    if not valid_intent(context.get("intent")):
        return False
    repositories = context["repositories"]
    if not isinstance(repositories, list) or not repositories:
        return False
    if any(not isinstance(repo, dict) or not nonempty_string(repo.get("id")) or not full_sha(repo.get("sha")) for repo in repositories):
        return False
    if len({repo["id"] for repo in repositories}) != len(repositories):
        return False
    if not string_array(context["refs"]) or any(FULL_REPO_REF.fullmatch(ref) is None for ref in context["refs"]):
        return False
    return all(string_array(context[key], allow_empty=True) for key in ("dependencies", "gists"))


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
    if not supported_features(case):
        return "UNSUPPORTED_FEATURE"
    validate_shape(case, C1_SHAPE, "C1")
    scope = case.get("source_scope")
    if not isinstance(scope, dict) or any(not nonempty_string(scope.get(key)) for key in ("environment", "project", "document_ref")):
        return "INVALID_DOCUMENT"
    points = case.get("points")
    if not isinstance(points, list) or not points:
        return "INVALID_DOCUMENT"
    point_ids = [point.get("id") for point in points if isinstance(point, dict)]
    if len(point_ids) != len(points) or any(not nonempty_string(point_id) for point_id in point_ids) or len(set(point_ids)) != len(points):
        return "INVALID_DOCUMENT"
    for point in points:
        if not nonempty_string(point.get("text")) or point.get("class") not in {"ACTIVE", "DEFERRED"} or point.get("state") not in {"PROPOSED", "REOPENED", "CONFIRMED", "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"}:
            return "INVALID_DOCUMENT"
        if point["state"] not in {"PROPOSED", "REOPENED"} and any(not point.get(key) for key in ("decided_by", "decided_at", "decision_history")):
            return "INVALID_DOCUMENT"
    tasks = case.get("tasks", [])
    ids = [task.get("id") for task in tasks if isinstance(task, dict)]
    if not ids or len(ids) != len(tasks) or any(not nonempty_string(task_id) for task_id in ids) or len(ids) != len(set(ids)):
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
    if not full_sha(review.get("target_sha")) or not full_sha(case.get("candidate_sha")):
        return "INVALID_DOCUMENT"
    if review.get("target_sha") != case.get("candidate_sha"):
        return "STALE_EVIDENCE"
    findings = review.get("findings", [])
    if not isinstance(findings, list):
        return "INVALID_DOCUMENT"
    unique_findings: dict[str, dict] = {}
    for item in findings:
        if not isinstance(item, dict) or not nonempty_string(item.get("finding_id")) or item.get("severity") not in {"P0", "P1", "P2"}:
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
    if any(not nonempty_string(item.get("check_id")) or not nonempty_string(item.get("requirement_or_case")) or item.get("result") not in {"PASS", "FAIL", "UNKNOWN", "NOT-RUN", "N/A"} for item in checks):
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
    if not supported_features(case):
        return "UNSUPPORTED_FEATURE"
    validate_shape(case, {"operation": str}, "C2")
    # Observations are typed facts, never Python truthiness. Validate even fields
    # unused by this operation so another consumer cannot reinterpret the case.
    for key in ("conditional_write", "mapping_changed", "rebind_during_write",
                "lock_serialized", "target_exists", "preview_alive",
                "known_partial", "response_lost"):
        if key in case and not isinstance(case[key], bool):
            raise BundleError(f"{case.get('case_id')}: {key} must be a boolean")
    operation = case.get("operation")
    if operation == "list":
        return "CURSOR_INVALID" if case.get("mapping_changed") else "VALID"
    if operation == "config_write":
        if "expected_config" not in case or "current_config" not in case or not isinstance(case["expected_config"], (dict, str)) or not isinstance(case["current_config"], (dict, str)):
            return "MISSING_CONDITION"
        if case.get("rebind_during_write") and not case.get("lock_serialized"):
            return "UNSAFE_INTERLEAVING"
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
    if not supported_features(case, frozenset({"source", "execution"})):
        return "UNSUPPORTED_FEATURE"
    validate_shape(case, {key: bool for key in ("source_changed", "valid", "service_available",
                                              "fallback_same_source", "profile_matches")}, "C3")
    if "display_extension" in case and not isinstance(case["display_extension"], dict):
        return "INVALID_ENVELOPE"
    if case.get("source_changed"):
        return "SOURCE_SET_CHANGED"
    if case.get("stage") == "execution" and (not full_sha(case.get("recorded_sha")) or not full_sha(case.get("actual_sha"))):
        return "MISSING_FIELD"
    if case.get("recorded_sha") != case.get("actual_sha"):
        return "STALE_REF"
    if not nonempty_string(case.get("authoritative_source_ref")) or case.get("authoritative_source_ref") != case.get("checkout_source_ref"):
        return "SOURCE_CHECKOUT_MISMATCH"
    if case.get("stage") == "source":
        return "SOURCE_ONLY" if case.get("valid") is False else "INVALID_ENVELOPE"
    if case.get("stage") != "execution" or case.get("valid") is not True:
        return "INVALID_ENVELOPE"
    if not case.get("service_available", True) and not case.get("fallback_same_source"):
        return "SOURCE_UNAVAILABLE"
    context = case.get("context")
    if not isinstance(context, dict) or not string_array(case.get("sources")):
        return "INVALID_ENVELOPE"
    if not execution_facts(context):
        return "MISSING_FIELD"
    if context.get("trace") != "VALIDATED":
        return "INVALID_ENVELOPE"
    source_facts = case.get("source_facts")
    if not execution_facts(source_facts) or source_facts.get("sources") != case["sources"]:
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
    contracts = manifest.get("contracts", {})
    if not isinstance(contracts, dict):
        raise BundleError("manifest contracts must be an object")
    required = manifest.get("required_features", [])
    if not isinstance(required, list) or any(not nonempty_string(item) for item in required):
        raise BundleError("manifest required_features must be an array of nonempty strings")
    unsupported = []
    if manifest.get("schema_version") != SCHEMA:
        unsupported.append(str(manifest.get("schema_version")))
    for name, version in VERSIONS.items():
        if contracts.get(name) != version:
            unsupported.append(f"{name}:{contracts.get(name)}")
    unsupported.extend(f"contract:{name}" for name in contracts if name not in VERSIONS)
    if set(required) != set(VERSIONS) or len(required) != len(VERSIONS):
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
    broken_hash = False
    for entry in files:
        if not isinstance(entry, dict):
            raise BundleError("file entry must be an object")
        if not supported_features(entry):
            return {"valid": False, "checked_cases": checked, "failures": failures,
                    "unsupported_versions": ["file.required_features"]}, 4
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
            broken_hash = True
            failures.append(fail(entry.get("case_id"), "sha256", entry.get("sha256"), actual_hash, relative))
            continue
        case_id = entry.get("case_id")
        contract = entry.get("contract")
        if not nonempty_string(contract):
            raise BundleError(f"contract must be a nonempty string: {relative}")
        if contract not in VERSIONS:
            return {"valid": False, "checked_cases": checked, "failures": failures,
                    "unsupported_versions": [f"contract:{contract}"]}, 4
        if case_id is None:
            if relative in {f"{name}.md" for name in VERSIONS} and relative != f"{contract}.md":
                raise BundleError(f"specification/contract mismatch: {relative}")
            continue
        if not isinstance(case_id, str) or case_id in seen_cases:
            raise BundleError(f"duplicate or invalid case_id: {case_id}")
        seen_cases.add(case_id)
        if not case_id.startswith(contract.upper() + "-"):
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
    code = 2 if broken_hash else (3 if failures else 0)
    return {"valid": not failures, "checked_cases": checked, "failures": failures, "unsupported_versions": []}, code


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
