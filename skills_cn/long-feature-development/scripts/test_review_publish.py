#!/usr/bin/env python3
"""Real remote ref leases and durable review drafts; no live forge writes."""
import sys
sys.dont_write_bytecode = True
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch
import test_review_sync as fixture
from test_task_context import git
import review_publish as publish
import review_comments as rv
import task_operation as op
from review_source import read_git_reviews


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.s = fixture.SyncTests()
        self.s.setUp()
        self.addCleanup(self.s.doCleanups)
        self.f, self.binding = self.s.f, self.s.binding
        self.comment = rv.new_review(dict(feature='PIRC-23', ref='owned.py'),
            dict(source_key='app:owned', source_text='version = 1\n', git_basis=self.f.app_head), 'Review this.')
        self.draft = rv.render([self.comment])
        self.grants = {}

    def prepare(self, **kwargs):
        receipt = publish.prepare(self.f.root, self.f.plan_ref, 'app', self.binding,
            read_git_reviews(**self.binding), self.draft, 'conversation:publish-this-draft',
            **{'authority': True, **kwargs})
        self.grants[receipt['operation_id']] = receipt['intent_digest']
        return receipt['operation_id']

    def execute(self, identifier):
        return publish.execute(self.f.root, self.f.plan_ref, identifier, authority=True,
                               expected_intent_digest=self.grants[identifier])

    def advance(self):
        git(self.f.app, 'checkout', 'master')
        (self.f.app / 'upstream.txt').write_text('remote advance\n', encoding='utf-8')
        git(self.f.app, 'commit', '-am', 'advance master')
        git(self.f.app, 'push', 'origin', 'master')
        head = git(self.f.app, 'rev-parse', 'HEAD')
        git(self.f.app, 'checkout', 'task')
        return head

    def test_conditional_publication_excludes_working_branch_and_reenters(self):
        identifier = self.prepare()
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), self.s.master)
        result = self.execute(identifier)
        self.assertEqual(result['observed_result']['status'], 'present', result)
        self.assertFalse(result['agent_consumed'])
        self.assertEqual(result['decision_effect'], 'NONE')
        head = git(self.s.remote, 'rev-parse', 'master')
        self.assertEqual(git(self.s.remote, 'show', '-s', '--format=%P', head), self.s.master)
        self.assertEqual(git(self.s.remote, 'diff-tree', '--no-commit-id', '--name-only', '-r', head), 'REVIEWS.md')
        self.assertNotIn('owned.py', git(self.s.remote, 'ls-tree', '--name-only', head).splitlines())
        self.assertEqual(git(self.f.app, 'rev-parse', 'HEAD'), self.f.app_head)
        self.assertFalse((self.f.app / 'REVIEWS.md').exists())
        self.assertEqual(self.execute(identifier)['effect'], 'UNCHANGED')
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), head)

    def test_reconcile_after_management_checkpoint(self):
        identifier = self.prepare()
        self.execute(identifier)
        self.f.commit_records()
        result = op.reconcile(self.f.root, self.f.plan_ref, identifier, apply=True, authority=True)
        self.assertEqual(result['effect'], 'UNCHANGED', result)

    def test_missing_authority_never_creates_intent(self):
        before = (self.f.root / self.f.plan_ref).read_bytes()
        with self.assertRaisesRegex(publish.Error, 'AUTHORITY_REQUIRED'):
            self.prepare(authority=False)
        self.assertEqual((self.f.root / self.f.plan_ref).read_bytes(), before)

    def test_changed_source_returns_conflict_and_retains_draft(self):
        identifier = self.prepare()
        head = self.advance()
        result = self.execute(identifier)
        self.assertEqual(result['observed_result']['http_status'], 409, result)
        record = op.read_gist(self.f.root, self.f.plan_ref)[3][identifier]
        self.assertEqual(record['expected_source']['draft'], self.draft)
        self.assertFalse(record['dispatched'])
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), head)

    def test_ref_lease_rejects_race_after_last_read(self):
        identifier = self.prepare()
        advanced = []
        def race(name):
            if name == 'review-publish-dispatched':
                advanced.append(self.advance())
        with patch.object(op, 'interruption_point', side_effect=race):
            result = self.execute(identifier)
        self.assertEqual(result['observed_result']['status'], 'conflict', result)
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), advanced[0])
        self.assertEqual(op.read_gist(self.f.root, self.f.plan_ref)[3][identifier]['expected_source']['draft'], self.draft)

    def test_lost_push_response_looks_up_same_uuid_without_republish(self):
        identifier = self.prepare()
        def interrupt(name):
            if name == 'review-publish-returned':
                raise RuntimeError('response lost')
        with patch.object(op, 'interruption_point', side_effect=interrupt):
            with self.assertRaises(RuntimeError):
                self.execute(identifier)
        head = git(self.s.remote, 'rev-parse', 'master')
        observed = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(observed['observed_result']['status'], 'present', observed)
        self.assertEqual(observed['effect'], 'NOT_APPLIED')
        self.execute(identifier)
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), head)
        self.assertEqual(read_git_reviews(**self.binding)['records'], [self.comment])

    def test_unknown_without_visible_effect_is_never_replayed(self):
        identifier = self.prepare()
        with patch.object(op, 'interruption_point', side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):
                self.execute(identifier)
        result = self.execute(identifier)
        self.assertEqual(result['observed_result']['status'], 'unknown', result)
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), self.s.master)
        with self.assertRaisesRegex(publish.Error, 'UNRESOLVED_REVIEW_PUBLICATION'):
            self.prepare()

    def test_invalid_draft_does_not_publish(self):
        self.draft = '# Reviews\n\nUnstructured content\n'
        with self.assertRaises(rv.ReviewCommentError):
            self.prepare()
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), self.s.master)

    def test_cannot_delete_existing_comments_through_full_document_replace(self):
        self.execute(self.prepare())
        self.draft = rv.render([])
        with self.assertRaisesRegex(publish.Error, 'REVIEW_DELETION_NOT_AUTHORIZED'):
            self.prepare()

    def test_changed_intent_does_not_reuse_host_approval(self):
        identifier = self.prepare()
        raw, _, _, records = op.read_gist(self.f.root, self.f.plan_ref)
        records[identifier]['expected_source']['draft'] += '\n'
        op.save(self.f.root, self.f.plan_ref, records[identifier], raw)
        with self.assertRaisesRegex(publish.Error, 'AUTHORITY_SCOPE_MISMATCH'):
            self.execute(identifier)
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), self.s.master)

    def test_conflict_is_terminal_even_if_remote_returns_to_old_version(self):
        identifier = self.prepare()
        self.advance()
        self.execute(identifier)
        git(self.f.app, 'push', '--force', 'origin', self.s.master + ':master')
        self.execute(identifier)
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), self.s.master)
        self.assertTrue(op.read_gist(self.f.root, self.f.plan_ref)[3][identifier]['terminal_conflict'])

    def test_explicit_new_conflict_attempt_retains_uuid_and_old_draft(self):
        previous = self.prepare()
        self.advance()
        self.execute(previous)
        old_draft = self.draft
        self.comment['Comment'] = 'Revised after explicit conflict review.'
        self.draft = rv.render([self.comment])
        current = self.prepare(supersedes=previous)
        self.assertEqual(self.execute(current)['observed_result']['status'], 'present')
        records = op.read_gist(self.f.root, self.f.plan_ref)[3]
        self.assertEqual(records[previous]['expected_source']['draft'], old_draft)
        self.assertEqual(records[current]['supersedes'], previous)
        self.assertEqual(read_git_reviews(**self.binding)['records'], [self.comment])
        with self.assertRaisesRegex(publish.Error, 'OPERATION_SUPERSEDED'):
            self.execute(previous)

    def test_superseding_draft_cannot_allocate_replacement_rv_uuid(self):
        previous = self.prepare()
        self.advance()
        self.execute(previous)
        replacement = rv.new_review(self.comment['Target'], self.comment['Basis'], 'Different ID is unsafe.')
        self.draft = rv.render([replacement])
        with self.assertRaisesRegex(publish.Error, 'RV_IDENTITY_CHANGED'):
            self.prepare(supersedes=previous)

    def test_actual_process_exit_after_push_keeps_readback_and_draft(self):
        identifier = self.prepare()
        code = """import os, sys, tempfile
sys.dont_write_bytecode = True
tempfile.tempdir = sys.argv[6]
sys.path.insert(0, sys.argv[1])
import review_publish as publish
import task_operation as op
op.interruption_point = lambda name: os._exit(70) if name == 'review-publish-returned' else None
publish.execute(sys.argv[2], sys.argv[3], sys.argv[4], authority=True, expected_intent_digest=sys.argv[5])
"""
        process = subprocess.run([sys.executable, '-B', '-c', code, str(Path(__file__).resolve().parent),
            str(self.f.root), self.f.plan_ref, identifier, self.grants[identifier], str(self.f.workspace)],
            capture_output=True, timeout=90)
        self.assertEqual(process.returncode, 70, process.stderr.decode(errors='replace'))
        self.assertTrue((self.f.root / '.operation.lock').exists())
        head = git(self.s.remote, 'rev-parse', 'master')
        observed = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(observed['observed_result']['status'], 'present', observed)
        self.assertEqual(observed['effect'], 'NOT_APPLIED')
        self.assertEqual(op.read_gist(self.f.root, self.f.plan_ref)[3][identifier]['expected_source']['draft'], self.draft)
        self.assertEqual(git(self.s.remote, 'rev-parse', 'master'), head)


if __name__ == '__main__':
    unittest.main()
