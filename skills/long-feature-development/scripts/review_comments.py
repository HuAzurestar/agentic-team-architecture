#!/usr/bin/env python3
"""Bounded RV Markdown codec. Comments never constitute human decisions."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import sys
import time
import uuid
sys.dont_write_bytecode = True
from decision_evidence import changed_span, line

MAX_BYTES = 4 * 1024 * 1024
MAX_REVIEWS = 1000
CPU_SECONDS = 2.0
STATES = {'PENDING', 'ADDRESSED', 'VERIFIED'}
ALIASES = {'OPEN': 'PENDING', 'CLOSED': 'VERIFIED'}
TEXT_FIELDS = {'Source', 'Comment', 'Resolution', 'Verification'}
SCALARS = {'Target.feature', 'Target.ref', 'Target.selector', 'Basis.source_key',
           'Basis.git_basis', 'Basis.line_start', 'Basis.line_end'}
RV = re.compile(r'RV-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z')


class ReviewCommentError(ValueError):
    pass


def _require(condition, code='INVALID_REVIEW_COMMENT'):
    if not condition:
        raise ReviewCommentError(code)


def _text(value):
    return isinstance(value, str) and '\x00' not in value and '\r' not in value


def _size(text):
    _require(isinstance(text, str), 'INVALID_REVIEW_DOCUMENT')
    try:
        _require(len(text) <= MAX_BYTES and len(text.encode('utf-8')) <= MAX_BYTES, 'RESOURCE_LIMIT')
    except UnicodeError:
        raise ReviewCommentError('INVALID_REVIEW_ENCODING') from None


def validate(record):
    _require(isinstance(record, dict) and set(record) <= {'rv_id', 'Target', 'Basis', 'Status', 'Comment', 'Resolution', 'Verification'}
             and {'rv_id', 'Target', 'Basis', 'Status', 'Comment'} <= set(record))
    _require(isinstance(record['rv_id'], str) and RV.fullmatch(record['rv_id']))
    _require(isinstance(record['Status'], str) and record['Status'] in STATES)
    target, basis = record['Target'], record['Basis']
    _require(isinstance(target, dict) and {'feature', 'ref'} <= set(target) <= {'feature', 'ref', 'selector'})
    _require(all(line(value) for value in target.values()))
    _require(isinstance(basis, dict) and {'source_key', 'source_text'} <= set(basis)
             <= {'source_key', 'source_text', 'git_basis', 'line_start', 'line_end'})
    _require(line(basis['source_key']) and _text(basis['source_text']))
    if 'git_basis' in basis:
        _require(isinstance(basis['git_basis'], str) and re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', basis['git_basis']))
    _require(('line_start' in basis) == ('line_end' in basis))
    if 'line_start' in basis:
        _require(type(basis['line_start']) is int and type(basis['line_end']) is int
                 and 1 <= basis['line_start'] <= basis['line_end'] <= 2**31 - 1)
    _require(all(_text(record[field]) for field in ('Comment', 'Resolution', 'Verification') if field in record))
    _require(bool(record['Comment'].strip()))
    _size(json.dumps(record, ensure_ascii=False))


def new_review(target, basis, comment):
    record = dict(rv_id='RV-' + str(uuid.uuid4()), Target=copy.deepcopy(target), Basis=copy.deepcopy(basis),
                  Status='PENDING', Comment=comment)
    validate(record)
    return record


def render(records):
    _require(isinstance(records, (list, tuple)) and len(records) <= MAX_REVIEWS, 'RESOURCE_LIMIT')
    started, seen, chunks, total = time.process_time(), set(), ['# Reviews\n'], 10
    for record in records:
        validate(record)
        _require(record['rv_id'] not in seen, 'DUPLICATE_REVIEW_ID')
        seen.add(record['rv_id'])
        lines = ['\n## ' + record['rv_id'], '', '- Status: ' + record['Status']]
        for group in ('Target', 'Basis'):
            for field in sorted(record[group]):
                if field == 'source_text':
                    continue
                # Every scalar is encoded as a JSON string, never raw Markdown.
                lines.append('- ' + group + '.' + field + ': ' + json.dumps(str(record[group][field]), ensure_ascii=True))
        for field, value in [('Source', record['Basis']['source_text'])] + [(key, record[key]) for key in ('Comment', 'Resolution', 'Verification') if key in record]:
            lines += ['', '### ' + field, '']
            lines.extend('> ' + part for part in value.split('\n'))
        chunk = '\n'.join(lines) + '\n'
        total += len(chunk.encode('utf-8'))
        _require(total <= MAX_BYTES, 'RESOURCE_LIMIT')
        chunks.append(chunk)
    _require(time.process_time() - started <= CPU_SECONDS, 'RESOURCE_LIMIT')
    return ''.join(chunks)


def parse(text, *, feature, reviews_ref):
    """Read known safe RV syntax. Preserve raw legacy input; never rewrite it."""
    _size(text)
    _require(line(feature) and line(reviews_ref), 'INVALID_REVIEW_BINDING')
    started = time.process_time()
    records, by_id, by_target, legacy = [], {}, {}, []
    record, scalars, blocks, section, legacy_basis, old_status = None, {}, {}, None, None, False

    def finish():
        if record is None:
            return
        record['Target'] = {key[7:]: value for key, value in scalars.items() if key.startswith('Target.')}
        basis = {key[6:]: value for key, value in scalars.items() if key.startswith('Basis.')}
        for field in ('line_start', 'line_end'):
            if field in basis:
                _require(re.fullmatch(r'[1-9][0-9]{0,9}', basis[field]))
                basis[field] = int(basis[field])
        _require('Source' in blocks and 'Comment' in blocks)
        basis['source_text'] = '\n'.join(blocks['Source'])
        record.update({key: '\n'.join(value) for key, value in blocks.items() if key != 'Source'})
        record['Basis'] = basis
        # Legacy free-text Basis is retained separately; do not invent a source.
        if legacy_basis is not None:
            _require(not any(key.startswith('Basis.') for key in scalars), 'AMBIGUOUS_REVIEW_BASIS')
            record['Basis'] = dict(source_key='legacy:unresolved', source_text=basis['source_text'])
        validate(record)
        _require(record['Target']['feature'] == feature, 'REVIEW_FEATURE_MISMATCH')
        key = (feature, reviews_ref, record['rv_id'])
        _require(key not in by_id, 'DUPLICATE_REVIEW_ID')
        by_id[key] = len(records)
        target = (feature, record['Target']['ref'], record['Target'].get('selector'))
        by_target.setdefault(target, []).append(len(records))
        records.append(record)
        if old_status or legacy_basis is not None:
            record['_legacy'] = True
            legacy.append(dict(rv_id=record['rv_id'], basis_text=legacy_basis, conversion_required=True))
        _require(len(records) <= MAX_REVIEWS, 'RESOURCE_LIMIT')

    for row in text.replace('\r\n', '\n').split('\n'):
        if row.startswith('## '):
            finish()
            identifier = row[3:]
            _require(RV.fullmatch(identifier))
            record, scalars, blocks, section, legacy_basis, old_status = {'rv_id': identifier}, {}, {}, None, None, False
        elif row.startswith('> '):
            _require(record is not None and section in TEXT_FIELDS)
            blocks[section].append(row[2:])
        elif row.startswith('### '):
            section = row[4:]
            _require(record is not None and section in TEXT_FIELDS and section not in blocks)
            blocks[section] = []
        elif row.startswith('- '):
            _require(record is not None and section is None and ': ' in row)
            key, value = row[2:].split(': ', 1)
            if key == 'Status':
                _require('Status' not in record)
                normalized = ALIASES.get(value.upper(), value.upper())
                _require(normalized in STATES)
                record['Status'], old_status = normalized, normalized != value
            elif key == 'Basis':
                _require(legacy_basis is None and line(value))
                legacy_basis = value
            else:
                _require(key in SCALARS and key not in scalars)
                try:
                    decoded = json.loads(value)
                except (ValueError, RecursionError):
                    raise ReviewCommentError('INVALID_REVIEW_SCALAR') from None
                _require(isinstance(decoded, str), 'INVALID_REVIEW_SCALAR')
                scalars[key] = decoded
        elif row.strip():
            _require(record is None and row == '# Reviews', 'UNSAFE_REVIEW_MARKDOWN')
    finish()
    _require(time.process_time() - started <= CPU_SECONDS, 'RESOURCE_LIMIT')
    return dict(records=records, by_id=by_id, by_target=by_target, legacy=legacy,
                original=text, source_digest=hashlib.sha256(text.encode('utf-8')).hexdigest(),
                decision_effect='NONE')


def preview_conversion(original, proposed, *, feature, reviews_ref):
    """Caller supplies explicit resolved records; show differences before editing."""
    before = parse(original, feature=feature, reviews_ref=reviews_ref)
    after = render(proposed)
    parsed = parse(after, feature=feature, reviews_ref=reviews_ref)
    _require(set(before['by_id']) == set(parsed['by_id']), 'REVIEW_IDENTITY_CHANGED')
    for item in before['legacy']:
        if item['basis_text'] is not None:
            record = proposed[parsed['by_id'][(feature, reviews_ref, item['rv_id'])]]
            _require(record['Basis']['source_key'] != 'legacy:unresolved', 'LEGACY_BASIS_UNRESOLVED')
    return dict(before_digest=before['source_digest'], after=after,
                diff=changed_span(original, after) if original != after else None,
                effect='NOT_APPLIED', conversion_required=bool(before['legacy']))


def select(parsed, *, statuses=None, rv_ids=None):
    """Default PENDING; explicit IDs without a status filter read any state."""
    if statuses is None:
        accepted = STATES if rv_ids is not None else {'PENDING'}
    else:
        _require(isinstance(statuses, (list, tuple)) and 1 <= len(statuses) <= 3, 'INVALID_REVIEW_SELECTION')
        _require(all(isinstance(value, str) and value in STATES for value in statuses), 'INVALID_REVIEW_SELECTION')
        accepted = set(statuses)
    chosen = None
    if rv_ids is not None:
        _require(isinstance(rv_ids, (list, tuple)) and 1 <= len(rv_ids) <= MAX_REVIEWS, 'INVALID_REVIEW_SELECTION')
        _require(all(isinstance(value, str) and RV.fullmatch(value) for value in rv_ids), 'INVALID_REVIEW_SELECTION')
        chosen = set(rv_ids)
        _require(len(chosen) == len(rv_ids), 'INVALID_REVIEW_SELECTION')
        _require(chosen <= {record['rv_id'] for record in parsed['records']}, 'REVIEW_NOT_FOUND')
    return [copy.deepcopy(record) for record in parsed['records']
            if record['Status'] in accepted and (chosen is None or record['rv_id'] in chosen)]
