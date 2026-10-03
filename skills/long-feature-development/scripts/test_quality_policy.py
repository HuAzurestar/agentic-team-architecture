#!/usr/bin/env python3
"""Synthetic trusted-host fixtures test policy, not actual human/host authority."""
import copy
from dataclasses import replace
import hashlib
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import quality_policy as q
import task_context as tc
import test_task_context as context_fixture
import test_review_report as reports
import test_decision_evidence as decisions
import review_report as rr


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.bodies = {'REQUIREMENT.md': context_fixture.REQUIREMENT, 'SOLUTION.md': context_fixture.SOLUTION}
        documents = SimpleNamespace(root=Path('PIRC-31'), read=self.bodies.__getitem__, records={
            k: SimpleNamespace(content_digest=hashlib.sha256(v.encode()).hexdigest()) for k, v in self.bodies.items()})
        self.feature = tc.ValidatedFeature(documents,
            {'REVIEW-1': dict(type='Review', state='DONE'), 'TEST-1': dict(type='Test', state='DONE')}, {}, {},
            {'app': {'actual_branch': 'source', 'actual_head': 'a' * 40}}, {}, {})
        report = reports.report()
        report['result'] = 'SUCCESS'
        report['checks'][0]['scope_ids'] = ['REQ-001', 'SOL-001']
        self.request = dict(schema='quality-request-v1', feature='PIRC-31', phase='pre_accept',
            target_refs={'app': 'a' * 40}, attempt_id='attempt-1', checklist_ref=copy.deepcopy(reports.REF),
            required_checks=[dict(id='C1', scope_ids=['REQ-001', 'SOL-001'])], report=report, related_reports=[],
            tests=dict(schema='test-results-v1', test_task='TEST-1', target_refs={'app': 'a' * 40}, attempt_id='attempt-1',
                checks=[dict(id='T1', required=True, outcome='PASS', scope_ids=['REQ-001', 'SOL-001'],
                             evidence_refs=[copy.deepcopy(reports.REF)], reason='Actual test fixture')]),
            result_tests=None, frozen={'app': dict(source_tree='b' * 40, target_before='c' * 40, result=None)}, acceptance=None)
        self.sources = {}

    def observed(self):
        frozen = self.request['frozen']['app']
        result = frozen['result']
        accepted = self.request['acceptance']
        return q.QualityObservations(q.request_digest(self.request), q.feature_digest(self.feature),
            source_refs=frozenset({(reports.REF['path'], reports.REF['sha256'])}),
            independent_reports=frozenset({rr.report_digest(self.request['report'])}),
            current_review_digest=rr.report_digest(self.request['report']),
            integration={'app': dict(repository_ref='app', source='a' * 40, source_tree='b' * 40,
                target_before='c' * 40, target_in_source=True, observed_target=result or 'c' * 40,
                result=result, result_tree='b' * 40 if result else None, result_contains_source=bool(result))},
            remote_targets=frozenset({('app', result or 'c' * 40)}), required_repositories=frozenset({'app'}),
            checklist_binding=q.request_digest(dict(ref=self.request['checklist_ref'], required_checks=self.request['required_checks'])),
            acceptance_bindings=frozenset({decisions.decision.decision_digest(accepted['record'])}) if accepted else frozenset())

    def assess(self, **kwargs):
        return q.assess_quality(self.feature, self.request,
            **(dict(observed=self.observed(), decision_sources=self.sources) | kwargs))

    def acceptance(self, outcome='CONFIRMED'):
        raw = decisions.evidence()
        raw.update(decision_kind='acceptance', exact_scope=['feature:PIRC-31'], outcome=outcome)
        self.request['acceptance'] = dict(record=raw, current=decisions.current(raw))
        self.sources[raw['decision_id']] = decisions.verified(raw)

    def assert_denied(self, code=None, **kwargs):
        got = self.assess(**kwargs)
        self.assertFalse(got['allowed'], got)
        self.assertFalse(got['merge_authorized'])
        if code:
            self.assertIn(code, got['reason_codes'], got)
        return got

    def test_pre_accept_does_not_require_nonexistent_acceptance(self):
        before = copy.deepcopy(self.request)
        result = self.assess()
        self.assertTrue(result['allowed'], result)
        self.assertFalse(result['merge_authorized'])
        self.assertEqual(result['required_next_actions'], ['request-current-candidate-acceptance'])
        self.assertEqual(self.request, before)

    def test_unverified_or_mutated_host_scope_cannot_pass(self):
        self.assert_denied('QUALITY_SOURCES_UNVERIFIED', observed=None)
        self.assert_denied('QUALITY_SOURCES_UNVERIFIED', observed=self.observed().__dict__)
        retained = self.observed()
        self.request['tests']['checks'][0]['reason'] += ' changed'
        self.assert_denied('QUALITY_SOURCES_UNVERIFIED', observed=retained)

    def test_missing_source_and_independence_are_not_schema_success(self):
        self.assert_denied('SOURCE_EVIDENCE_UNVERIFIED', observed=replace(self.observed(), source_refs=frozenset()))
        self.assert_denied('INDEPENDENCE_UNVERIFIED', observed=replace(self.observed(), independent_reports=frozenset()))
        self.assert_denied('CHECKLIST_SCOPE_UNVERIFIED', observed=replace(self.observed(), checklist_binding=''))

    def test_legacy_report_cannot_promote_old_done(self):
        self.request['report'].pop('checks')
        # No report digest required from an invalid legacy source.
        observed = q.QualityObservations(q.request_digest(self.request), q.feature_digest(self.feature),
            source_refs=frozenset({(reports.REF['path'], reports.REF['sha256'])}), required_repositories=frozenset({'app'}),
            checklist_binding=q.request_digest(dict(ref=self.request['checklist_ref'], required_checks=self.request['required_checks'])))
        got = q.assess_quality(self.feature, self.request, observed=observed)
        self.assertFalse(got['allowed'])
        self.assertIn('LEGACY_EVIDENCE_INCOMPLETE', got['reason_codes'])

    def test_done_test_with_failure_is_not_quality_success(self):
        self.feature.records['TEST-1'] = dict(type='Test', state='DONE')
        for outcome in ('FAIL', 'UNKNOWN', 'NOT-RUN'):
            self.request['tests']['checks'][0]['outcome'] = outcome
            self.assert_denied('REQUIRED_TEST_NOT_PASSED')

    def test_missing_required_check_and_scope(self):
        self.request['required_checks'].append(dict(id='C2', scope_ids=['REQ-001']))
        self.assert_denied('MISSING_REQUIRED_CHECK')
        self.request['required_checks'] = [dict(id='C1', scope_ids=['REQ-001'])]
        self.request['report']['checks'][0]['scope_ids'] = ['REQ-001']
        self.assert_denied('MISSING_SCOPE')

    def test_missing_test_scope_and_invalid_reference(self):
        self.request['tests']['checks'][0]['scope_ids'] = ['REQ-001']
        self.assert_denied('MISSING_TEST_SCOPE')
        self.request['tests']['checks'][0]['evidence_refs'] = ['pretend-reference']
        self.assert_denied('INVALID_EVIDENCE_REF')

    def test_stale_review_or_test_never_reuses_whole_report(self):
        self.request['report']['target_refs']['app'] = 'd' * 40
        self.assert_denied('STALE_REVIEW')
        self.request['report']['target_refs']['app'] = 'a' * 40
        self.request['tests']['target_refs']['app'] = 'd' * 40
        self.assert_denied('STALE_TESTS')

    def test_open_blocker_is_not_hidden_by_pass_ratio(self):
        report = self.request['report']
        report['result'] = 'BLOCKED'
        report['findings'] = [reports.finding()]
        report['checks'][0]['finding_ids'] = ['F1']
        self.assert_denied('OPEN_BLOCKERS')

    def test_non_applicable_requires_exact_human_exclusion(self):
        self.request['report']['checks'].append(reports.check('C2', 'N/A'))
        self.request['report']['checks'][1]['scope_ids'] = ['REQ-001']
        self.assert_denied('SCOPE_EXCEPTION_UNVERIFIED')
        observed = replace(self.observed(), excluded_scopes=frozenset({'REQ-001'}))
        self.assertTrue(self.assess(observed=observed)['allowed'])

    def test_pre_merge_requires_confirmed_current_human_decision(self):
        self.request['phase'] = 'pre_merge'
        self.assert_denied('ACCEPTANCE_REQUIRED')
        for outcome in ('REJECTED', 'REWORK'):
            self.acceptance(outcome)
            self.assert_denied('ACCEPTANCE_NOT_CONFIRMED')
        self.acceptance()
        self.assertTrue(self.assess()['allowed'])
        self.sources = {}
        self.assert_denied('HUMAN_SOURCE_UNVERIFIED')

    def test_approval_must_bind_exact_candidate_and_current_body(self):
        self.request['phase'] = 'pre_merge'
        self.acceptance()
        self.assert_denied('ACCEPTANCE_CANDIDATE_UNVERIFIED',
                           observed=replace(self.observed(), acceptance_bindings=frozenset()))
        self.request['acceptance']['current']['body'] = 'Rewritten acceptance scope.'
        self.assert_denied('DECISION_STALE')

    def test_post_merge_needs_actual_correspondence_and_result_tests(self):
        self.request['phase'] = 'post_merge'
        self.request['frozen']['app']['result'] = 'd' * 40
        self.feature.repositories['app']['actual_head'] = 'd' * 40
        self.acceptance()
        self.assert_denied('TEST_DETAILS_REQUIRED')
        self.request['result_tests'] = copy.deepcopy(self.request['tests'])
        self.request['result_tests']['target_refs']['app'] = 'd' * 40
        self.assertTrue(self.assess()['allowed'])
        self.request['result_tests']['checks'][0]['outcome'] = 'FAIL'
        self.assert_denied('REQUIRED_TEST_NOT_PASSED')
        observed = self.observed()
        observed.integration['app']['result_tree'] = 'e' * 40
        self.assert_denied('MERGE_CORRESPONDENCE_UNVERIFIED', observed=observed)

    def test_moving_candidate_or_remote_requires_recheck(self):
        self.assert_denied('INTEGRATION_TARGET_UNVERIFIED', observed=replace(self.observed(), remote_targets=frozenset()))
        self.feature.repositories['app']['actual_head'] = 'e' * 40
        self.assert_denied('CANDIDATE_MOVED')

    def test_reuse_needs_current_attempt_and_independent_per_check_basis(self):
        old = copy.deepcopy(self.request['report'])
        old.update(report_ref='old-report', attempt_id='old-attempt', target_refs={'app': 'e' * 40})
        self.request['related_reports'] = [old]
        self.request['report']['checks'][0]['reuse'] = dict(
            prior_check_ref=dict(feature='PIRC-31', report_ref='old-report', attempt_id='old-attempt', check_id='C1'),
            diff_refs=[copy.deepcopy(reports.REF)], dependency_refs=[copy.deepcopy(reports.REF)], reviewer_basis='Verified unchanged dependencies')
        self.assert_denied('REUSE_UNVERIFIED')
        observation = replace(self.observed(), reused_checks=frozenset({(rr.report_digest(self.request['report']), 'C1')}))
        self.assertTrue(self.assess(observed=observation)['allowed'])
        old['attempt_id'] = self.request['attempt_id']
        self.assert_denied('NEW_CANDIDATE_REQUIRES_NEW_ATTEMPT')

    def test_resource_limit_and_unknown_phase_fail_closed(self):
        with patch.object(q, 'MAX_ITEMS', 2):
            self.assert_denied('RESOURCE_LIMIT')
        self.request['phase'] = 'untrusted-body'
        got = self.assert_denied('INVALID_QUALITY_REQUEST')
        self.assertIsNone(got['event']['stage'])

    def test_actual_task_state_and_current_chain_are_required(self):
        self.assert_denied('REVIEW_CHAIN_UNVERIFIED', observed=replace(self.observed(), current_review_digest=''))
        self.feature.records['REVIEW-1']['state'] = 'WIP'
        self.assert_denied('REVIEW_NOT_COMPLETE')
        self.feature.records['REVIEW-1']['state'] = 'DONE'
        self.feature.records['TEST-1']['state'] = 'WIP'
        self.assert_denied('TEST_NOT_COMPLETE')

    def test_candidate_repository_scope_cannot_be_omitted(self):
        self.assert_denied('INCOMPLETE_REPOSITORY_SCOPE',
                           observed=replace(self.observed(), required_repositories=frozenset({'app', 'other'})))

    def test_author_declared_closure_is_not_independent_verification(self):
        report = self.request['report']
        report['result'] = 'BLOCKED'
        finding = reports.finding()
        finding.update(status='closed', resolution_ref=copy.deepcopy(reports.REF), verified_by='reviewer-2',
                       verified_ref=copy.deepcopy(reports.REF), verified_target_refs=copy.deepcopy(report['target_refs']))
        report['findings'] = [finding]
        report['checks'][0]['finding_ids'] = ['F1']
        got = self.assert_denied('CLOSURE_UNVERIFIED')
        self.assertTrue(got['open_blockers'])

    def test_untrusted_diagnostic_text_is_not_logged_as_code(self):
        report = self.request['report']
        report['result'] = 'BLOCKED'
        report['diagnostics'] = [dict(code='private-source-text', reason='More private text', blocking=True)]
        got = self.assert_denied('REVIEW_DIAGNOSTIC_BLOCKS')
        self.assertNotIn('private', str(got['event']))

    def test_cpu_and_serialized_byte_limits_fail_closed(self):
        observed = self.observed()
        for key, value in (('CPU_SECONDS', -1), ('MAX_BYTES', 10), ('MAX_LINKS', 1)):
            with patch.object(q, key, value):
                result = q.assess_quality(self.feature, self.request, observed=observed)
                self.assertFalse(result['allowed'])
                self.assertIn('RESOURCE_LIMIT', result['reason_codes'])

    def test_retained_observation_does_not_cover_mutated_task_facts(self):
        observed = self.observed()
        self.feature.records['TEST-1']['state'] = 'WIP'
        got = q.assess_quality(self.feature, self.request, observed=observed)
        self.assertIn('QUALITY_SOURCES_UNVERIFIED', got['reason_codes'])


if __name__ == '__main__':
    unittest.main()
