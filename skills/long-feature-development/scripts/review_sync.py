#!/usr/bin/env python3
"""Journal exact-master synchronization in F03; never publish or replay unknowns."""
from __future__ import annotations

from pathlib import Path
import sys
import uuid
sys.dont_write_bytecode = True
import task_operation as op
import task_reconcile as recovery
import task_context as tc
import task_checkpoint as cp
from review_source import read_git_reviews, _run, _head, _master, SHA, ReviewSourceError
from review_application import _status

Error = recovery.RecoveryError


def validate(record):
    source = record['expected_source']
    binding = source['review_binding']
    if (record['owned_paths'] or source['files'] != {}
            or set(binding) != {'remote', 'expected_remote', 'repository_ref', 'relative_path', 'feature', 'reviews_ref'}
            or binding['feature'] != record['feature']
            or not isinstance(source['master_sha'], str) or not SHA.fullmatch(source['master_sha'])
            or type(record['dispatched']) is not bool
            or source['observation']['source_version'] != {
                'kind': 'git', 'ref': 'refs/heads/master', 'value': source['master_sha']}):
        raise Error('INVALID_REVIEW_SYNC_INTENT')


def _fresh(repo, source):
    fresh = read_git_reviews(repo, **source['review_binding'], statuses=['PENDING', 'ADDRESSED', 'VERIFIED'])
    old = source['observation']
    if any(fresh[key] != old[key] for key in ('source_version', 'source_digest', 'repository_ref', 'reviews_ref', 'original')):
        raise Error('REVIEW_SOURCE_CHANGED')
    actual = {r['rv_id']: r for r in fresh['records']}
    selected = old['records']
    if (not isinstance(selected, list) or len(selected) > 1000
            or len({r['rv_id'] for r in selected}) != len(selected)
            or any(actual.get(r['rv_id']) != r for r in selected)):
        raise Error('REVIEW_CONTENT_CHANGED')
    return fresh


def locate(repo, record, git):
    """Read actual Git effects, including a lost response; never run merge here."""
    validate(record)
    source = record['expected_source']
    previous, master = source['head'], source['master_sha']
    head = git.run(repo, 'rev-parse', 'HEAD')
    merging = git.run(repo, 'rev-parse', '--verify', 'MERGE_HEAD', check=False)
    if merging is not None:
        if merging != master or head != previous or not record['dispatched']:
            raise Error('UNOWNED_MERGE_STATE')
        raise Error('MERGE_CONFLICT_OR_INCOMPLETE', operation_id=record['operation_id'])
    if head == previous:
        if git.commit_exists(repo, master) and git.is_ancestor(repo, master, head):
            return head
        return None
    trailer = 'Operation-Id: ' + record['operation_id']
    if (not record['dispatched']
            or git.run(repo, 'show', '-s', '--format=%P', head) != previous + ' ' + master
            or trailer not in git.run(repo, 'show', '-s', '--format=%B', head).splitlines()):
        raise Error('REF_MOVED')
    return head


def prepare(feature, gist, repository, binding, observation, authority_source_ref,
            overrides=None, *, authority=False):
    """Durably record a sync in a declared, tracked F03 gist before Git mutation.

    Currently supports a registered implementation repository separate from the
    management journal. A management-repository sync needs its own clean-journal
    staging protocol and is explicitly refused, not performed with dirty files.
    """
    if authority is not True:
        raise Error('AUTHORITY_REQUIRED')
    cp.safe_line(authority_source_ref, 'authority source')
    root = Path(feature).resolve()
    with op.coordinator(root):
        raw, _, _, existing = op.read_gist(root, gist)
        if any(r['kind'] == 'review-master-sync' and r['target_identity']['repository'] == repository
               and r['observed_result']['status'] != 'success' for r in existing.values()):
            raise Error('UNRESOLVED_REVIEW_SYNC')
        plan = recovery.inspect(root, overrides or {}, plan_gist=gist, _allowed_dirty=('.operation.lock',))
        if not plan['complete'] or plan['edits']:
            raise Error('RECOVERY_REQUIRED', blockers=plan['blockers'])
        git = recovery.GitProbe()
        status = recovery.bounded_bytes(recovery.safe_path(root, 'STATUS.md'))
        repos = recovery.resolve_repositories(root, tc.repository_registry(recovery.decode(status)), overrides or {}, git)
        target = repos[repository]
        if target['role'] != 'implementation':
            raise Error('MANAGEMENT_SYNC_PROTOCOL_REQUIRED')
        repo = Path(target['path'])
        if (Path(binding['repo']).resolve() != repo.resolve() or binding['feature'] != root.name
                or binding['expected_remote'] != target['remote']
                or recovery.public_remote(target['remote']) != target['remote']):
            raise Error('REPO_IDENTITY_MISMATCH')
        management = [Path(r['path']) for r in repos.values() if r['role'] == 'project-management']
        if len(management) != 1:
            raise Error('INVALID_REPOSITORY_SET')
        task = plan['task_id']
        record = dict(operation_version='operation-v1', operation_id=str(uuid.uuid4()), kind='review-master-sync',
            feature=root.name, task=task, authority_source_ref=authority_source_ref,
            target_identity=dict(repository=repository, branch=target['actual_branch'],
                                 remote_digest=recovery.digest(target['remote'].encode())),
            expected_source=dict(head=git.run(repo, 'rev-parse', 'HEAD'),
                management_head=git.run(management[0], 'rev-parse', 'HEAD'),
                documents={p: op.raw_snapshot(recovery.bounded_bytes(recovery.safe_path(root, p)))
                           for p in ('STATUS.md', 'TASKS.md', f'tasks/{task}.md')},
                files={}, review_binding={k: v for k, v in binding.items() if k != 'repo'},
                master_sha=observation['source_version']['value'], observation=observation),
            owned_paths=[], intent_ref=gist, summary='synchronize observed review master',
            resume_action='Re-read authoritative reviews and recheck target samples before application',
            dispatched=False, observed_result={'status': 'not-observed'}, recorded_fields=[])
        op.validate_record(root, gist, record)
        op.desired(root, record, record['expected_source']['head'])
        op.refs(root, record, overrides or {}, git)
        _fresh(repo, record['expected_source'])
        if _head(repo) != record['expected_source']['head'] or _status(repo):
            raise Error('DIRTY_OR_MOVED_WORKTREE')
        op.save(root, gist, record, raw)
        return record['operation_id']


