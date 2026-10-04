#!/usr/bin/env python3
"""Same-repository F03 review sync: journal-only commit before clean merge."""
from __future__ import annotations
import copy
import json
from pathlib import PurePosixPath
import uuid
import task_operation as op
import task_reconcile as recovery
from review_source import _run, SHA, ReviewSourceError
from review_application import _status

Error = recovery.RecoveryError


def paths(record):
    relative = record['expected_source']['feature_relative']
    if relative == '.':
        return record['intent_ref'], '.operation.lock'
    parts = PurePosixPath(relative).parts
    if not parts or relative.startswith('/') or '\\' in relative or any(p in ('.', '..', '.git') for p in parts):
        raise Error('INVALID_REVIEW_SYNC_INTENT')
    if '/'.join(parts) != relative or parts[-1] != record['feature']:
        raise Error('INVALID_REVIEW_SYNC_INTENT')
    return relative + '/' + record['intent_ref'], relative + '/.operation.lock'


def prefix(record):
    relative = record['expected_source']['feature_relative']
    return '' if relative == '.' else relative + '/'


def validate(record):
    source = record['expected_source']
    if (source['head'] != source['management_head'] or not SHA.fullmatch(source['recorded_head'])):
        raise Error('INVALID_REVIEW_SYNC_INTENT')
    paths(record)


def clean(root, repo, record, *, journal=False, metadata=False):
    gist, lock = paths(record)
    if root.relative_to(repo).as_posix() != record['expected_source']['feature_relative']:
        raise Error('INVALID_REVIEW_SYNC_INTENT')
    allowed = {gist} if journal else set()
    if metadata:
        allowed |= {prefix(record) + p
                    for p in record['expected_source']['documents']}
    for raw in _status(repo).split(b'\0'):
        if not raw:
            continue
        entry = raw.decode('utf-8')
        if entry == '?? ' + lock:
            marker = json.loads(recovery.bounded_bytes(root / '.operation.lock', 1024))
            if set(marker) != {'coordinator_id', 'owner_pid'} or type(marker['owner_pid']) is not int:
                raise Error('UNOWNED_CHANGES')
            uuid.UUID(marker['coordinator_id'])
            continue
        if len(entry) < 4 or entry[:2] != ' M' or entry[3:] not in allowed:
            raise Error('DIRTY_WORKTREE')


def journal_bytes(repo, record, *, dispatched):
    gist, _ = paths(record)
    original = _run(repo, 'show', record['expected_source']['head'] + ':' + gist)[1]
    initial = copy.deepcopy(record)
    initial.update(dispatched=dispatched, observed_result={'status': 'not-observed'}, recorded_fields=[])
    initial.pop('initial_observed_result', None)
    return op.render_gist(original, initial)


