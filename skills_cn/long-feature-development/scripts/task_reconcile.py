#!/usr/bin/env python3
"""Inspect a moved feature; explicitly apply a bounded local metadata repair.

No Git writes, network requests, task-state changes or implicit authorization.
Plans are kept in a gist already declared by the current task. Applying a plan
is a single-coordinator operation, not a multi-file transaction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit

sys.dont_write_bytecode = True
import task_context as tc

MAX_FILES = 1000
MAX_BYTES = 64 * 1024 * 1024
MAX_PLAN_BYTES = 4 * 1024 * 1024
MAX_REPOS = 32


class RecoveryError(ValueError):
    def __init__(self, code, **details):
        self.diagnostic = {"code": code, **details}
        super().__init__(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bounded_bytes(path, limit=MAX_BYTES):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise RecoveryError("RESOURCE_LIMIT", resource="document_bytes")
    return raw


def safe_path(root, relative):
    if not isinstance(relative, str) or "\\" in relative:
        raise RecoveryError("UNSAFE_PATH")
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(p in {".", ".."} or ":" in p for p in path.parts) or len(path.parts) > 8:
        raise RecoveryError("UNSAFE_PATH")
    component = root
    for part in path.parts:
        component = component / part
        if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
            raise RecoveryError("UNSAFE_PATH")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise RecoveryError("UNSAFE_PATH")
    return resolved


def decode(raw):
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise RecoveryError("INVALID_UTF8") from None
    if "\r" in text.replace("\r\n", ""):
        raise RecoveryError("UNSUPPORTED_NEWLINE")
    if "\r\n" in text and "\n" in text.replace("\r\n", ""):
        raise RecoveryError("UNSUPPORTED_NEWLINE")
    return text.replace("\r\n", "\n")


def encode(text, original):
    if b"\r\n" in original:
        text = text.replace("\n", "\r\n")
    return (b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b"") + text.encode("utf-8")


def remote_identity(value):
    # Preserve path case; a case-insensitive comparison can accept another repo.
    value = value.strip().replace("\\", "/").rstrip("/")
    return value[:-4] if value.endswith(".git") else value


def public_remote(value):
    if "://" in value:
        parts = urlsplit(value)
        return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))
    if "@" in value:
        return value.rsplit("@", 1)[-1]
    return value


class GitProbe:
    def __init__(self):
        self.deadline = time.monotonic() + 60

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RecoveryError("RESOURCE_LIMIT", resource="elapsed_seconds")
        return remaining

    def run(self, path, *args, check=True):
        remaining = self.remaining()
        try:
            result = subprocess.run(["git", "--no-optional-locks", "-C", str(path), *args], capture_output=True,
                                    timeout=min(10, remaining))
        except subprocess.TimeoutExpired:
            raise RecoveryError("GIT_TIMEOUT") from None
        except OSError:
            raise RecoveryError("GIT_UNAVAILABLE") from None
        if check and result.returncode:
            # Never leak credential-bearing remotes or raw Git stderr.
            raise RecoveryError("GIT_CHECK_FAILED")
        if result.returncode:
            return None
        output = result.stdout.decode("utf-8", errors="strict")
        return output if "-z" in args else output.rstrip("\r\n")

    def commit_exists(self, path, sha):
        tc.validate_literal_sha(sha, "recovery commit")
        return self.run(path, "rev-parse", "--verify", f"{sha}^{{commit}}", check=False) is not None

    def is_ancestor(self, path, older, newer):
        tc.validate_literal_sha(older, "recovery ancestor")
        tc.validate_literal_sha(newer, "recovery descendant")
        return self.run(path, "merge-base", "--is-ancestor", older, newer, check=False) is not None


class ReadSet:
    def __init__(self, root, originals=None):
        self.root, self.originals, self.raw = root, originals or {}, {}
        self.total = 0

    def load(self, relative):
        if relative not in self.raw:
            path = safe_path(self.root, relative)
            if not path.is_file():
                raise RecoveryError("EVIDENCE_MISSING", path=relative)
            raw = bounded_bytes(path, MAX_BYTES - self.total)
            raw = self.originals.get(relative, raw)
            self.total += len(raw)
            if self.total > MAX_BYTES or len(self.raw) >= MAX_FILES:
                raise RecoveryError("RESOURCE_LIMIT", resource="documents")
            self.raw[relative] = raw
        return self.raw[relative]

    def read(self, relative):
        return decode(self.load(relative))


def row_line(text, cells):
    matches = [line for line in text.splitlines() if [tc.clean_cell(v) for v in tc.split_row(line)] == cells]
    if len(matches) != 1:
        raise RecoveryError("AMBIGUOUS_ROW")
    return matches[0]


def replace_operations(text, operations, reverse=False):
    for operation in reversed(operations) if reverse else operations:
        old, new = operation["old_value"], operation["new_value"]
        if reverse:
            old, new = new, old
        if operation["kind"] == "append":
            if reverse:
                if not text.endswith(old):
                    raise RecoveryError("CONTENT_CONFLICT")
                text = text[:-len(old)]
            else:
                text += new
        else:
            if not old or text.splitlines().count(old) != 1:
                raise RecoveryError("CONTENT_CONFLICT")
            lines = text.splitlines(keepends=True)
            text = "".join(new + ("\n" if line.endswith("\n") else "")
                           if line.rstrip("\n") == old else line for line in lines)
    return text


def resolve_repositories(root, registry, overrides, git):
    if not registry or len(registry) > MAX_REPOS or set(overrides) - set(registry):
        raise RecoveryError("INVALID_REPOSITORY_SET")
    management_root = git.run(root, "rev-parse", "--show-toplevel")
    management_root = Path(management_root).resolve()
    resolved = {}
    siblings = None
    for name, item in registry.items():
        if name in overrides:
            candidates = [Path(overrides[name]).resolve()]
        else:
            candidates = [(management_root / h.strip()).resolve() for h in item["path_hints"].split(";")]
            if siblings is None:
                siblings = []
                for child in management_root.parent.iterdir():
                    if child.is_dir():
                        siblings.append(child.resolve())
                        if len(siblings) > MAX_REPOS:
                            raise RecoveryError("RESOURCE_LIMIT", resource="repository_candidates")
            candidates += siblings
        candidates = list(dict.fromkeys(candidates))
        if len(candidates) > MAX_REPOS:
            raise RecoveryError("RESOURCE_LIMIT", resource="repository_candidates")
        matches = {}
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            actual = git.run(candidate, "rev-parse", "--show-toplevel", check=False)
            if not actual or Path(actual).resolve() != candidate:
                continue
            remotes = git.run(candidate, "remote").splitlines()
            if any(remote_identity(git.run(candidate, "remote", "get-url", remote)) == remote_identity(item["remote"])
                   for remote in remotes):
                matches[str(candidate)] = candidate
        if len(matches) != 1:
            raise RecoveryError("AMBIGUOUS_REPOSITORY" if len(matches) > 1 else "REPO_IDENTITY_MISMATCH", repository=name)
        path = next(iter(matches.values()))
        if item["role"] == "project-management" and path != management_root:
            raise RecoveryError("REPO_IDENTITY_MISMATCH", repository=name)
        branch = git.run(path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
        if not branch:
            raise RecoveryError("DETACHED_HEAD", repository=name)
        resolved[name] = dict(item, path=str(path), actual_branch=branch,
                              actual_head=git.run(path, "rev-parse", "HEAD"))
    return resolved


def inspect(feature, repo_overrides=None, *, plan_gist, _originals=None, _allowed_dirty=(),
            _plan_id=None, _observed_at=None, _git=None):
    root = Path(feature).resolve()
    plan = dict(plan_version="recovery-plan-v1", feature_key=root.name, feature_root=str(root),
                plan_id=_plan_id or str(uuid.uuid4()), observed_at=_observed_at or datetime.now(timezone.utc).isoformat(),
                task_id=None, plan_gist=plan_gist, repositories=[], comparisons=[], edits=[],
                read_set={}, blockers=[], complete=False, next_action="inspect-diagnostics")
    git = _git or GitProbe()
    documents = ReadSet(root, _originals)
    operations = {}
    try:
        requirement, solution, status, tasks = [documents.read(f) for f in
                                               ("REQUIREMENT.md", "SOLUTION.md", "STATUS.md", "TASKS.md")]
        tc.reject_legacy_status_table(status)
        records = tc.task_records(tasks)
        tc.validate_dependency_graph(records)
        tc.validate_topology(tasks, records)
        tc.validate_decision_mapping(records, requirement, solution)
        tc.validate_feature_state(status, records)
        task_id = tc.selected_task_id(status, None)
        plan["task_id"] = task_id
        if task_id not in records:
            raise RecoveryError("INVALID_CURRENT_TASK")
        actual_files = set()
        for path in (root / "tasks").glob("*.md"):
            actual_files.add(path.name)
            if len(actual_files) > MAX_FILES:
                raise RecoveryError("RESOURCE_LIMIT", resource="documents")
        if actual_files != {f"{key}.md" for key in records}:
            raise RecoveryError("TASK_SET_MISMATCH")
        details = {}
        for key, record in records.items():
            text = documents.read(f"tasks/{key}.md")
            details[key] = tc.task_detail(root, record, text=text)
            for relative, _ in tc.declared_gist_paths(text, root):
                if relative != plan_gist:
                    documents.read(relative)
        declared = dict(tc.declared_gist_paths(details[task_id][0], root))
        if plan_gist not in declared:
            raise RecoveryError("PLAN_NOT_DECLARED")
        tc.validate_type_contracts(records, details, root)
        registry = tc.repository_registry(status)
        overrides = {name: Path(path).resolve() for name, path in (repo_overrides or {}).items()}
        resolved = resolve_repositories(root, registry, overrides, git)
        summary = tc.focused_status(status)
        working = summary["working_branches"]["rows"]
        if len(working) != len(resolved) or {row[0] for row in working} != set(resolved):
            raise RecoveryError("INVALID_REPOSITORY_SET")
        detail_path = f"tasks/{task_id}.md"
        current_detail, current_refs = details[task_id]
        current_ref_map = {r["repository"]: r for r in current_refs}
        head_refs = dict(records[task_id]["head_refs"])

        def change(relative, field, cells, new_cells):
            if cells != new_cells:
                operations.setdefault(relative, []).append(dict(kind="row", field=field,
                    old_value=row_line(documents.read(relative), cells), new_value="| " + " | ".join(new_cells) + " |"))

        def note(relative, value):
            operations.setdefault(relative, []).append(dict(kind="append", field="recovery_history", old_value="", new_value="\n" + value + "\n"))

        for row in working:
            name, old_path, old_branch, old_head = row[:4]
            repo = resolved[name]
            path = Path(repo["path"])
            head = repo["actual_head"]
            relative_root = root.relative_to(path).as_posix() if repo["role"] == "project-management" else None
            status_z = git.run(path, "status", "--porcelain=v1", "-z", "--untracked-files=all")
            changes = [entry for entry in status_z.split("\0") if entry]
            allowed = {plan_gist, *_allowed_dirty}
            for entry in changes:
                # Renames have a second path; none is a valid metadata repair.
                if len(entry) < 4 or "R" in entry[:2] or "C" in entry[:2]:
                    raise RecoveryError("UNOWNED_CHANGES", repository=name)
                changed = entry[3:]
                if relative_root is not None:
                    prefix = relative_root + "/" if relative_root != "." else ""
                    if prefix and not changed.startswith(prefix):
                        continue
                    if changed[len(prefix):] in allowed:
                        continue
                raise RecoveryError("UNOWNED_CHANGES", repository=name)
            if relative_root is not None:
                tracked = set(git.run(path, "ls-files", "-z").split("\0"))
                for relative in documents.raw:
                    full = (root / relative).relative_to(path).as_posix()
                    if full not in tracked:
                        raise RecoveryError("UNTRACKED_RECORD", path=relative)
                if (root / plan_gist).relative_to(path).as_posix() not in tracked:
                    raise RecoveryError("UNTRACKED_RECORD", path=plan_gist)
            if old_head == "DERIVED:HEAD":
                if repo["role"] != "project-management":
                    raise RecoveryError("INVALID_DERIVED_HEAD")
            elif not git.commit_exists(path, old_head):
                raise RecoveryError("MISSING_COMMIT", repository=name)
            elif not git.is_ancestor(path, old_head, head):
                raise RecoveryError("REF_MOVED", repository=name)
            elif old_head != head and old_branch == repo["actual_branch"]:
                raise RecoveryError("UNRECORDED_HEAD", repository=name)
            branch_changed = old_branch != repo["actual_branch"]
            if branch_changed:
                if records[task_id]["state"] not in {"WIP", "RECORDING", "BLOCKED"} or name not in current_ref_map:
                    raise RecoveryError("ATTEMPT_REQUIRED", repository=name)
                ref = current_ref_map[name]
                retained = [sha for _, sha in tc.ref_tokens(ref["start_refs"], ";")] + [ref["head_sha"]]
                if any(not git.commit_exists(path, sha) for sha in retained):
                    raise RecoveryError("MISSING_COMMIT", repository=name)
                if any(not git.is_ancestor(path, sha, head) for sha in retained):
                    raise RecoveryError("REF_MOVED", repository=name)
                old_cells = [ref[k] for k in ("repository", "branch", "baseline_history", "start_refs", "head_sha", "completion_sha")]
                new_cells = list(old_cells)
                new_cells[1] = repo["actual_branch"]
                start = f"{repo['actual_branch']}@{head}"
                new_cells[3] += "; " + start
                new_cells[4] = head
                change(detail_path, "repository_attempt:" + name, old_cells, new_cells)
                note(detail_path, f"- Recovery attempt {plan['plan_id']}: {name} branch {old_branch} -> {repo['actual_branch']}; observed {name}@{head}; previous start refs retained.")
                head_refs[name] = head
            new_row = list(row)
            new_row[1], new_row[2] = path.as_posix(), repo["actual_branch"]
            new_row[3] = "DERIVED:HEAD" if repo["role"] == "project-management" else head
            change("STATUS.md", "working_repository:" + name, row, new_row)
            plan["repositories"].append(dict(name=name, registered_remote=public_remote(repo["remote"]),
                remote_digest=digest(repo["remote"].encode()), resolved_path=str(path),
                recorded_branch=old_branch, recorded_head=old_head,
                observed_branch=repo["actual_branch"], observed_head=head))

        record = records[task_id]
        if head_refs != record["head_refs"]:
            cells = [record[k] for k in ("id", "type", "name", "state", "owner", "depends_raw", "started_at", "completed_at", "head_raw")]
            new_cells = list(cells)
            new_cells[3] = f"`{record['state']}`"
            new_cells[-1] = "; ".join(f"{name}@{sha}" for name, sha in head_refs.items())
            change("TASKS.md", "task_heads:" + task_id, cells, new_cells)

        for row in summary["integration_opponents"]["rows"]:
            name, branch, previous = row[:3]
            if name not in resolved:
                raise RecoveryError("INVALID_REPOSITORY_SET")
            path = Path(resolved[name]["path"])
            observed = git.run(path, "rev-parse", "--verify", f"refs/heads/{branch}")
            if not git.commit_exists(path, previous) or not git.is_ancestor(path, previous, observed):
                raise RecoveryError("REF_MOVED", repository=name, field="integration")
            changed_paths, overlap = [], []
            if previous != observed:
                changed_paths = git.run(path, "diff", "--name-only", previous, observed, "--").splitlines()
                working_paths = git.run(path, "diff", "--name-only", previous, resolved[name]["actual_head"], "--").splitlines()
                overlap = sorted(set(changed_paths) & set(working_paths))
                if overlap:
                    raise RecoveryError("INTEGRATION_SCOPE_CONFLICT", repository=name, paths=overlap)
                updated = list(row)
                updated[2] = observed
                change("STATUS.md", "integration_observation:" + name, row, updated)
                note("STATUS.md", f"Recovery observation {plan['plan_id']}: {name} {branch}@{previous} -> {branch}@{observed}; compared unrelated paths; task baselines unchanged; no merge performed.")
            plan["comparisons"].append(dict(repository=name, kind="integration", branch=branch,
                previous=previous, observed=observed, ancestor=True, changed_paths=changed_paths))

        for row in summary["pr_mr_objects"]["rows"]:
            _, name, source_branch, source_sha, target_branch, target_sha = row[:6]
            if name not in resolved:
                raise RecoveryError("INVALID_REPOSITORY_SET")
            path = Path(resolved[name]["path"])
            if (git.run(path, "rev-parse", "--verify", f"refs/heads/{source_branch}") != source_sha
                    or git.run(path, "rev-parse", "--verify", f"refs/heads/{target_branch}") != target_sha
                    or not git.is_ancestor(path, target_sha, source_sha)):
                raise RecoveryError("PR_REFS_CHANGED", repository=name)

        proposed = {}
        for relative, changes in operations.items():
            before = documents.raw[relative]
            after_text = replace_operations(documents.read(relative), changes)
            after = encode(after_text, before)
            proposed[relative] = after_text
            plan["edits"].append(dict(path=relative, expected_bytes_digest=digest(before),
                resulting_bytes_digest=digest(after), operations=changes))
        candidate_records = tc.task_records(proposed.get("TASKS.md", tasks))
        candidate_details = dict(details)
        candidate_details[task_id] = tc.task_detail(root, candidate_records[task_id],
                                                   text=proposed.get(detail_path, current_detail))
        trace = tc.validate_trace_graph(proposed.get("STATUS.md", status), candidate_records, candidate_details, resolved, [], git_probe=git)
        plan["comparisons"].append(dict(kind="task_trace", result="VALID", task_count=len(records), edges=trace["edges"]))
        plan["read_set"] = {p: digest(raw) for p, raw in documents.raw.items()}
        for p, raw in documents.raw.items():
            actual = bounded_bytes(safe_path(root, p))
            if p not in (_originals or {}) and actual != raw:
                raise RecoveryError("SOURCE_CHANGED", path=p)
        verify_observations(plan, git)
        plan["complete"] = True
        plan["next_action"] = "record-plan-then-authorized-apply" if plan["edits"] else "task-context"
        if len(json.dumps(plan).encode()) > MAX_PLAN_BYTES:
            raise RecoveryError("RESOURCE_LIMIT", resource="plan_bytes")
        git.remaining()
    except (RecoveryError, tc.ContextError, OSError, UnicodeError, ValueError) as exc:
        plan["complete"] = False
        plan["edits"] = []
        plan["blockers"] = [exc.diagnostic if isinstance(exc, RecoveryError) else {"code": "INVALID_FEATURE"}]
        plan["next_action"] = "inspect-diagnostics"
    return plan


def verify_observations(plan, git):
    for repo in plan["repositories"]:
        path = Path(repo["resolved_path"])
        if (git.run(path, "rev-parse", "HEAD") != repo["observed_head"]
                or git.run(path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False) != repo["observed_branch"]):
            raise RecoveryError("REF_MOVED", repository=repo["name"])
    paths = {r["name"]: Path(r["resolved_path"]) for r in plan["repositories"]}
    for comparison in plan["comparisons"]:
        if comparison["kind"] == "integration":
            observed = git.run(paths[comparison["repository"]], "rev-parse", "--verify", "refs/heads/" + comparison["branch"])
            if observed != comparison["observed"]:
                raise RecoveryError("REF_MOVED", repository=comparison["repository"])


def read_plan(root, relative):
    path = safe_path(root, relative)
    with path.open("rb") as stream:
        raw = stream.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise RecoveryError("RESOURCE_LIMIT", resource="plan_bytes")
    matches = re.findall(r"^```json[ \t]*\n(.*?)^```[ \t]*$", decode(raw), re.MULTILINE | re.DOTALL)
    if len(matches) != 1:
        raise RecoveryError("INVALID_PLAN_GIST")
    return json.loads(matches[0])


def atomic_replace(path, raw):
    mode = stat.S_IMODE(path.stat().st_mode)
    handle, name = tempfile.mkstemp(prefix=path.name + ".recovery-", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply(plan, authority=False):
    result = dict(applied_files=[], unchanged_files=[], conflicts=[], effect="NOT_APPLIED")
    lock = None
    lock_raw = None
    git = GitProbe()
    try:
        if authority is not True:
            raise RecoveryError("AUTHORITY_REQUIRED")
        if (not isinstance(plan, dict) or plan.get("plan_version") != "recovery-plan-v1"
                or plan.get("complete") is not True or plan.get("blockers")):
            raise RecoveryError("INVALID_PLAN")
        if len(json.dumps(plan).encode()) > MAX_PLAN_BYTES or len(plan["read_set"]) > MAX_FILES:
            raise RecoveryError("RESOURCE_LIMIT", resource="plan_bytes")
        uuid.UUID(plan["plan_id"])
        root = Path(plan["feature_root"]).resolve()
        if read_plan(root, plan["plan_gist"]) != plan:
            raise RecoveryError("PLAN_NOT_RECORDED")
        lock = root / ".reconcile.lock"
        lock_raw = (plan["plan_id"] + ":" + str(os.getpid())).encode()
        try:
            with lock.open("xb") as stream:
                stream.write(lock_raw)
        except FileExistsError:
            lock = None
            raise RecoveryError("COORDINATOR_BUSY") from None
        originals, targets = {}, {}
        observed_sources = ReadSet(root)
        for edit in plan["edits"]:
            relative = edit["path"]
            if relative not in {"STATUS.md", "TASKS.md", f"tasks/{plan['task_id']}.md"} or relative in originals:
                raise RecoveryError("INVALID_PLAN")
            raw = observed_sources.load(relative)
            if digest(raw) == edit["expected_bytes_digest"]:
                original = raw
            elif digest(raw) == edit["resulting_bytes_digest"]:
                original = encode(replace_operations(decode(raw), edit["operations"], reverse=True), raw)
            else:
                raise RecoveryError("CONTENT_CONFLICT", path=relative)
            if digest(original) != edit["expected_bytes_digest"]:
                raise RecoveryError("INVALID_PLAN")
            originals[relative] = original
            targets[relative] = encode(replace_operations(decode(original), edit["operations"]), original)
            if digest(targets[relative]) != edit["resulting_bytes_digest"]:
                raise RecoveryError("INVALID_PLAN")
        for relative, expected in plan["read_set"].items():
            observed_sources.load(relative)
            if digest(originals.get(relative, observed_sources.raw[relative])) != expected:
                raise RecoveryError("SOURCE_CHANGED", path=relative)
        overrides = {r["name"]: Path(r["resolved_path"]) for r in plan["repositories"]}
        checked = inspect(root, overrides, plan_gist=plan["plan_gist"], _originals=originals,
                          _allowed_dirty=(*originals, ".reconcile.lock"),
                          _plan_id=plan["plan_id"], _observed_at=plan["observed_at"], _git=git)
        if checked != plan:
            raise RecoveryError("PLAN_STALE", blockers=checked["blockers"])
        if read_plan(root, plan["plan_gist"]) != plan:
            raise RecoveryError("PLAN_NOT_RECORDED")
        for relative, target in targets.items():
            path = safe_path(root, relative)
            observed = bounded_bytes(path)
            if observed == target:
                result["unchanged_files"].append(relative)
            elif observed == originals[relative]:
                atomic_replace(path, target)
                result["applied_files"].append(relative)
            else:
                raise RecoveryError("CONTENT_CONFLICT", path=relative)
        verify_observations(plan, git)
        git.remaining()
        result["effect"] = "APPLIED" if result["applied_files"] else "UNCHANGED"
        result["next_action"] = "commit-management-then-task-context"
    except (RecoveryError, KeyError, TypeError, ValueError, OSError) as exc:
        result["conflicts"] = [exc.diagnostic if isinstance(exc, RecoveryError) else {"code": "INVALID_PLAN_OR_IO_FAILURE"}]
        result["effect"] = "PARTIAL" if result["applied_files"] else "NOT_APPLIED"
    finally:
        if lock is not None and lock.exists() and lock.read_bytes() == lock_raw:
            lock.unlink()
    return result


def main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature_directory")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--plan-gist", required=True, help="Existing gist declared by current task")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--authorized", action="store_true", help="Caller attests actual session authorization; file text is not authority")
    parser.add_argument("--operation-id", help="Inspect or record an existing checkpoint operation instead of a relocation plan")
    args = parser.parse_args(argv)
    try:
        if args.operation_id:
            import task_operation
            result = task_operation.reconcile(args.feature_directory, args.plan_gist, args.operation_id,
                                               tc.parse_repo_overrides(args.repo), apply=args.apply, authority=args.authorized)
            ok = not result["conflicts"]
        elif args.apply:
            root = Path(args.feature_directory).resolve()
            plan = read_plan(root, args.plan_gist)
            if not isinstance(plan, dict) or Path(plan.get("feature_root", "")).resolve() != root or plan.get("plan_gist") != args.plan_gist:
                raise RecoveryError("INVALID_PLAN_ROOT")
            result = apply(plan, args.authorized)
            ok = not result["conflicts"]
        else:
            plan = inspect(args.feature_directory, tc.parse_repo_overrides(args.repo), plan_gist=args.plan_gist)
            result = dict(plan=plan, blockers=plan["blockers"], complete=plan["complete"])
            ok = plan["complete"]
        result["event"] = dict(name="reconcile." + ("apply" if args.apply and ok else "inspect" if not args.apply else "conflict"),
                               elapsed_ms=round((time.monotonic() - started) * 1000))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if ok else 2
    except (RecoveryError, ValueError, OSError):
        print(json.dumps({"complete": False, "blockers": [{"code": "INVALID_REQUEST"}]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
