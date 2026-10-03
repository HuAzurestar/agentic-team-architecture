#!/usr/bin/env python3
"""Select bounded original Markdown for one purpose. No writes or network calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PURPOSES = ("requirement", "solution", "development", "review", "delivery")
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
MAX_SELECTORS = 100
ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|[ \t]*)$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


class SelectionError(ValueError):
    def __init__(self, code, **details):
        self.diagnostic = {"code": code, **details}
        super().__init__(code)


def heading_path(value):
    if not isinstance(value, (list, tuple)) or not value or len(value) > 32:
        raise SelectionError("INVALID_SELECTOR")
    if any(not isinstance(part, str) or not part or "\n" in part or "\r" in part for part in value):
        raise SelectionError("INVALID_SELECTOR")
    return tuple(value)


def read_snapshot(path, limit):
    """Read at most limit+1 bytes, even if the source grows during reading."""
    try:
        source = Path(path).resolve(strict=True)
        if not source.is_file():
            raise SelectionError("SOURCE_UNAVAILABLE")
        with source.open("rb") as stream:
            raw = stream.read(limit + 1)
    except (OSError, ValueError):
        raise SelectionError("SOURCE_UNAVAILABLE") from None
    if len(raw) > limit:
        raise SelectionError("DOCUMENT_TOO_LARGE", limit_bytes=limit)
    try:
        raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SelectionError("INVALID_UTF8") from None
    return source, raw


def index_sections(raw):
    """Exact ATX paths and raw byte ranges; reject unsupported ambiguous syntax.

    task_context's H2 point reader remains unchanged: its task/point semantics
    are not interchangeable with environment paths and byte-preserving ranges.
    """
    sections, stack = [], []
    offset = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
    fence = None
    previous = ""
    seen_content = False
    for line_number, raw_line in enumerate(raw[offset:].splitlines(keepends=True), 1):
        line = raw_line.decode("utf-8").rstrip("\r\n")
        start = offset
        offset += len(raw_line)
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            if marker[1][0] == "`" and "`" in marker[2]:
                raise SelectionError("UNSUPPORTED_SELECTOR", line=line_number)
            fence = marker[1]
            seen_content = True
            continue
        # HTML block headings and Setext need a richer parser; do not guess.
        if (re.match(r"^ {0,3}<[/!A-Za-z]", line)
                or (previous.strip() and re.fullmatch(r" {0,3}(?:=+|-+)[ \t]*", line))):
            raise SelectionError("UNSUPPORTED_SELECTOR", line=line_number)
        match = ATX.match(line)
        if match:
            level = len(match[1])
            title = re.sub(r"[ \t]+#+[ \t]*$", "", match[2] or "").strip()
            if not title:
                raise SelectionError("UNSUPPORTED_SELECTOR", line=line_number)
            if level == 1:
                if seen_content or sections:
                    raise SelectionError("UNSUPPORTED_SELECTOR", line=line_number)
                seen_content = True
                previous = line
                continue
            while stack and stack[-1]["level"] >= level:
                stack.pop()["end"] = start
            path = tuple(s["title"] for s in stack) + (title,)
            section = dict(path=path, title=title, level=level, start=offset,
                           end=len(raw), line=line_number)
            sections.append(section)
            stack.append(section)
            if len(sections) > 10000:
                raise SelectionError("TOO_MANY_HEADINGS")
        seen_content = seen_content or bool(line.strip())
        previous = line
    if fence:
        raise SelectionError("UNSUPPORTED_SELECTOR", reason="UNCLOSED_FENCE")
    by_path = {}
    for section in sections:
        by_path.setdefault(section["path"], []).append(section)
    return sections, by_path


def select_sections(raw, sections, by_path, paths):
    selected = []
    for path in dict.fromkeys(paths):
        matches = by_path.get(path, [])
        if not matches:
            raise SelectionError("MISSING_SECTION", heading_path=list(path))
        if len(matches) != 1:
            raise SelectionError("AMBIGUOUS_SECTION", heading_path=list(path))
        section = matches[0]
        # An ancestor would silently include sibling purposes or environments.
        if any(s["path"][:len(path)] == path and len(s["path"]) > len(path) for s in sections):
            raise SelectionError("NEEDS_SCOPE", heading_path=list(path), reason="SELECT_LEAF_SECTIONS")
        start, end = section["start"], section["end"]
        body = raw[start:end]
        selected.append(dict(heading_path=list(path), body_range=[start, end],
                             text=body.decode("utf-8"), selected_digest=hashlib.sha256(body).hexdigest()))
    return sorted(selected, key=lambda s: s["body_range"][0])


def source_ref(path, raw):
    return dict(path=str(path), raw_sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))


def verify_repositories(repositories):
    """Explicit read-only Git probes; raw remotes/errors never enter output."""
    results = []
    for repo in repositories:
        if not isinstance(repo, dict) or set(repo) != {"name", "path", "expected_remote"}:
            raise SelectionError("INVALID_REPOSITORY")
        if any(not isinstance(value, str) or not value.strip() for value in repo.values()):
            raise SelectionError("INVALID_REPOSITORY")
        def git(*argv):
            try:
                proc = subprocess.run(["git", "-C", repo["path"], *argv], capture_output=True,
                                      text=True, encoding="utf-8", errors="replace", timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                raise SelectionError("REPOSITORY_UNAVAILABLE") from None
            if proc.returncode:
                raise SelectionError("REPOSITORY_UNAVAILABLE")
            return proc.stdout.strip()
        root = git("rev-parse", "--show-toplevel")
        if Path(root).resolve() != Path(repo["path"]).resolve():
            raise SelectionError("IDENTITY_MISMATCH")
        remotes = [git("remote", "get-url", name) for name in git("remote").splitlines()]
        # Repository path case is meaningful on many forges/filesystems. Prefer
        # a conservative mismatch to treating another repository as the same one.
        def identity(value):
            value = value.strip().replace("\\", "/").rstrip("/")
            return value[:-4] if value.endswith(".git") else value
        if identity(repo["expected_remote"]) not in {identity(r) for r in remotes}:
            raise SelectionError("IDENTITY_MISMATCH")
        results.append(dict(target_alias=repo["name"], kind="git", status="VERIFIED"))
    return results


def build_context(*, task_ref, purpose, background=None, environment=None, common_paths=None,
                  route_path=None, evidence_path=None, purpose_path=None, heading_paths=None,
                  repositories=None, max_file_bytes=MAX_FILE_BYTES, max_output_bytes=MAX_OUTPUT_BYTES):
    result = dict(route="DIRECT" if background is None else "BACKGROUND", complete=False,
                  prompt_sections=[], selected_sections=[], source_refs=[], required_facts={},
                  diagnostics=[], verifications=[], metrics={})
    try:
        if purpose not in PURPOSES:
            raise SelectionError("INVALID_PURPOSE")
        if not task_ref or not Path(task_ref).is_dir():
            raise SelectionError("PROJECT_ENTRY_REQUIRED")
        if (not isinstance(max_file_bytes, int) or isinstance(max_file_bytes, bool)
                or not 0 < max_file_bytes <= MAX_FILE_BYTES
                or not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool)
                or not 0 < max_output_bytes <= MAX_OUTPUT_BYTES):
            raise SelectionError("INVALID_BUDGET")
        common_paths = common_paths or []
        heading_paths = heading_paths or []
        if len(common_paths) + len(heading_paths) + 3 > MAX_SELECTORS:
            raise SelectionError("TOO_MANY_SELECTORS", limit=MAX_SELECTORS)
        if len(repositories or []) > MAX_SELECTORS:
            raise SelectionError("TOO_MANY_REPOSITORIES")
        prompt_file, prompt_raw = read_snapshot(Path(__file__).parent.parent / "references" / "prompts.md", max_file_bytes)
        prompt_index, prompt_map = index_sections(prompt_raw)
        prompts = select_sections(prompt_raw, prompt_index, prompt_map, [("common",), (purpose,)])
        refs = [source_ref(prompt_file, prompt_raw)]
        snapshots = [(prompt_file, prompt_raw)]
        selected = []
        scanned_bytes = len(prompt_raw)
        if background is not None:
            source, raw = read_snapshot(background, max_file_bytes)
            sections, by_path = index_sections(raw)
            if environment is None:
                common = {heading_path(p) for p in common_paths}
                candidates = [list(p) for p in by_path if len(p) == 1 and p not in common]
                raise SelectionError("ENVIRONMENT_REQUIRED", candidates=candidates)
            env = heading_path(environment)
            if len(by_path.get(env, [])) != 1:
                raise SelectionError("AMBIGUOUS_ENVIRONMENT" if env in by_path else "MISSING_ENVIRONMENT")
            if not common_paths or route_path is None or evidence_path is None or purpose_path is None:
                raise SelectionError("REQUIRED_SELECTORS_MISSING")
            common = [heading_path(p) for p in common_paths]
            paths = [heading_path(p) for p in [route_path, evidence_path, purpose_path, *heading_paths]]
            if any(p[:len(env)] != env for p in paths):
                raise SelectionError("ENVIRONMENT_MISMATCH")
            if any(p[:len(env)] == env for p in common):
                raise SelectionError("COMMON_SCOPE_MISMATCH")
            selected = select_sections(raw, sections, by_path, [*common, *paths])
            refs.append(source_ref(source, raw))
            snapshots.append((source, raw))
            scanned_bytes += len(raw)
        verifications = verify_repositories(repositories or [])
        for path, original in snapshots:
            _, observed = read_snapshot(path, max_file_bytes)
            scanned_bytes += len(observed)
            if observed != original:
                raise SelectionError("SOURCE_CHANGED")
        required_facts = dict(task_ref=str(Path(task_ref).resolve()), purpose=purpose,
                              background_is_authorization=False, execution_validated=False,
                              next_validation="task_context.py",
                              reason="NO_BACKGROUND" if background is None else "EXPLICIT_SELECTION")
        candidate = dict(result, complete=True, prompt_sections=prompts, selected_sections=selected,
                         source_refs=refs, required_facts=required_facts, verifications=verifications,
                         metrics=dict(scanned_bytes=scanned_bytes,
                                      returned_chars=sum(len(s["text"]) for s in prompts + selected),
                                      selected_sections=len(selected), lookup_count=len(prompts) + len(selected)))
        required_bytes = len(json.dumps(candidate, ensure_ascii=False).encode("utf-8"))
        if required_bytes > max_output_bytes:
            raise SelectionError("NEEDS_SCOPE", required_bytes=required_bytes, limit_bytes=max_output_bytes,
                                 reason="NARROW_EXPLICIT_SELECTORS_OR_SPLIT_PURPOSE")
        return candidate
    except SelectionError as exc:
        diagnostic = dict(exc.diagnostic)
        if "candidates" in diagnostic:
            result["candidates"] = diagnostic.pop("candidates")
        result["diagnostics"] = [diagnostic]
        if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_OUTPUT_BYTES:
            result.pop("candidates", None)
            result["diagnostics"] = [dict(code="NEEDS_SCOPE", reason="DIRECTORY_EXCEEDS_OUTPUT_LIMIT")]
        return result


def main(argv=None):
    # CLI wire output is UTF-8 on every platform, including redirected pipes.
    # In-process callers may supply StringIO streams without reconfigure().
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-ref", required=True, help="Explicit feature/project directory")
    parser.add_argument("--purpose", required=True, choices=PURPOSES)
    parser.add_argument("--file", dest="background")
    for name in ("environment-section", "route-section", "evidence-section", "purpose-section"):
        parser.add_argument("--" + name, help="Exact heading path as a JSON array")
    parser.add_argument("--common-section", action="append", default=[])
    parser.add_argument("--section-path", action="append", default=[])
    parser.add_argument("--repo", action="append", default=[], help="JSON {name,path,expected_remote}; read-only verification")
    parser.add_argument("--max-output-bytes", type=int, default=MAX_OUTPUT_BYTES)
    args = parser.parse_args(argv)
    try:
        def path(value):
            return heading_path(json.loads(value)) if value is not None else None
        result = build_context(task_ref=args.task_ref, purpose=args.purpose, background=args.background,
                               environment=path(args.environment_section), common_paths=[path(p) for p in args.common_section],
                               route_path=path(args.route_section), evidence_path=path(args.evidence_section),
                               purpose_path=path(args.purpose_section), heading_paths=[path(p) for p in args.section_path],
                               repositories=[json.loads(r) for r in args.repo], max_output_bytes=args.max_output_bytes)
    except (ValueError, TypeError):
        result = dict(complete=False, diagnostics=[dict(code="INVALID_SELECTOR")])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
