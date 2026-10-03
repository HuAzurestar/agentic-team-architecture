#!/usr/bin/env python3
"""Read the authoritative remote master snapshot without merging or publishing."""
from __future__ import annotations
from pathlib import Path
import hashlib
import os
import re
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
from context_loader import safe_relative, LoaderError
from decision_evidence import line
from review_comments import MAX_BYTES, parse, select, ReviewCommentError

SHA = re.compile(r'[a-f0-9]{40}|[a-f0-9]{64}')


class ReviewSourceError(ValueError):
    pass


def read_for_purpose(purpose, *, git_binding=None, explicit_review=False, statuses=None, rv_ids=None):
    """Foreground-only trigger; absence of binding differs from failed binding."""
    _require(purpose in ('requirement', 'solution', 'development', 'review', 'delivery')
             and type(explicit_review) is bool, 'INVALID_REVIEW_PURPOSE')
    if purpose != 'review' and not explicit_review:
        return dict(status='NOT_REQUESTED', read_executed=False, records=[], agent_consumed=False)
    if git_binding is None:
        _require(statuses is None and rv_ids is None, 'REVIEW_NOT_BOUND')
        return dict(status='UNBOUND_EMPTY', read_executed=False, records=[], agent_consumed=False)
    _require(isinstance(git_binding, dict) and set(git_binding) == {
        'repo', 'remote', 'expected_remote', 'repository_ref', 'relative_path', 'feature', 'reviews_ref'}, 'INVALID_REVIEW_BINDING')
    observed = read_git_reviews(**git_binding, statuses=statuses, rv_ids=rv_ids)
    observed.update(status='READ', read_executed=True, agent_consumed=False)
    return observed


def _require(ok, code):
    if not ok:
        raise ReviewSourceError(code)


def _run(repo, *args, accepted=(0,)):
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_ALLOW_PROTOCOL='file:https:http:ssh:git')
    try:
        # Bound returned data; do not include remote diagnostics or credentials.
        with tempfile.TemporaryFile() as output:
            process = subprocess.run(['git', '--no-pager', '--literal-pathspecs', '-C', str(repo), *args],
                                     env=env, stdout=output, stderr=subprocess.DEVNULL, timeout=50)
            _require(process.returncode in accepted, 'REVIEW_SOURCE_UNAVAILABLE')
            _require(output.tell() <= MAX_BYTES, 'RESOURCE_LIMIT')
            output.seek(0)
            return process.returncode, output.read(MAX_BYTES + 1)
    except (OSError, subprocess.TimeoutExpired):
        raise ReviewSourceError('REVIEW_SOURCE_UNAVAILABLE') from None


def _head(repo):
    value = _run(repo, 'rev-parse', '--verify', 'HEAD')[1].decode('ascii').strip()
    _require(SHA.fullmatch(value), 'INVALID_REVIEW_SOURCE')
    return value


def _master(repo, remote):
    rows = _run(repo, 'ls-remote', '--refs', remote, 'refs/heads/master')[1].decode('ascii').splitlines()
    _require(len(rows) == 1, 'REVIEW_MASTER_UNAVAILABLE')
    parts = rows[0].split('\t')
    _require(len(parts) == 2 and parts[1] == 'refs/heads/master' and SHA.fullmatch(parts[0]), 'INVALID_REVIEW_SOURCE')
    return parts[0]


def read_git_reviews(repo, *, remote, expected_remote, repository_ref, relative_path,
                     feature, reviews_ref, statuses=None, rv_ids=None):
    """Observe remote master twice and read only its exact immutable snapshot.

    Bindings come from the registered source, not from comment content. A private
    temporary bare repository holds fetched objects, leaving working repository
    refs, index, files and FETCH_HEAD untouched. Fetch uses shallow history and
    requests blob filtering; transport/pack cost is not the 4 MiB document budget.
    This observation does not authorize applying comments or claim remote ACLs.
    """
    try:
        _require(isinstance(remote, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', remote), 'INVALID_REVIEW_BINDING')
        _require(all(line(value) for value in (expected_remote, repository_ref, feature, reviews_ref)), 'INVALID_REVIEW_BINDING')
        relative = safe_relative(relative_path)
        _require(not any(part.casefold() == '.git' for part in relative.parts), 'UNSAFE_PATH')
        root = Path(repo).resolve(strict=True)
        actual_root = Path(_run(root, 'rev-parse', '--show-toplevel')[1].decode('utf-8').strip()).resolve(strict=True)
        _require(actual_root == root, 'INVALID_REVIEW_BINDING')
        urls = _run(root, 'remote', 'get-url', '--all', remote)[1].decode('utf-8').splitlines()
        _require(urls == [expected_remote] and not expected_remote.startswith('-'), 'REVIEW_REMOTE_MISMATCH')
        working = _head(root)
        observed = _master(root, remote)
        with tempfile.TemporaryDirectory(prefix='lfd-review-read-') as cache:
            _run(cache, 'init', '--bare', '-q', '--object-format=' + ('sha256' if len(observed) == 64 else 'sha1'))
            _run(cache, 'fetch', '--quiet', '--depth=1', '--filter=blob:none', '--no-tags',
                 '--no-recurse-submodules', '--no-write-fetch-head', expected_remote, observed)
            entry = _run(cache, 'ls-tree', '-z', observed, '--', relative_path)[1]
            missing = not entry
            if missing:
                # Reachable authoritative tree proves absence; not a transport error.
                content = b''
            else:
                rows = entry.rstrip(b'\0').split(b'\0')
                _require(len(rows) == 1 and b'\t' in rows[0], 'INVALID_REVIEW_SOURCE')
                header, name = rows[0].split(b'\t', 1)
                fields = header.split()
                _require(len(fields) == 3 and fields[0] in (b'100644', b'100755')
                         and fields[1] == b'blob' and name.decode('utf-8') == relative_path, 'UNSAFE_PATH')
                blob = fields[2].decode('ascii')
                size = int(_run(cache, 'cat-file', '-s', blob)[1])
                _require(0 <= size <= MAX_BYTES, 'RESOURCE_LIMIT')
                content = _run(cache, 'cat-file', 'blob', blob)[1]
                _require(len(content) == size, 'REVIEW_SOURCE_CHANGED')
        parsed = parse(content.decode('utf-8'), feature=feature, reviews_ref=reviews_ref)
        selected = select(parsed, statuses=statuses, rv_ids=rv_ids)
        _require(_master(root, remote) == observed and _head(root) == working, 'REVIEW_SOURCE_CHANGED')
        _require(_run(root, 'remote', 'get-url', '--all', remote)[1].decode('utf-8').splitlines() == urls,
                 'REVIEW_SOURCE_CHANGED')
        contained = _run(root, 'merge-base', '--is-ancestor', observed, working, accepted=(0, 1, 128))[0] == 0
        return dict(repository_ref=repository_ref, reviews_ref=reviews_ref, working_head=working,
                    source_version=dict(kind='git', ref='refs/heads/master', value=observed),
                    source_digest=hashlib.sha256(content).hexdigest(), source_missing=missing,
                    records=selected, original=parsed['original'], legacy=parsed['legacy'],
                    master_contained=contained, application_authorized=False, decision_effect='NONE',
                    event=dict(name='reviews.read', ref=reviews_ref, status='READ', error_code=None))
    except (ReviewSourceError, ReviewCommentError):
        raise
    except LoaderError as exc:
        raise ReviewSourceError(exc.code) from None
    except (OSError, UnicodeError, TypeError, ValueError):
        raise ReviewSourceError('INVALID_REVIEW_SOURCE') from None
