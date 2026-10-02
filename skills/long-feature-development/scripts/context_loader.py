#!/usr/bin/env python3
"""Bounded raw-document loading; no Git, network or source writes."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import time
from types import MappingProxyType
from typing import Mapping, Protocol

SCHEMA = "lfd-context-v1"
MAX_DOCUMENTS = 1000
MAX_BYTES = 64 * 1024 * 1024
MAX_DEPTH = 8
PAGE_SIZE = 200
MAX_COMPUTE_SECONDS = 2.0
MAIN_PATHS = ("REQUIREMENT.md", "SOLUTION.md", "STATUS.md", "TASKS.md")


class LoaderError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DocumentRecord:
    logical_path: str
    text: str
    source_key: str
    content_digest: str
    byte_count: int
    encoding: str = "utf-8"
    newline: str = "none"
    ref: str | None = None
    provider_condition: str | None = None

    @property
    def legacy_text(self) -> str:
        # Exactly the universal-newline behavior of Path.read_text(encoding=utf-8).
        # UTF-8 BOM is retained, never silently stripped.
        return self.text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True)
class TaskPage:
    paths: tuple[str, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class ReadSetEvidence:
    task_paths: tuple[str, ...]
    documents: tuple[tuple[str, str], ...]
    total_bytes: int
    complete: bool = True


@dataclass(frozen=True)
class FeatureDocuments:
    root: Path
    records: Mapping[str, DocumentRecord]
    task_paths: tuple[str, ...]
    read_set: ReadSetEvidence
    context_schema: str = SCHEMA

    def read(self, path: str) -> str:
        try:
            return self.records[path].legacy_text
        except KeyError as exc:
            raise LoaderError("INCOMPLETE_CONTEXT", f"required document is missing: {path}") from exc


class DocumentLoader(Protocol):
    root: Path
    def list_task_paths(self, cursor: str | None = None, limit: int = PAGE_SIZE) -> TaskPage: ...
    def read(self, relative_path: str) -> DocumentRecord: ...
    def finish(self) -> ReadSetEvidence: ...


def safe_relative(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise LoaderError("UNSAFE_PATH", "document path must be feature-relative")
    parts = value.split("/")
    if (len(parts) > MAX_DEPTH or any(part in {"", ".", ".."} for part in parts)
            or PurePosixPath(value).is_absolute()):
        raise LoaderError("UNSAFE_PATH", "document path contains unsafe segments or exceeds depth")
    return PurePosixPath(value)


def _link(path: Path) -> bool:
    info = path.lstat()
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def _newline(text: str) -> str:
    crlf = "\r\n" in text
    remainder = text.replace("\r\n", "")
    kinds = [name for present, name in ((crlf, "CRLF"), ("\r" in remainder, "CR"),
                                        ("\n" in remainder, "LF")) if present]
    return kinds[0] if len(kinds) == 1 else "mixed" if kinds else "none"


class LocalMarkdownLoader:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise LoaderError("INCOMPLETE_CONTEXT", "feature root is not a directory")
        self._records: dict[str, DocumentRecord] = {}
        self._identities: dict[str, str] = {}
        self._paths: tuple[str, ...] | None = None
        self._bytes = 0

    def _path(self, name: str) -> Path:
        relative = safe_relative(name)
        path = self.root
        for part in relative.parts:
            path = path / part
            try:
                if _link(path):
                    raise LoaderError("UNSAFE_PATH", f"document path uses a link or junction: {name}")
            except FileNotFoundError as exc:
                message = ("required directory is missing: tasks" if name == "tasks"
                           else f"required file is missing: {name}")
                raise LoaderError("INCOMPLETE_CONTEXT", message) from exc
        if not path.resolve().is_relative_to(self.root):
            raise LoaderError("UNSAFE_PATH", "document escaped its feature root")
        return path

    def _enumerate(self) -> tuple[str, ...]:
        directory = self._path("tasks")
        if not directory.is_dir():
            raise LoaderError("INCOMPLETE_CONTEXT", "required directory is missing: tasks")
        paths = []
        scanned = 0
        with os.scandir(directory) as entries:
            for entry in entries:
                scanned += 1
                if scanned > MAX_DOCUMENTS:
                    raise LoaderError("RESOURCE_LIMIT", "task directory exceeds document limit")
                if os.path.normcase(entry.name).endswith(".md"):
                    name = "tasks/" + entry.name
                    self._path(name)
                    paths.append(name)
        return tuple(sorted(paths))

    def list_task_paths(self, cursor: str | None = None, limit: int = PAGE_SIZE) -> TaskPage:
        if type(limit) is not int or not 1 <= limit <= PAGE_SIZE:
            raise LoaderError("INVALID_CURSOR", "task page limit must be between 1 and 200")
        if self._paths is None:
            self._paths = self._enumerate()
        if cursor is None:
            offset = 0
        elif isinstance(cursor, str) and cursor.startswith("offset:") and cursor[7:].isdigit():
            offset = int(cursor[7:])
        else:
            raise LoaderError("INVALID_CURSOR", "invalid task page cursor")
        if not 0 <= offset <= len(self._paths):
            raise LoaderError("INVALID_CURSOR", "task page cursor is outside the listing")
        end = min(offset + limit, len(self._paths))
        return TaskPage(self._paths[offset:end], f"offset:{end}" if end < len(self._paths) else None)

    def _read_raw(self, name: str, allowance: int) -> tuple[bytes, str]:
        path = self._path(name)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise LoaderError("UNSAFE_PATH", f"document is not a regular file: {name}")
        if info.st_size > allowance:
            raise LoaderError("RESOURCE_LIMIT", "document byte budget exceeded")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise LoaderError("SOURCE_CHANGED", "document identity changed while opening")
            content = stream.read(allowance + 1)
            after = os.fstat(stream.fileno())
        self._path(name)
        if len(content) > allowance:
            raise LoaderError("RESOURCE_LIMIT", "document byte budget exceeded")
        if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise LoaderError("SOURCE_CHANGED", "document changed while reading")
        identity = f"local:{info.st_dev}:{info.st_ino}"
        return content, identity

    def read(self, relative_path: str) -> DocumentRecord:
        safe_relative(relative_path)
        if relative_path in self._records:
            return self._records[relative_path]
        if len(self._records) >= MAX_DOCUMENTS:
            raise LoaderError("RESOURCE_LIMIT", "document count budget exceeded")
        raw, identity = self._read_raw(relative_path, MAX_BYTES - self._bytes)
        previous = self._identities.get(identity)
        if previous is not None and previous != relative_path:
            raise LoaderError("DUPLICATE_IDENTITY", "two document paths name the same local file")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LoaderError("INVALID_ENCODING", f"{Path(relative_path).name} is not valid UTF-8: {exc}") from exc
        record = DocumentRecord(relative_path, text, identity, hashlib.sha256(raw).hexdigest(),
                                len(raw), newline=_newline(text), ref=str(self.root / relative_path))
        self._bytes += len(raw)
        self._identities[identity] = relative_path
        self._records[relative_path] = record
        return record

    def finish(self) -> ReadSetEvidence:
        if self._paths is None:
            raise LoaderError("INCOMPLETE_CONTEXT", "task membership was never enumerated")
        if self._enumerate() != self._paths:
            raise LoaderError("SOURCE_CHANGED", "task membership changed during loading")
        if set(self._paths) - self._records.keys():
            raise LoaderError("INCOMPLETE_CONTEXT", "not every enumerated task document was read")
        for name, record in self._records.items():
            if self._path(name).stat().st_size != record.byte_count:
                raise LoaderError("SOURCE_CHANGED", "loaded document size changed")
            raw, identity = self._read_raw(name, record.byte_count)
            if identity != record.source_key or hashlib.sha256(raw).hexdigest() != record.content_digest:
                raise LoaderError("SOURCE_CHANGED", "loaded document content or identity changed")
        return ReadSetEvidence(self._paths, tuple((key, value.content_digest)
                               for key, value in sorted(self._records.items())), self._bytes)


def enumerate_tasks(loader: DocumentLoader) -> tuple[str, ...]:
    paths, cursors = [], set()
    cursor = None
    while True:
        page = loader.list_task_paths(cursor, PAGE_SIZE)
        if not isinstance(page, TaskPage) or len(page.paths) > PAGE_SIZE:
            raise LoaderError("INCOMPLETE_CONTEXT", "invalid loader task page")
        for path in page.paths:
            relative = safe_relative(path)
            if len(relative.parts) != 2 or relative.parts[0] != "tasks" or os.path.normcase(relative.suffix) != ".md":
                raise LoaderError("UNSAFE_PATH", "task listing contains a non-task path")
            paths.append(path)
        if len(paths) > MAX_DOCUMENTS:
            raise LoaderError("RESOURCE_LIMIT", "task listing exceeds document limit")
        if page.next_cursor is None:
            break
        if not page.paths or page.next_cursor in cursors:
            raise LoaderError("INCOMPLETE_CONTEXT", "task listing did not advance")
        cursors.add(page.next_cursor)
        cursor = page.next_cursor
    if len(paths) != len(set(paths)):
        raise LoaderError("DUPLICATE_IDENTITY", "task listing contains duplicate paths")
    return tuple(paths)


def load_feature(loader: DocumentLoader) -> FeatureDocuments:
    # Import only at the call boundary to keep the raw loader usable independently.
    import task_context as tc
    records = {}
    identities = {}
    total = 0
    start_cpu = time.process_time()

    def take(name):
        nonlocal total
        if name in records:
            return records[name]
        if len(records) >= MAX_DOCUMENTS:
            raise LoaderError("RESOURCE_LIMIT", "document count budget exceeded")
        safe_relative(name)
        record = loader.read(name)
        if not isinstance(record, DocumentRecord) or record.logical_path != name:
            raise LoaderError("INCOMPLETE_CONTEXT", "loader returned a mismatched document")
        raw = record.text.encode("utf-8")
        if (record.encoding != "utf-8" or record.byte_count != len(raw)
                or record.content_digest != hashlib.sha256(raw).hexdigest() or not record.source_key):
            raise LoaderError("INCOMPLETE_CONTEXT", "loader record has inconsistent raw evidence")
        if record.source_key in identities and identities[record.source_key] != name:
            raise LoaderError("DUPLICATE_IDENTITY", "loader reused a source identity")
        total += len(raw)
        if total > MAX_BYTES or time.process_time() - start_cpu > MAX_COMPUTE_SECONDS:
            raise LoaderError("RESOURCE_LIMIT", "loader computation or byte budget exceeded")
        records[name] = record
        identities[record.source_key] = name
        return record

    for name in MAIN_PATHS:
        take(name)
    task_paths = enumerate_tasks(loader)
    # Membership is structural input discovery. Diagnose missing/extra task files
    # before trying to interpret declarations in an unindexed stray document.
    indexed = {f"tasks/{key}.md" for key in tc.task_records(records["TASKS.md"].legacy_text)}
    missing, extra = sorted(indexed - set(task_paths)), sorted(set(task_paths) - indexed)
    if missing:
        raise LoaderError("INCOMPLETE_CONTEXT", "tasks/ is missing detail files: " +
                          ", ".join(PurePosixPath(path).name for path in missing))
    if extra:
        raise LoaderError("INCOMPLETE_CONTEXT", "tasks/ has detail files absent from TASKS.md: " +
                          ", ".join(PurePosixPath(path).name for path in extra))
    for name in task_paths:
        take(name)
    for name in task_paths:
        for gist in tc.declared_gist_names(records[name].legacy_text):
            try:
                take(gist)
            except LoaderError as exc:
                if exc.code == "INCOMPLETE_CONTEXT":
                    raise LoaderError(exc.code, f"declared gist is missing: {gist}") from exc
                raise
    evidence = loader.finish()
    expected = tuple((key, record.content_digest) for key, record in sorted(records.items()))
    if (not isinstance(evidence, ReadSetEvidence) or evidence.complete is not True
            or set(evidence.task_paths) != set(task_paths) or evidence.documents != expected
            or evidence.total_bytes != total):
        raise LoaderError("INCOMPLETE_CONTEXT", "loader finish does not cover the complete read set")
    return FeatureDocuments(loader.root.resolve(), MappingProxyType(records), task_paths, evidence)
