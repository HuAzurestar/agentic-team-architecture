#!/usr/bin/env python3
"""Bounded three-phase facts policy; no task mutation or operation authority."""
from dataclasses import dataclass, field
import hashlib
import json
import sys
import time
sys.dont_write_bytecode = True
import task_context as tc
import review_report as rr
import decision_evidence as de
import quality_tests as qt

PHASES = ('pre_accept', 'pre_merge', 'post_merge')
MAX_ITEMS, MAX_LINKS, MAX_BYTES, CPU_SECONDS = 10000, 30000, 64 * 1024 * 1024, 2.0
FIELDS = {'schema', 'feature', 'phase', 'target_refs', 'attempt_id', 'checklist_ref', 'required_checks',
          'report', 'related_reports', 'tests', 'result_tests', 'frozen', 'acceptance'}


@dataclass(frozen=True)
class QualityObservations:
    """Host-only readback facts, never construct from uploaded JSON assertions.

    Digest binds the WHOLE request and validated feature observation. The host
    must verify sources, reviewer independence, exact human exceptions/reuse,
    remote targets and actual Git observations before supplying these values.
    Type or digest alone is not authentication. Host wiring remains separate.
    """
    request_digest: str
    feature_digest: str
    source_refs: frozenset = field(default_factory=frozenset)
    independent_reports: frozenset = field(default_factory=frozenset)
    excluded_scopes: frozenset = field(default_factory=frozenset)
    reused_checks: frozenset = field(default_factory=frozenset)
    integration: dict = field(default_factory=dict)
    remote_targets: frozenset = field(default_factory=frozenset)
    acceptance_bindings: frozenset = field(default_factory=frozenset)
    required_repositories: frozenset = field(default_factory=frozenset)
    checklist_binding: str = ''
    current_review_digest: str = ''
    applicable_tests: frozenset = field(default_factory=frozenset)
    test_impacts: dict = field(default_factory=dict)


