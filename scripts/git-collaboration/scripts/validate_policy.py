#!/usr/bin/env python3
"""Validate git-collaboration's canonical taxonomy and locale parity."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[a-z][a-z0-9-]*\Z")
LOCAL_LINK_RE = re.compile(r"\]\((?!https?://|mailto:|#)<?([^)>#\s]+)")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate policy-model.json and optional locale-package parity."
    )
    parser.add_argument("skill_root", help="Path to the git-collaboration skill root")
    parser.add_argument("--counterpart", help="Optional translated/canonical skill root")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--print-ruleset-regex",
        action="store_true",
        help="Print the GitHub commit-metadata regex derived from the model",
    )
    return parser.parse_args(argv)


def load_model(root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    model_path = root / "references" / "policy-model.json"
    if not model_path.is_file():
        return None, ["references/policy-model.json is missing"]
    try:
        model = json.loads(model_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"cannot parse references/policy-model.json: {exc}"]
    if not isinstance(model, dict):
        return None, ["policy model must be a JSON object"]
    return model, []


def _require_token(entry: dict[str, Any], key: str, location: str, findings: list[str]) -> str | None:
    value = entry.get(key)
    if not isinstance(value, str) or TOKEN_RE.fullmatch(value) is None:
        findings.append(f"{location}.{key} must be a lowercase hyphen token")
        return None
    return value


def validate_model(model: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if not isinstance(model.get("schema_version"), str):
        findings.append("schema_version must be a string")

    primary = model.get("primary_types")
    if not isinstance(primary, list) or not primary:
        return findings + ["primary_types must be a non-empty array"]

    issue_types: list[str] = []
    branch_prefixes: list[str] = []
    commit_types: list[str] = []
    for index, raw in enumerate(primary):
        location = f"primary_types[{index}]"
        if not isinstance(raw, dict):
            findings.append(f"{location} must be an object")
            continue
        issue_type = _require_token(raw, "issue_type", location, findings)
        branch_prefix = _require_token(raw, "branch_prefix", location, findings)
        commit_type = _require_token(raw, "commit_type", location, findings)
        if issue_type:
            issue_types.append(issue_type)
        if branch_prefix:
            branch_prefixes.append(branch_prefix)
        if commit_type:
            commit_types.append(commit_type)
        if "optional" in raw and not isinstance(raw["optional"], bool):
            findings.append(f"{location}.optional must be boolean")

    for label, values in (
        ("issue_type", issue_types),
        ("primary branch_prefix", branch_prefixes),
        ("primary commit_type", commit_types),
    ):
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            findings.append(f"duplicate {label}: {', '.join(duplicates)}")

    issue_type_set = set(issue_types)
    overrides = model.get("overrides")
    if not isinstance(overrides, list):
        findings.append("overrides must be an array")
        overrides = []
    override_names: list[str] = []
    for index, raw in enumerate(overrides):
        location = f"overrides[{index}]"
        if not isinstance(raw, dict):
            findings.append(f"{location} must be an object")
            continue
        name = _require_token(raw, "name", location, findings)
        prefix = _require_token(raw, "branch_prefix", location, findings)
        commit_type = _require_token(raw, "commit_type", location, findings)
        if name:
            override_names.append(name)
        if prefix:
            if prefix in branch_prefixes:
                findings.append(f"{location}.branch_prefix duplicates a primary prefix: {prefix}")
            branch_prefixes.append(prefix)
            branch_pattern = raw.get("branch_pattern")
            if not isinstance(branch_pattern, str) or not branch_pattern.startswith(prefix + "/"):
                findings.append(f"{location}.branch_pattern must start with {prefix}/")
        if commit_type:
            commit_types.append(commit_type)
        allowed = raw.get("allowed_issue_types")
        if not isinstance(allowed, list) or not allowed:
            findings.append(f"{location}.allowed_issue_types must be a non-empty array")
        else:
            unknown = sorted(set(allowed) - issue_type_set)
            if unknown:
                findings.append(f"{location} references unknown issue types: {', '.join(unknown)}")
        for key in ("requires_issue", "issue_in_branch_name"):
            if not isinstance(raw.get(key), bool):
                findings.append(f"{location}.{key} must be boolean")

    duplicate_overrides = sorted(
        {value for value in override_names if override_names.count(value) > 1}
    )
    if duplicate_overrides:
        findings.append(f"duplicate override name: {', '.join(duplicate_overrides)}")

    exemptions = model.get("exemptions")
    if not isinstance(exemptions, list):
        findings.append("exemptions must be an array")
        exemptions = []
    exemption_names: list[str] = []
    for index, raw in enumerate(exemptions):
        location = f"exemptions[{index}]"
        if not isinstance(raw, dict):
            findings.append(f"{location} must be an object")
            continue
        name = _require_token(raw, "name", location, findings)
        if name:
            exemption_names.append(name)
        if raw.get("requires_issue") is not False:
            findings.append(f"{location}.requires_issue must be false")
        if raw.get("require_documented_reason") is not True:
            findings.append(f"{location}.require_documented_reason must be true")
    duplicate_exemptions = sorted(
        {value for value in exemption_names if exemption_names.count(value) > 1}
    )
    if duplicate_exemptions:
        findings.append(f"duplicate exemption name: {', '.join(duplicate_exemptions)}")

    return findings


def ruleset_regex(model: dict[str, Any]) -> str:
    ordered: list[str] = []
    for group in (model.get("primary_types", []), model.get("overrides", [])):
        for entry in group:
            if isinstance(entry, dict):
                value = entry.get("commit_type")
                if isinstance(value, str) and value not in ordered:
                    ordered.append(value)
    choices = "|".join(re.escape(value) for value in ordered)
    return (
        rf"^#[1-9][0-9]* ({choices})"
        rf"(\([a-z0-9][a-z0-9-]*\))?!?: [^\r\n]+"
    )


def validate_document_projection(root: Path, model: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    branches_path = root / "references" / "branches.md"
    github_path = root / "references" / "github.md"
    if not branches_path.is_file():
        findings.append("references/branches.md is missing")
        return findings
    branches = branches_path.read_text(encoding="utf-8")
    for entry in model.get("primary_types", []):
        issue_type = entry["issue_type"]
        prefix = entry["branch_prefix"]
        commit_type = entry["commit_type"]
        pattern = f"{prefix}/<issue>-<summary>"
        row_prefix = f"| `{issue_type}` | `{prefix}/<issue>-...` | `{commit_type}` |"
        if pattern not in branches:
            findings.append(f"branches.md is missing branch pattern: {pattern}")
        if row_prefix not in branches:
            findings.append(
                f"branches.md is missing policy-model mapping: {issue_type}/{prefix}/{commit_type}"
            )
    for entry in model.get("overrides", []):
        pattern = entry.get("branch_pattern")
        if isinstance(pattern, str) and pattern not in branches:
            findings.append(f"branches.md is missing override pattern: {pattern}")
    if not github_path.is_file():
        findings.append("references/github.md is missing")
    elif ruleset_regex(model) not in github_path.read_text(encoding="utf-8"):
        findings.append("github.md Ruleset regex differs from policy-model.json")
    return findings


def package_inventory(root: Path) -> set[str]:
    inventory: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix in IGNORED_SUFFIXES:
            continue
        inventory.add(path.relative_to(root).as_posix())
    return inventory


def markdown_local_targets(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return sorted(match.group(1) for match in LOCAL_LINK_RE.finditer(text))


def normalized_code_blocks(path: Path) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    compare_current = False
    marker_char = ""
    marker_length = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        fence = FENCE_RE.match(raw_line)
        if fence:
            marker = fence.group(1)
            if current is None:
                current = []
                language = raw_line[fence.end() :].strip().lower()
                compare_current = language in {"bash", "shell", "sh", "regex", "yaml", "yml", "json"}
                marker_char = marker[0]
                marker_length = len(marker)
            elif marker[0] == marker_char and len(marker) >= marker_length:
                if compare_current:
                    blocks.append(current)
                current = None
                compare_current = False
                marker_char = ""
                marker_length = 0
            continue
        if current is None:
            continue
        line = raw_line.strip()
        if not line or line.startswith("# "):
            continue
        line = re.sub(r"\s+#\s+.*$", "", line).rstrip()
        if line:
            current.append(line)
    if current is not None and compare_current:
        blocks.append(current)
    return blocks


def validate_localized_structure(root: Path, counterpart: Path) -> list[str]:
    findings: list[str] = []
    common = package_inventory(root) & package_inventory(counterpart)
    for relative in sorted(common):
        first = root / relative
        second = counterpart / relative
        if relative.endswith(".md"):
            if markdown_local_targets(first) != markdown_local_targets(second):
                findings.append(f"counterpart local link targets differ: {relative}")
            if normalized_code_blocks(first) != normalized_code_blocks(second):
                findings.append(f"counterpart normalized code blocks differ: {relative}")
        elif relative.startswith("scripts/") and first.read_bytes() != second.read_bytes():
            findings.append(f"counterpart validation script differs: {relative}")
    return findings


def validate_counterpart(root: Path, counterpart: Path, model: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if not counterpart.is_dir():
        return [f"counterpart directory not found: {counterpart}"]
    missing = sorted(package_inventory(root) - package_inventory(counterpart))
    extra = sorted(package_inventory(counterpart) - package_inventory(root))
    if missing:
        findings.append("counterpart missing files: " + ", ".join(missing))
    if extra:
        findings.append("counterpart has extra files: " + ", ".join(extra))
    other_model, load_findings = load_model(counterpart)
    findings.extend(f"counterpart {item}" for item in load_findings)
    if other_model is not None and other_model != model:
        findings.append("counterpart policy-model.json differs from the canonical model")
    findings.extend(validate_localized_structure(root, counterpart))
    return findings


def emit(findings: list[str], output_format: str) -> None:
    payload = {"passed": not findings, "findings": findings}
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"passed={str(not findings).lower()}")
    for finding in findings:
        print(f"ERROR {finding}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.skill_root).resolve()
    if not root.is_dir():
        print(f"skill root not found: {root}", file=sys.stderr)
        return 2
    model, findings = load_model(root)
    if model is not None:
        findings.extend(validate_model(model))
        if not findings:
            findings.extend(validate_document_projection(root, model))
        if args.counterpart:
            findings.extend(validate_counterpart(root, Path(args.counterpart).resolve(), model))
    if args.print_ruleset_regex and model is not None and not findings:
        print(ruleset_regex(model))
    else:
        emit(findings, args.format)
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
