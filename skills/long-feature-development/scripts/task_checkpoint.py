#!/usr/bin/env python3
"""Create a scoped local Git checkpoint and persist its task resume metadata."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

import task_context


SENSITIVE_NAMES = {".env", "id_rsa", "id_ed25519", "credentials", "secrets", "token"}
SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Commit one owned work unit locally and update its task checkpoint metadata."
    )
    parser.add_argument("feature_directory")
    parser.add_argument("task_id")
    parser.add_argument("repository")
    parser.add_argument("--include", action="append", required=True, metavar="RELATIVE_FILE")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--resume-action", required=True)
    parser.add_argument("--repo", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--operation-gist", help="Declared tracked gist for a recoverable operation")
    parser.add_argument("--operation-id", help="Resume an existing operation by its exact UUID")
    parser.add_argument("--authority-source-ref", help="Actual caller/session authorization reference, not a Markdown approval")
    return parser.parse_args(argv)


def safe_line(value: str, label: str) -> str:
    value = value.strip()
    if not value or "\n" in value or "\r" in value or "|" in value:
        raise task_context.ContextError(f"{label} must be one non-empty safe line")
    return value


def safe_include(value: str) -> str:
    if "\\" in value:
        raise task_context.ContextError("checkpoint paths must use forward slashes")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise task_context.ContextError(f"unsafe checkpoint path: {value}")
    lowered = {part.casefold() for part in relative.parts}
    filename = relative.name.casefold()
    sensitive_filename = filename.startswith(".env") or any(
        marker in filename for marker in ("credential", "secret", "token")
    )
    if lowered & SENSITIVE_NAMES or sensitive_filename or relative.suffix.casefold() in SENSITIVE_SUFFIXES:
        raise task_context.ContextError(f"sensitive path is not allowed in a checkpoint: {value}")
    return relative.as_posix()


def status_entries(repo: Path) -> list[tuple[str, str]]:
    process = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    result: list[tuple[str, str]] = []
    for line in process.stdout.splitlines():
        if len(line) < 4:
            continue
        result.append((line[:2], line[3:].strip('"').replace("\\", "/")))
    return result


def replace_detail_checkpoint(
    text: str, repository: str, sha: str, resume_action: str, summary: str
) -> str:
    lines = text.splitlines(keepends=True)
    table_header = None
    for index, line in enumerate(lines):
        header = tuple(task_context.clean_cell(cell) for cell in task_context.split_row(line))
        if header in task_context.REPO_TABLE_HEADERS:
            table_header = index
            break
    if table_header is None:
        raise task_context.ContextError("task detail is missing Repository refs")
    matches: list[int] = []
    for index in range(table_header + 2, len(lines)):
        row = task_context.split_row(lines[index])
        if not row:
            break
        if task_context.clean_cell(row[0]) == repository:
            matches.append(index)
    if len(matches) != 1:
        raise task_context.ContextError(
            f"task detail must contain exactly one repository row for {repository}"
        )
    row = [task_context.clean_cell(cell) for cell in task_context.split_row(lines[matches[0]])]
    row[4] = sha
    ending = "\r\n" if lines[matches[0]].endswith("\r\n") else "\n"
    lines[matches[0]] = "| " + " | ".join(row) + " |" + ending
    updated = "".join(lines)
    updated, count = re.subn(
        r"^- Resume action[:：][ \t]*.*$",
        f"- Resume action: {resume_action}",
        updated,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise task_context.ContextError("task detail must contain exactly one Resume action")
    marker = "## Attempt notes"
    marker_at = updated.find(marker)
    if marker_at < 0:
        raise task_context.ContextError("task detail is missing Attempt notes")
    next_section = updated.find("\n## ", marker_at + len(marker))
    note = f"\n- Checkpoint `{sha}`: {summary}\n"
    if next_section < 0:
        updated = updated.rstrip() + note
    else:
        updated = updated[:next_section].rstrip() + note + updated[next_section:]
    return updated.rstrip() + "\n"


def replace_task_head(text: str, task_id: str, repository: str, sha: str) -> str:
    records = task_context.task_records(text)
    record = records.get(task_id)
    if record is None:
        raise task_context.ContextError(f"unknown task: {task_id}")
    heads = dict(record["head_refs"])
    if repository not in heads:
        raise task_context.ContextError(f"task {task_id} does not own repository {repository}")
    heads[repository] = sha
    head_value = "; ".join(f"{name}@{value}" for name, value in heads.items())
    values = [
        record["id"], record["type"], record["name"], f"`{record['state']}`",
        record["owner"], record["depends_raw"], record["started_at"],
        record["completed_at"], head_value,
    ]
    lines = text.splitlines(keepends=True)
    matches = [
        index for index, line in enumerate(lines)
        if task_context.split_row(line)
        and task_context.clean_cell(task_context.split_row(line)[0]) == task_id
    ]
    if len(matches) != 1:
        raise task_context.ContextError(f"TASKS.md must contain exactly one row for {task_id}")
    ending = "\r\n" if lines[matches[0]].endswith("\r\n") else "\n"
    lines[matches[0]] = "| " + " | ".join(values) + " |" + ending
    return task_context.synchronized_topology("".join(lines))


def atomic_write(path: Path, text: str) -> None:
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def checkpoint(args: argparse.Namespace) -> str:
    if getattr(args, "operation_gist", None):
        import task_operation
        return task_operation.checkpoint(args)
    if getattr(args, "operation_id", None) or getattr(args, "authority_source_ref", None):
        raise task_context.ContextError("operation options require --operation-gist")
    root = Path(args.feature_directory).resolve()
    tasks_path = root / "TASKS.md"
    tasks_text = task_context.read_utf8(tasks_path)
    records = task_context.task_records(tasks_text)
    record = records.get(args.task_id)
    if record is None:
        raise task_context.ContextError(f"unknown task: {args.task_id}")
    if record["state"] not in {"WIP", "RECORDING"}:
        raise task_context.ContextError("checkpoints require a WIP or RECORDING task")
    status_text = task_context.read_utf8(root / "STATUS.md")
    registry = task_context.repository_registry(status_text)
    resolved = task_context.resolve_repositories(root, registry, task_context.parse_repo_overrides(args.repo))
    if args.repository not in resolved:
        raise task_context.ContextError(f"unknown repository: {args.repository}")
    repo = Path(resolved[args.repository]["path"])
    includes = [safe_include(value) for value in args.include]
    if len(set(includes)) != len(includes):
        raise task_context.ContextError("checkpoint includes the same path more than once")
    for value in includes:
        path = repo / Path(*PurePosixPath(value).parts)
        if path.is_dir():
            raise task_context.ContextError(f"checkpoint paths must name files, not directories: {value}")
    entries = status_entries(repo)
    staged = [path for state, path in entries if state[0] not in {" ", "?"}]
    if staged:
        raise task_context.ContextError("checkpoint refuses pre-staged changes: " + ", ".join(staged))
    changed = {path for _, path in entries}
    if changed != set(includes):
        extra = sorted(changed - set(includes))
        missing = sorted(set(includes) - changed)
        parts = []
        if extra:
            parts.append("unowned changes: " + ", ".join(extra))
        if missing:
            parts.append("unchanged includes: " + ", ".join(missing))
        raise task_context.ContextError("checkpoint scope mismatch; " + "; ".join(parts))
    summary = safe_line(args.summary, "summary")
    resume_action = safe_line(args.resume_action, "resume action")
    feature_key = safe_line(root.name, "feature key")
    # Validate both metadata transformations before staging or committing code.
    # A malformed resume record must not leave an unrecorded implementation SHA.
    detail_path = root / "tasks" / f"{args.task_id}.md"
    observed_head = task_context.run_git(repo, "rev-parse", "HEAD").lower()
    replace_detail_checkpoint(task_context.read_utf8(detail_path), args.repository,
                              observed_head, resume_action, summary)
    replace_task_head(tasks_text, args.task_id, args.repository, observed_head)
    subprocess.run(["git", "-C", str(repo), "add", "--", *includes], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", f"{feature_key}/{args.task_id}: checkpoint {summary}"],
        check=True,
    )
    sha = task_context.run_git(repo, "rev-parse", "HEAD").lower()
    detail_path = root / "tasks" / f"{args.task_id}.md"
    detail = replace_detail_checkpoint(
        task_context.read_utf8(detail_path), args.repository, sha, resume_action, summary
    )
    candidate_tasks = replace_task_head(tasks_text, args.task_id, args.repository, sha)
    atomic_write(detail_path, detail)
    atomic_write(tasks_path, candidate_tasks)
    return sha


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        sha = checkpoint(args)
    except (task_context.ContextError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
