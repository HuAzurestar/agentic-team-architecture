#!/usr/bin/env python3
"""Host contract fixtures are synthetic, not live-provider authentication."""
import copy
from dataclasses import replace
import sys
import unittest
from unittest.mock import Mock, patch
sys.dont_write_bytecode = True
import decision_host as host
from test_decision_evidence import evidence, current
from decision_evidence import decision_digest


class HostTests(unittest.TestCase):
    def setUp(self):
        self.raw = evidence()
        self.material = current(self.raw)
        self.reply = host.HumanReply(self.raw['human_source_ref'], self.raw['actor'], 'human',
            self.raw['received_at'], self.raw['original_reply'], 'conversation', 'message-version-1', 'host:readback-1')
        self.grant = host.HumanGrant(self.raw['actor'], self.raw['feature'], self.raw['decision_kind'],
            self.raw['target_ref']['source_key'], tuple(self.raw['exact_scope']), ('CONFIRMED', 'REJECTED'))
        self.read_current = Mock(side_effect=lambda: copy.deepcopy(self.material))
        self.read_reply = Mock(return_value=self.reply)
        self.interpret = Mock(return_value=host.HumanInterpretation(decision_digest(self.raw), 'host:interpretation-1'))

    def inspect(self, **changes):
        return host.inspect_decision(self.raw, **(dict(read_current=self.read_current,
            read_reply=self.read_reply, interpret=self.interpret, grant=self.grant) | changes))

    def test_exact_transport_contract_observations_are_checked_twice(self):
        result = self.inspect()
        self.assertTrue(result['applicable'], result)
        self.assertEqual(self.read_current.call_count, 2)
        self.assertEqual(self.read_reply.call_count, 2)
        self.assertEqual(result['effect'], 'NOT_APPLIED')
        self.assertFalse(result['merge_authorized'])

    def test_missing_host_adapter_does_not_fall_back_to_file_claim(self):
        for field in ('read_reply', 'read_current', 'interpret'):
            with self.subTest(field=field):
                self.assertIn('HUMAN_SOURCE_UNAVAILABLE', self.inspect(**{field: None})['reason_codes'])

    def test_uploaded_grant_dictionary_cannot_authorize(self):
        result = self.inspect(grant=self.grant.__dict__)
        self.assertIn('HUMAN_AUTHORITY_UNVERIFIED', result['reason_codes'])
        self.read_reply.assert_not_called()

    def test_wrong_actor_kind_cannot_authorize(self):
        for kind in ('agent', 'bot', 'unknown'):
            self.read_reply.return_value = replace(self.reply, actor_kind=kind)
            self.assertFalse(self.inspect()['applicable'])

    def test_exact_reply_actor_source_time_and_body_required(self):
        for field in ('actor', 'source_ref', 'received_at', 'text'):
            self.read_reply.return_value = replace(self.reply, **{field: 'different'})
            self.assertIn('HUMAN_SOURCE_MISMATCH', self.inspect()['reason_codes'])

    def test_actual_reply_edited_between_reads_refuses(self):
        self.read_reply.side_effect = [self.reply, replace(self.reply, source_version='message-version-2')]
        self.assertIn('HUMAN_SOURCE_CHANGED', self.inspect()['reason_codes'])

    def test_current_target_changed_during_host_readback_refuses(self):
        changed = dict(self.material, body='Changed')
        self.read_current.side_effect = [self.material, changed]
        self.assertIn('DECISION_SOURCE_CHANGED', self.inspect()['reason_codes'])

    def test_stale_decision_still_returns_bounded_diff(self):
        self.material['body'] = 'Changed target'
        result = self.inspect()
        self.assertIn('DECISION_STALE', result['reason_codes'])
        self.assertTrue(result['diff'])

    def test_authority_does_not_expand_to_other_scope_kind_or_feature(self):
        for field, value in (('feature', 'OTHER'), ('decision_kind', 'acceptance'),
                             ('exact_scope', ('REQ-102', 'REQ-103')), ('source_key', 'other')):
            self.assertIn('HUMAN_AUTHORITY_UNVERIFIED', self.inspect(grant=replace(self.grant, **{field: value}))['reason_codes'])

    def test_outcome_must_be_authorized(self):
        self.assertFalse(self.inspect(grant=replace(self.grant, outcomes=('REJECTED',)))['applicable'])

    def test_ambiguous_or_wrong_interpretation_cannot_authorize(self):
        for mapped in (None, {'decision_digest': decision_digest(self.raw)},
                       host.HumanInterpretation('f' * 64, 'host:basis'),
                       host.HumanInterpretation(decision_digest(self.raw), '')):
            self.interpret.return_value = mapped
            self.assertIn('HUMAN_INTERPRETATION_UNVERIFIED', self.inspect()['reason_codes'])

    def test_provider_exception_is_unknown_and_does_not_leak(self):
        self.read_reply.side_effect = RuntimeError('TOKEN secret actual reply')
        result = self.inspect()
        self.assertIn('SOURCE_UNAVAILABLE', result['reason_codes'])
        self.assertNotIn('secret', str(result))
        self.assertEqual(self.read_reply.call_count, 1)

    def test_json_reply_does_not_become_authenticated(self):
        self.read_reply.return_value = self.reply.__dict__
        self.assertFalse(self.inspect()['applicable'])

    def test_interpreter_cannot_mutate_original_record(self):
        before = copy.deepcopy(self.raw)
        def mutate(reply, record):
            record['outcome'] = 'REJECTED'
            return host.HumanInterpretation(decision_digest(record), 'host:basis')
        result = self.inspect(interpret=mutate)
        self.assertFalse(result['applicable'])
        self.assertEqual(self.raw, before)

    def test_event_has_no_private_reply_or_actor(self):
        result = self.inspect()
        self.assertNotIn(self.raw['original_reply'], str(result['event']))
        self.assertNotIn(self.raw['actor'], str(result['event']))

    def test_cpu_budget_is_fail_closed(self):
        with patch.object(host, 'CPU_SECONDS', -1):
            self.assertIn('RESOURCE_LIMIT', self.inspect()['reason_codes'])

    def test_size_budget_is_checked_before_human_transport(self):
        with patch.object(host, 'MAX_BYTES', 1):
            self.assertIn('RESOURCE_LIMIT', self.inspect()['reason_codes'])
        self.read_reply.assert_not_called()

    def test_real_git_reader_connects_to_host_gateway_without_writes(self):
        from test_decision_source import GitDecisionTests
        case = GitDecisionTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        self.raw = case.record(case.read())
        reply = host.HumanReply(self.raw['human_source_ref'], self.raw['actor'], 'human',
            self.raw['received_at'], self.raw['original_reply'], 'conversation', 'v1', 'synthetic:readback')
        grant = host.HumanGrant(self.raw['actor'], self.raw['feature'], 'point',
            self.raw['target_ref']['source_key'], tuple(self.raw['exact_scope']), ('CONFIRMED',))
        interpretation = host.HumanInterpretation(decision_digest(self.raw), 'synthetic:interpretation')
        before = case.git('status', '--porcelain'), case.git('rev-parse', 'HEAD'), case.path.read_bytes()
        result = self.inspect(read_current=case.read, read_reply=lambda ref: reply,
                              interpret=lambda message, record: interpretation, grant=grant)
        self.assertTrue(result['applicable'], result)
        self.assertFalse(result['merge_authorized'])
        self.assertEqual(before, (case.git('status', '--porcelain'), case.git('rev-parse', 'HEAD'), case.path.read_bytes()))

    def test_negative_acceptance_can_be_recordable_without_merge_authority(self):
        self.raw['decision_kind'], self.raw['outcome'] = 'acceptance', 'REWORK'
        self.material = current(self.raw)
        self.grant = replace(self.grant, decision_kind='acceptance', outcomes=('REWORK',))
        self.interpret.return_value = host.HumanInterpretation(decision_digest(self.raw), 'synthetic:negative')
        result = self.inspect()
        self.assertTrue(result['applicable'], result)
        self.assertFalse(result['merge_authorized'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
