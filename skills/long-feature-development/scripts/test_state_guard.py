#!/usr/bin/env python3
"""Actual state writes; synthetic human transports do not prove platform identity."""
import copy
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import task_context as tc
import task_state as state
import state_guard as guard
import decision_host as human
import decision_evidence as decision
import test_task_context as fixture
import test_decision_evidence as decisions
import test_quality_policy as policies
import task_next as selection


class WriterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = fixture.TaskContextTests().make_feature(Path(temp.name))
        self.task = 'ACCEPT-01'
        self.body = '# Acceptance\n\nTarget version: `' + 'a' * 40 + '`\n'
        for title in ('What changed', 'How to check', 'Evidence', 'Out of scope', 'Known limitations', 'Decision options'):
            self.body += '\n## ' + title + '\n\nSynthetic fixture only.\n'
        (self.root / 'gists/brief.md').write_text(self.body, encoding='utf-8')

    def prepare(self, outcome='REJECTED', source='RECORDING', target='DONE'):
        tasks = fixture.TASKS.replace('DEV-02', self.task).replace('| Development |', '| Acceptance |').replace('`WIP`', '`' + source + '`')
        (self.root / 'TASKS.md').write_text(tc.synchronized_topology(tasks), encoding='utf-8')
        (self.root / 'tasks/DEV-02.md').unlink()
        detail = fixture.DETAILS['DEV-02'].replace('DEV-02', self.task).replace('gists/parser.md', 'gists/brief.md')
        if target == 'DONE':
            detail = detail.replace('| 4444444 | - |', '| 4444444 | 4444444 |').replace('| 3333333 | - |', '| 3333333 | 3333333 |')
        detail += '\n## Type contract\n\n| Field | Value |\n| --- | --- |\n'
        for k, v in {'Target SHA': 'a' * 40, 'Acceptance scope': 'Current feature', 'Decision': outcome,
                     'Decided by': 'person-1', 'Acceptance brief': 'gists/brief.md'}.items():
            detail += '| ' + k + ' | ' + v + ' |\n'
        (self.root / ('tasks/' + self.task + '.md')).write_text(detail, encoding='utf-8')
        gate = (self.root / 'tasks/GATE-ACCEPT.md')
        gate.write_text(gate.read_text(encoding='utf-8').replace('DEV-02', self.task), encoding='utf-8')
        self.raw = decisions.evidence()
        self.raw.update(feature=self.root.name, decision_kind='acceptance', exact_scope=['feature:' + self.root.name],
            outcome=outcome, approved_body=self.body)
        self.args = state.parse_args([str(self.root), self.task, '--to', target, '--completed-at', '2026-10-03T03:00:00Z'])
        self.calls = 0

    def reader(self, request):
        self.calls += 1
        raw = copy.deepcopy(self.raw)
        reply = human.HumanReply(raw['human_source_ref'], raw['actor'], 'human', raw['received_at'],
            raw['original_reply'], 'conversation', 'version-1', 'host:fixture')
        grant = human.HumanGrant(raw['actor'], raw['feature'], 'acceptance', raw['target_ref']['source_key'],
            tuple(raw['exact_scope']), ('CONFIRMED', 'REJECTED', 'REWORK'))
        inputs = guard.HumanDecisionInputs(raw, lambda: decisions.current(raw), lambda ref: reply,
            lambda reply, record: human.HumanInterpretation(decision.decision_digest(record), 'host:interpretation'), grant)
        return guard.TransitionEvidence(request.digest, human_decision=inputs)

    def test_human_name_without_readback_cannot_complete(self):
        self.prepare()
        before = (self.root / 'TASKS.md').read_bytes()
        with self.assertRaisesRegex(tc.ContextError, 'STATE_EVIDENCE_REQUIRED'):
            state.update(self.root, self.args)
        self.assertEqual(before, (self.root / 'TASKS.md').read_bytes())

    def test_real_rejected_and_rework_decisions_can_complete(self):
        for outcome in ('REJECTED', 'REWORK', 'CONFIRMED'):
            with self.subTest(outcome=outcome):
                # Each iteration owns a fresh task fixture, never rewrites an old decision.
                case = WriterTests()
                case.setUp()
                self.addCleanup(case.doCleanups)
                case.prepare(outcome)
                state.update(case.root, case.args, evidence_reader=case.reader)
                self.assertEqual(tc.task_records(tc.read_utf8(case.root / 'TASKS.md'))[case.task]['state'], 'DONE')
                self.assertEqual(case.calls, 2)

    def test_recording_a_rejection_needs_provenance(self):
        self.prepare(source='WIP', target='RECORDING')
        with self.assertRaisesRegex(tc.ContextError, 'STATE_EVIDENCE_REQUIRED'):
            state.update(self.root, self.args)
        state.update(self.root, self.args, evidence_reader=self.reader)
        self.assertEqual(tc.task_records(tc.read_utf8(self.root / 'TASKS.md'))[self.task]['state'], 'RECORDING')

    def test_old_transition_binding_or_dict_claim_refuses(self):
        self.prepare()
        for reader in (lambda r: {'allowed': True}, lambda r: replace(self.reader(r), request_digest='old')):
            with self.assertRaisesRegex(tc.ContextError, 'STATE_EVIDENCE_BINDING_MISMATCH'):
                state.update(self.root, self.args, evidence_reader=reader)

    def test_callback_failure_is_redacted(self):
        self.prepare()
        def reader(request):
            raise RuntimeError('secret provider credential')
        with self.assertRaisesRegex(tc.ContextError, '^STATE_SOURCE_UNAVAILABLE$'):
            state.update(self.root, self.args, evidence_reader=reader)

    def test_brief_actor_outcome_and_target_cannot_be_swapped(self):
        for key, value in (('approved_body', 'different'), ('actor', 'someone-else'), ('outcome', 'CONFIRMED')):
            case = WriterTests()
            case.setUp()
            self.addCleanup(case.doCleanups)
            case.prepare()
            case.raw[key] = value
            with self.assertRaises(tc.ContextError):
                state.update(case.root, case.args, evidence_reader=case.reader)
        self.prepare()
        self.raw['approved_body'] = self.body.replace('a' * 40, 'b' * 40)
        (self.root / 'gists/brief.md').write_text(self.raw['approved_body'], encoding='utf-8')
        with self.assertRaisesRegex(tc.ContextError, 'ACCEPTANCE_TARGET_MISMATCH'):
            state.update(self.root, self.args, evidence_reader=self.reader)

    def test_source_changed_during_host_readback_is_preserved(self):
        self.prepare()
        original = (self.root / 'TASKS.md').read_bytes()
        def reader(request):
            evidence = self.reader(request)
            (self.root / 'gists/parser.md').write_text('external edit', encoding='utf-8')
            return evidence
        with self.assertRaisesRegex(tc.ContextError, 'STATE_SOURCE_CHANGED'):
            state.update(self.root, self.args, evidence_reader=reader)
        self.assertEqual(original, (self.root / 'TASKS.md').read_bytes())
        self.assertEqual((self.root / 'gists/parser.md').read_text(), 'external edit')

    def test_second_readback_failure_keeps_original_and_cleans_temp(self):
        self.prepare()
        original = (self.root / 'TASKS.md').read_bytes()
        def reader(request):
            evidence = self.reader(request)
            return evidence if self.calls == 1 else replace(evidence, human_decision=None)
        with self.assertRaisesRegex(tc.ContextError, 'HUMAN_SOURCE_UNVERIFIED'):
            state.update(self.root, self.args, evidence_reader=reader)
        self.assertEqual(original, (self.root / 'TASKS.md').read_bytes())
        self.assertEqual(list(self.root.glob('TASKS.*.tmp')), [])

    def test_concurrent_tasks_edit_is_never_overwritten(self):
        self.prepare()
        replacement = (self.root / 'TASKS.md').read_bytes() + b'\nExternal coordinator edit.\n'
        def reader(request):
            evidence = self.reader(request)
            if self.calls == 2:
                (self.root / 'TASKS.md').write_bytes(replacement)
            return evidence
        with self.assertRaisesRegex(tc.ContextError, 'STATE_SOURCE_CHANGED'):
            state.update(self.root, self.args, evidence_reader=reader)
        self.assertEqual(replacement, (self.root / 'TASKS.md').read_bytes())
        self.assertEqual(list(self.root.glob('TASKS.*.tmp')), [])

    def test_agent_reply_cannot_be_written_as_human_decision(self):
        self.prepare()
        def reader(request):
            evidence = self.reader(request)
            inputs = evidence.human_decision
            read_reply = inputs.read_reply
            return replace(evidence, human_decision=replace(inputs,
                read_reply=lambda ref: replace(read_reply(ref), actor_kind='agent')))
        with self.assertRaisesRegex(tc.ContextError, 'HUMAN_SOURCE_MISMATCH'):
            state.update(self.root, self.args, evidence_reader=reader)

    def test_dry_run_still_requires_evidence_but_never_writes(self):
        self.prepare()
        self.args.dry_run = True
        original = (self.root / 'TASKS.md').read_bytes()
        with self.assertRaises(tc.ContextError):
            state.update(self.root, self.args)
        state.update(self.root, self.args, evidence_reader=self.reader)
        self.assertEqual(self.calls, 1)
        self.assertEqual(original, (self.root / 'TASKS.md').read_bytes())


