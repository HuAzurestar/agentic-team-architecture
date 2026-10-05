#!/usr/bin/env python3
"""Strict-reader adapter and read-only CLI for task_next; not a task writer."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import MappingProxyType
from typing import Any

sys.dont_write_bytecode = True
import task_context as tc
import task_next as selector

MAX_FILES = 11_004
MAX_BYTES = 64 * 1024 * 1024
MAX_HOST_BYTES = 1024 * 1024


class SelectionError(tc.ContextError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _linked(path: Path) -> bool:
    info = path.lstat()
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def file_snapshot(root: Path) -> dict[str, str]:
    """Bound raw control files, task files and gist tree, including membership.

    This is a consistency envelope around the existing reader, not the full
    DocumentLoader refactor. It intentionally includes undeclared gist files so
    additions/removals cannot disappear between validation and selection.
    """
    files = {}
    consumed = 0
    entries = 0
    pending = [root / name for name in ("REQUIREMENT.md", "SOLUTION.md", "STATUS.md", "TASKS.md",
                                       "tasks", "gists")]
    while pending:
        path = pending.pop()
        if path == root / "gists" and not path.exists() and not path.is_symlink():
            continue
        entries += 1
        if entries > MAX_FILES + 1024:
            raise SelectionError("RESOURCE_LIMIT")
        if _linked(path) or not path.resolve().is_relative_to(root):
            raise SelectionError("UNSAFE_SOURCE_PATH")
        if path.is_dir():
            # scandir is incremental: do not materialize an unbounded directory.
            with os.scandir(path) as iterator:
                for entry in iterator:
                    pending.append(Path(entry.path))
                    if len(pending) + entries > MAX_FILES + 1024:
                        raise SelectionError("RESOURCE_LIMIT")
            continue
        if not path.is_file():
            raise SelectionError("UNSAFE_SOURCE_PATH")
        if len(files) >= MAX_FILES:
            raise SelectionError("RESOURCE_LIMIT")
        info = path.stat()
        if info.st_size > MAX_BYTES - consumed:
            raise SelectionError("RESOURCE_LIMIT")
        with path.open("rb") as stream:
            content = stream.read(MAX_BYTES - consumed + 1)
        consumed += len(content)
        if consumed > MAX_BYTES:
            raise SelectionError("RESOURCE_LIMIT")
        files[path.relative_to(root).as_posix()] = hashlib.sha256(content).hexdigest()
    return files


def _git(path: Path, *arguments: str) -> str:
    process = subprocess.run(["git", "--no-optional-locks", "-C", str(path), *arguments],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=10, check=False)
    if process.returncode:
        # Do not echo repository URLs, config values, credentials or document data.
        raise SelectionError("GIT_OBSERVATION_FAILED")
    if len(process.stdout) > MAX_BYTES:
        raise SelectionError("RESOURCE_LIMIT")
    return hashlib.sha256(process.stdout).hexdigest()


def repo_snapshot(root: Path, repositories: dict) -> dict:
    result = {}
    status = tc.focused_status(tc.read_utf8(root / "STATUS.md"))
    for name, repository in repositories.items():
        path = Path(repository["path"])
        # Worktrees share a ref database. Other features' branches may advance
        # concurrently; bind only refs this feature actually registers/validates.
        branches = {repository[key] for key in ("stable_branch", "integration_branch", "actual_branch")}
        branches.update(row[2] for row in status["working_branches"]["rows"] if row[0] == name)
        branches.update(row[1] for row in status["integration_opponents"]["rows"] if row[0] == name)
        for row in status["pr_mr_objects"]["rows"]:
            if len(row) >= 6 and row[1] == name:
                branches.update((row[2], row[4]))
        status_args = ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
        if repository["role"] == "project-management":
            status_args += ["--", root.relative_to(path).as_posix()]
        result[name] = {
            "path": str(path.resolve()),
            "identity": _git(path, "rev-parse", "--absolute-git-dir", "--git-common-dir"),
            "head": _git(path, "rev-parse", "HEAD"),
            "branch": _git(path, "symbolic-ref", "-q", "HEAD"),
            "refs": _git(path, "show-ref", "--verify", "--",
                         *("refs/heads/" + branch for branch in sorted(branches))),
            "config": _git(path, "config", "--local", "--null", "--list"),
            "status": _git(path, *status_args),
        }
    return result


def load_validated(feature_directory: Path, repo_overrides: dict[str, Path] | None = None
                   ) -> selector.ValidatedContext:
    root = feature_directory.resolve(strict=True)
    before_files = file_snapshot(root)
    # Resolve real repo identities before taking the before-ref observation. The
    # strict reader repeats that check; source/ref equality encloses both reads.
    registry = tc.repository_registry(tc.read_utf8(root / "STATUS.md"))
    repositories = tc.resolve_repositories(root, registry, repo_overrides or {})
    if not repositories:
        raise SelectionError("UNVERIFIED_TRACE")
    before_refs = repo_snapshot(root, repositories)
    context = tc.build_context(root, repo_overrides=repo_overrides, include_selection=True)
    if context["trace"]["mode"] != "VALIDATED":
        raise SelectionError("UNVERIFIED_TRACE")
    if repositories != context["repositories"]:
        raise SelectionError("SOURCE_CHANGED")
    after_refs = repo_snapshot(root, context["repositories"])
    after_files = file_snapshot(root)
    if before_files != after_files or before_refs != after_refs:
        raise SelectionError("SOURCE_CHANGED")
    projected = context["selection"]
    binding = "selection-sha256:" + _digest({"feature_root": str(root), "files": before_files,
                                            "repositories": before_refs, "projection": projected})
    tasks = tuple(selector.Task(
        id=item["id"], state=item["state"], dependencies=tuple(item["dependencies"]),
        kind=item["kind"], contract=MappingProxyType(dict(item["contract"])),
        release_condition=item["release_condition"]) for item in projected["tasks"])
    return selector.ValidatedContext(binding, projected["current_task"], projected["current_gate"], tasks)


def _object(value: Any, fields: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) - fields:
        raise SelectionError("INVALID_HOST_INPUT")
    return value


def _text(value: Any, *, optional: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 1024 or (not optional and not value.strip()):
        raise SelectionError("INVALID_HOST_INPUT")
    return value


def _boolean(value: Any) -> bool:
    if type(value) is not bool:
        raise SelectionError("INVALID_HOST_INPUT")
    return value


def _strings(value: Any, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise SelectionError("INVALID_HOST_INPUT")
    result = tuple(_text(item) for item in value)
    if len(set(result)) != len(result):
        raise SelectionError("INVALID_HOST_INPUT")
    return result


def parse_host_input(raw: bytes, context: selector.ValidatedContext, authority_ref: str
                     ) -> tuple[selector.Authorization, selector.ObservedGateEvidence]:
    """Parse only explicit host stdin, never files from the feature."""
    if len(raw) > MAX_HOST_BYTES:
        raise SelectionError("RESOURCE_LIMIT")
    _text(authority_ref)
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise SelectionError("INVALID_HOST_INPUT")
            value[key] = item
        return value
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise SelectionError("INVALID_HOST_INPUT") from exc
    obj = _object(obj, {"source_ref", "grants", "evidence"})
    source_ref = _text(obj.get("source_ref"))
    ids = {task.id for task in context.tasks}
    grants = _object(obj.get("grants", {}), ids)
    evidence = _object(obj.get("evidence", {}), ids)
    normalized_grants = {}
    for key, raw_grant in grants.items():
        item = _object(raw_grant, {"operation", "capabilities", "outside_scope"})
        operation = _text(item.get("operation"))
        if operation not in selector.OPERATIONS:
            raise SelectionError("INVALID_HOST_INPUT")
        capabilities = frozenset(_strings(item.get("capabilities", []), 4))
        if capabilities - {"execute", "merge", "publish", "request-acceptance"}:
            raise SelectionError("INVALID_HOST_INPUT")
        normalized_grants[key] = selector.Grant(
            operation, capabilities, authority_ref, _boolean(item.get("outside_scope", False)))
    normalized_evidence = {}
    for key, raw_evidence in evidence.items():
        item = _object(raw_evidence, {"verdict", "evidence_refs", "target_sha", "acceptance_task",
                                    "release_condition", "release_satisfied"})
        verdict = _text(item.get("verdict"))
        if verdict not in selector.VERDICTS:
            raise SelectionError("INVALID_HOST_INPUT")
        acceptance = item.get("acceptance_task")
        if acceptance is not None and (not isinstance(acceptance, str) or acceptance not in ids):
            raise SelectionError("INVALID_HOST_INPUT")
        normalized_evidence[key] = selector.GateEvidence(
            verdict, _strings(item.get("evidence_refs", []), 32),
            _text(item.get("target_sha", ""), optional=True), acceptance,
            _text(item.get("release_condition", ""), optional=True),
            _boolean(item.get("release_satisfied", False)))
    return (selector.Authorization(source_ref, MappingProxyType(normalized_grants)),
            selector.ObservedGateEvidence(source_ref, MappingProxyType(normalized_evidence)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only next-action suggestion after full recovery.")
    parser.add_argument("feature_directory")
    parser.add_argument("--repo", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--host-input", action="store_true",
                        help="Read bounded host grants/evidence JSON from stdin, never from feature files")
    parser.add_argument("--authority-source-ref",
                        help="Actual current host/user instruction reference; does not authenticate a decision")
    args = parser.parse_args(argv)
    if args.host_input != bool(args.authority_source_ref):
        parser.error("--host-input and --authority-source-ref are required together")
    source_ref = None
    count, elapsed = 0, 0.0
    try:
        context = load_validated(Path(args.feature_directory), tc.parse_repo_overrides(args.repo))
        source_ref = context.source_ref
        if args.host_input:
            raw = sys.stdin.buffer.read(MAX_HOST_BYTES + 1)
            authorization, evidence = parse_host_input(raw, context, args.authority_source_ref)
        else:
            authorization = selector.Authorization(source_ref)
            evidence = selector.ObservedGateEvidence(source_ref)
        action, count, elapsed = selector.select_with_metrics(context, authorization, evidence)
        exit_code = 2 if action.action == "repair-plan" else 0
    except (tc.ContextError, OSError, subprocess.SubprocessError) as exc:
        if isinstance(exc, SelectionError):
            code = exc.code
        elif isinstance(exc, tc.ContextError) and str(exc).startswith("RESOURCE_LIMIT:"):
            code = "RESOURCE_LIMIT"
        elif isinstance(exc, tc.ContextError) and str(exc).startswith("INVALID_GRAPH:"):
            code = "INVALID_GRAPH"
        else:
            code = "CONTEXT_INVALID"
        action = selector.NextAction("repair-plan", None, code)
        exit_code = 2
    print(json.dumps({"source_ref": source_ref, "next_action": asdict(action)},
                     ensure_ascii=True, separators=(",", ":")))
    print(json.dumps({"event": "selector.result", "action": action.action,
                      "reason_code": action.reason_code, "candidate_count": count,
                      "elapsed_ms": elapsed}, separators=(",", ":")), file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
