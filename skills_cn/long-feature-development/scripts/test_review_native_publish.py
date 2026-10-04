#!/usr/bin/env python3
"""Real local Git journals plus loopback HTTP, not live provider acceptance."""
import sys
sys.dont_write_bytecode = True
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch
import test_task_reconcile as fixture
import test_review_native as http_fixture
import review_native as native
import review_native_publish as publish
import review_comments as rv
import task_operation as op


class NativePublishTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.RecoveryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.http = http_fixture.NativeTests()
        self.http.setUp()
        self.addCleanup(self.http.tearDown)
        self.http.state['body'] = rv.render([]).encode()
        self.endpoint = native.NativeDocument('fixture', 'native:reviews', self.f.root.name,
            'native:reviews', self.http.url, allow_loopback_http=True, headers={'Authorization': 'fake-test-secret'})
        self.comment = rv.new_review(dict(feature=self.f.root.name, ref='REQ.md'),
                                    dict(source_key='pm:REQ.md', source_text='Original.'), 'Please check.')
        self.draft = rv.render([self.comment])
        self.grants = {}

    def prepare(self, **kwargs):
        receipt = publish.prepare(self.f.root, self.f.plan_ref, self.endpoint,
            native.read_for_purpose('review', endpoint=self.endpoint), self.draft, 'conversation:exact-draft',
            **{'authority': True, **kwargs})
        self.grants[receipt['operation_id']] = receipt['intent_digest']
        return receipt['operation_id']

    def execute(self, identifier):
        return publish.execute(self.f.root, self.f.plan_ref, identifier, self.endpoint,
                               authority=True, expected_intent_digest=self.grants[identifier])

    def test_durable_draft_single_write_and_idempotent_readback(self):
        identifier = self.prepare()
        raw, _, _, records = op.read_gist(self.f.root, self.f.plan_ref)
        self.assertEqual(records[identifier]['expected_source']['draft'], self.draft)
        self.assertNotIn(b'fake-test-secret', raw)
        self.assertNotIn(self.http.url.encode(), raw)
        self.assertEqual(self.http.state['puts'], 0)
        result = self.execute(identifier)
        self.assertEqual(result['publication_status'], 'present', result)
        self.assertTrue(result['draft_preserved'])
        self.assertFalse(result['agent_consumed'])
        self.assertEqual(self.execute(identifier)['effect'], 'UNCHANGED')
        self.assertEqual(self.http.state['puts'], 1)
        self.f.commit_records()
        checked = op.reconcile(self.f.root, self.f.plan_ref, identifier, native_endpoint=self.endpoint)
        self.assertEqual(checked['publication_status'], 'present', checked)

    def test_lost_response_looks_up_same_uuid(self):
        self.http.state['drop'] = True
        identifier = self.prepare()
        result = self.execute(identifier)
        self.assertEqual(result['publication_status'], 'present', result)
        self.assertEqual(self.http.state['puts'], 1)
        self.assertEqual(self.execute(identifier)['publication_status'], 'present')
        self.assertEqual(self.http.state['puts'], 1)

    def test_dispatch_interruption_cannot_replay_or_prepare_another(self):
        identifier = self.prepare()
        with patch.object(op, 'interruption_point', side_effect=RuntimeError('stop after intent')):
            with self.assertRaises(RuntimeError):
                self.execute(identifier)
        self.assertEqual(self.execute(identifier)['publication_status'], 'unknown')
        self.assertEqual(self.http.state['puts'], 0)
        with self.assertRaisesRegex(publish.Error, 'UNRESOLVED_REVIEW_PUBLICATION'):
            self.prepare()

    def test_actual_conflict_stays_terminal_when_old_version_returns(self):
        identifier = self.prepare()
        self.http.state['version'] = '"changed"'
        self.assertEqual(self.execute(identifier)['publication_status'], 'conflict')
        self.http.state['version'] = '"opaque-one"'
        self.assertEqual(self.execute(identifier)['publication_status'], 'conflict')
        self.assertEqual(self.http.state['puts'], 0)
        self.assertEqual(op.read_gist(self.f.root, self.f.plan_ref)[3][identifier]['expected_source']['draft'], self.draft)

    def test_lease_race_conflict_persisted_even_if_source_restored(self):
        identifier = self.prepare()
        def race(name):
            if name == 'review-native-publish-dispatched':
                self.http.state['version'] = '"raced"'
            if name == 'review-native-publish-returned':
                self.http.state['version'] = '"opaque-one"'
        with patch.object(op, 'interruption_point', side_effect=race):
            result = self.execute(identifier)
        self.assertEqual(result['publication_status'], 'conflict', result)
        self.assertEqual(self.http.state['body'], rv.render([]).encode())
        self.assertEqual(self.execute(identifier)['publication_status'], 'conflict')
        self.assertEqual(self.http.state['puts'], 1)

    def test_new_explicit_attempt_retains_uuid_and_retires_old(self):
        old = self.prepare()
        self.http.state['version'] = '"changed"'
        self.execute(old)
        new = self.prepare(supersedes=old)
        self.assertNotEqual(old, new)
        self.assertEqual(self.execute(new)['publication_status'], 'present')
        with self.assertRaisesRegex(publish.Error, 'OPERATION_SUPERSEDED'):
            self.execute(old)
        records = op.read_gist(self.f.root, self.f.plan_ref)[3]
        self.assertEqual(records[old]['expected_source']['draft'], records[new]['expected_source']['draft'])
        self.assertEqual(self.http.state['puts'], 1)

    def test_missing_binding_or_changed_grant_cannot_publish(self):
        identifier = self.prepare()
        result = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(result['conflicts'][0]['code'], 'NATIVE_BINDING_REQUIRED')
        self.endpoint.url += '/other'
        with self.assertRaisesRegex(publish.Error, 'NATIVE_BINDING_MISMATCH'):
            self.execute(identifier)
        self.endpoint.url = self.http.url
        raw, _, _, records = op.read_gist(self.f.root, self.f.plan_ref)
        records[identifier]['expected_source']['draft'] += '\n'
        op.save(self.f.root, self.f.plan_ref, records[identifier], raw)
        with self.assertRaisesRegex(publish.Error, 'AUTHORITY_SCOPE_MISMATCH'):
            self.execute(identifier)
        self.assertEqual(self.http.state['puts'], 0)

    def test_readback_failure_is_unknown_not_empty_or_retried(self):
        identifier = self.prepare()
        def lose_readback(name):
            if name == 'review-native-publish-returned':
                self.http.state['status'] = 503
        with patch.object(op, 'interruption_point', side_effect=lose_readback):
            self.assertEqual(self.execute(identifier)['publication_status'], 'unknown')
        self.assertEqual(self.execute(identifier)['publication_status'], 'unknown')
        self.assertEqual(self.http.state['puts'], 1)
        self.http.state['status'] = 200
        self.assertEqual(self.execute(identifier)['publication_status'], 'present')
        self.assertEqual(self.http.state['puts'], 1)

    def test_actual_process_exit_after_write_preserves_journal(self):
        identifier = self.prepare()
        code = """import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import review_native as native
import review_native_publish as publish
import task_operation as op
endpoint = native.NativeDocument('fixture', 'native:reviews', sys.argv[7], 'native:reviews', sys.argv[6], allow_loopback_http=True)
op.interruption_point = lambda name: os._exit(70) if name == 'review-native-publish-returned' else None
publish.execute(sys.argv[2], sys.argv[3], sys.argv[4], endpoint, authority=True, expected_intent_digest=sys.argv[5])
"""
        child = subprocess.run([sys.executable, '-B', '-c', code, str(Path(__file__).resolve().parent),
            str(self.f.root), self.f.plan_ref, identifier, self.grants[identifier], self.http.url, self.f.root.name],
            capture_output=True, timeout=90)
        self.assertEqual(child.returncode, 70, child.stderr.decode(errors='replace'))
        self.assertTrue((self.f.root / '.operation.lock').exists())
        before = (self.f.root / self.f.plan_ref).read_bytes()
        result = op.reconcile(self.f.root, self.f.plan_ref, identifier, native_endpoint=self.endpoint)
        self.assertEqual(result['publication_status'], 'present', result)
        self.assertEqual(result['effect'], 'NOT_APPLIED')
        self.assertEqual((self.f.root / self.f.plan_ref).read_bytes(), before)
        self.assertEqual(self.http.state['puts'], 1)

    def test_changed_body_under_reused_etag_is_conflict(self):
        identifier = self.prepare()
        self.http.state['body'] = (rv.render([]) + '\n').encode()
        result = self.execute(identifier)
        self.assertEqual(result['publication_status'], 'conflict', result)
        self.assertEqual(self.http.state['puts'], 0)

    def test_authority_and_original_rv_identity_required(self):
        before = (self.f.root / self.f.plan_ref).read_bytes()
        with self.assertRaisesRegex(publish.Error, 'AUTHORITY_REQUIRED'):
            self.prepare(authority=False)
        self.assertEqual((self.f.root / self.f.plan_ref).read_bytes(), before)
        old = self.prepare()
        self.http.state['version'] = '"changed"'
        self.execute(old)
        self.draft = rv.render([rv.new_review(self.comment['Target'], self.comment['Basis'], 'Replacement')])
        with self.assertRaisesRegex(publish.Error, 'RV_IDENTITY_CHANGED'):
            self.prepare(supersedes=old)
        self.assertEqual(self.http.state['puts'], 0)


if __name__ == '__main__':
    unittest.main()
