#!/usr/bin/env python3
"""Bounded review-packet preparation. Never dispatches, grants authority or writes."""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from context_loader import LoaderError, LocalMarkdownLoader, safe_relative
from review_resume import _markdown, _object

MAX_FILES = 1000
MAX_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_CHECKS = 10000
PACKET_FIELDS = frozenset(('schema', 'packet_id', 'attempt_id', 'reviewer_assignment',
    'feature', 'review_task', 'mode', 'target_refs', 'repositories', 'scope',
    'checklist_ref', 'checklist_reason', 'required_check_ids', 'evidence_refs',
    'authority', 'limits', 'prior_report_refs', 'expected_output'))


@dataclass(frozen=True)
class HandoffEvidence:
    """Trusted host adapter input, NOT deserialized from packet/user Markdown.

    The host must obtain authorization and provenance from its actual API or
    user dialogue. Constructing this value cannot authenticate an arbitrary host.
    CLI intentionally has no switch to import these claims from a JSON file.
    """
    packet_digest: str
    authority_ref: str
    reviewer_assignment: str
    context_ref: str
    fresh_context: bool
    authorized: bool
    writable_output: str
    provenance_ref: str


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4096


def _id(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value) is not None


def _digest(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def _keys(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _path(value):
    try:
        safe_relative(value)
        # Windows aliases, device files, alternate streams and control bytes
        # must not bypass either source deduplication or output protection.
        for part in value.split('/'):
            if (part[-1:] in (' ', '.') or any(ord(c) < 32 for c in part)
                    or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)):
                return False
        return True
    except LoaderError:
        return False


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def build_packet(inputs, *, documents=None, host=None, previous_packets=()):
    """Validate explicit packet + immutable source bytes supplied by a host.

    Missing sources fail closed. No implicit filesystem/network discovery.
    Prior reports are syntax checked but excluded from initial material reads.
    previous_packets is host-owned dispatch history, not packet-controlled.
    complete describes material only; handoff_allowed also requires host facts.
    Neither field means a reviewer executed anything or a quality Gate passed.
    """
    started = time.monotonic()
    missing, codes = [], []
    source_refs, paths = {}, {}
    byte_count = 0
    already_dispatched = False
    packet, packet_digest = None, None

    def reject(field, code='INVALID_PACKET'):
        missing.append({'field': field, 'code': code})
        if code not in codes:
            codes.append(code)

    def require(condition, field, code='INVALID_PACKET'):
        if not condition:
            reject(field, code)
        return bool(condition)

    def ref(value, field, *, deferred=False):
        if not require(_keys(value, ('path', 'sha256')), field):
            return
        name = value['path']
        if not require(_path(name) and _digest(value['sha256'])
                       and (name in ('REQUIREMENT.md', 'SOLUTION.md') or name.startswith('gists/')), field):
            return
        if deferred:
            return
        normalized = name.casefold()
        if normalized in paths and paths[normalized] != name:
            reject(field, 'DUPLICATE_SOURCE')
        paths[normalized] = name
        if name in source_refs and source_refs[name] != value['sha256']:
            reject(field, 'SOURCE_CHANGED')
        source_refs[name] = value['sha256']
        if not isinstance(documents, dict) or name not in documents:
            reject(field, 'EVIDENCE_MISSING')

    if not isinstance(inputs, dict):
        reject('packet')
    else:
        try:
            raw = _json_bytes(inputs)
            if len(raw) > MAX_FILE_BYTES:
                reject('packet', 'RESOURCE_LIMIT')
            else:
                # JSON round trip detaches nested values and disallows opaque
                # provider objects. Failed envelopes are never echoed by CLI.
                packet = json.loads(raw)
                packet_digest = hashlib.sha256(raw).hexdigest()
        except (TypeError, ValueError, RecursionError, UnicodeError):
            reject('packet')

    if packet is not None:
        require(set(packet) == PACKET_FIELDS, 'packet.fields')
        require(packet.get('schema') == 'review-packet-v1', 'schema')
        for name in ('packet_id', 'attempt_id', 'reviewer_assignment', 'feature', 'review_task'):
            require(_id(packet.get(name)), name)
        require(packet.get('mode') in ('review', 'recheck'), 'mode')
        require(_text(packet.get('checklist_reason')), 'checklist_reason')
        ref(packet.get('checklist_ref'), 'checklist_ref')
        checks = packet.get('required_check_ids')
        valid_checks = isinstance(checks, list) and 0 < len(checks) <= MAX_CHECKS and all(_id(c) for c in checks)
        if require(valid_checks, 'required_check_ids'):
            require(len(checks) == len(set(checks)), 'required_check_ids')

        targets, repositories = packet.get('target_refs'), packet.get('repositories')
        if require(isinstance(targets, dict) and 0 < len(targets) <= MAX_FILES,
                   'target_refs'):
            require(all(_id(k) and _digest(v, 40) for k, v in targets.items()), 'target_refs')
            if require(isinstance(repositories, dict) and repositories.keys() == targets.keys(), 'repositories'):
                for name, repository in repositories.items():
                    field = 'repositories.' + name if _id(name) else 'repositories'
                    if require(_keys(repository, ('identity', 'source_refs')), field):
                        require(_text(repository['identity']), field + '.identity')
                        refs = repository['source_refs']
                        if require(isinstance(refs, list) and 0 < len(refs) <= MAX_FILES, field + '.source_refs'):
                            repository_paths = set()
                            for item in refs:
                                ref(item, field + '.source_refs')
                                if isinstance(item, dict) and isinstance(item.get('path'), str):
                                    path = item['path'].casefold()
                                    require(path not in repository_paths, field + '.source_refs', 'DUPLICATE_SOURCE')
                                    repository_paths.add(path)

        scope = packet.get('scope')
        if require(_keys(scope, ('requirement_ids', 'solution_ids', 'requirement_ref',
                                'solution_ref', 'acceptance_scope', 'exclusions')), 'scope'):
            for name, prefix in (('requirement_ids', 'REQ-'), ('solution_ids', 'SOL-')):
                ids = scope[name]
                valid = (isinstance(ids, list) and 0 < len(ids) <= MAX_CHECKS
                         and all(_id(x) and x.startswith(prefix) for x in ids))
                if require(valid, 'scope.' + name):
                    require(len(ids) == len(set(ids)), 'scope.' + name)
            ref(scope['requirement_ref'], 'scope.requirement_ref')
            ref(scope['solution_ref'], 'scope.solution_ref')
            for name, filename in (('requirement_ref', 'REQUIREMENT.md'), ('solution_ref', 'SOLUTION.md')):
                require(isinstance(scope[name], dict) and scope[name].get('path') == filename, 'scope.' + name)
            require(_text(scope['acceptance_scope']), 'scope.acceptance_scope')
            exclusions = scope['exclusions']
            if require(isinstance(exclusions, list) and len(exclusions) <= MAX_CHECKS, 'scope.exclusions'):
                for exclusion in exclusions:
                    if require(_keys(exclusion, ('scope', 'reason', 'decision_ref')), 'scope.exclusions'):
                        require(_text(exclusion['scope']) and _text(exclusion['reason']), 'scope.exclusions')
                        ref(exclusion['decision_ref'], 'scope.exclusions.decision_ref')

        evidence = packet.get('evidence_refs')
        kinds, evidence_paths = set(), set()
        if require(isinstance(evidence, list) and 0 < len(evidence) <= MAX_FILES, 'evidence_refs'):
            for item in evidence:
                if require(_keys(item, ('path', 'sha256', 'kind')), 'evidence_refs'):
                    kind, path = item['kind'], item['path']
                    if require(isinstance(kind, str) and kind in ('test', 'contract', 'fixture', 'dependency'), 'evidence_refs.kind'):
                        kinds.add(kind)
                    ref({'path': path, 'sha256': item['sha256']}, 'evidence_refs')
                    if isinstance(path, str):
                        require(path.casefold() not in evidence_paths, 'evidence_refs', 'DUPLICATE_SOURCE')
                        evidence_paths.add(path.casefold())
            require('test' in kinds and bool(kinds & {'contract', 'fixture', 'dependency'}), 'evidence_refs.coverage')

        prior = packet.get('prior_report_refs')
        if require(isinstance(prior, list) and len(prior) <= MAX_FILES, 'prior_report_refs'):
            seen = set()
            for item in prior:
                ref(item, 'prior_report_refs', deferred=True)
                if isinstance(item, dict) and _path(item.get('path')):
                    name = item['path'].casefold()
                    require(name not in seen and name not in paths, 'prior_report_refs', 'DUPLICATE_SOURCE')
                    seen.add(name)
        authority = packet.get('authority')
        if require(_keys(authority, ('source_ref', 'read_only', 'allowed_tools')), 'authority'):
            require(_text(authority['source_ref']) and authority['read_only'] is True, 'authority')
            allowed = authority['allowed_tools']
            if require(isinstance(allowed, list) and 0 < len(allowed) <= 100 and all(_id(x) for x in allowed), 'authority.allowed_tools'):
                require(len(allowed) == len(set(allowed)), 'authority.allowed_tools')
        output = packet.get('expected_output')
        if require(_keys(output, ('schema', 'path', 'coordinator', 'missing_policy')), 'expected_output'):
            require(output['schema'] == 'report-v1' and output['missing_policy'] == 'UNKNOWN/NOT-RUN'
                    and _text(output['coordinator']), 'expected_output')
            name = output['path']
            # The dedicated output namespace prevents overwriting task/control
            # inputs even if those were not among the selected source files.
            require(_path(name) and name.startswith('review-output/') and name.casefold() not in paths,
                    'expected_output.path')

        limits = packet.get('limits')
        ceilings = {'max_files': MAX_FILES, 'max_bytes': MAX_BYTES,
                    'max_file_bytes': MAX_FILE_BYTES, 'max_checks': MAX_CHECKS}
        if require(_keys(limits, ceilings), 'limits'):
            for key, maximum in ceilings.items():
                require(type(limits[key]) is int and 0 < limits[key] <= maximum, 'limits.' + key)
            if all(type(limits[k]) is int and 0 < limits[k] <= v for k, v in ceilings.items()):
                require(len(source_refs) <= limits['max_files'], 'sources', 'RESOURCE_LIMIT')
                if valid_checks:
                    require(len(checks) <= limits['max_checks'], 'required_check_ids', 'RESOURCE_LIMIT')
                for name, digest in source_refs.items():
                    value = documents.get(name) if isinstance(documents, dict) else None
                    if not isinstance(value, bytes):
                        reject('sources', 'EVIDENCE_MISSING')
                        continue
                    byte_count += len(value)
                    if byte_count > limits['max_bytes']:
                        reject('sources', 'RESOURCE_LIMIT')
                        break
                    if not require(len(value) <= limits['max_file_bytes'], 'sources', 'RESOURCE_LIMIT'):
                        continue
                    if hashlib.sha256(value).hexdigest() != digest:
                        reject('sources', 'SOURCE_CHANGED')
                require(byte_count <= limits['max_bytes'], 'sources', 'RESOURCE_LIMIT')
                if isinstance(scope, dict) and isinstance(documents, dict):
                    for key, filename in (('requirement_ids', 'REQUIREMENT.md'), ('solution_ids', 'SOLUTION.md')):
                        value, selected = documents.get(filename), scope.get(key)
                        if isinstance(value, bytes) and len(value) <= limits['max_file_bytes'] and isinstance(selected, list):
                            try:
                                headings = {match[1] for kind, _, line in _markdown(value.decode('utf-8-sig'))
                                            if kind == 'line' and (match := re.match(r'^## ((?:REQ|SOL)-[A-Za-z0-9_.-]+)(?:\s|$)', line))}
                                require(all(isinstance(x, str) and x in headings for x in selected), 'scope.' + key, 'SCOPE_MISSING')
                            except UnicodeError:
                                reject('scope.' + key, 'INVALID_ENCODING')

        if not isinstance(previous_packets, (tuple, list)) or len(previous_packets) > MAX_FILES:
            reject('previous_packets', 'RESOURCE_LIMIT')
        else:
            for previous in previous_packets:
                if not isinstance(previous, dict):
                    reject('previous_packets')
                    continue
                # Exact same packet is safe to re-validate, not to redispatch.
                if previous == packet:
                    already_dispatched = True
                    continue
                if any(previous.get(k) == packet.get(k) for k in
                       ('packet_id', 'attempt_id', 'reviewer_assignment')):
                    reject('previous_packets', 'ATTEMPT_REUSED')

    complete = not missing
    if not complete:
        codes.insert(0, 'INCOMPLETE_PACKET')
    if already_dispatched:
        codes.append('ALREADY_DISPATCHED')
    verified = (complete and not already_dispatched and isinstance(host, HandoffEvidence)
                and host.packet_digest == packet_digest
                and host.authority_ref == packet['authority']['source_ref']
                and host.reviewer_assignment == packet['reviewer_assignment']
                and host.fresh_context is True and host.authorized is True
                and host.writable_output == packet['expected_output']['path']
                and _text(host.context_ref) and _text(host.provenance_ref))
    if not verified:
        codes.append('INDEPENDENCE_UNVERIFIED')
    return {'packet': packet, 'packet_digest': packet_digest, 'missing': missing,
            'complete': complete, 'handoff_allowed': bool(verified),
            'independent_executed': 0, 'reason_codes': codes,
            'initial_source_paths': sorted(source_refs),
            'event': {'name': 'packet.build',
                      'attempt': packet.get('attempt_id') if packet and _id(packet.get('attempt_id')) else None,
                      'files': len(source_refs), 'checks': len(packet.get('required_check_ids', []))
                      if packet and isinstance(packet.get('required_check_ids'), list) else 0,
                      'bytes': byte_count, 'elapsed_ms': round((time.monotonic() - started) * 1000),
                      'reason_codes': codes}}


def remaining_checks(required_ids, executed, reason, next_action):
    """Preserve observed rows, fill untouched checks; not a report validator."""
    if (not isinstance(required_ids, list) or len(required_ids) > MAX_CHECKS
            or not all(_id(x) for x in required_ids) or len(set(required_ids)) != len(required_ids)
            or not isinstance(executed, list) or len(executed) > MAX_CHECKS
            or not _text(reason) or not _text(next_action)):
        raise LoaderError('INVALID_REPORT', 'invalid partial check inventory')
    required, seen = set(required_ids), set()
    for row in executed:
        if (not isinstance(row, dict) or not _id(row.get('id'))
                or row['id'] not in required or row['id'] in seen):
            raise LoaderError('INVALID_REPORT', 'invalid partial check identity')
        seen.add(row['id'])
    return copy.deepcopy(executed) + [
        {'id': key, 'outcome': 'NOT-RUN', 'evidence_refs': [], 'finding_ids': [],
         'reason': reason, 'next_action': next_action}
        for key in required_ids if key not in seen]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feature_directory', type=Path)
    parser.add_argument('packet', help='Declared gists/ path relative to the feature')
    args = parser.parse_args(argv)
    try:
        if not _path(args.packet) or not args.packet.startswith('gists/'):
            raise LoaderError('INVALID_PACKET', 'packet must be a declared gist')
        loader = LocalMarkdownLoader(args.feature_directory)
        raw, packet_identity = loader._read_raw(args.packet, MAX_FILE_BYTES)
        packet = _object(raw.decode('utf-8-sig'), 'review-packet-v1')
        task = packet.get('review_task')
        if not _id(task):
            raise LoaderError('INVALID_PACKET', 'invalid review task')
        import task_context as tc
        detail_path = 'tasks/' + task + '.md'
        detail, detail_identity = loader._read_raw(detail_path, MAX_FILE_BYTES)
        declared = set(tc.declared_gist_names(detail.decode('utf-8-sig')))
        if len(declared) > MAX_FILES or args.packet not in declared:
            raise LoaderError('INVALID_PACKET', 'packet is not a declared gist')
        # First pass discovers only explicitly referenced original inputs.
        draft = build_packet(packet)
        documents = {}
        identities = {}
        seen_identities = {packet_identity, detail_identity}
        total = len(raw) + len(detail)
        if len(draft['initial_source_paths']) + 2 > MAX_FILES:
            raise LoaderError('RESOURCE_LIMIT', 'packet file budget exceeded')
        for path in draft['initial_source_paths']:
            if path.startswith('gists/') and path not in declared:
                raise LoaderError('INVALID_PACKET', 'source is not a declared gist')
            try:
                value, identity = loader._read_raw(path, min(MAX_FILE_BYTES, MAX_BYTES - total))
            except LoaderError as error:
                if error.code == 'INCOMPLETE_CONTEXT':
                    continue
                raise
            if identity in seen_identities:
                raise LoaderError('DUPLICATE_IDENTITY', 'packet sources alias one file')
            seen_identities.add(identity)
            documents[path] = value
            identities[path] = identity
            total += len(value)
        # Revalidate selected bytes and identity after all reads. Do not call
        # whole-feature finish(), which would expand unrelated task/history.
        for path, expected in {**documents, args.packet: raw, detail_path: detail}.items():
            observed, identity = loader._read_raw(path, len(expected))
            if observed != expected or (path in identities and identity != identities[path]):
                raise LoaderError('SOURCE_CHANGED', 'packet read set changed')
            if path == detail_path and identity != detail_identity:
                raise LoaderError('SOURCE_CHANGED', 'task identity changed')
            if path == args.packet and identity != packet_identity:
                raise LoaderError('SOURCE_CHANGED', 'packet identity changed')
        result = build_packet(packet, documents=documents)
        # Summary only. Never prints source material, authority text or secrets.
        summary = {k: result[k] for k in ('complete', 'handoff_allowed', 'independent_executed',
                                         'missing', 'reason_codes', 'packet_digest', 'event')}
        if result['complete']:
            summary.update(target_refs=packet['target_refs'],
                           scope_ids=packet['scope']['requirement_ids'] + packet['scope']['solution_ids'])
        print(json.dumps(summary, ensure_ascii=True))
        return 0 if result['complete'] else 2
    except (LoaderError, OSError, UnicodeError, ValueError, RecursionError) as error:
        print(json.dumps({'complete': False, 'handoff_allowed': False,
                          'reason_codes': ['INCOMPLETE_PACKET', getattr(error, 'code', 'SOURCE_UNAVAILABLE')]}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
