#!/usr/bin/env python3
"""Real policy/selector composition with synthetic host provenance, not acceptance."""
import copy
import json
from dataclasses import replace
import unittest
from unittest.mock import patch
import task_next as n
import test_quality_policy as fixtures
import test_review_report as reports


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.policy = fixtures.PolicyTests()
        self.policy.setUp()
        self.plan = 'selection-sha256:fixture'

    def inputs(self, phase='pre_accept', operation=None):
        p = self.policy
        p.request['phase'] = phase
        if phase != 'pre_accept':
            p.acceptance()
        if phase == 'post_merge':
            result = 'd' * 40
            p.request['frozen']['app']['result'] = result
            p.feature.repositories['app']['actual_head'] = result
            p.request['result_tests'] = copy.deepcopy(p.request['tests'])
            p.request['result_tests']['target_refs'] = {'app': result}
        target = 'ACCEPT-1' if phase == 'pre_accept' else 'GATE-1' if phase == 'post_merge' else 'INTEGRATE'
        operation = operation or ('accept' if phase == 'pre_accept' else 'gate' if phase == 'post_merge' else 'merge')
        tasks = (
            n.Task('TEST-1', 'DONE', (), 'Test', {'Executed': '1', 'Passed': '1', 'Failed': '0', 'Skipped': '0', 'Unknown': '0'}),
            n.Task('REVIEW-1', 'DONE', ('TEST-1',), 'Review', {'Blocking findings': '0'}),
            n.Task('ACCEPT-1', 'PENDING' if phase == 'pre_accept' else 'DONE', ('REVIEW-1',), 'Acceptance',
                   {} if phase == 'pre_accept' else {'Decision': 'CONFIRMED', 'Target SHA': 'a' * 40}),
            n.Task('INTEGRATE', 'DONE' if phase == 'post_merge' else 'PENDING', ('ACCEPT-1',)),
            n.Task('GATE-1', 'PENDING', ('INTEGRATE',), 'Gate', {'To phase': 'DONE'}))
        p.feature.records.clear()
        p.feature.records.update({t.id: dict(type=t.kind, state=t.state, dependencies=list(t.dependencies)) for t in tasks})
        p.feature.type_contracts.update({t.id: dict(t.contract) for t in tasks})
        current = 'REVIEW-1' if phase == 'pre_accept' else 'INTEGRATE' if phase == 'post_merge' else 'ACCEPT-1'
        ctx = n.ValidatedContext(self.plan, current, 'GATE-1', tasks)
        auth = n.Authorization(self.plan, {target: n.Grant(operation,
            frozenset({'execute', 'request-acceptance', 'merge', 'publish'}), 'host:explicit-operation')})
        inputs = n.QualityInputs(self.plan, target, p.feature, p.request, p.observed(), decision_sources=p.sources)
        gate = n.GateEvidence('ready', ('host:verified-quality-readback',), target_sha='a' * 40,
            acceptance_task=None if phase == 'pre_accept' else 'ACCEPT-1', quality_inputs=inputs)
        evidence = n.ObservedGateEvidence(self.plan, {target: gate})
        self.ctx, self.auth, self.evidence, self.target = ctx, auth, evidence, target
        return ctx, auth, evidence

    def select(self):
        return n.select_next(self.ctx, self.auth, self.evidence)

    def refresh(self):
        gate = self.evidence.tasks[self.target]
        self.evidence.tasks[self.target] = replace(gate, quality_inputs=replace(gate.quality_inputs,
            observations=self.policy.observed()))

    def test_pre_accept_requests_without_existing_acceptance(self):
        args = self.inputs()
        result = n.select_next(*args)
        self.assertEqual(('assign', 'ACCEPT-1'), (result.action, result.task_id))
        self.assertIsNone(self.policy.request['acceptance'])
        self.assertEqual(self.policy.feature.records['ACCEPT-1']['state'], 'PENDING')

    def test_pre_merge_and_publish_recompute_real_policy(self):
        for operation in ('merge', 'publish'):
            with self.subTest(operation=operation):
                self.setUp()
                self.inputs('pre_merge', operation)
                self.assertEqual('assign', self.select().action)
                self.policy.request['tests']['checks'][0]['outcome'] = 'FAIL'
                self.refresh()
                result = self.select()
                self.assertEqual('wait-external', result.action)
                self.assertEqual('REQUIRED_TEST_NOT_PASSED', result.reason_code)

    def test_post_merge_normal_result_does_not_demand_reacceptance(self):
        self.inputs('post_merge')
        self.assertEqual('assign', self.select().action)
        gate = self.evidence.tasks[self.target]
        observed = gate.quality_inputs.observations
        broken = copy.deepcopy(observed.integration)
        broken['app']['result_tree'] = 'e' * 40
        self.evidence.tasks[self.target] = replace(gate, quality_inputs=replace(gate.quality_inputs,
            observations=replace(observed, integration=broken)))
        self.assertNotEqual('assign', self.select().action)

    def test_ready_summary_and_uploaded_dict_cannot_bypass_policy(self):
        self.inputs()
        gate = self.evidence.tasks[self.target]
        for value, code in ((None, 'LEGACY_EVIDENCE_INCOMPLETE'), ({'allowed': True}, 'QUALITY_SOURCES_UNVERIFIED')):
            self.evidence.tasks[self.target] = replace(gate, quality_inputs=value)
            self.assertEqual(code, self.select().reason_code)

    def test_stale_selection_or_different_task_binding_refuses(self):
        self.inputs()
        gate = self.evidence.tasks[self.target]
        for kwargs in ({'source_ref': 'old'}, {'task_id': 'INTEGRATE'}):
            self.evidence.tasks[self.target] = replace(gate, quality_inputs=replace(gate.quality_inputs, **kwargs))
            self.assertEqual('STALE_QUALITY_INPUT', self.select().reason_code)

    def test_wrong_phase_cannot_substitute_pre_accept_for_merge(self):
        self.inputs('pre_merge')
        self.policy.request['phase'] = 'pre_accept'
        self.refresh()
        self.assertEqual('QUALITY_PHASE_MISMATCH', self.select().reason_code)

    def test_old_request_cannot_reuse_observations(self):
        self.inputs()
        self.policy.request['attempt_id'] = 'changed'
        self.assertEqual('QUALITY_SOURCES_UNVERIFIED', self.select().reason_code)

    def test_other_plan_cannot_supply_valid_quality(self):
        self.inputs()
        self.policy.feature.records['TEST-1']['dependencies'] = ['REVIEW-1']
        self.refresh()
        self.assertEqual('QUALITY_PLAN_MISMATCH', self.select().reason_code)

    def test_open_blockers_and_missing_scope_override_ready(self):
        self.inputs()
        finding = reports.finding()
        self.policy.request['report']['findings'] = [finding]
        self.policy.request['report']['checks'][0]['finding_ids'] = [finding['id']]
        self.refresh()
        self.assertNotEqual('assign', self.select().action)
        self.setUp()
        self.inputs()
        self.policy.request['required_checks'][0]['scope_ids'] = ['REQ-001']
        self.refresh()
        self.assertNotEqual('assign', self.select().action)

    def test_no_operation_permission_is_created_by_quality(self):
        self.inputs('pre_merge')
        self.auth.grants[self.target] = replace(self.auth.grants[self.target], capabilities=frozenset({'execute'}))
        result = self.select()
        self.assertEqual(('merge',), result.required_authority)
        self.assertEqual('wait-human', result.action)

    def test_cli_cannot_deserialize_a_quality_approval(self):
        import selection_context
        self.inputs()
        raw = json.dumps({'source_ref': self.plan, 'evidence': {self.target: {
            'verdict': 'ready', 'evidence_refs': ['host:claim'], 'quality_inputs': {'allowed': True}}}}).encode()
        with self.assertRaises(selection_context.SelectionError):
            selection_context.parse_host_input(raw, self.ctx, 'host:instruction')

    def test_successful_composition_does_no_io_or_mutation(self):
        import builtins
        import socket
        import subprocess
        self.inputs('pre_merge')
        before = copy.deepcopy(self.policy.request)
        with patch.object(builtins, 'open', side_effect=AssertionError('file IO')), \
             patch.object(socket, 'socket', side_effect=AssertionError('network')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('process')):
            self.assertEqual('assign', self.select().action)
        self.assertEqual(before, self.policy.request)
        self.assertEqual(self.policy.feature.records['INTEGRATE']['state'], 'PENDING')

    def test_positive_policy_for_different_contract_refuses(self):
        self.inputs()
        self.policy.feature.type_contracts['TEST-1']['Unknown'] = '1'
        self.refresh()
        self.assertEqual('QUALITY_PLAN_MISMATCH', self.select().reason_code)

    def test_rejected_acceptance_keeps_rework_available(self):
        self.inputs('pre_merge')
        self.policy.acceptance('REJECTED')
        self.refresh()
        self.assertNotEqual('assign', self.select().action)
        task = n.Task('FIX', 'PENDING', ('ACCEPT-1',), 'Rework')
        self.ctx = replace(self.ctx, tasks=self.ctx.tasks[:-1] + (task,
            replace(self.ctx.tasks[-1], dependencies=('INTEGRATE', 'FIX'))))
        self.auth.grants['FIX'] = n.Grant('rework', frozenset({'execute'}), 'host:rework')
        self.evidence.tasks['FIX'] = n.GateEvidence('ready', ('host:rework-facts',))
        self.assertEqual('FIX', self.select().task_id)


if __name__ == '__main__':
    unittest.main()
