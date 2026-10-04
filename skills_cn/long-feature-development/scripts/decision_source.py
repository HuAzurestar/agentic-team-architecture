#!/usr/bin/env python3
"""Read an actual local Git decision target; never authenticate a human."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
import sys
import time
sys.dont_write_bytecode = True
from context_loader import LocalMarkdownLoader, LoaderError, safe_relative
from decision_evidence import MAX_BYTES, CPU_SECONDS, validate_material, Invalid


class SourceError(ValueError):
    """Safe reason code, with no document body or subprocess diagnostics."""


def _git(repo, *args):
    # Caller process Git overrides must not redirect the registered repository.
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS='0')
    try:
        result = subprocess.run(['git', '--no-pager', '--literal-pathspecs', '-C', str(repo), *args],
                                env=env, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        raise SourceError('SOURCE_UNAVAILABLE') from None
    if result.returncode:
        raise SourceError('SOURCE_UNAVAILABLE')
    return result.stdout


def _point(text, point_id):
    """Exact H2 point, ignoring quoted/code headings; one linear scan."""
    offset, start, end, fence, found = 0, None, None, None, 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip('\r\n')
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', bare)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
        else:
            boundary = re.match(r'^#{1,2}[ \t]+', bare)
            if boundary and start is not None and end is None:
                end = offset
            match = re.fullmatch(r'##[ \t]+`?(REQ-[A-Za-z0-9-]+|SOL-[A-Za-z0-9-]+)`?(?:[ \t]+(?:—|–|-)[ \t]+.*)?[ \t]*', bare)
            if match and match[1] == point_id:
                found += 1
                if start is None:
                    start = offset
        offset += len(line)
    if found != 1:
        raise SourceError('POINT_MISSING_OR_AMBIGUOUS')
    return text[start:end]


def read_git_current(repo, relative_path, *, source_key, feature, decision_kind,
                     exact_scope, expected_head):
    """Read configured source independently from the decision's claims.

    The coordinator supplies the registered repo/path/source key and an actual
    observed HEAD, never values copied blindly from an uploaded decision. This
    local adapter does not establish remote freshness, human identity, or write
    permission. Writers must repeat this read immediately before mutation.
    """
    started = time.process_time()
    try:
        relative = safe_relative(relative_path)
        if any(part.casefold() == '.git' for part in relative.parts):
            raise SourceError('UNSAFE_PATH')
        if not isinstance(expected_head, str) or not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', expected_head):
            raise SourceError('INVALID_SOURCE_BINDING')
        # Validate bounded selectors before using them or loading any document.
        probe = dict(feature=feature, decision_kind=decision_kind, exact_scope=exact_scope,
                     target_ref=dict(source_key=source_key, version_kind='git', version=expected_head), body='probe')
        validate_material(probe, current=True)
        root = Path(repo).resolve(strict=True)
        actual_root = Path(_git(root, 'rev-parse', '--show-toplevel').decode('utf-8').strip()).resolve(strict=True)
        if root != actual_root:
            raise SourceError('INVALID_SOURCE_BINDING')
        if _git(root, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip() != expected_head:
            raise SourceError('SOURCE_CHANGED')
        entry = _git(root, 'ls-tree', '-z', expected_head, '--', relative_path)
        entries = entry.rstrip(b'\0').split(b'\0')
        if len(entries) != 1 or b'\t' not in entries[0]:
            raise SourceError('SOURCE_UNAVAILABLE')
        header, name = entries[0].split(b'\t', 1)
        parts = header.split()
        if (len(parts) != 3 or parts[0] not in (b'100644', b'100755') or parts[1] != b'blob'
                or name.decode('utf-8') != relative_path):
            raise SourceError('UNSAFE_PATH')
        blob = parts[2].decode('ascii')
        size = int(_git(root, 'cat-file', '-s', blob))
        if not 0 < size <= MAX_BYTES:
            raise SourceError('RESOURCE_LIMIT')
        committed = _git(root, 'cat-file', 'blob', blob)
        if len(committed) != size:
            raise SourceError('SOURCE_CHANGED')
        # An index-only edit must not be hidden by restoring the working file.
        staged = _git(root, 'ls-files', '--stage', '-z', '--', relative_path)
        if staged != parts[0] + b' ' + parts[2] + b' 0\t' + name + b'\0':
            raise SourceError('SOURCE_DIRTY')
        loader = LocalMarkdownLoader(root)
        if loader._path(relative_path).stat().st_nlink != 1:
            raise SourceError('UNSAFE_PATH')
        working, identity = loader._read_raw(relative_path, MAX_BYTES)
        # Git text checkouts commonly use CRLF; no whitespace/body normalization.
        text = committed.decode('utf-8').replace('\r\n', '\n')
        if working.decode('utf-8').replace('\r\n', '\n') != text:
            raise SourceError('SOURCE_DIRTY')
        body = _point(text, exact_scope[0]) if decision_kind == 'point' else text
        again, next_identity = loader._read_raw(relative_path, MAX_BYTES)
        if (again != working or next_identity != identity
                or loader._path(relative_path).stat().st_nlink != 1
                or _git(root, 'ls-files', '--stage', '-z', '--', relative_path) != staged
                or _git(root, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip() != expected_head):
            raise SourceError('SOURCE_CHANGED')
        if time.process_time() - started > CPU_SECONDS:
            raise SourceError('RESOURCE_LIMIT')
        probe['body'] = body
        validate_material(probe, current=True)
        return probe
    except SourceError:
        raise
    except LoaderError as exc:
        raise SourceError(exc.code) from None
    except (Invalid, OSError, TypeError, ValueError, UnicodeError):
        raise SourceError('INVALID_SOURCE_BINDING') from None