def execute(feature, gist, operation_id, overrides=None, *, authority=False):
    """One authorized dispatch; reentry only observes and repairs F03 metadata.

    Fetch has no refspec destination or FETCH_HEAD write. Merge uses an exact
    frozen SHA and an operation trailer. No master push, abort, reset, or automatic
    conflict resolution occurs. After dispatch, an unknown outcome is never retried.
    """
    if authority is not True:
        raise Error('AUTHORITY_REQUIRED')
    root = Path(feature).resolve()
    with op.coordinator(root):
        raw, _, _, records = op.read_gist(root, gist)
        record = records[operation_id]
        if record['kind'] != 'review-master-sync':
            raise Error('INVALID_REVIEW_SYNC_INTENT')
        git = recovery.GitProbe()
        repo, _ = op.refs(root, record, overrides or {}, git)
        observed = locate(repo, record, git)
        if observed is not None:
            result = dict(recorded_fields=[])
            op.reconcile_locked(root, gist, operation_id, overrides or {}, result, True)
            return result
        if record['dispatched']:
            raise Error('UNKNOWN_MERGE_OUTCOME_NO_REPLAY', operation_id=operation_id)
        for relative, snapshot in record['expected_source']['documents'].items():
            if recovery.bounded_bytes(recovery.safe_path(root, relative)) != op.original(snapshot):
                raise Error('SOURCE_CHANGED', path=relative)
        if _status(repo):
            raise Error('DIRTY_WORKTREE')
        source = record['expected_source']
        _fresh(repo, source)
        _run(repo, 'fetch', '--quiet', '--no-tags', '--no-recurse-submodules', '--no-write-fetch-head',
             source['review_binding']['remote'], source['master_sha'])
        # Fetch is repeatable object acquisition; the irreversible dispatch marker
        # is persisted only after rechecking refs, authoritative source and dirt.
        _fresh(repo, source)
        if _head(repo) != source['head'] or _status(repo):
            raise Error('DIRTY_OR_MOVED_WORKTREE')
        if _master(repo, source['review_binding']['remote']) != source['master_sha']:
            raise Error('REVIEW_SOURCE_CHANGED')
        op.refs(root, record, overrides or {}, recovery.GitProbe())
        for relative, snapshot in source['documents'].items():
            if recovery.bounded_bytes(recovery.safe_path(root, relative)) != op.original(snapshot):
                raise Error('SOURCE_CHANGED', path=relative)
        record['dispatched'] = True
        op.save(root, gist, record, raw)
        op.interruption_point('review-sync-dispatched')
        if (_head(repo) != source['head'] or _status(repo)
                or _run(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD')[1].decode().strip()
                != record['target_identity']['branch']):
            raise Error('DIRTY_OR_MOVED_WORKTREE')
        message = f"{root.name}/{record['task']}: synchronize review master\n\nOperation-Id: {operation_id}"
        try:
            _run(repo, 'merge', '--no-ff', '--no-edit', '-m', message, source['master_sha'],
                 accepted=(0, 1, 128), configured=True)
        except ReviewSourceError:
            # A timeout/lost response does not prove failure. Read Git, never retry.
            pass
        op.interruption_point('review-sync-returned')
        git = recovery.GitProbe()
        if locate(repo, record, git) is None:
            raise Error('UNKNOWN_MERGE_OUTCOME_NO_REPLAY', operation_id=operation_id)
        result = dict(recorded_fields=[])
        op.reconcile_locked(root, gist, operation_id, overrides or {}, result, True)
        return result
