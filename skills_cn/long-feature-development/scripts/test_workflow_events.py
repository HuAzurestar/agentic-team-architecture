#!/usr/bin/env python3
"""Event ledger integrity, explicit external delivery and reply boundary tests."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import runtime_state as state
import workflow_events as events
from test_runtime_state import notify_profile


def request(event_id='event/../1', revision='v1'):
    return {'event id': event_id, 'event type': 'design.confirmation.requested', 'phase': 'design',
            'purpose': 'decision', 'priority': 'high', 'feature': 'EXTERNAL-1', 'task': 'REQ-1',
            'object revision': revision, 'occurred at': '2026-10-21T00:00:00Z', 'actor': 'orchestrator',
            'correlation id': 'question-1', 'decision required': True, 'decider': 'human-1',
            'requested scope': 'REQ v1', 'allowed consequences': 'record answer for policy evaluation',
            'payload': {'question': 'Choose A or B', 'evidence': []}}


def attempt():
    return {'event id': 'event/../1', 'attempt id': 'attempt-1', 'occurred at': 'time-1',
            'adapter tool reference': 'fixture-delivery', 'route': 'review'}


def reply():
    return {'event id': 'event/../1', 'reply id': 'reply-1', 'correlation id': 'question-1',
            'object revision': 'v1', 'declared decider': 'human-1', 'original wording': 'Choose A',
            'source': 'fixture receiver message 1', 'occurred at': 'time-2'}


class WorkflowEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'state'
        self.profile = notify_profile(self.root)
        state.configure(self.config, 'A', 'notification', self.profile)

    def op(self, command, data=None, **kwargs):
        return events.operate(self.config, 'A', command, data, **kwargs)

    def inspect(self):
        return self.op('inspect')['events']['event/../1']

    def test_event_replay_is_idempotent_and_conflict_does_not_overwrite(self):
        self.assertTrue(self.op('record', request())['changed'])
        self.assertFalse(self.op('record', request())['changed'])
        changed = request()
        changed['payload']['question'] = 'Different request'
        with self.assertRaises(state.StateError):
            self.op('record', changed)
        self.assertEqual(self.inspect()['event'], request())
        self.assertEqual(list((self.root / 'delivery').glob('*.json')), [self.root / 'delivery/workflow-events.json'])
        self.assertFalse((self.root / '1').exists())

    def test_json_boolean_and_integer_conflict_across_all_idempotent_records(self):
        event = request()
        event['payload'] = {'value': True}
        self.op('record', event)
        with self.assertRaises(state.StateError):
            self.op('record', dict(event, payload={'value': 1}))
        delivery = dict(attempt(), metadata=True)
        self.op('attempt', delivery)
        with self.assertRaises(state.StateError):
            self.op('attempt', dict(delivery, metadata=1))
        ack = {'event id': 'event/../1', 'attempt id': 'attempt-1', 'occurred at': 'time-2', 'status': 'accepted', 'receipt': True}
        self.op('ack', ack)
        with self.assertRaises(state.StateError):
            self.op('ack', dict(ack, receipt=1))
        answer = dict(reply(), decision=True)
        self.op('reply', answer, current_object_revision='v1')
        with self.assertRaises(state.StateError):
            self.op('reply', dict(answer, decision=1), current_object_revision='v1')
        entry = self.inspect()
        self.assertIs(entry['event']['payload']['value'], True)
        self.assertIs(entry['attempts']['attempt-1']['request']['metadata'], True)
        self.assertIs(entry['attempts']['attempt-1']['acknowledgement']['receipt'], True)
        self.assertIs(entry['replies']['reply-1']['decision'], True)

    def test_event_and_attempt_must_precede_acknowledgement(self):
        with self.assertRaises(state.StateError):
            self.op('attempt', attempt())
        self.op('record', request())
        acknowledgement = {'event id': 'event/../1', 'attempt id': 'attempt-1', 'occurred at': 'time-2', 'status': 'accepted'}
        with self.assertRaises(state.StateError):
            self.op('ack', acknowledgement)
        self.op('attempt', attempt())
        self.assertIsNone(self.inspect()['attempts']['attempt-1']['acknowledgement'])
        self.op('ack', acknowledgement)
        self.assertEqual(self.inspect()['attempts']['attempt-1']['acknowledgement'], acknowledgement)
        self.assertEqual(self.inspect()['replies'], {})

    def test_failed_and_unknown_delivery_retained_without_retry_or_approval(self):
        self.op('record', request())
        for number, status in enumerate(('failed', 'unknown')):
            delivery = dict(attempt(), **{'attempt id': str(number)})
            self.op('attempt', delivery)
            self.op('ack', {'event id': 'event/../1', 'attempt id': str(number), 'occurred at': 'time-3', 'status': status, 'receipt': {'error': 'fixture failure'}})
        entry = self.inspect()
        self.assertEqual(len(entry['attempts']), 2)
        self.assertTrue(entry['event']['decision required'])
        self.assertEqual(entry['replies'], {})
        self.assertNotIn('authorization', entry)

    def test_acknowledgement_replay_and_conflict_after_restart(self):
        self.op('record', request())
        self.op('attempt', attempt())
        ack = {'event id': 'event/../1', 'attempt id': 'attempt-1', 'occurred at': 'time-2', 'status': 'unknown'}
        self.op('ack', ack)
        command = [sys.executable, '-B', str(Path(events.__file__).resolve()), '--state-root', str(self.config), '--runtime-id', 'A']
        source = self.root / 'ack.json'
        source.write_text(json.dumps(ack), encoding='utf-8')
        result = subprocess.run(command + ['ack', '--input', str(source)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)['changed'])
        with self.assertRaises(state.StateError):
            self.op('ack', dict(ack, status='accepted'))
        self.assertEqual(self.inspect()['attempts']['attempt-1']['acknowledgement'], ack)

    def test_replies_check_current_revision_correlation_and_declared_decider(self):
        self.op('record', request())
        with self.assertRaisesRegex(state.StateError, 'stale'):
            self.op('reply', reply(), current_object_revision='v2')
        for key in ('correlation id', 'object revision', 'declared decider'):
            with self.assertRaises(state.StateError):
                self.op('reply', dict(reply(), **{key: 'wrong'}), current_object_revision='v1')
        self.assertEqual(self.inspect()['replies'], {})
        outcome = self.op('reply', reply(), current_object_revision='v1')
        self.assertEqual(outcome['identity authentication'], 'not performed')
        self.assertEqual(outcome['workflow authorization'], 'not evaluated')
        self.assertEqual(self.inspect()['replies']['reply-1']['original wording'], 'Choose A')

    def test_reply_replay_and_conflict_after_restart(self):
        self.op('record', request())
        self.op('reply', reply(), current_object_revision='v1')
        source = self.root / 'reply.json'
        source.write_text(json.dumps(reply()), encoding='utf-8')
        command = [sys.executable, '-B', str(Path(events.__file__).resolve()), '--state-root', str(self.config), '--runtime-id', 'A', 'reply', '--input', str(source), '--current-object-revision', 'v1']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)['changed'])
        with self.assertRaises(state.StateError):
            self.op('reply', dict(reply(), **{'original wording': 'Choose B'}), current_object_revision='v1')
        self.assertEqual(self.inspect()['replies']['reply-1'], reply())

    def test_muting_receiver_does_not_drop_event_or_approve_decision(self):
        muted = copy.deepcopy(self.profile)
        muted['revision'] = 'r2'
        muted['routes']['review']['muted'] = True
        state.configure(self.config, 'A', 'notification', muted, 'r1')
        self.op('record', request())
        entry = self.inspect()
        self.assertTrue(entry['event']['decision required'])
        self.assertEqual(entry['replies'], {})
        self.assertEqual(entry['attempts'], {})

    def test_failed_atomic_write_preserves_previous_ledger(self):
        self.op('record', request())
        original = (self.root / 'delivery/workflow-events.json').read_bytes()
        with patch.object(events, 'atomic_write', side_effect=OSError('fixture full disk')):
            with self.assertRaises(OSError):
                self.op('attempt', attempt())
        self.assertEqual((self.root / 'delivery/workflow-events.json').read_bytes(), original)
        self.op('attempt', attempt())
        self.assertEqual(len(self.inspect()['attempts']), 1)

    def test_lock_and_destination_runtime_identity_conflicts(self):
        self.op('record', request())
        directory = self.root / 'delivery'
        with state.locked(directory):
            with self.assertRaisesRegex(state.StateError, 'concurrent writer'):
                self.op('attempt', attempt())
        other = self.root / 'B'
        moved = notify_profile(self.root, runtime='B')
        state.configure(other, 'B', 'notification', moved)
        with self.assertRaisesRegex(state.StateError, 'handoff'):
            events.operate(other, 'B', 'inspect')
        self.assertEqual(self.inspect()['event'], request())

    def test_arbitrary_config_command_is_never_executed(self):
        config = copy.deepcopy(self.profile)
        config['adapter tool reference'] = 'SHOULD-NOT-EXECUTE $(exit 9)'
        config['revision'] = 'r2'
        state.configure(self.config, 'A', 'notification', config, 'r1')
        with patch('subprocess.run', side_effect=AssertionError('must not execute adapter')):
            self.op('record', request())
            record = dict(attempt(), **{'adapter tool reference': config['adapter tool reference']})
            self.op('attempt', record)
        self.assertEqual(len(self.inspect()['attempts']), 1)

if __name__ == '__main__':
    unittest.main()
