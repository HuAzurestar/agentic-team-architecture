#!/usr/bin/env python3
"""Validate and summarize report-v1 ledgers; never grant quality or acceptance."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import sys
import time

from context_loader import LoaderError, LocalMarkdownLoader
from review_packet import _digest, _id, _keys, _path, _text
from review_resume import _object

OUTCOMES = ('PASS', 'FAIL', 'UNKNOWN', 'NOT-RUN', 'N/A')
LEVELS = ('P0', 'P1', 'P2')
MAX_CHECKS = 10000
MAX_FINDINGS = 10000
MAX_LINKS = 30000
MAX_BYTES = 64 * 1024 * 1024
MAX_REPORTS = 1000
MAX_SECONDS = 2.0
FIELDS = frozenset(('schema', 'report_ref', 'feature', 'review_task', 'packet_id',
    'attempt_id', 'target_refs', 'checklist_ref', 'reviewer', 'context',
    'evidence_refs', 'checks', 'findings', 'diagnostics', 'summary'))
FINDING_FIELDS = frozenset(('id', 'severity', 'blocking', 'status', 'description',
    'evidence_refs', 'affected_check_ids', 'resolution_ref', 'verified_by', 'verified_ref',
    'verified_target_refs', 'nonblocking_reason', 'violates_requirement', 'severity_history'))
CHECK_FIELDS = frozenset(('id', 'outcome', 'required', 'scope_ids', 'evidence_refs',
                          'reason', 'next_action', 'finding_ids'))
KEY_FIELDS = ('feature', 'report_ref', 'attempt_id', 'finding_id')


class ReportError(ValueError):
    def __init__(self, code, location='report'):
        self.code, self.location = code, location
        super().__init__(code)


@dataclass(frozen=True)
class VerifiedReportEvidence:
    """Host-only evidence, never loaded from JSON or Markdown assertions.

    Each authorization is bound to the canonical digest of the exact report
    containing that finding. The host must actually verify independent closure,
    current human exceptions and severity-change evidence before constructing it.
    """
    report_digests: frozenset = field(default_factory=frozenset)
    closures: frozenset = field(default_factory=frozenset)
    exceptions: frozenset = field(default_factory=frozenset)
    severity_changes: frozenset = field(default_factory=frozenset)


def _require(condition, code='INVALID_REPORT', location='report'):
    if not condition:
        raise ReportError(code, location)


def _canonical(value, budget):
    chunks, total = [], 0
    for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True,
                                 separators=(',', ':'), allow_nan=False).iterencode(value):
        encoded = chunk.encode('utf-8')
        total += len(encoded)
        _require(total <= MAX_BYTES, 'RESOURCE_LIMIT')
        chunks.append(encoded)
        budget.check()
    return b''.join(chunks)


class Budget:
    def __init__(self):
        self.start = time.process_time()
        self.bytes = self.checks = self.findings = self.links = 0

    def check(self):
        _require(time.process_time() - self.start <= MAX_SECONDS, 'RESOURCE_LIMIT')
        _require(self.bytes <= MAX_BYTES and self.checks <= MAX_CHECKS
                 and self.findings <= MAX_FINDINGS and self.links <= MAX_LINKS, 'RESOURCE_LIMIT')

    def link(self, count=1):
        self.links += count
        self.check()


def _reference(value, budget):
    _require(_keys(value, ('path', 'sha256')) and _path(value['path'])
             and _digest(value['sha256']), 'INVALID_EVIDENCE_REF')
    budget.link()
    return value


def _refs(value, budget, required=False):
    _require(isinstance(value, list), 'INVALID_EVIDENCE_REF')
    _require(not required or bool(value), 'EVIDENCE_MISSING')
    _require(len(value) <= MAX_LINKS, 'RESOURCE_LIMIT')
    seen = set()
    for item in value:
        _reference(item, budget)
        identity = (item['path'], item['sha256'])
        _require(identity not in seen, 'DUPLICATE_EVIDENCE')
        seen.add(identity)


def _ids(value, required=False):
    _require(isinstance(value, list))
    _require(len(value) <= MAX_LINKS, 'RESOURCE_LIMIT')
    _require(all(_id(x) for x in value))
    _require(not required or bool(value), 'EVIDENCE_MISSING')
    _require(len(value) == len(set(value)), 'DUPLICATE_ID')
    return set(value)


def _targets(value):
    return (isinstance(value, dict) and bool(value) and len(value) <= MAX_REPORTS
            and all(_id(k) and _digest(v, 40) for k, v in value.items()))


def _key(value):
    _require(_keys(value, KEY_FIELDS) and all(_id(value[k]) for k in KEY_FIELDS), 'INVALID_FINDING_KEY')
    return tuple(value[k] for k in KEY_FIELDS)


def _key_object(key):
    return dict(zip(KEY_FIELDS, key))


def report_digest(raw):
    """Canonical binding digest only; this does not validate or authorize raw."""
    return hashlib.sha256(_canonical(raw, Budget())).hexdigest()


def _identity(report):
    return report['feature'], report['report_ref'], report['attempt_id']


def _roots(nodes, links, budget):
    """Iterative three-colour walk: linear even for a 10000-node chain."""
    colors, roots = {}, {}
    for start in nodes:
        if colors.get(start) == 2:
            continue
        path, current = [], start
        while current not in roots:
            budget.check()
            _require(current in nodes, 'FINDING_MISSING')
            _require(colors.get(current) != 1, 'DUPLICATE_CYCLE')
            colors[current] = 1
            path.append(current)
            if current not in links:
                roots[current] = current
                break
            current = links[current]
        root = roots[current]
        for node in reversed(path):
            roots[node], colors[node] = root, 2
    return roots


def compute_report(raw, *, related_reports=(), verified=None):
    """Pure schema/count calculation over explicit original report objects.

    report_ref is a stable report ID, not a content hash of itself. Together with
    feature/attempt/finding it forms the complete ledger key. Actual source bytes
    are bound separately by the host/CLI read set. Evidence refs are checked for
    shape here, not remotely fetched or authenticated. No schema result permits
    a merge. Legacy recovery records are not silently upgraded to full reports.
    """
    budget = Budget()
    diagnostics = []
    try:
        budget.check()
        _require(isinstance(related_reports, (list, tuple)) and len(related_reports) < MAX_REPORTS,
                 'RESOURCE_LIMIT')
        reports, digests = [], {}
        for incoming in (raw, *related_reports):
            budget.check()
            is_text = isinstance(incoming, str)
            if is_text:
                budget.bytes += len(incoming.encode('utf-8'))
                budget.check()
                incoming = _object(incoming, 'report-v1')
            _require(isinstance(incoming, dict))
            canonical = _canonical(incoming, budget)
            # Charge the actual representation only once for each report.
            if not is_text:
                budget.bytes += len(canonical)
            budget.check()
            _require(FIELDS <= incoming.keys(), 'LEGACY_EVIDENCE_INCOMPLETE')
            _require(set(incoming) == FIELDS and incoming['schema'] == 'report-v1')
            for name in ('feature', 'report_ref', 'review_task', 'packet_id', 'attempt_id'):
                _require(_id(incoming[name]))
            identity = _identity(incoming)
            _require(identity not in digests, 'DUPLICATE_REPORT')
            digests[identity] = hashlib.sha256(canonical).hexdigest()
            reports.append(incoming)

        current = reports[0]
        nodes, links = {}, {}
        check_maps, check_links, affected_sets = {}, {}, {}
        current_outcomes = {x: 0 for x in OUTCOMES}
        for report in reports:
            identity = _identity(report)
            _require(report['feature'] == current['feature'], 'FEATURE_MISMATCH')
            _require(_targets(report['target_refs']), 'INVALID_TARGET')
            _reference(report['checklist_ref'], budget)
            _refs(report['evidence_refs'], budget, True)
            _require(_text(report['reviewer']))
            context = report['context']
            _require(_keys(context, ('source_ref', 'authority_ref', 'implementation_author'))
                     and all(_text(v) for v in context.values()), 'CONTEXT_MISSING')
            _require(isinstance(report['diagnostics'], list) and len(report['diagnostics']) <= MAX_CHECKS)
            for diagnostic in report['diagnostics']:
                _require(_keys(diagnostic, ('code', 'reason')) and _id(diagnostic['code'])
                         and _text(diagnostic['reason']))
                diagnostics.append({'code': diagnostic['code'], 'reported': True,
                    'report_ref': report['report_ref'], 'attempt_id': report['attempt_id'],
                    'evidence_scope': 'current' if report is current else 'historical'})
            _require(isinstance(report['summary'], dict))
            checks, findings = report['checks'], report['findings']
            _require(isinstance(checks, list) and bool(checks) and isinstance(findings, list))
            budget.checks += len(checks)
            budget.findings += len(findings)
            budget.check()
            check_map = {}
            for check in checks:
                budget.check()
                _require(isinstance(check, dict) and CHECK_FIELDS <= check.keys()
                         and not (check.keys() - CHECK_FIELDS - {'scope_exception_ref', 'reuse'})
                         and _id(check['id']))
                _require(check['id'] not in check_map, 'DUPLICATE_CHECK')
                _require(check['outcome'] in OUTCOMES, 'INVALID_OUTCOME')
                _require(type(check['required']) is bool)
                scopes = _ids(check['scope_ids'], True)
                linked = _ids(check['finding_ids'])
                budget.link(len(scopes) + len(linked))
                _require(isinstance(check['reason'], str) and isinstance(check['next_action'], str))
                _refs(check['evidence_refs'], budget, check['outcome'] in ('PASS', 'FAIL'))
                if check['outcome'] in ('UNKNOWN', 'NOT-RUN', 'N/A'):
                    _require(_text(check['reason']), 'EVIDENCE_MISSING')
                if check['outcome'] in ('UNKNOWN', 'NOT-RUN'):
                    _require(_text(check['next_action']), 'EVIDENCE_MISSING')
                if check['outcome'] == 'FAIL':
                    _require(bool(linked), 'EVIDENCE_MISSING')
                if 'scope_exception_ref' in check:
                    _reference(check['scope_exception_ref'], budget)
                if 'reuse' in check:
                    reuse = check['reuse']
                    _require(_keys(reuse, ('prior_check_ref', 'diff_refs', 'dependency_refs', 'reviewer_basis')))
                    prior = reuse['prior_check_ref']
                    _require(_keys(prior, ('feature', 'report_ref', 'attempt_id', 'check_id'))
                             and all(_id(v) for v in prior.values()), 'INVALID_CHECK_KEY')
                    _require(_text(reuse['reviewer_basis']), 'EVIDENCE_MISSING')
                    _refs(reuse['diff_refs'], budget, True)
                    _refs(reuse['dependency_refs'], budget, True)
                    budget.link()
                check_map[check['id']] = check
                check_links[(*identity, check['id'])] = linked
                if report is current:
                    current_outcomes[check['outcome']] += 1
            check_maps[identity] = check_map

            for finding in findings:
                budget.check()
                _require(isinstance(finding, dict) and FINDING_FIELDS <= finding.keys())
                _require(not (finding.keys() - FINDING_FIELDS - {'duplicate_of', 'duplicate_reason',
                            'duplicate_evidence_refs', 'exception_ref'}))
                _require(_id(finding['id']))
                key = (*identity, finding['id'])
                if key in nodes:
                    _require(_canonical(nodes[key], budget) == _canonical(finding, budget), 'CONFLICTING_FINDING')
                    continue
                _require(finding['severity'] in LEVELS and finding['status'] in ('open', 'addressed', 'closed'))
                _require(type(finding['blocking']) is bool and type(finding['violates_requirement']) is bool,
                         'INVALID_BLOCKING')
                _require(finding['severity'] != 'P0' or finding['blocking'], 'INVALID_BLOCKING')
                _require(_text(finding['description']))
                _refs(finding['evidence_refs'], budget, True)
                affected = _ids(finding['affected_check_ids'], True)
                budget.link(len(affected))
                _require(affected <= check_map.keys(), 'CHECK_MISSING')
                for check_id in affected:
                    _require(finding['id'] in check_links[(*identity, check_id)], 'FINDING_LINK_MISMATCH')
                affected_sets[key] = affected
                requires_blocking = finding['violates_requirement'] or any(
                    check_map[x]['required'] and check_map[x]['outcome'] == 'FAIL' for x in affected)
                if not finding['blocking']:
                    _require(_text(finding['nonblocking_reason']), 'EVIDENCE_MISSING')
                    if 'exception_ref' in finding:
                        _reference(finding['exception_ref'], budget)
                    if requires_blocking:
                        _require('exception_ref' in finding, 'EXCEPTION_UNVERIFIED')
                        _require(_trusted(verified, key, digests, 'exceptions'), 'EXCEPTION_UNVERIFIED')
                else:
                    _require(isinstance(finding['nonblocking_reason'], str))
                    if 'exception_ref' in finding:
                        _reference(finding['exception_ref'], budget)
                if finding['status'] in ('addressed', 'closed'):
                    _reference(finding['resolution_ref'], budget)
                elif finding['resolution_ref'] is not None:
                    _reference(finding['resolution_ref'], budget)
                if finding['status'] == 'closed':
                    _require(_text(finding['verified_by']) and finding['verified_by'] != context['implementation_author'],
                             'INVALID_CLOSURE')
                    _reference(finding['verified_ref'], budget)
                    _require(_targets(finding['verified_target_refs'])
                             and finding['verified_target_refs'] == report['target_refs'], 'INVALID_CLOSURE')
                else:
                    _require(finding['verified_by'] is None and finding['verified_ref'] is None
                             and finding['verified_target_refs'] is None, 'INVALID_CLOSURE')
                history = finding['severity_history']
                _require(isinstance(history, list) and len(history) <= MAX_LINKS)
                last = None
                for change in history:
                    budget.link()
                    _require(_keys(change, ('from', 'to', 'reason', 'verified_by', 'verified_ref', 'target_refs')))
                    _require(change['from'] in LEVELS and change['to'] in LEVELS
                             and (last is None or last == change['from']) and _text(change['reason'])
                             and _text(change['verified_by']) and change['verified_by'] != context['implementation_author']
                             and change['target_refs'] == report['target_refs'], 'INVALID_SEVERITY_HISTORY')
                    _reference(change['verified_ref'], budget)
                    last = change['to']
                _require(last is None or last == finding['severity'], 'INVALID_SEVERITY_HISTORY')
                if 'duplicate_of' in finding:
                    origin = _key(finding['duplicate_of'])
                    _require(_text(finding.get('duplicate_reason')), 'EVIDENCE_MISSING')
                    _refs(finding.get('duplicate_evidence_refs'), budget, True)
                    links[key] = origin
                    budget.link()
                else:
                    _require('duplicate_reason' not in finding and 'duplicate_evidence_refs' not in finding)
                nodes[key] = finding

        for identity, checks in check_maps.items():
            for check in checks.values():
                for finding_id in check['finding_ids']:
                    key = (*identity, finding_id)
                    _require(key in nodes, 'FINDING_MISSING')
                    _require(check['id'] in affected_sets[key], 'FINDING_LINK_MISMATCH')
        roots = _roots(nodes, links, budget)
        groups = {}
        for key, root in roots.items():
            groups.setdefault(root, []).append(key)
        by_severity = {x: 0 for x in LEVELS}
        opened = {x: 0 for x in LEVELS}
        blockers, discovered, inherited, historical, ledger = 0, 0, 0, 0, []
        current_identity = _identity(current)
        same_candidate = {_identity(r) for r in reports if r['target_refs'] == current['target_refs']}
        for root, members in groups.items():
            budget.check()
            active = [k for k in members if k[:3] == current_identity]
            levels = [nodes[k]['severity'] for k in members]
            for k in members:
                levels.extend(h['from'] for h in nodes[k]['severity_history'])
            severity = min(levels, key=LEVELS.index)
            changes = [k for k in active if nodes[k]['severity_history']
                       and _trusted(verified, k, digests, 'severity_changes')]
            if changes:
                approved = {nodes[k]['severity'] for k in changes}
                _require(len(approved) == 1 and all(nodes[k]['severity_history'][0]['from'] == severity for k in changes),
                         'INVALID_SEVERITY_HISTORY')
                severity = next(iter(approved))
            blocking = severity == 'P0' or any(nodes[k]['blocking'] for k in members)
            if severity != 'P0' and active and all(not nodes[k]['blocking']
                    and 'exception_ref' in nodes[k] and _trusted(verified, k, digests, 'exceptions') for k in active):
                blocking = False
            closure_candidates = active or [k for k in members if k[:3] in same_candidate]
            closed = bool(closure_candidates) and all(nodes[k]['status'] == 'closed'
                and _trusted(verified, k, digests, 'closures') for k in closure_candidates)
            if any(nodes[k]['status'] == 'closed' for k in members) and not closed:
                diagnostics.append({'code': 'CLOSURE_UNVERIFIED', 'finding_key': _key_object(root)})
            if any(nodes[k]['severity_history'] for k in members) and not changes:
                diagnostics.append({'code': 'SEVERITY_UNVERIFIED', 'finding_key': _key_object(root)})
            by_severity[severity] += 1
            if not closed:
                opened[severity] += 1
                blockers += int(blocking)
            origin = 'current' if root[:3] == current_identity else 'inherited' if active else 'historical-only'
            discovered += int(origin == 'current')
            inherited += int(origin == 'inherited')
            historical += int(origin == 'historical-only')
            ledger.append({'root': _key_object(root), 'members': [_key_object(k) for k in members],
                           'severity': severity, 'blocking': blocking, 'closed': closed, 'origin': origin})
        applicable = sum(current_outcomes[x] for x in OUTCOMES if x != 'N/A')
        ratio = current_outcomes['PASS'] / applicable if applicable else None
        counts = {'by_outcome': current_outcomes, 'all': applicable, 'total': sum(current_outcomes.values()),
                  'findings_total': len(groups), 'by_severity': by_severity, 'open_by_severity': opened,
                  'open_blockers': blockers, 'discovered_current': discovered,
                  'inherited_current': inherited, 'historical_only': historical}
        summary = {'valid': True, 'counts': counts, 'ratio': ratio}
        if current['summary']:
            _require(_canonical(current['summary'], budget) == _canonical(summary, budget), 'SUMMARY_MISMATCH')
        budget.check()
        return {'summary': summary, 'counts': counts, 'ratio': ratio, 'diagnostics': diagnostics,
                'ledger': ledger, 'target_refs': dict(current['target_refs']),
                'report_digest': digests[current_identity], 'quality_assessed': False,
                'source_evidence_verified': False, 'event': {'name': 'report.summarize',
                'checks': budget.checks, 'findings': budget.findings, 'links': budget.links,
                'target_refs': dict(current['target_refs']), 'reason_codes': sorted({x['code'] for x in diagnostics})}}
    except (ReportError, LoaderError, TypeError, ValueError, RecursionError, UnicodeError, KeyError) as error:
        code = getattr(error, 'code', 'INVALID_REPORT')
        return {'summary': {'valid': False}, 'counts': None, 'ratio': None,
                'diagnostics': [{'code': code}], 'quality_assessed': False,
                'source_evidence_verified': False,
                'event': {'name': 'report.validate', 'reason_codes': [code]}}


def _trusted(evidence, key, digests, category):
    return (isinstance(evidence, VerifiedReportEvidence)
            and (key[:3], digests[key[:3]]) in evidence.report_digests
            and key in getattr(evidence, category))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feature_directory', type=Path)
    parser.add_argument('report', help='Declared report gist, relative to the feature')
    parser.add_argument('--related', action='append', default=[], help='Explicit historical report gist')
    args = parser.parse_args(argv)
    try:
        names = [args.report, *args.related]
        _require(len(names) <= MAX_REPORTS and len(set(names)) == len(names), 'RESOURCE_LIMIT')
        loader = LocalMarkdownLoader(args.feature_directory)
        loaded, total, identities = {}, 0, set()
        _require(_path(args.report) and args.report.startswith('gists/'), 'INVALID_EVIDENCE_REF')
        data, identity = loader._read_raw(args.report, MAX_BYTES)
        primary = _object(data.decode('utf-8-sig'), 'report-v1')
        _require(FIELDS <= primary.keys(), 'LEGACY_EVIDENCE_INCOMPLETE')
        loaded[args.report] = (data, identity)
        total += len(data)
        identities.add(identity)
        task = primary.get('review_task')
        _require(_id(task))
        detail_name = 'tasks/' + task + '.md'
        detail, identity = loader._read_raw(detail_name, MAX_BYTES - total)
        total += len(detail)
        import task_context as tc
        declared = set(tc.declared_gist_names(detail.decode('utf-8-sig')))
        _require(set(names) <= declared, 'UNDECLARED_REPORT')
        loaded[detail_name] = (detail, identity)
        for name in args.related:
            _require(_path(name) and name.startswith('gists/'), 'INVALID_EVIDENCE_REF')
            data, identity = loader._read_raw(name, MAX_BYTES - total)
            _require(identity not in identities, 'DUPLICATE_REPORT')
            identities.add(identity)
            total += len(data)
            loaded[name] = (data, identity)
        objects = [_object(loaded[name][0].decode('utf-8-sig'), 'report-v1') for name in names]
        result = compute_report(objects[0], related_reports=objects[1:])
        for name, (data, identity) in loaded.items():
            observed, now = loader._read_raw(name, len(data))
            _require(observed == data and now == identity, 'SOURCE_CHANGED')
        # No prose, report bodies or human authorization claims in output.
        output = {k: result[k] for k in ('summary', 'counts', 'ratio', 'diagnostics',
                         'quality_assessed', 'source_evidence_verified', 'event')}
        output['source_refs'] = [{'path': name, 'sha256': hashlib.sha256(loaded[name][0]).hexdigest()}
                                 for name in names]
        print(json.dumps(output, ensure_ascii=True))
        return 0 if result['summary']['valid'] else 2
    except (ReportError, LoaderError, OSError, ValueError, UnicodeError, RecursionError) as error:
        print(json.dumps({'summary': {'valid': False}, 'counts': None, 'ratio': None,
                          'diagnostics': [{'code': getattr(error, 'code', 'SOURCE_UNAVAILABLE')}]}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
