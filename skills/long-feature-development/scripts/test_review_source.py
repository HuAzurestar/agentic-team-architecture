#!/usr/bin/env python3
"""Real local remote Git fixtures; no live forge authentication is implied."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import review_source as source
import review_comments as rv


class ReviewSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.origin, self.author, self.work = (self.root / name for name in ('origin.git', 'author', 'work'))
        self.git(self.root, 'init', '--bare', '-q', str(self.origin))
        self.git(self.root, 'init', '-q', '-b', 'master', str(self.author))
        self.git(self.author, 'config', 'user.email', 'fixture@example.invalid')
        self.git(self.author, 'config', 'user.name', 'Fixture')
        self.git(self.author, 'config', 'core.autocrlf', 'false')
        self.record = rv.new_review(dict(feature='F1', ref='TARGET.md'),
                                   dict(source_key='repo:target', source_text='original', git_basis='a'*40), 'Review this.')
        (self.author / 'REVIEWS.md').write_bytes(rv.render([self.record]).encode())
        self.git(self.author, 'add', 'REVIEWS.md')
        self.git(self.author, 'commit', '-qm', 'initial')
        self.git(self.author, 'remote', 'add', 'origin', str(self.origin))
        self.git(self.author, 'push', '-q', 'origin', 'master')
        self.git(self.root, 'clone', '-q', str(self.origin), str(self.work))
        self.kw = dict(remote='origin', expected_remote=str(self.origin), repository_ref='repo:pm',
                       relative_path='REVIEWS.md', feature='F1', reviews_ref='repo:pm/REVIEWS.md')

    def git(self, repo, *args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL, text=True)

    def read(self, **changes):
        return source.read_git_reviews(self.work, **(self.kw | changes))

    def publish(self, record):
        (self.author / 'REVIEWS.md').write_bytes(rv.render([record]).encode())
        self.git(self.author, 'add', 'REVIEWS.md')
        self.git(self.author, 'commit', '-qm', 'changed')
        self.git(self.author, 'push', '-q', 'origin', 'master')
        return self.git(self.author, 'rev-parse', 'HEAD').strip()

    def test_reads_remote_master_not_stale_working_copy(self):
        self.record['Comment'] = 'Latest remote comment'
        master = self.publish(self.record)
        local_head = self.git(self.work, 'rev-parse', 'HEAD').strip()
        before = self.git(self.work, 'show-ref'), (self.work / 'REVIEWS.md').read_bytes()
        result = self.read()
        self.assertEqual(result['source_version']['value'], master)
        self.assertEqual(result['working_head'], local_head)
        self.assertNotEqual(master, local_head)
        self.assertEqual(result['records'], [self.record])
        self.assertFalse(result['master_contained'])
        self.assertFalse(result['application_authorized'])
        self.assertEqual(before, (self.git(self.work, 'show-ref'), (self.work / 'REVIEWS.md').read_bytes()))

    def test_review_version_is_not_target_code_basis(self):
        result = self.read()
        self.assertNotEqual(result['source_version']['value'], result['records'][0]['Basis']['git_basis'])
        self.assertTrue(result['master_contained'])

    def test_reachable_source_proves_missing_file_is_empty(self):
        result = self.read(relative_path='MISSING.md')
        self.assertEqual(result['records'], [])
        self.assertTrue(result['source_missing'])
        self.assertEqual(result['source_version']['value'], self.git(self.author, 'rev-parse', 'HEAD').strip())

    def test_unreachable_is_never_empty(self):
        self.git(self.work, 'remote', 'set-url', 'origin', str(self.root / 'absent.git'))
        with self.assertRaisesRegex(source.ReviewSourceError, 'REVIEW_SOURCE_UNAVAILABLE'):
            self.read(expected_remote=str(self.root / 'absent.git'))

    def test_remote_identity_mismatch_stops_before_fetch(self):
        with self.assertRaisesRegex(source.ReviewSourceError, 'REVIEW_REMOTE_MISMATCH'):
            self.read(expected_remote='https://wrong.invalid/repo')

    def test_explicit_verified_request_not_hidden(self):
        self.record['Status'] = 'VERIFIED'
        self.publish(self.record)
        self.assertEqual(self.read()['records'], [])
        self.assertEqual(self.read(statuses=['VERIFIED'])['records'], [self.record])
        self.assertEqual(self.read(rv_ids=[self.record['rv_id']])['records'], [self.record])

    def test_dirty_worktree_does_not_block_read_or_get_overwritten(self):
        dirty = b'UNSAVED LOCAL DRAFT'
        (self.work / 'REVIEWS.md').write_bytes(dirty)
        self.assertEqual(self.read()['records'], [self.record])
        self.assertEqual((self.work / 'REVIEWS.md').read_bytes(), dirty)

    def test_remote_movement_during_read_refuses_snapshot(self):
        actual = source._master
        observed = 0
        def changing(repo, remote):
            nonlocal observed
            observed += 1
            if observed == 2:
                self.record['Comment'] = 'Moved again'
                self.publish(self.record)
            return actual(repo, remote)
        with patch.object(source, '_master', side_effect=changing):
            with self.assertRaisesRegex(source.ReviewSourceError, 'REVIEW_SOURCE_CHANGED'):
                self.read()

    def test_unsafe_paths_and_missing_master_refuse(self):
        for path in ('../REVIEWS.md', '.git/config'):
            with self.assertRaises(source.ReviewSourceError):
                self.read(relative_path=path)
        self.git(self.origin, 'update-ref', '-d', 'refs/heads/master')
        with self.assertRaisesRegex(source.ReviewSourceError, 'REVIEW_MASTER_UNAVAILABLE'):
            self.read()

    def test_document_budget_refuses(self):
        with patch.object(source, 'MAX_BYTES', 256):
            with self.assertRaisesRegex(source.ReviewSourceError, 'RESOURCE_LIMIT'):
                self.read()

    def test_filter_capable_remote_can_supply_lazy_blob(self):
        self.git(self.origin, 'config', 'uploadpack.allowFilter', 'true')
        result = self.read()
        self.assertEqual(result['records'], [self.record])

    def test_event_excludes_comments_and_remote_credentials(self):
        result = self.read()
        self.assertNotIn(self.record['Comment'], str(result['event']))
        self.assertNotIn(str(self.origin), str(result['event']))
        self.assertEqual(result['decision_effect'], 'NONE')

    def test_foreground_review_and_explicit_instruction_trigger_actual_read(self):
        binding = dict(repo=self.work, **self.kw)
        for purpose, explicit in [('review', False), ('development', True)]:
            result = source.read_for_purpose(purpose, git_binding=binding, explicit_review=explicit)
            self.assertTrue(result['read_executed'])
            self.assertEqual(result['records'], [self.record])
            self.assertFalse(result['agent_consumed'])

    def test_no_background_read_and_unbound_empty_are_distinct(self):
        with patch.object(source, 'read_git_reviews') as reader:
            self.assertEqual(source.read_for_purpose('development')['status'], 'NOT_REQUESTED')
            self.assertEqual(source.read_for_purpose('review')['status'], 'UNBOUND_EMPTY')
            reader.assert_not_called()
        with self.assertRaisesRegex(source.ReviewSourceError, 'REVIEW_NOT_BOUND'):
            source.read_for_purpose('review', rv_ids=[self.record['rv_id']])

    def test_foreground_bound_failure_propagates_not_empty(self):
        binding = dict(repo=self.work, **(self.kw | {'relative_path': '../unsafe'}))
        with self.assertRaises(source.ReviewSourceError):
            source.read_for_purpose('review', git_binding=binding)

    def test_working_head_movement_during_observation_refuses(self):
        actual = source._head
        count = 0
        def changing(repo):
            nonlocal count
            count += 1
            return actual(repo) if count == 1 else 'f' * 40
        with patch.object(source, '_head', side_effect=changing):
            with self.assertRaisesRegex(source.ReviewSourceError, 'REVIEW_SOURCE_CHANGED'):
                self.read()


if __name__ == '__main__':
    unittest.main(verbosity=2)
