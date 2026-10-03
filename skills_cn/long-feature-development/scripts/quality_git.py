#!/usr/bin/env python3
"""Actual local integration facts; neither acceptance nor merge permission."""
from dataclasses import dataclass
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from decision_evidence import line
from review_source import _run, SHA, ReviewSourceError


@dataclass(frozen=True)
class IntegrationBinding:
    # Independently supplied by the host's registered repository and candidate.
    repo: Path
    repository_ref: str
    remote: str
    expected_remote: str
    source_branch: str
    source_sha: str
    source_tree: str
    target_branch: str
    target_before: str


class IntegrationError(ValueError):
    pass


def _require(value, code):
    if not value:
        raise IntegrationError(code)


def _git(root, *args):
    return _run(root, *args)[1].decode('utf-8').strip()


def _snapshot(root, binding):
    actual_root = Path(_git(root, 'rev-parse', '--show-toplevel')).resolve(strict=True)
    _require(actual_root == root, 'REPO_IDENTITY_MISMATCH')
    grafts = Path(_git(root, 'rev-parse', '--git-path', 'info/grafts'))
    if not grafts.is_absolute():
        grafts = root / grafts
    _require(not grafts.exists() and not grafts.is_symlink(), 'GRAFTED_HISTORY_UNSUPPORTED')
    urls = _git(root, 'remote', 'get-url', '--all', binding.remote).splitlines()
    _require(urls == [binding.expected_remote], 'REPO_IDENTITY_MISMATCH')
    return dict(source=_git(root, 'rev-parse', '--verify', 'refs/heads/' + binding.source_branch),
                target=_git(root, 'rev-parse', '--verify', 'refs/heads/' + binding.target_branch))


def observe_integration(binding, phase, *, result_sha=None):
    """Check local refs, exact trees and actual ancestry before/after a merge.

    A clean working tree is deliberately not asserted: immutable commit facts do
    not establish readiness of a worktree. The caller must separately verify
    clean state, authoritative remote target, tests, human decision and grants.
    No fetch, merge, branch update or index refresh occurs here.
    """
    result = dict(valid=False, phase=phase, reason_codes=[], facts=None,
                  effect='NOT_APPLIED', merge_authorized=False, quality_assessed=False,
                  remote_target_verified=False, worktree_verified=False)
    try:
        _require(type(binding) is IntegrationBinding, 'REGISTERED_BINDING_REQUIRED')
        _require(phase in ('pre_accept', 'pre_merge', 'post_merge'), 'INVALID_QUALITY_PHASE')
        _require(all(line(v) for v in (binding.repository_ref, binding.expected_remote)), 'INVALID_INTEGRATION_BINDING')
        _require(isinstance(binding.remote, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', binding.remote),
                 'INVALID_INTEGRATION_BINDING')
        for value in (binding.source_sha, binding.source_tree, binding.target_before):
            _require(isinstance(value, str) and SHA.fullmatch(value), 'EXACT_GIT_OBJECT_REQUIRED')
        _require((phase == 'post_merge' and isinstance(result_sha, str) and SHA.fullmatch(result_sha))
                 or (phase != 'post_merge' and result_sha is None), 'INVALID_RESULT_REF')
        root = Path(binding.repo).resolve(strict=True)
        for branch in (binding.source_branch, binding.target_branch):
            _require(line(branch) and not branch.startswith('-') and len(branch) <= 200, 'INVALID_BRANCH')
            _run(root, 'check-ref-format', 'refs/heads/' + branch)
        _require(binding.source_branch != binding.target_branch, 'DISTINCT_SOURCE_TARGET_REQUIRED')
        before = _snapshot(root, binding)
        _require(before['source'] == binding.source_sha, 'SOURCE_MOVED')
        _require(before['target'] == (result_sha if phase == 'post_merge' else binding.target_before), 'TARGET_MOVED')
        # Full OIDs can still identify blobs or trees; require actual commits.
        for value in (binding.source_sha, binding.target_before, *((result_sha,) if result_sha else ())):
            _require(_git(root, 'cat-file', '-t', value) == 'commit', 'COMMIT_REQUIRED')
        tree = _git(root, 'rev-parse', binding.source_sha + '^{tree}')
        _require(tree == binding.source_tree, 'CANDIDATE_TREE_CHANGED')
        _require(_run(root, 'merge-base', '--is-ancestor', binding.target_before, binding.source_sha,
                      accepted=(0, 1))[0] == 0, 'TARGET_NOT_IN_CANDIDATE')
        result_tree = None
        if phase == 'post_merge':
            _require(_run(root, 'merge-base', '--is-ancestor', binding.source_sha, result_sha,
                          accepted=(0, 1))[0] == 0, 'RESULT_ANCESTRY_CHANGED')
            result_tree = _git(root, 'rev-parse', result_sha + '^{tree}')
            _require(result_tree == tree, 'RESULT_TREE_CHANGED')
        _require(_snapshot(root, binding) == before, 'REF_MOVED_DURING_READ')
        result.update(valid=True, facts=dict(repository_ref=binding.repository_ref, source=binding.source_sha,
            source_tree=tree, target_before=binding.target_before, observed_target=before['target'],
            result=result_sha, result_tree=result_tree, target_in_source=True,
            result_contains_source=True if result_sha else None, observation_scope='local-registered-repository'))
    except (IntegrationError, ReviewSourceError, OSError, ValueError, TypeError, UnicodeError) as exc:
        result['reason_codes'] = [str(exc) if isinstance(exc, (IntegrationError, ReviewSourceError)) else 'INTEGRATION_READ_FAILED']
    result['event'] = dict(name='quality.integration.observe',
                          phase=phase if phase in ('pre_accept', 'pre_merge', 'post_merge') else None, valid=result['valid'],
                          reason_codes=list(result['reason_codes']))
    return result


def _working_snapshot(root, binding, phase, result_sha):
    """Actual workspace facts, never caller supplied PASS flags."""
    branch = binding.target_branch if phase == 'post_merge' else binding.source_branch
    head = result_sha if phase == 'post_merge' else binding.source_sha
    _require(_git(root, 'symbolic-ref', '--quiet', 'HEAD') == 'refs/heads/' + branch,
             'WORKING_BRANCH_MISMATCH')
    _require(_git(root, 'rev-parse', '--verify', 'HEAD') == head, 'WORKING_HEAD_MISMATCH')
    # Honor checkout configuration (notably Windows CRLF), without refreshing
    # the index. Hidden tracked changes must not become a false clean result.
    entries = _run(root, 'ls-files', '-v', '-z', configured=True)[1].split(b'\0')
    _require(all(not entry or entry[:1] == b'H' for entry in entries), 'HIDDEN_INDEX_STATE')
    status = _run(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all',
                  '--ignore-submodules=none', configured=True)[1]
    if status:
        # A CRLF checkout with stale index stat data may say M even when the
        # normalized content is unchanged. Never refresh the real index merely
        # to observe it. Only plain unstaged M is eligible for content recheck;
        # staged/untracked/conflicted/renamed entries still fail immediately.
        _require(all(row.startswith(b' M ') for row in status.rstrip(b'\0').split(b'\0')),
                 'WORKTREE_DIRTY')
        _require(_run(root, 'diff', '--quiet', '--no-ext-diff', '--no-textconv',
                      '--ignore-submodules=none', 'HEAD', '--', accepted=(0, 1),
                      configured=True)[0] == 0, 'WORKTREE_DIRTY')
    for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge',
                 'rebase-apply', 'sequencer'):
        path = Path(_git(root, 'rev-parse', '--git-path', name))
        if not path.is_absolute():
            path = root / path
        _require(not path.exists() and not path.is_symlink(), 'GIT_OPERATION_IN_PROGRESS')
    return dict(working_branch=branch, working_head=head)


