#!/usr/bin/env python3
"""Durable native review publication; host bindings never come from journals."""
from pathlib import Path
import hashlib
import sys
import uuid
sys.dont_write_bytecode = True
import review_native as native
import review_publish as common
import review_comments as rv
import task_operation as op

Error = common.Error
KIND = 'review-native-publish'
intent_digest = common.intent_digest


def _identity(endpoint):
    if not isinstance(endpoint, native.NativeDocument):
        raise Error('NATIVE_BINDING_REQUIRED')
    return dict(provider_key=endpoint.provider_key, source_ref=endpoint.source_ref,
                feature=endpoint.feature, reviews_ref=endpoint.reviews_ref,
                endpoint_digest=hashlib.sha256(endpoint.url.encode()).hexdigest())


def _context(root, gist, overrides, record=None):
    return common._context(root, gist, overrides, record, kind=KIND)


def _validate(endpoint, record):
    binding = _identity(endpoint)
    source = record['expected_source']
    if binding != record['target_identity'] or binding['feature'] != record['feature']:
        raise Error('NATIVE_BINDING_MISMATCH')
    native.condition(source['version'])
    if (hashlib.sha256(source['original'].encode()).hexdigest() != source['digest']
            or common._draft(binding, source['draft'], source['original']) != source['changes']):
        raise Error('INVALID_PUBLISH_INTENT')


def _read(endpoint):
    return native.read_for_purpose('review', endpoint=endpoint, statuses=common.STATES)


def _observe(endpoint, record):
    try:
        fresh = _read(endpoint)
    except (native.NativeSourceError, rv.ReviewCommentError):
        return dict(status='unknown', code='NATIVE_READBACK_UNAVAILABLE')
    source = record['expected_source']
    actual = {r['rv_id']: r for r in fresh['records']}
    if all(actual.get(key) == value for key, value in source['changes'].items()):
        return dict(status='present', source_version=fresh['source_version'],
                    evidence='current-RV-readback-not-call-receipt')
    if fresh['source_version']['value'] != source['version'] or fresh['source_digest'] != source['digest']:
        return dict(status='conflict', http_status=409, source_version=fresh['source_version'])
    return dict(status='unknown' if record['dispatched'] else 'not-observed', source_version=fresh['source_version'])


def prepare(feature, gist, endpoint, observation, draft, authority_source_ref, overrides=None,
            *, authority=False, supersedes=None):
    if authority is not True:
        raise Error('AUTHORITY_REQUIRED')
    common.cp.safe_line(authority_source_ref, 'authority source')
    root = Path(feature).resolve()
    identity = _identity(endpoint)
    if identity['feature'] != root.name:
        raise Error('NATIVE_BINDING_MISMATCH')
    with op.coordinator(root):
        plan = _context(root, gist, overrides or {})
        raw, _, _, records = op.read_gist(root, gist)
        retired = {r.get('supersedes') for r in records.values() if r['kind'] == KIND}
        pending = {key: r for key, r in records.items() if r['kind'] == KIND
                   and r['target_identity'] == identity and r['observed_result']['status'] != 'present'
                   and key not in retired}
        if set(pending) != ({supersedes} if supersedes is not None else set()):
            raise Error('UNRESOLVED_REVIEW_PUBLICATION')
        fresh = _read(endpoint)
        if any(fresh[k] != observation[k] for k in ('source_version', 'source_digest', 'original', 'source_ref', 'reviews_ref')):
            raise Error('CONFLICT', http_status=409)
        changes = common._draft(identity, draft, fresh['original'])
        if supersedes is not None:
            prior = pending[supersedes]
            _validate(endpoint, prior)
            if _observe(endpoint, prior)['status'] != 'conflict':
                raise Error('UNRESOLVED_REMOTE_OUTCOME')
            ids = {r['rv_id'] for r in rv.parse(draft, feature=root.name, reviews_ref=identity['reviews_ref'])['records']}
            if not set(prior['expected_source']['changes']).issubset(ids):
                raise Error('RV_IDENTITY_CHANGED')
        record = dict(operation_version='operation-v1', operation_id=str(uuid.uuid4()), kind=KIND,
            feature=root.name, task=plan['task_id'], authority_source_ref=authority_source_ref,
            target_identity=identity, intent_ref=gist, supersedes=supersedes, owned_paths=[],
            dispatched=False, recorded_fields=[], observed_result={'status': 'not-observed'},
            expected_source=dict(version=fresh['source_version']['value'], digest=fresh['source_digest'],
                original=fresh['original'], draft=draft, changes=changes,
                read_set=plan['read_set'], repositories=plan['repositories']))
        _context(root, gist, overrides or {}, record)
        _validate(endpoint, record)
        op.save(root, gist, record, raw)
        return dict(operation_id=record['operation_id'], intent_digest=intent_digest(record))


def reconcile(root, gist, operation_id, overrides, write, endpoint):
    raw, _, _, records = op.read_gist(root, gist)
    record = records[operation_id]
    _context(root, gist, overrides, record)
    _validate(endpoint, record)
    observed = _observe(endpoint, record)
    result = dict(operation_id=operation_id, observed_result=observed, effect='NOT_APPLIED',
        recorded_fields=[], conflicts=[], draft_ref=gist + '#' + operation_id, draft_preserved=True,
        agent_consumed=False, decision_effect='NONE',
        publication_status='conflict' if record.get('terminal_conflict') and observed['status'] != 'present' else observed['status'],
        next_check='inspect-RV-UUIDs-no-retry' if observed['status'] != 'present' else 'commit-management-record')
    if result['publication_status'] == 'conflict':
        result['http_status'] = 409
    if write:
        _context(root, gist, overrides, record)
        record['observed_result'] = observed
        record['recorded_fields'] = ['observed_result']
        if observed['status'] == 'conflict':
            record['terminal_conflict'] = True
        changed = op.save(root, gist, record, raw) != raw
        result.update(effect='APPLIED' if changed else 'UNCHANGED', recorded_fields=[gist + '#observed_result'] if changed else [])
    result['event'] = dict(name='reviews.publish.readback', ref=endpoint.reviews_ref, status=observed['status'])
    return result


def execute(feature, gist, operation_id, endpoint, overrides=None, *, authority=False, expected_intent_digest=None):
    if authority is not True:
        raise Error('AUTHORITY_REQUIRED')
    root, overrides = Path(feature).resolve(), overrides or {}
    with op.coordinator(root):
        raw, _, _, records = op.read_gist(root, gist)
        record = records[operation_id]
        if expected_intent_digest != intent_digest(record):
            raise Error('AUTHORITY_SCOPE_MISMATCH')
        if any(r['kind'] == KIND and r.get('supersedes') == operation_id for r in records.values()):
            raise Error('OPERATION_SUPERSEDED')
        _context(root, gist, overrides, record)
        _validate(endpoint, record)
        observed = _observe(endpoint, record)
        if record['dispatched'] or record.get('terminal_conflict') or observed['status'] != 'not-observed':
            return reconcile(root, gist, operation_id, overrides, True, endpoint)
        _context(root, gist, overrides, record)
        _validate(endpoint, record)
        record['dispatched'] = True
        raw = op.save(root, gist, record, raw)
        op.interruption_point('review-native-publish-dispatched')
        result = endpoint.conditional_put(record['expected_source']['draft'], record['expected_source']['version'], authority=True)
        if result['status'] == 'conflict':
            record['terminal_conflict'] = True
            op.save(root, gist, record, raw)
        op.interruption_point('review-native-publish-returned')
        return reconcile(root, gist, operation_id, overrides, True, endpoint)