class Invalid(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise Invalid(code)


def canonical(value):
    chunks, size = [], 0
    started = time.process_time()
    for index, chunk in enumerate(json.JSONEncoder(sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).iterencode(value)):
        raw = chunk.encode('utf-8')
        size += len(raw)
        require(size <= MAX_BYTES, 'RESOURCE_LIMIT')
        if index % 256 == 0:
            require(time.process_time() - started <= CPU_SECONDS, 'RESOURCE_LIMIT')
        chunks.append(raw)
    require(time.process_time() - started <= CPU_SECONDS, 'RESOURCE_LIMIT')
    return b''.join(chunks)


def request_digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def feature_digest(feature):
    require(type(feature) is tc.ValidatedFeature, 'VALIDATED_FEATURE_REQUIRED')
    return request_digest(dict(feature=feature.documents.root.name,
        sources={p: r.content_digest for p, r in feature.documents.records.items()},
        tasks=feature.records, contracts=feature.type_contracts, task_refs=feature.details,
        repositories={n: [r['actual_branch'], r['actual_head']] for n, r in feature.repositories.items()}))


def test_applicability_key(tests, expected, attempt):
    return request_digest(dict(tests=tests, expected=expected, attempt=attempt))


def _ids(values):
    require(isinstance(values, list) and len(values) <= MAX_ITEMS
            and all(rr._id(x) for x in values) and len(set(values)) == len(values), 'INVALID_SCOPE')
    return set(values)


def assess_quality(feature, request, *, observed=None, report_evidence=None, decision_sources=None):
    started = time.process_time()
    reasons, missing, stale, blockers, evidence = set(), set(), set(), [], set()
    test_audits = []
    event_targets = {}
    phase = request.get('phase') if isinstance(request, dict) else None
    phase = phase if phase in PHASES else None
    def budget():
        require(time.process_time() - started <= CPU_SECONDS, 'RESOURCE_LIMIT')
    def deny(code):
        reasons.add(code)
    try:
        require(isinstance(request, dict) and set(request) == FIELDS
                and request['schema'] == 'quality-request-v1' and phase is not None, 'INVALID_QUALITY_REQUEST')
        require(type(feature) is tc.ValidatedFeature, 'VALIDATED_FEATURE_REQUIRED')
        require(type(observed) is QualityObservations
                and observed.request_digest == request_digest(request)
                and observed.feature_digest == feature_digest(feature), 'QUALITY_SOURCES_UNVERIFIED')
        budget()
        require(request['feature'] == feature.documents.root.name, 'FEATURE_MISMATCH')
        require(rr._targets(request['target_refs']) and rr._id(request['attempt_id']), 'INVALID_TARGET')
        targets = request['target_refs']
        event_targets = dict(targets)
        require(set(targets) <= set(feature.repositories), 'UNKNOWN_REPOSITORY')
        require(set(targets) == observed.required_repositories, 'INCOMPLETE_REPOSITORY_SCOPE')
        require(observed.checklist_binding == request_digest(dict(ref=request['checklist_ref'],
            required_checks=request['required_checks'])), 'CHECKLIST_SCOPE_UNVERIFIED')
        scopes = set()
        for filename, prefix, state in [('REQUIREMENT.md', 'REQ', 'CONFIRMED'), ('SOLUTION.md', 'SOL', 'BASELINED')]:
            states = tc.validate_decision_document(feature.documents.read(filename), prefix, state)
            require(states and all(value in tc.DECIDED_POINT_STATES for value in states.values()), 'INTENT_NOT_CONFIRMED')
            scopes.update(k for k, value in states.items() if value == 'CONFIRMED')
        require(scopes and observed.excluded_scopes <= scopes, 'INVALID_SCOPE')
        required_scope = scopes - observed.excluded_scopes
        # Source hashes are checked against host readback, not JSON claims. Walk
        # every nested reference, including reused checks and historical closure.
        stack, links = [request], 0
        while stack:
            budget()
            value = stack.pop()
            if isinstance(value, dict):
                if 'path' in value and 'sha256' in value:
                    require(rr._path(value['path']) and rr._digest(value['sha256']), 'INVALID_EVIDENCE_REF')
                    ref = (value['path'], value['sha256'])
                    require(ref in observed.source_refs, 'SOURCE_EVIDENCE_UNVERIFIED')
                    evidence.add(ref)
                    links += 1
                stack.extend(value.values())
            elif isinstance(value, list):
                links += len(value)
                stack.extend(value)
            require(links <= MAX_LINKS, 'RESOURCE_LIMIT')
        report, related = request['report'], request['related_reports']
        require(isinstance(report, dict) and isinstance(related, list), 'INVALID_REPORT')
        summary = rr.compute_report(report, related_reports=related, verified=report_evidence)
        require(summary['summary']['valid'], summary['diagnostics'][0]['code'] if summary['diagnostics'] else 'INVALID_REPORT')
        digest = rr.report_digest(report)
        require(digest in observed.independent_reports, 'INDEPENDENCE_UNVERIFIED')
        require(observed.current_review_digest == digest, 'REVIEW_CHAIN_UNVERIFIED')
        review_task = feature.records.get(report['review_task'])
        require(review_task is not None and review_task['type'] == 'Review' and review_task['state'] == 'DONE',
                'REVIEW_NOT_COMPLETE')
        require(report['feature'] == request['feature'] and report['target_refs'] == targets
                and report['attempt_id'] == request['attempt_id']
                and report['checklist_ref'] == request['checklist_ref'], 'STALE_REVIEW')
        blockers = [row['root'] for row in summary['ledger'] if row['blocking'] and not row['closed']]
        if blockers:
            deny('OPEN_BLOCKERS')
        if report['result'] != 'SUCCESS':
            deny('REVIEW_NOT_SUCCESSFUL')
        for diagnostic in summary['diagnostics']:
            if diagnostic.get('blocking', True) and diagnostic.get('evidence_scope') != 'historical':
                known = {'MISSING_SCOPE', 'EVIDENCE_MISSING', 'SOURCE_CHANGED', 'INDEPENDENCE_UNVERIFIED',
                         'RESOURCE_LIMIT', 'CLOSURE_UNVERIFIED', 'SEVERITY_UNVERIFIED'}
                deny(diagnostic['code'] if diagnostic['code'] in known else 'REVIEW_DIAGNOSTIC_BLOCKS')
        require(isinstance(request['required_checks'], list) and request['required_checks'], 'CHECKLIST_REQUIRED')
        checks = {row['id']: row for row in report['checks']}
        catalog, covered = set(), set()
        for item in request['required_checks']:
            require(isinstance(item, dict) and set(item) == {'id', 'scope_ids'} and rr._id(item['id']), 'INVALID_CHECKLIST')
            require(item['id'] not in catalog, 'DUPLICATE_CHECK')
            catalog.add(item['id'])
            ids = _ids(item['scope_ids'])
            require(ids and ids <= scopes, 'INVALID_SCOPE')
            covered.update(ids)
            check = checks.get(item['id'])
            if check is None or not check['required'] or set(check['scope_ids']) != ids:
                missing.add(item['id']); deny('MISSING_REQUIRED_CHECK')
            elif check['outcome'] != 'PASS' and not (check['outcome'] == 'N/A' and ids <= observed.excluded_scopes):
                missing.add(item['id']); deny('REQUIRED_CHECK_NOT_PASSED')
        if not required_scope <= covered:
            missing.update(required_scope - covered); deny('MISSING_SCOPE')
        historical_checks = {(r['feature'], r['report_ref'], r['attempt_id'], c['id']): c
                             for r in related for c in r['checks']}
        for old in related:
            if old['target_refs'] != targets and old['attempt_id'] == request['attempt_id']:
                deny('NEW_CANDIDATE_REQUIRES_NEW_ATTEMPT')
        for check in report['checks']:
            require(set(check['scope_ids']) <= scopes, 'INVALID_SCOPE')
            if check['required'] and check['outcome'] not in ('PASS', 'N/A'):
                missing.add(check['id']); deny('REQUIRED_CHECK_NOT_PASSED')
            if check['required'] and check['outcome'] == 'N/A' and not set(check['scope_ids']) <= observed.excluded_scopes:
                deny('SCOPE_EXCEPTION_UNVERIFIED')
            if 'reuse' in check:
                prior = check['reuse']['prior_check_ref']
                old_check = historical_checks.get((prior['feature'], prior['report_ref'], prior['attempt_id'], prior['check_id']))
                if (old_check is None or old_check['outcome'] != 'PASS'
                        or set(old_check['scope_ids']) != set(check['scope_ids'])
                        or (digest, check['id']) not in observed.reused_checks):
                    deny('REUSE_UNVERIFIED')
        items = sum(len(r['checks']) + len(r['findings']) for r in [report, *related]) + len(catalog)
        def test_details(tests, expected, label):
            nonlocal items
            require(isinstance(tests, dict) and set(tests) == {'schema', 'test_task', 'target_refs', 'attempt_id', 'checks'}
                    and tests['schema'] == 'test-results-v1' and isinstance(tests['checks'], list)
                    and tests['checks'], 'TEST_DETAILS_REQUIRED')
            test_task = feature.records.get(tests['test_task'])
            require(test_task is not None and test_task['type'] == 'Test' and test_task['state'] == 'DONE',
                    'TEST_NOT_COMPLETE')
            items += len(tests['checks'])
            require(items <= MAX_ITEMS, 'RESOURCE_LIMIT')
            binding_error = qt.task_binding(feature, tests)
            if binding_error:
                stale.add(label + ':task-report'); deny(binding_error)
            applicability = test_applicability_key(tests, expected, request['attempt_id'])
            if tests['target_refs'] != expected or tests['attempt_id'] != request['attempt_id']:
                if applicability not in observed.applicable_tests:
                    stale.add(label); deny('STALE_TESTS')
                    impact = observed.test_impacts.get(applicability)
                    if impact in {'TEST_INPUTS_CHANGED', 'UNVERIFIED_TEST_IMPACT'}:
                        deny(impact)
            seen, coverage = set(), set()
            for check in tests['checks']:
                budget()
                require(isinstance(check, dict) and set(check) == {'id', 'required', 'outcome', 'scope_ids', 'evidence_refs', 'reason'}
                        and rr._id(check['id']) and type(check['required']) is bool
                        and check['outcome'] in rr.OUTCOMES and isinstance(check['reason'], str), 'INVALID_TEST_DETAILS')
                require(check['id'] not in seen, 'DUPLICATE_CHECK')
                seen.add(check['id'])
                ids = _ids(check['scope_ids'])
                require(ids and ids <= scopes and isinstance(check['evidence_refs'], list), 'INVALID_SCOPE')
                require(all(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}
                            and rr._path(ref['path']) and rr._digest(ref['sha256'])
                            for ref in check['evidence_refs']), 'INVALID_EVIDENCE_REF')
                if check['outcome'] in ('PASS', 'FAIL'):
                    require(check['evidence_refs'], 'EVIDENCE_MISSING')
                if check['outcome'] != 'PASS':
                    require(check['reason'].strip(), 'EVIDENCE_MISSING')
                if check['required']:
                    coverage.update(ids)
                    if check['outcome'] != 'PASS' and not (check['outcome'] == 'N/A' and ids <= observed.excluded_scopes):
                        missing.add(label + ':' + check['id']); deny('REQUIRED_TEST_NOT_PASSED')
            if not required_scope <= coverage:
                missing.update(required_scope - coverage); deny('MISSING_TEST_SCOPE')
            audit = qt.audit_counts(feature.type_contracts.get(tests['test_task'], {}), tests['checks'])
            test_audits.append(dict(label=label, test_task=tests['test_task'], **audit,
                applicability=observed.test_impacts.get(applicability, 'EXACT_TARGET_AND_ATTEMPT'
                    if tests['target_refs'] == expected and tests['attempt_id'] == request['attempt_id']
                    else 'UNVERIFIED_TEST_IMPACT')))
            reasons.update(audit['reason_codes'])
        test_details(request['tests'], targets, 'candidate')
        require(items <= MAX_ITEMS and set(request['frozen']) == set(targets), 'INVALID_FROZEN_TARGET')
        results = {}
        for name, source in targets.items():
            frozen = request['frozen'][name]
            require(isinstance(frozen, dict) and set(frozen) == {'source_tree', 'target_before', 'result'}, 'INVALID_FROZEN_TARGET')
            facts = observed.integration.get(name)
            require(isinstance(facts, dict) and facts.get('repository_ref') == name
                    and facts.get('source') == source and facts.get('source_tree') == frozen['source_tree']
                    and facts.get('target_before') == frozen['target_before']
                    and facts.get('target_in_source') is True, 'INTEGRATION_UNVERIFIED')
            expected = frozen['result'] if phase == 'post_merge' else source
            if feature.repositories[name]['actual_head'] != expected:
                stale.add(name); deny('CANDIDATE_MOVED')
            remote_target = frozen['result'] if phase == 'post_merge' else frozen['target_before']
            if (name, remote_target) not in observed.remote_targets:
                stale.add(name); deny('INTEGRATION_TARGET_UNVERIFIED')
            if phase == 'post_merge':
                require(frozen['result'] and facts.get('result') == frozen['result']
                        and facts.get('observed_target') == frozen['result']
                        and facts.get('result_contains_source') is True
                        and facts.get('result_tree') == frozen['source_tree'], 'MERGE_CORRESPONDENCE_UNVERIFIED')
                results[name] = frozen['result']
            else:
                require(frozen['result'] is None and facts.get('observed_target') == frozen['target_before'], 'TARGET_MOVED')
        if phase == 'post_merge':
            test_details(request['result_tests'], results, 'result')
        else:
            require(request['result_tests'] is None, 'UNEXPECTED_RESULT_TESTS')
        if phase != 'pre_accept':
            acceptance = request['acceptance']
            require(isinstance(acceptance, dict) and set(acceptance) == {'record', 'current'}, 'ACCEPTANCE_REQUIRED')
            record = acceptance['record']
            decision = de.check_decision(record, acceptance['current'],
                verified=(decision_sources or {}).get(record.get('decision_id')))
            if not decision['applicable']:
                reasons.update(decision['reason_codes'])
            if record.get('decision_kind') != 'acceptance' or record.get('feature') != request['feature']:
                deny('ACCEPTANCE_SCOPE_MISMATCH')
            if decision.get('outcome') != 'CONFIRMED':
                deny('ACCEPTANCE_NOT_CONFIRMED')
            if de.decision_digest(record) not in observed.acceptance_bindings:
                deny('ACCEPTANCE_CANDIDATE_UNVERIFIED')
        budget()
    except (Invalid, rr.ReportError, tc.ContextError, de.Invalid, KeyError, TypeError, ValueError, AttributeError,
            RecursionError, UnicodeError) as exc:
        reasons.add(str(exc) if isinstance(exc, Invalid) else 'INVALID_QUALITY_EVIDENCE')
    allowed = not reasons
    actions = set()
    if allowed:
        actions.add({'pre_accept': 'request-current-candidate-acceptance',
                     'pre_merge': 'obtain-explicit-merge-authorization',
                     'post_merge': 'record-result-and-evaluate-final-gate'}[phase])
    else:
        for code in reasons:
            if code in {'OPEN_BLOCKERS', 'CLOSURE_UNVERIFIED'}:
                actions.add('rework-and-independently-recheck-blockers')
            elif code == 'ACCEPTANCE_NOT_CONFIRMED':
                actions.add('follow-recorded-human-decision-no-merge')
            elif code in {'ACCEPTANCE_REQUIRED', 'HUMAN_SOURCE_UNVERIFIED', 'ACCEPTANCE_CANDIDATE_UNVERIFIED'}:
                actions.add('obtain-exact-current-human-acceptance-evidence')
            elif 'STALE' in code or 'MOVED' in code or code in {'MERGE_CORRESPONDENCE_UNVERIFIED', 'NEW_CANDIDATE_REQUIRES_NEW_ATTEMPT'}:
                actions.add('freeze-current-candidate-and-recheck-applicable-acceptance')
            elif code in {'TEST_SUMMARY_DETAIL_CONFLICT', 'TEST_COUNT_TOTAL_MISMATCH', 'INVALID_TEST_COUNTS'}:
                actions.add('inspect-original-execution-and-reconcile-task-and-report')
            elif 'TEST' in code or 'CHECK' in code or 'SCOPE' in code:
                actions.add('complete-current-required-checks-and-scope-evidence')
            else:
                actions.add('obtain-current-verified-evidence-and-reassess')
    return dict(eligible=allowed, allowed=allowed, reason_codes=sorted(reasons), missing_checks=sorted(missing),
        open_blockers=blockers, stale_refs=sorted(stale), evidence_refs=[dict(path=p, sha256=s) for p, s in sorted(evidence)],
        required_next_actions=sorted(actions),
        test_audits=test_audits,
        merge_authorized=False, effect='NOT_APPLIED',
        event=dict(name='quality.evaluate', stage=phase, allowed=allowed, reason_codes=sorted(reasons),
                   target_refs=event_targets, cpu_ms=round((time.process_time() - started) * 1000, 3)))
