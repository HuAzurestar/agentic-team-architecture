#!/usr/bin/env python3
"""F03-journaled, exact-version Git review publication; no working-branch push."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import tempfile
import sys
import uuid
sys.dont_write_bytecode = True
import task_operation as op
import task_reconcile as recovery
import task_checkpoint as cp
import task_context as tc
import review_comments as rv
from review_source import _run, SHA, ReviewSourceError, read_git_reviews

Error = recovery.RecoveryError
STATES = ['PENDING', 'ADDRESSED', 'VERIFIED']


def intent_digest(record):
    """Host-retained scope binding, not authentication or a Markdown grant."""
    immutable = {k: v for k, v in record.items()
                 if k not in ('dispatched', 'observed_result', 'recorded_fields', 'terminal_conflict')}
    return hashlib.sha256(json.dumps(immutable, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def _context(root, gist, overrides, record=None):
    plan = recovery.inspect(root, overrides, plan_gist=gist, _allowed_dirty=('.operation.lock',))
    if not plan['complete'] or plan['edits']:
        raise Error('RECOVERY_REQUIRED', blockers=plan['blockers'])
    if record is not None:
        source = record['expected_source']
        if (record['operation_version'] != 'operation-v1' or record['kind'] != 'review-publish'
                or record['feature'] != root.name or record['intent_ref'] != gist
                or record['task'] != plan['task_id'] or record['owned_paths']
                or type(record['dispatched']) is not bool
                or plan['read_set'] != source['read_set']):
            raise Error('INVALID_PUBLISH_INTENT')
        cp.safe_line(record['authority_source_ref'], 'authority source')
        retained = {r['name']: (r['remote_digest'], r['observed_branch'], r['observed_head'])
                    for r in source['repositories']}
        actual = {r['name']: (r['remote_digest'], r['observed_branch'], r['observed_head'])
                  for r in plan['repositories']}
        if set(retained) != set(actual):
            raise Error('REF_MOVED')
        registry = tc.repository_registry(recovery.decode(recovery.bounded_bytes(root / 'STATUS.md')))
        git = recovery.GitProbe()
        for name, value in actual.items():
            if retained[name] == value:
                continue
            repo = next(r for r in plan['repositories'] if r['name'] == name)
            if (registry[name]['role'] != 'project-management' or retained[name][:2] != value[:2]
                    or not git.is_ancestor(Path(repo['resolved_path']), retained[name][2], value[2])):
                raise Error('REF_MOVED')
    return plan


def _binding(plan, record):
    target = record['target_identity']
    repos = [r for r in plan['repositories'] if r['name'] == target['repository']]
    if len(repos) != 1 or repos[0]['remote_digest'] != target['remote_digest']:
        raise Error('REPO_IDENTITY_MISMATCH')
    binding = dict(record['expected_source']['binding'], repo=Path(repos[0]['resolved_path']))
    if (binding['feature'] != record['feature']
            or recovery.digest(binding['expected_remote'].encode()) != target['remote_digest']):
        raise Error('REPO_IDENTITY_MISMATCH')
    return binding


def _draft(binding, text, original):
    parsed = rv.parse(text, feature=binding['feature'], reviews_ref=binding['reviews_ref'])
    if parsed['legacy'] or rv.render(parsed['records']) != text:
        raise Error('CANONICAL_REVIEW_DRAFT_REQUIRED')
    previous = rv.parse(original, feature=binding['feature'], reviews_ref=binding['reviews_ref'])
    old = {r['rv_id']: r for r in previous['records']}
    new = {r['rv_id']: r for r in parsed['records']}
    if not set(old).issubset(new):
        raise Error('REVIEW_DELETION_NOT_AUTHORIZED')
    changed = {key: value for key, value in new.items() if old.get(key) != value}
    if not changed:
        raise Error('UNCHANGED_INTENT')
    return changed


@contextmanager
def _candidate(binding, source, identifier, task, *, commit=None):
    """Build only the authoritative tree plus this document in private storage."""
    base, path = source['version'], binding['relative_path']
    if not isinstance(base, str) or not SHA.fullmatch(base):
        raise Error('INVALID_PUBLISH_INTENT')
    with tempfile.TemporaryDirectory(prefix='lfd-review-publish-') as cache:
        _run(cache, 'init', '--bare', '-q', '--object-format=' + ('sha256' if len(base) == 64 else 'sha1'))
        _run(cache, 'remote', 'add', 'authority', binding['expected_remote'])
        _run(cache, 'fetch', '--quiet', '--depth=1', '--no-tags', '--no-recurse-submodules',
             '--no-write-fetch-head', 'authority', base)
        entry = _run(cache, 'ls-tree', '-z', base, '--', path)[1]
        mode = '100644'
        content = b''
        if entry:
            header, name = entry.rstrip(b'\0').split(b'\t')
            mode, kind, blob = header.decode().split()
            if mode not in ('100644', '100755') or kind != 'blob' or name.decode() != path:
                raise Error('UNSAFE_PATH')
            content = _run(cache, 'cat-file', 'blob', blob)[1]
        if recovery.digest(content) != source['digest'] or content.decode('utf-8') != source['original']:
            raise Error('REVIEW_SOURCE_CHANGED')
        _run(cache, 'read-tree', base)
        blob = _run(cache, 'hash-object', '-w', '--stdin', input_bytes=source['draft'].encode('utf-8'))[1].decode().strip()
        _run(cache, 'update-index', '--add', '--cacheinfo', mode, blob, path)
        tree = _run(cache, 'write-tree')[1].decode().strip()
        if commit is None:
            actor = _run(binding['repo'], 'config', 'user.name', configured=True)[1].decode().strip()
            email = _run(binding['repo'], 'config', 'user.email', configured=True)[1].decode().strip()
            cp.safe_line(actor, 'Git author'); cp.safe_line(email, 'Git author email')
            message = f"{binding['feature']}/{task}: publish review document\n\nOperation-Id: {identifier}"
            sha = _run(cache, '-c', 'user.name=' + actor, '-c', 'user.email=' + email,
                       'commit-tree', tree, '-p', base, '-m', message)[1].decode().strip()
            commit = dict(sha=sha, raw=_run(cache, 'cat-file', 'commit', sha)[1].decode('utf-8'))
        else:
            if (not isinstance(commit['raw'], str) or len(commit['raw'].encode('utf-8')) > 16384
                    or not SHA.fullmatch(commit['sha'])):
                raise Error('INVALID_PUBLISH_INTENT')
            sha = _run(cache, 'hash-object', '-w', '-t', 'commit', '--stdin', input_bytes=commit['raw'].encode('utf-8'))[1].decode().strip()
            if sha != commit['sha']:
                raise Error('INVALID_PUBLISH_INTENT')
        if len(commit['raw'].encode('utf-8')) > 16384:
            raise Error('RESOURCE_LIMIT')
        if (_run(cache, 'show', '-s', '--format=%P', sha)[1].decode().strip() != base
                or _run(cache, 'rev-parse', sha + '^{tree}')[1].decode().strip() != tree
                or 'Operation-Id: ' + identifier not in commit['raw'].splitlines()):
            raise Error('INVALID_PUBLISH_INTENT')
        changed = _run(cache, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', base, sha)[1]
        if changed != path.encode('utf-8') + b'\0':
            raise Error('INVALID_PUBLISH_SCOPE')
        yield cache, commit


def prepare(feature, gist, repository, binding, observation, draft, authority_source_ref,
            overrides=None, *, authority=False, supersedes=None):
    if authority is not True:
        raise Error('AUTHORITY_REQUIRED')
    cp.safe_line(authority_source_ref, 'authority source')
    binding = dict(binding)
    root = Path(feature).resolve()
    with op.coordinator(root):
        plan = _context(root, gist, overrides or {})
        raw, _, _, records = op.read_gist(root, gist)
        retired = {r.get('supersedes') for r in records.values() if r['kind'] == 'review-publish'}
        pending = {key: r for key, r in records.items() if r['kind'] == 'review-publish'
                   and r['target_identity']['repository'] == repository
                   and r['observed_result']['status'] != 'present' and key not in retired}
        if set(pending) != ({supersedes} if supersedes is not None else set()):
            raise Error('UNRESOLVED_REVIEW_PUBLICATION')
        repos = [r for r in plan['repositories'] if r['name'] == repository]
        if (len(repos) != 1 or Path(binding['repo']).resolve() != Path(repos[0]['resolved_path']).resolve()
                or recovery.digest(binding['expected_remote'].encode()) != repos[0]['remote_digest']
                or recovery.public_remote(binding['expected_remote']) != binding['expected_remote']
                or binding['feature'] != root.name):
            raise Error('REPO_IDENTITY_MISMATCH')
        fresh = read_git_reviews(**binding, statuses=STATES)
        if any(fresh[key] != observation[key] for key in ('source_version', 'source_digest', 'original', 'reviews_ref', 'repository_ref')):
            raise Error('CONFLICT', http_status=409)
        changes = _draft(binding, draft, fresh['original'])
        if supersedes is not None:
            prior = pending[supersedes]
            if _observe(_binding(plan, prior), prior)['status'] != 'conflict':
                raise Error('UNRESOLVED_REMOTE_OUTCOME')
            proposed_ids = {r['rv_id'] for r in rv.parse(draft, feature=root.name, reviews_ref=binding['reviews_ref'])['records']}
            if not set(prior['expected_source']['changes']).issubset(proposed_ids):
                raise Error('RV_IDENTITY_CHANGED')
        record = dict(operation_version='operation-v1', operation_id=str(uuid.uuid4()), kind='review-publish',
            feature=root.name, task=plan['task_id'], authority_source_ref=authority_source_ref,
            target_identity=dict(repository=repository, remote_digest=repos[0]['remote_digest']),
            intent_ref=gist, supersedes=supersedes, owned_paths=[], dispatched=False, recorded_fields=[], observed_result={'status': 'not-observed'},
            expected_source=dict(binding={k: v for k, v in binding.items() if k != 'repo'},
                version=fresh['source_version']['value'], digest=fresh['source_digest'], original=fresh['original'],
                draft=draft, changes=changes, read_set=plan['read_set'], repositories=plan['repositories']))
        with _candidate(binding, record['expected_source'], record['operation_id'], record['task']) as (_, commit):
            record['candidate'] = commit
        _context(root, gist, overrides or {}, record)
        op.save(root, gist, record, raw)
        return dict(operation_id=record['operation_id'], intent_digest=intent_digest(record))


def _observe(binding, record):
    fresh = read_git_reviews(**binding, statuses=STATES)
    actual = {r['rv_id']: r for r in fresh['records']}
    changes = record['expected_source']['changes']
    if all(actual.get(key) == value for key, value in changes.items()):
        return dict(status='present', source_version=fresh['source_version'], evidence='current-RV-readback-not-call-receipt')
    if fresh['source_version']['value'] != record['expected_source']['version']:
        return dict(status='conflict', http_status=409, source_version=fresh['source_version'])
    return dict(status='unknown' if record['dispatched'] else 'not-observed', source_version=fresh['source_version'])


def reconcile(root, gist, operation_id, overrides, write):
    raw, _, _, records = op.read_gist(root, gist)
    record = records[operation_id]
    plan = _context(root, gist, overrides, record)
    binding = _binding(plan, record)
    if _draft(binding, record['expected_source']['draft'], record['expected_source']['original']) != record['expected_source']['changes']:
        raise Error('INVALID_PUBLISH_INTENT')
    observed = _observe(binding, record)
    result = dict(operation_id=operation_id, observed_result=observed, effect='NOT_APPLIED', recorded_fields=[], conflicts=[],
                  draft_ref=gist + '#' + operation_id, agent_consumed=False, decision_effect='NONE',
                  publication_status='conflict' if record.get('terminal_conflict') and observed['status'] != 'present' else observed['status'],
                  draft_preserved=True,
                  next_check='inspect-RV-UUIDs-no-retry' if observed['status'] != 'present' else 'commit-management-record')
    if result['publication_status'] == 'conflict':
        result['http_status'] = 409
    if write:
        _context(root, gist, overrides, record)
        record['observed_result'] = observed
        record['recorded_fields'] = ['observed_result']
        if observed['status'] == 'conflict':
            record['terminal_conflict'] = True
        if op.save(root, gist, record, raw) != raw:
            result.update(effect='APPLIED', recorded_fields=[gist + '#observed_result'])
        else:
            result['effect'] = 'UNCHANGED'
    result['event'] = dict(name='reviews.publish.readback', ref=binding['reviews_ref'], status=observed['status'])
    return result


def execute(feature, gist, operation_id, overrides=None, *, authority=False, expected_intent_digest=None):
    if authority is not True:
        raise Error('AUTHORITY_REQUIRED')
    root = Path(feature).resolve()
    overrides = overrides or {}
    with op.coordinator(root):
        raw, _, _, records = op.read_gist(root, gist)
        record = records[operation_id]
        if expected_intent_digest != intent_digest(record):
            raise Error('AUTHORITY_SCOPE_MISMATCH')
        if any(r['kind'] == 'review-publish' and r.get('supersedes') == operation_id for r in records.values()):
            raise Error('OPERATION_SUPERSEDED')
        plan = _context(root, gist, overrides, record)
        binding = _binding(plan, record)
        changes = _draft(binding, record['expected_source']['draft'], record['expected_source']['original'])
        if changes != record['expected_source']['changes']:
            raise Error('INVALID_PUBLISH_INTENT')
        observed = _observe(binding, record)
        if record['dispatched'] or record.get('terminal_conflict') or observed['status'] != 'not-observed':
            return reconcile(root, gist, operation_id, overrides, True)
        with _candidate(binding, record['expected_source'], operation_id, record['task'], commit=record['candidate']) as (cache, commit):
            _context(root, gist, overrides, record)
            if _observe(binding, record)['status'] != 'not-observed':
                return reconcile(root, gist, operation_id, overrides, True)
            record['dispatched'] = True
            op.save(root, gist, record, raw)
            op.interruption_point('review-publish-dispatched')
            try:
                # Exact old-ref lease plus a commit whose sole parent is that
                # ref gives a conditional fast-forward, never a branch rewrite.
                _run(cache, 'push', '--porcelain', '--force-with-lease=refs/heads/master:' + record['expected_source']['version'],
                     'authority', commit['sha'] + ':refs/heads/master', accepted=(0, 1, 128))
            except ReviewSourceError:
                pass
            op.interruption_point('review-publish-returned')
        return reconcile(root, gist, operation_id, overrides, True)
