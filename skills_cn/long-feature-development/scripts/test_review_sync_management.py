#!/usr/bin/env python3
"""Real same-repository journal commits, merge recovery and dirt preservation."""
import sys
sys.dont_write_bytecode = True
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch
import test_task_reconcile as fixture
from test_task_context import git
import task_context as tc
import task_operation as op
import review_sync as sync
from review_source import read_git_reviews
from review_application import _status


class ManagementSyncTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.RecoveryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f = self.f
        self.remote = f.workspace / 'management.git'
        git(f.workspace, 'init', '--bare', str(self.remote))
        git(f.pm, 'remote', 'set-url', 'origin', self.remote.as_posix())
        status = f.root / 'STATUS.md'
        status.write_text(status.read_text(encoding='utf-8').replace(
            'https://example.invalid/pm.git', self.remote.as_posix()), encoding='utf-8')
        detail = f.root / 'tasks/DEV-02.md'
        detail.write_text(detail.read_text(encoding='utf-8') + '\n## Attempt notes\n\n', encoding='utf-8')
        f.commit_records()
        self.before = git(f.pm, 'rev-parse', 'HEAD')
        git(f.pm, 'checkout', '-b', 'master')
        (f.pm / 'upstream.txt').write_text('authoritative content\n', encoding='utf-8')
        git(f.pm, 'add', 'upstream.txt')
        git(f.pm, 'commit', '-m', 'master update')
        self.master = git(f.pm, 'rev-parse', 'HEAD')
        git(f.pm, 'push', 'origin', 'master')
        git(f.pm, 'checkout', 'feature')
        self.binding = dict(repo=f.pm, remote='origin', expected_remote=self.remote.as_posix(),
            repository_ref='pm', relative_path='project/PIRC-23/REVIEWS.md', feature='PIRC-23', reviews_ref='reviews')

    def prepare(self):
        return sync.prepare(self.f.root, self.f.plan_ref, 'pm', self.binding,
                            read_git_reviews(**self.binding), 'conversation:authorized-sync', authority=True)

    def execute(self, identifier):
        return sync.execute(self.f.root, self.f.plan_ref, identifier, authority=True)

    def test_journal_only_commit_clean_merge_and_metadata_checkpoint(self):
        f = self.f
        identifier = self.prepare()
        seen = []
        def observe(name):
            if name == 'review-sync-dispatched':
                head = git(f.pm, 'rev-parse', 'HEAD')
                self.assertEqual(git(f.pm, 'show', '-s', '--format=%P', head), self.before)
                self.assertEqual(git(f.pm, 'diff-tree', '--no-commit-id', '--name-only', '-r', head),
                                 'project/PIRC-23/' + f.plan_ref)
                self.assertEqual(_status(f.pm), b'?? project/PIRC-23/.operation.lock\0')
                seen.append(head)
        with patch.object(op, 'interruption_point', side_effect=observe):
            result = self.execute(identifier)
        self.assertEqual(result['effect'], 'APPLIED', result)
        merged = git(f.pm, 'rev-parse', 'HEAD')
        self.assertEqual(git(f.pm, 'show', '-s', '--format=%P', merged), seen[0] + ' ' + self.master)
        self.assertEqual(git(self.remote, 'rev-parse', 'master'), self.master)
        self.assertEqual(self.execute(identifier)['effect'], 'UNCHANGED')
        f.commit_records()
        self.assertEqual(tc.build_context(f.root)['task']['id'], 'DEV-02')
        restored = op.reconcile(f.root, f.plan_ref, identifier, apply=True, authority=True)
        self.assertEqual(restored['effect'], 'UNCHANGED', restored)
        self.assertEqual(git(f.pm, 'status', '--porcelain'), '')

    def test_unrelated_dirty_file_is_not_committed(self):
        identifier = self.prepare()
        path = self.f.pm / 'user-draft.txt'
        path.write_text('keep me', encoding='utf-8')
        with self.assertRaisesRegex(sync.Error, 'DIRTY_WORKTREE'):
            self.execute(identifier)
        self.assertEqual(path.read_text(encoding='utf-8'), 'keep me')
        self.assertEqual(git(self.f.pm, 'rev-parse', 'HEAD'), self.before)

    def test_prestaged_journal_is_not_absorbed(self):
        identifier = self.prepare()
        git(self.f.pm, 'add', 'project/PIRC-23/' + self.f.plan_ref)
        with self.assertRaisesRegex(sync.Error, 'DIRTY_WORKTREE'):
            self.execute(identifier)
        self.assertEqual(git(self.f.pm, 'rev-parse', 'HEAD'), self.before)

    def test_journal_other_text_change_is_preserved(self):
        identifier = self.prepare()
        path = self.f.root / self.f.plan_ref
        path.write_text(path.read_text(encoding='utf-8') + '\nHuman note\n', encoding='utf-8')
        with self.assertRaisesRegex(sync.Error, 'CONTENT_CONFLICT'):
            self.execute(identifier)
        self.assertIn('Human note', path.read_text(encoding='utf-8'))

    def test_crash_after_journal_commit_never_replays_merge(self):
        identifier = self.prepare()
        def interrupt(name):
            if name == 'review-sync-journal-committed':
                raise RuntimeError('crash')
        with patch.object(op, 'interruption_point', side_effect=interrupt):
            with self.assertRaises(RuntimeError):
                self.execute(identifier)
        head = git(self.f.pm, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(sync.Error, 'UNKNOWN_MERGE_OUTCOME_NO_REPLAY'):
            self.execute(identifier)
        result = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(result['observed_result']['status'], 'unknown', result)
        self.assertEqual(git(self.f.pm, 'rev-parse', 'HEAD'), head)

    def test_lost_merge_response_records_actual_merge_once(self):
        identifier = self.prepare()
        def interrupt(name):
            if name == 'review-sync-returned':
                raise RuntimeError('lost response')
        with patch.object(op, 'interruption_point', side_effect=interrupt):
            with self.assertRaises(RuntimeError):
                self.execute(identifier)
        head = git(self.f.pm, 'rev-parse', 'HEAD')
        observed = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(observed['observed_result']['commit_sha'], head, observed)
        self.execute(identifier)
        self.assertEqual(git(self.f.pm, 'rev-parse', 'HEAD'), head)

    def test_conflict_is_not_aborted_or_overwritten(self):
        f = self.f
        (f.pm / 'upstream.txt').write_text('local content\n', encoding='utf-8')
        git(f.pm, 'add', 'upstream.txt')
        git(f.pm, 'commit', '-m', 'local content')
        identifier = self.prepare()
        with self.assertRaisesRegex(sync.Error, 'MERGE_CONFLICT_OR_INCOMPLETE'):
            self.execute(identifier)
        self.assertEqual(git(f.pm, 'rev-parse', 'MERGE_HEAD'), self.master)
        conflict = (f.pm / 'upstream.txt').read_bytes()
        result = op.reconcile(f.root, f.plan_ref, identifier, apply=True, authority=True)
        self.assertEqual(result['conflicts'][0]['code'], 'MERGE_CONFLICT_OR_INCOMPLETE', result)
        self.assertEqual((f.pm / 'upstream.txt').read_bytes(), conflict)

    def test_remote_journal_change_stops_before_dispatch_commit(self):
        f = self.f
        git(f.pm, 'checkout', 'master')
        (f.root / f.plan_ref).write_text('# Changed authoritative journal\n', encoding='utf-8')
        git(f.pm, 'commit', '-am', 'journal changes')
        git(f.pm, 'push', 'origin', 'master')
        git(f.pm, 'checkout', 'feature')
        identifier = self.prepare()
        with self.assertRaisesRegex(sync.Error, 'JOURNAL_SOURCE_CONFLICT'):
            self.execute(identifier)
        self.assertEqual(git(f.pm, 'rev-parse', 'HEAD'), self.before)
        self.assertFalse(op.read_gist(f.root, f.plan_ref)[3][identifier]['dispatched'])

    def test_already_contained_master_only_records_without_journal_commit(self):
        git(self.f.pm, 'push', '--force', 'origin', 'HEAD:master')
        identifier = self.prepare()
        self.execute(identifier)
        self.assertEqual(git(self.f.pm, 'rev-parse', 'HEAD'), self.before)
        self.f.commit_records()
        observed = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(observed['observed_result']['commit_sha'], self.before, observed)

    def test_merge_changed_metadata_is_preserved_as_third_value(self):
        f = self.f
        git(f.pm, 'checkout', 'master')
        path = f.root / 'STATUS.md'
        path.write_text(path.read_text(encoding='utf-8') + '\nAuthoritative new note\n', encoding='utf-8')
        git(f.pm, 'commit', '-am', 'update source metadata')
        git(f.pm, 'push', 'origin', 'master')
        git(f.pm, 'checkout', 'feature')
        identifier = self.prepare()
        with self.assertRaisesRegex(sync.Error, 'CONTENT_CONFLICT'):
            self.execute(identifier)
        self.assertIn('Authoritative new note', path.read_text(encoding='utf-8'))
        result = op.reconcile(f.root, f.plan_ref, identifier)
        self.assertEqual(result['conflicts'][0]['code'], 'CONTENT_CONFLICT', result)
        self.assertIn('Authoritative new note', path.read_text(encoding='utf-8'))

    def _actual_exit(self, point):
        identifier = self.prepare()
        code = """import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import review_sync as sync
import task_operation as op
op.interruption_point = lambda name: os._exit(70) if name == sys.argv[5] else None
sync.execute(sys.argv[2], sys.argv[3], sys.argv[4], authority=True)
"""
        process = subprocess.run([sys.executable, '-B', '-c', code, str(Path(__file__).resolve().parent),
            str(self.f.root), self.f.plan_ref, identifier, point], capture_output=True, timeout=90)
        self.assertEqual(process.returncode, 70, process.stderr.decode(errors='replace'))
        self.assertTrue((self.f.root / '.operation.lock').exists())
        head = git(self.f.pm, 'rev-parse', 'HEAD')
        observed = op.reconcile(self.f.root, self.f.plan_ref, identifier)
        self.assertEqual(observed['observed_result']['status'], 'unknown', observed)
        self.assertEqual(observed['next_check'], 'inspect-git-no-replay')
        self.assertEqual(git(self.f.pm, 'rev-parse', 'HEAD'), head)
        return head

    def test_actual_process_exit_after_journal_save_keeps_intent(self):
        self.assertEqual(self._actual_exit('review-sync-journal-saved'), self.before)

    def test_actual_process_exit_after_journal_commit_keeps_clean_checkpoint(self):
        head = self._actual_exit('review-sync-journal-committed')
        self.assertNotEqual(head, self.before)
        self.assertEqual(git(self.f.pm, 'show', '-s', '--format=%P', head), self.before)


if __name__ == '__main__':
    unittest.main()
