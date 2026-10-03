#!/usr/bin/env python3
"""Actual Git merge, conflict and F03 lost-response recovery regressions."""
import sys
sys.dont_write_bytecode = True
import unittest
from unittest.mock import patch
import test_task_reconcile as fixture
from test_task_context import git
import task_context as tc
import task_operation as op
import review_sync as sync
import review_comments as rv
from review_source import read_git_reviews


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.RecoveryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f = self.f
        self.remote = f.workspace / 'authority.git'
        git(f.workspace, 'init', '--bare', str(self.remote))
        git(f.app, 'remote', 'set-url', 'origin', self.remote.as_posix())
        status = f.root / 'STATUS.md'
        status.write_text(status.read_text(encoding='utf-8').replace(
            'https://example.invalid/app.git', self.remote.as_posix()), encoding='utf-8')
        detail = f.root / 'tasks/DEV-02.md'
        detail.write_text(detail.read_text(encoding='utf-8') + '\n## Attempt notes\n\n', encoding='utf-8')
        f.commit_records()
        git(f.app, 'checkout', '-b', 'master', f.app_base)
        (f.app / 'upstream.txt').write_text('upstream\n', encoding='utf-8')
        git(f.app, 'add', 'upstream.txt')
        git(f.app, 'commit', '-m', 'master update')
        self.master = git(f.app, 'rev-parse', 'HEAD')
        git(f.app, 'push', 'origin', 'master')
        git(f.app, 'checkout', 'task')
        self.binding = dict(repo=f.app, remote='origin', expected_remote=self.remote.as_posix(),
                            repository_ref='app', relative_path='REVIEWS.md', feature='PIRC-23', reviews_ref='reviews')

    def prepare(self, **kwargs):
        f = self.f
        return sync.prepare(f.root, f.plan_ref, 'app', self.binding, read_git_reviews(**self.binding),
                            'conversation:explicit-sync', **{'authority': True, **kwargs})

    def execute(self, identifier):
        return sync.execute(self.f.root, self.f.plan_ref, identifier, authority=True)

    def test_merge_journal_metadata_and_reentry(self):
        f = self.f
        identifier = self.prepare()
        before = op.read_gist(f.root, f.plan_ref)[3][identifier]
        self.assertFalse(before['dispatched'])
        self.assertEqual(before['expected_source']['master_sha'], self.master)
        self.assertEqual(git(f.app, 'rev-parse', 'HEAD'), f.app_head)
        result = self.execute(identifier)
        self.assertEqual(result['effect'], 'APPLIED', result)
        head = git(f.app, 'rev-parse', 'HEAD')
        self.assertEqual(git(f.app, 'show', '-s', '--format=%P', head), f.app_head + ' ' + self.master)
        self.assertIn('Operation-Id: ' + identifier, git(f.app, 'show', '-s', '--format=%B', head))
        self.assertEqual(git(self.remote, 'rev-parse', 'master'), self.master)
        self.assertEqual(self.execute(identifier)['effect'], 'UNCHANGED')
        f.commit_records()
        self.assertEqual(tc.build_context(f.root)['task']['id'], 'DEV-02')

    def test_authority_missing_does_not_write_intent(self):
        before = (self.f.root / self.f.plan_ref).read_bytes()
        with self.assertRaisesRegex(sync.Error, 'AUTHORITY_REQUIRED'):
            self.prepare(authority=False)
        self.assertEqual((self.f.root / self.f.plan_ref).read_bytes(), before)

    def test_dirty_after_prepare_preserves_file_and_head(self):
        identifier = self.prepare()
        path = self.f.app / 'draft.txt'
        path.write_text('unsaved draft', encoding='utf-8')
        with self.assertRaisesRegex(sync.Error, 'DIRTY_WORKTREE'):
            self.execute(identifier)
        self.assertEqual(path.read_text(encoding='utf-8'), 'unsaved draft')
        self.assertEqual(git(self.f.app, 'rev-parse', 'HEAD'), self.f.app_head)

    def test_record_changed_before_dispatch_blocks(self):
        identifier = self.prepare()
        path = self.f.root / 'STATUS.md'
        path.write_text(path.read_text(encoding='utf-8') + '\nUser note\n', encoding='utf-8')
        with self.assertRaisesRegex(sync.Error, 'SOURCE_CHANGED'):
            self.execute(identifier)
        self.assertFalse(op.read_gist(self.f.root, self.f.plan_ref)[3][identifier]['dispatched'])

    def test_master_advance_requires_new_observation(self):
        identifier = self.prepare()
        f = self.f
        git(f.app, 'checkout', 'master')
        (f.app / 'upstream.txt').write_text('changed again\n', encoding='utf-8')
        git(f.app, 'commit', '-am', 'advance authority')
        git(f.app, 'push', 'origin', 'master')
        git(f.app, 'checkout', 'task')
        with self.assertRaisesRegex(sync.Error, 'REVIEW_SOURCE_CHANGED'):
            self.execute(identifier)
        self.assertEqual(git(f.app, 'rev-parse', 'HEAD'), f.app_head)

    def test_lost_response_recovers_without_second_merge(self):
        identifier = self.prepare()
        def interrupt(name):
            if name == 'review-sync-returned':
                raise RuntimeError('lost response')
        with patch.object(op, 'interruption_point', side_effect=interrupt):
            with self.assertRaisesRegex(RuntimeError, 'lost response'):
                self.execute(identifier)
        head = git(self.f.app, 'rev-parse', 'HEAD')
        readonly = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(readonly['observed_result']['commit_sha'], head, readonly)
        self.assertEqual(readonly['effect'], 'NOT_APPLIED')
        self.execute(identifier)
        self.assertEqual(git(self.f.app, 'rev-parse', 'HEAD'), head)

    def test_dispatch_crash_is_unknown_and_never_replayed(self):
        identifier = self.prepare()
        with patch.object(op, 'interruption_point', side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):
                self.execute(identifier)
        with self.assertRaisesRegex(sync.Error, 'UNKNOWN_MERGE_OUTCOME_NO_REPLAY'):
            self.execute(identifier)
        result = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(result['observed_result']['status'], 'unknown', result)
        self.assertEqual(result['next_check'], 'inspect-git-no-replay')
        self.assertEqual(git(self.f.app, 'rev-parse', 'HEAD'), self.f.app_head)
        with self.assertRaisesRegex(sync.Error, 'UNRESOLVED_REVIEW_SYNC'):
            self.prepare()

    def test_contained_master_does_not_create_commit(self):
        git(self.f.app, 'push', '--force', 'origin', 'HEAD:master')
        identifier = self.prepare()
        self.execute(identifier)
        self.assertEqual(git(self.f.app, 'rev-parse', 'HEAD'), self.f.app_head)
        record = op.read_gist(self.f.root, self.f.plan_ref)[3][identifier]
        self.assertFalse(record['dispatched'])
        self.assertEqual(record['observed_result']['commit_sha'], self.f.app_head)

    def test_actual_comment_basis_is_retained_in_intent(self):
        f = self.f
        git(f.app, 'checkout', 'master')
        comment = rv.new_review(dict(feature='PIRC-23', ref='owned.py'),
            dict(source_key='app:owned', source_text='version = 1\n', git_basis=f.app_head), 'Check this sample.')
        (f.app / 'REVIEWS.md').write_text(rv.render([comment]), encoding='utf-8')
        git(f.app, 'add', 'REVIEWS.md')
        git(f.app, 'commit', '-m', 'publish actual fixture comment')
        git(f.app, 'push', 'origin', 'master')
        git(f.app, 'checkout', 'task')
        identifier = self.prepare()
        record = op.read_gist(f.root, f.plan_ref)[3][identifier]
        self.assertEqual(record['expected_source']['observation']['records'], [comment])
        self.assertNotEqual(record['expected_source']['master_sha'], comment['Basis']['git_basis'])
        self.execute(identifier)
        self.assertIn('Check this sample.', (f.app / 'REVIEWS.md').read_text(encoding='utf-8'))

    def test_conflict_retains_index_and_merge_head(self):
        f = self.f
        git(f.app, 'checkout', 'master')
        (f.app / 'owned.py').write_text('conflicting upstream\n', encoding='utf-8')
        git(f.app, 'add', 'owned.py')
        git(f.app, 'commit', '-m', 'conflict')
        self.master = git(f.app, 'rev-parse', 'HEAD')
        git(f.app, 'push', 'origin', 'master')
        git(f.app, 'checkout', 'task')
        identifier = self.prepare()
        with self.assertRaisesRegex(sync.Error, 'MERGE_CONFLICT_OR_INCOMPLETE'):
            self.execute(identifier)
        self.assertEqual(git(f.app, 'rev-parse', 'MERGE_HEAD'), self.master)
        before = git(f.app, 'ls-files', '-u')
        self.assertTrue(before)
        result = op.reconcile(f.root, f.plan_ref, identifier, apply=True, authority=True)
        self.assertEqual(result['conflicts'][0]['code'], 'MERGE_CONFLICT_OR_INCOMPLETE', result)
        self.assertEqual(git(f.app, 'ls-files', '-u'), before)


if __name__ == '__main__':
    unittest.main()