def _delivery_snapshot(root, binding, phase, result_sha):
    working = _working_snapshot(root, binding, phase, result_sha)
    ref = 'refs/heads/' + binding.target_branch
    rows = _run(root, 'ls-remote', '--refs', binding.remote, ref)[1].decode('ascii').splitlines()
    _require(len(rows) == 1 and len(rows[0].split('\t')) == 2, 'REMOTE_TARGET_UNAVAILABLE')
    remote_sha, remote_ref = rows[0].split('\t')
    _require(remote_ref == ref and SHA.fullmatch(remote_sha), 'REMOTE_TARGET_UNAVAILABLE')
    _require(remote_sha == (result_sha if phase == 'post_merge' else binding.target_before),
             'REMOTE_TARGET_MOVED')
    _require(_working_snapshot(root, binding, phase, result_sha) == working,
             'DELIVERY_CHANGED_DURING_READ')
    return dict(working, remote_target=remote_sha)


def observe_delivery(binding, phase, *, result_sha=None):
    """Compose local correspondence with live remote and workspace reads.

    Pre-accept/merge observes the checked-out candidate branch; post-merge
    observes the checked-out result branch. Missing/offline remote, dirty or
    hidden index state and unfinished Git operations fail closed. All reads are
    repeated around the aggregate observation. No fetch or mutation occurs.
    This still does not establish reviewer/human authority or grant a merge.
    """
    result = observe_integration(binding, phase, result_sha=result_sha)
    if not result['valid']:
        return result
    try:
        root = Path(binding.repo).resolve(strict=True)
        first = _delivery_snapshot(root, binding, phase, result_sha)
        local = observe_integration(binding, phase, result_sha=result_sha)
        _require(local['valid'] and local['facts'] == result['facts'], 'REF_MOVED_DURING_READ')
        second = _delivery_snapshot(root, binding, phase, result_sha)
        _require(first == second, 'DELIVERY_CHANGED_DURING_READ')
        # Last check also covers remote identity changed during ls-remote.
        _require(_snapshot(root, binding) == dict(source=binding.source_sha,
                 target=result_sha if phase == 'post_merge' else binding.target_before),
                 'REF_MOVED_DURING_READ')
        result['facts'] = dict(result['facts'], **second,
                              observation_scope='registered-repository-and-remote')
        result.update(remote_target_verified=True, worktree_verified=True)
    except (IntegrationError, ReviewSourceError, OSError, ValueError, TypeError, UnicodeError) as exc:
        result.update(valid=False, facts=None, remote_target_verified=False, worktree_verified=False)
        result['reason_codes'] = [str(exc) if isinstance(exc, (IntegrationError, ReviewSourceError))
                                  else 'DELIVERY_READ_FAILED']
    result['event'] = dict(name='quality.delivery.observe', phase=phase, valid=result['valid'],
                          reason_codes=list(result['reason_codes']))
    return result