def verify_journal(repo, record, sha, git):
    gist, _ = paths(record)
    if (git.run(repo, 'show', '-s', '--format=%P', sha) != record['expected_source']['head']
            or 'Operation-Intent: ' + record['operation_id'] not in git.run(repo, 'show', '-s', '--format=%B', sha).splitlines()
            or git.run(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', sha) != gist + '\0'):
        raise Error('JOURNAL_COMMIT_MISMATCH')
    actual = _run(repo, 'show', sha + ':' + gist)[1]
    before_mode = _run(repo, 'ls-tree', record['expected_source']['head'], '--', gist)[1].split(b' ', 1)[0]
    after_mode = _run(repo, 'ls-tree', sha, '--', gist)[1].split(b' ', 1)[0]
    if before_mode not in (b'100644', b'100755') or before_mode != after_mode:
        raise Error('JOURNAL_COMMIT_MISMATCH')
    if recovery.decode(actual) != recovery.decode(journal_bytes(repo, record, dispatched=True)):
        raise Error('JOURNAL_COMMIT_MISMATCH')


def _locate_at(repo, record, head, git):
    source = record['expected_source']
    if head == source['head']:
        return head if git.commit_exists(repo, source['master_sha']) and git.is_ancestor(repo, source['master_sha'], head) else None
    parents = git.run(repo, 'show', '-s', '--format=%P', head).split()
    if parents == [source['head']]:
        verify_journal(repo, record, head, git)
        return None
    if (len(parents) != 2 or parents[1] != source['master_sha'] or not record['dispatched']
            or 'Operation-Id: ' + record['operation_id'] not in git.run(repo, 'show', '-s', '--format=%B', head).splitlines()):
        raise Error('REF_MOVED')
    verify_journal(repo, record, parents[0], git)
    return head


def locate(repo, record, git):
    validate(record)
    head = git.run(repo, 'rev-parse', 'HEAD')
    merging = git.run(repo, 'rev-parse', '--verify', 'MERGE_HEAD', check=False)
    if merging is not None:
        verify_journal(repo, record, head, git)
        if merging != record['expected_source']['master_sha'] or not record['dispatched']:
            raise Error('UNOWNED_MERGE_STATE')
        raise Error('MERGE_CONFLICT_OR_INCOMPLETE', operation_id=record['operation_id'])
    # A single explicit metadata checkpoint after successful reconciliation is
    # allowed; unrelated implementation changes are not hidden by that receipt.
    observed = record['observed_result']
    result = observed.get('commit_sha') if observed.get('status') == 'success' else None
    if result and head != result and git.run(repo, 'show', '-s', '--format=%P', head) == result:
        gist, _ = paths(record)
        allowed = {gist} | {prefix(record) + p
                           for p in record['expected_source']['documents']}
        changed = set(filter(None, git.run(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', head).split('\0')))
        if not changed.issubset(allowed):
            raise Error('REF_MOVED')
        if _locate_at(repo, record, result, git) != result:
            raise Error('REF_MOVED')
        return result
    return _locate_at(repo, record, head, git)


def commit_dispatch(root, repo, gist, record, raw):
    """Commit only the known dispatch journal; retain staged state on uncertainty."""
    clean(root, repo, record, journal=True)
    if recovery.decode(raw) != recovery.decode(journal_bytes(repo, record, dispatched=False)):
        raise Error('CONTENT_CONFLICT', path=gist)
    # Do not merge an authority change to the journal through the recovery log.
    # Its original must remain readable even if another document conflicts.
    relative, lock = paths(record)
    source = record['expected_source']
    base = _run(repo, 'merge-base', source['head'], source['master_sha'])[1].decode().strip()
    if _run(repo, 'diff', '--name-only', '-z', base, source['master_sha'], '--', relative)[1]:
        raise Error('JOURNAL_SOURCE_CONFLICT')
    if _run(repo, 'ls-tree', '-z', source['master_sha'], '--', lock)[1]:
        raise Error('COORDINATOR_PATH_CONFLICT')
    record['dispatched'] = True
    op.save(root, gist, record, raw)
    op.interruption_point('review-sync-journal-saved')
    clean(root, repo, record, journal=True)
    if _run(repo, 'rev-parse', 'HEAD')[1].decode().strip() != source['head']:
        raise Error('REF_MOVED')
    try:
        _run(repo, 'add', '--', relative, configured=True)
        if _run(repo, 'diff', '--cached', '--name-only', '-z')[1] != relative.encode() + b'\0':
            raise Error('PRESTAGED_CHANGES')
        staged = _run(repo, 'show', ':' + relative)[1]
        if recovery.decode(staged) != recovery.decode(journal_bytes(repo, record, dispatched=True)):
            raise Error('CONTENT_CONFLICT')
        message = f"{record['feature']}/{record['task']}: record review synchronization intent\n\nOperation-Intent: {record['operation_id']}"
        _run(repo, 'commit', '--only', '-m', message, '--', relative, configured=True)
    except ReviewSourceError:
        pass
    head = _run(repo, 'rev-parse', 'HEAD')[1].decode().strip()
    verify_journal(repo, record, head, recovery.GitProbe())
    clean(root, repo, record)
    op.interruption_point('review-sync-journal-committed')
    return head
