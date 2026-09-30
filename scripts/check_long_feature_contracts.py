"""Read-only validation of the PIRC-31 C1/C2/C3 fixture bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
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


class BundleError(Exception):
    pass


def fail(case_id: str | None, field: str, expected: object, observed: object) -> dict:
    return {"case_id": case_id, "field": field, "expected": expected, "observed": observed}


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
    tasks = case.get("tasks", [])
    ids = [task.get("id") for task in tasks if isinstance(task, dict)]
    if not ids or len(ids) != len(tasks) or len(ids) != len(set(ids)):
        return "INVALID_DOCUMENT"
    if any(ref not in case.get("available_evidence", []) for ref in case.get("declared_evidence", [])):
        return "MISSING_EVIDENCE"
    review = case.get("review", {})
    if review.get("target_sha") != case.get("candidate_sha"):
        return "STALE_EVIDENCE"
    findings = review.get("findings", [])
    if len({f.get("finding_id") for f in findings}) != len(findings):
        return "INVALID_DOCUMENT"
    checks = review.get("checks", [])
    if not checks or any(item.get("result") not in {"PASS", "FAIL", "UNKNOWN", "NOT-RUN", "N/A"} for item in checks):
        return "INVALID_DOCUMENT"
    if any(item.get("result") == "N/A" and not item.get("reason") for item in checks):
        return "INVALID_DOCUMENT"
    if not any(item.get("result") != "N/A" for item in checks):
        return "INVALID_DOCUMENT"
    blocking = any(f.get("severity") in {"P0", "P1"} and not f.get("closed_for_candidate", False) for f in findings)
    if case.get("request_rework") and review.get("report_done") and case.get("request_acceptance") and blocking:
        return "REWORK_READY_ACCEPT_BLOCKED"
    if case.get("request_acceptance") and blocking:
        return "ACCEPT_BLOCKED"
    if case.get("request_rework") and not review.get("report_done"):
        return "REWORK_WAITING_REPORT"
    return "VALID"


def evaluate_c2(case: dict) -> str:
    operation = case.get("operation")
    if operation == "list":
        return "CURSOR_INVALID" if case.get("mapping_changed") else "VALID"
    if operation == "config_write":
        return "CONFIG_CONFLICT" if case.get("expected_config") != case.get("current_config") else "SAVED"
    if operation not in {"update", "create", "preview_apply"}:
        return "UNSUPPORTED_OPERATION"
    if not case.get("conditional_write"):
        return "READ_ONLY"
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
    if not case.get("same_source") or not case.get("profile_matches", True):
        return "SOURCE_CHECKOUT_MISMATCH"
    if case.get("stage") == "source":
        return "SOURCE_ONLY"
    if case.get("stage") != "execution" or case.get("valid") is not True:
        return "INVALID_ENVELOPE"
    if not case.get("service_available", True) and not case.get("fallback_same_source"):
        return "SOURCE_UNAVAILABLE"
    context = case.get("context")
    if not isinstance(context, dict) or not case.get("sources"):
        return "INVALID_ENVELOPE"
    if any(key not in context or context[key] in (None, "", [], {}) for key in REQUIRED_CONTEXT):
        return "MISSING_FIELD"
    if not isinstance(context.get("task_detail"), dict) or "blocker" not in context["task_detail"]:
        return "MISSING_FIELD"
    if context.get("trace") != "VALIDATED":
        return "INVALID_ENVELOPE"
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
            failures.append(fail(entry.get("case_id"), "sha256", entry.get("sha256"), actual_hash))
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
            failures.append(fail(case_id, "case_id", case_id, data.get("case_id") if isinstance(data, dict) else None))
            continue
        observed = {"c1": evaluate_c1, "c2": evaluate_c2, "c3": evaluate_c3}[contract](data)
        expected = entry.get("expected_result")
        checked += 1
        if observed != expected:
            failures.append(fail(case_id, "expected_result", expected, observed))
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