class QualityGuardTests(unittest.TestCase):
    def setUp(self):
        self.policy = policies.PolicyTests()
        self.policy.setUp()
        self.policy.feature.records['ACCEPT-1'] = dict(type='Acceptance', state='PENDING', dependencies=[])
        self.policy.feature.documents.root = Path('PIRC-31').resolve()
        self.request = guard.TransitionRequest(str(self.policy.feature.documents.root), 'ACCEPT-1', 'PENDING', 'WIP',
            'a' * 64, 'b' * 64, tuple((k, r.content_digest) for k, r in self.policy.feature.documents.records.items()))
        self.records = self.policy.feature.records

    def reader(self, request):
        return guard.TransitionEvidence(request.digest, quality_inputs=selection.QualityInputs(request.digest,
            request.task_id, self.policy.feature, self.policy.request, self.policy.observed(), decision_sources=self.policy.sources))

    def test_pre_accept_and_failed_test_policy(self):
        guard.verify(self.request, self.reader, self.records, {})
        self.policy.request['tests']['checks'][0]['outcome'] = 'FAIL'
        with self.assertRaisesRegex(tc.ContextError, 'REQUIRED_TEST_NOT_PASSED'):
            guard.verify(self.request, self.reader, self.records, {})

    def test_final_gate_requires_post_merge_not_pre_accept(self):
        self.records['GATE-1'] = dict(type='Gate', state='RECORDING', dependencies=[])
        request = replace(self.request, task_id='GATE-1', target='DONE')
        with self.assertRaisesRegex(tc.ContextError, 'STATE_QUALITY_PHASE_MISMATCH'):
            guard.verify(request, self.reader, self.records, {'To phase': 'DONE'})

    def test_changed_intent_refuses_even_valid_policy(self):
        request = replace(self.request, read_set=(('REQUIREMENT.md', 'f' * 64),))
        with self.assertRaisesRegex(tc.ContextError, 'STATE_INTENT_CHANGED'):
            guard.verify(request, self.reader, self.records, {})

    def test_actual_post_merge_policy_is_consumed(self):
        self.records['GATE-1'] = dict(type='Gate', state='RECORDING', dependencies=[])
        self.policy.request['phase'] = 'post_merge'
        self.policy.acceptance()
        self.policy.request['frozen']['app']['result'] = 'd' * 40
        self.policy.feature.repositories['app']['actual_head'] = 'd' * 40
        self.policy.request['result_tests'] = copy.deepcopy(self.policy.request['tests'])
        self.policy.request['result_tests']['target_refs'] = {'app': 'd' * 40}
        request = replace(self.request, task_id='GATE-1', target='DONE')
        guard.verify(request, self.reader, self.records, {'To phase': 'DONE'})
        self.policy.request['result_tests']['checks'][0]['outcome'] = 'UNKNOWN'
        with self.assertRaisesRegex(tc.ContextError, 'REQUIRED_TEST_NOT_PASSED'):
            guard.verify(request, self.reader, self.records, {'To phase': 'DONE'})

    def test_review_done_and_waiting_recording_do_not_require_zero_blockers(self):
        self.assertEqual(guard.requirements('REVIEW-1', 'DONE', {}), (None, False))
        self.assertEqual(guard.requirements('ACCEPT-1', 'RECORDING', {'Decision': 'WAITING'}), (None, False))
        guard.verify(replace(self.request, task_id='REVIEW-1', target='DONE'), None, {}, {})


if __name__ == '__main__':
    unittest.main()
