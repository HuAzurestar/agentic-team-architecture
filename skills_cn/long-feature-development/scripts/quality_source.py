#!/usr/bin/env python3
"""Actual Git-backed quality documents; source integrity is not reviewer authority."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import MappingProxyType
sys.dont_write_bytecode = True
from context_loader import LocalMarkdownLoader, LoaderError, safe_relative
from review_resume import _object

MAX_BYTES, MAX_DOCUMENTS = 64 * 1024 * 1024, 1000
SHA = re.compile(r'[a-f0-9]{40}|[a-f0-9]{64}')


class SourceError(ValueError):
    """Fixed safe codes only; never include source bodies or Git diagnostics."""


def require(condition, code):
    if not condition:
        raise SourceError(code)


@dataclass(frozen=True)
class GitDocument:
    """Host configuration, not deserialized evidence claims.

    logical_path is the reference used by the quality request. relative_path is
    the actual registered repository path. HEAD must be independently observed.
    """
    logical_path: str
    repository: Path
    relative_path: str
    expected_head: str


@dataclass(frozen=True)
class SourceSnapshot:
    documents: object
    versions: object
    source_refs: frozenset

    def object(self, path, schema):
        """Parse the actual original document, rejecting duplicate JSON keys.

        Each call returns a fresh object, never a caller-provided summary.
        Only source/schema integrity is established; authorship is not.
        """
        try:
            return _object(self.documents[path].decode('utf-8-sig'), schema)
        except (KeyError, ValueError, UnicodeError, RecursionError):
            raise SourceError('INVALID_SOURCE_OBJECT') from None

    def require_object(self, path, schema, expected):
        """Bind a policy input to the complete parsed source, not just its ref."""
        from quality_policy import canonical
        actual = self.object(path, schema)
        try:
            require(canonical(actual) == canonical(expected), 'SOURCE_OBJECT_MISMATCH')
        except SourceError:
            raise
        except (TypeError, ValueError, RecursionError, UnicodeError):
            raise SourceError('INVALID_SOURCE_OBJECT') from None
        return actual


def _git(root, *args):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(['git', '--no-pager', '--literal-pathspecs', '-C', str(root), *args],
                env=env, stdout=output, stderr=subprocess.DEVNULL, timeout=50)
            require(result.returncode == 0, 'SOURCE_UNAVAILABLE')
            require(output.tell() <= MAX_BYTES, 'RESOURCE_LIMIT')
            output.seek(0)
            return output.read(MAX_BYTES + 1)
    except (OSError, subprocess.TimeoutExpired):
        raise SourceError('SOURCE_UNAVAILABLE') from None


def read_git_documents(bindings):
    """Read and recheck a bounded set without modifying Git or source files.

    All sources must be regular tracked current-HEAD files with unchanged index
    entries and clean contents (only Git CRLF checkout differences are allowed).
    Hashes bind exact working bytes, matching report source-ref semantics. Git
    blob IDs and observed HEADs are retained separately. Remote freshness,
    reviewer independence, closure, human decisions and grants remain unproven.
    The read does not lock sources; consumers must repeat it at mutation time.
    """
    try:
        require(type(bindings) is tuple and 0 < len(bindings) <= MAX_DOCUMENTS, 'INVALID_SOURCE_BINDING')
        loaded, versions, identities, roots, total = {}, {}, set(), {}, 0
        pending = []
        for binding in bindings:
            require(type(binding) is GitDocument, 'INVALID_SOURCE_BINDING')
            for name in (binding.logical_path, binding.relative_path):
                parts = safe_relative(name).parts
                require(not any(p.casefold() == '.git' for p in parts), 'UNSAFE_PATH')
            require(binding.logical_path not in loaded, 'DUPLICATE_SOURCE')
            require(isinstance(binding.expected_head, str) and SHA.fullmatch(binding.expected_head), 'INVALID_SOURCE_BINDING')
            root = Path(binding.repository).resolve(strict=True)
            require(Path(_git(root, 'rev-parse', '--show-toplevel').decode('utf-8').strip()).resolve(strict=True) == root,
                    'INVALID_SOURCE_BINDING')
            head = _git(root, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip()
            require(head == binding.expected_head and roots.get(root, head) == head, 'SOURCE_CHANGED')
            roots[root] = head
            entry = _git(root, 'ls-tree', '-z', head, '--', binding.relative_path)
            rows = entry.rstrip(b'\0').split(b'\0')
            require(len(rows) == 1 and b'\t' in rows[0], 'SOURCE_UNAVAILABLE')
            header, name = rows[0].split(b'\t', 1)
            fields = header.split()
            require(len(fields) == 3 and fields[0] in (b'100644', b'100755') and fields[1] == b'blob'
                    and name.decode('utf-8') == binding.relative_path, 'UNSAFE_PATH')
            blob = fields[2].decode('ascii')
            size = int(_git(root, 'cat-file', '-s', blob))
            require(0 <= size <= MAX_BYTES - total, 'RESOURCE_LIMIT')
            committed = _git(root, 'cat-file', 'blob', blob)
            require(len(committed) == size, 'SOURCE_CHANGED')
            staged = fields[0] + b' ' + fields[2] + b' 0\t' + name + b'\0'
            require(_git(root, 'ls-files', '--stage', '-z', '--', binding.relative_path) == staged, 'SOURCE_DIRTY')
            loader = LocalMarkdownLoader(root)
            require(loader._path(binding.relative_path).stat().st_nlink == 1, 'UNSAFE_PATH')
            working, identity = loader._read_raw(binding.relative_path, MAX_BYTES - total)
            require(identity not in identities, 'DUPLICATE_SOURCE')
            identities.add(identity)
            require(working.decode('utf-8').replace('\r\n', '\n') == committed.decode('utf-8').replace('\r\n', '\n'),
                    'SOURCE_DIRTY')
            total += max(len(working), len(committed))
            require(total <= MAX_BYTES, 'RESOURCE_LIMIT')
            loaded[binding.logical_path] = working
            versions[binding.logical_path] = (head, blob)
            pending.append((binding, root, loader, working, identity, staged))
        # Re-observe the whole set after loading, not just each file in isolation.
        for binding, root, loader, working, identity, staged in pending:
            again, next_identity = loader._read_raw(binding.relative_path, len(working))
            require(again == working and next_identity == identity
                    and loader._path(binding.relative_path).stat().st_nlink == 1
                    and _git(root, 'ls-files', '--stage', '-z', '--', binding.relative_path) == staged,
                    'SOURCE_CHANGED')
        for root, head in roots.items():
            require(_git(root, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip() == head, 'SOURCE_CHANGED')
        refs = frozenset((name, hashlib.sha256(body).hexdigest()) for name, body in loaded.items())
        return SourceSnapshot(MappingProxyType(loaded), MappingProxyType(versions), refs)
    except SourceError:
        raise
    except LoaderError as error:
        raise SourceError(error.code) from None
    except (OSError, TypeError, ValueError, UnicodeError, RecursionError):
        raise SourceError('INVALID_SOURCE_BINDING') from None
