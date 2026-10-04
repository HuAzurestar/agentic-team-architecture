#!/usr/bin/env python3
"""Application preflight with actual local Git remotes and target files."""
import copy
from dataclasses import replace
import sys
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import review_application as app
import review_comments as rv
import test_review_source as fixtures


class ApplicationTests(unittest.TestCase):
    git = fixtures.ReviewSourceTests.git
    read = fixtures.ReviewSourceTests.read
    publish = fixtures.ReviewSourceTests.publish

    def setUp(self):
        fixtures.ReviewSourceTests.setUp(self)
        (self.author / 'TARGET.md').write_bytes(b'original')
        self.git(self.author, 'add', 'TARGET.md')
        self.git(self.author, 'commit', '-qm', 'target')
        self.record['Basis']['git_basis'] = self.git(self.author, 'rev-parse', 'HEAD').strip()
        self.publish(self.record)
        self.sync()
        self.observed = self.read()
        self.binding = dict(repo=self.work, **self.kw)
        self.samples = {'repo:target': app.GitSampleBinding(self.work, 'TARGET.md', self.git(self.work, 'rev-parse', 'HEAD').strip(), 'TARGET.md', 'F1')}

    def sync(self):
        self.git(self.work, 'fetch', '-q', 'origin', 'master')
        self.git(self.work, 'merge', '--ff-only', '-q', 'FETCH_HEAD')

    def assess(self, **changes):
        return app.assess_application(self.binding, self.observed, **(dict(
            expected_working_head=self.git(self.work, 'rev-parse', 'HEAD').strip(), expected_branch='master',
            samples=self.samples, authorized=True, authority_source_ref='fixture:authorization') | changes))

    def test_exact_sample_and_contained_master_pass_without_writes(self):
        before = self.git(self.work, 'show-ref'), (self.work / 'TARGET.md').read_bytes()
        result = self.assess()
        self.assertTrue(result['preflight_passed'], result)
        self.assertEqual(result['effect'], 'NOT_APPLIED')
        self.assertFalse(result['merge_authorized'])
        self.assertEqual(before, (self.git(self.work, 'show-ref'), (self.work / 'TARGET.md').read_bytes()))

    def test_missing_or_string_authority_stops_before_source_reads(self):
        for authority in (False, 'true', 1):
            with patch.object(app, 'read_git_reviews', side_effect=AssertionError('should not read')):
                self.assertIn('AUTHORITY_REQUIRED', self.assess(authorized=authority)['reason_codes'])

    def test_dirty_worktree_cannot_apply_readable_review(self):
        path = self.work / 'TARGET.md'
        path.write_bytes(b'UNSAVED')
        self.assertIn('DIRTY_WORKTREE', self.assess()['reason_codes'])
        self.assertEqual(path.read_bytes(), b'UNSAVED')

    def test_missing_master_requires_exact_sync_and_does_not_merge(self):
        self.record['Comment'] = 'new review'
        master = self.publish(self.record)
        self.observed = self.read()
        before = self.git(self.work, 'rev-parse', 'HEAD')
        result = self.assess()
        self.assertIn('MASTER_SYNC_REQUIRED', result['reason_codes'])
        self.assertEqual(result['required_actions'][0]['sha'], master)
        self.assertEqual(before, self.git(self.work, 'rev-parse', 'HEAD'))

    def test_changed_original_requires_recheck_not_auto_resolution(self):
        (self.author / 'TARGET.md').write_bytes(b'revised')
        self.git(self.author, 'add', 'TARGET.md')
        self.git(self.author, 'commit', '-qm', 'revise target')
        self.git(self.author, 'push', '-q', 'origin', 'master')
        self.sync()
        self.observed = self.read()
        self.samples['repo:target'] = app.GitSampleBinding(self.work, 'TARGET.md', self.git(self.work, 'rev-parse', 'HEAD').strip(), 'TARGET.md', 'F1')
        before = copy.deepcopy(self.observed)
        result = self.assess()
        self.assertIn('BASIS_NEEDS_RECHECK', result['reason_codes'])
        self.assertTrue(result['sample_checks'][0]['diff'])
        self.assertEqual(self.observed, before)

    def test_edited_observation_cannot_replace_authoritative_comment(self):
        self.observed['records'][0]['Basis']['source_text'] = 'forged'
        self.assertIn('REVIEW_CONTENT_CHANGED', self.assess()['reason_codes'])

    def test_remote_advance_invalidates_saved_observation(self):
        self.record['Comment'] = 'new'
        self.publish(self.record)
        self.assertIn('REVIEW_SOURCE_CHANGED', self.assess()['reason_codes'])

    def test_target_binding_is_not_taken_from_uploaded_comment(self):
        self.assertIn('SAMPLE_SOURCE_UNVERIFIED', self.assess(samples={})['reason_codes'])

    def test_wrong_expected_head_or_branch_refused(self):
        self.assertIn('WORKING_REF_CHANGED', self.assess(expected_working_head='f'*40)['reason_codes'])
        self.assertIn('WORKING_REF_CHANGED', self.assess(expected_branch='other')['reason_codes'])

    def test_event_contains_no_body_or_diff(self):
        result = self.assess()
        self.assertNotIn('original', str(result['event']))
        self.assertNotIn('diff', result['event'])

    def test_wrong_target_binding_cannot_reuse_same_text(self):
        changed = replace(self.samples['repo:target'], target_ref='OTHER.md')
        self.assertIn('SAMPLE_TARGET_MISMATCH', self.assess(samples={'repo:target': changed})['reason_codes'])

    def test_claimed_basis_text_must_match_actual_historical_object(self):
        self.record['Basis']['source_text'] = 'invented historical text'
        self.publish(self.record)
        self.sync()
        self.observed = self.read()
        self.samples['repo:target'] = replace(self.samples['repo:target'], expected_head=self.git(self.work, 'rev-parse', 'HEAD').strip())
        self.assertIn('BASIS_PROVENANCE_MISMATCH', self.assess()['reason_codes'])

    def test_missing_basis_version_remains_unverified(self):
        self.record['Basis'].pop('git_basis')
        self.publish(self.record)
        self.sync()
        self.observed = self.read()
        self.samples['repo:target'] = replace(self.samples['repo:target'], expected_head=self.git(self.work, 'rev-parse', 'HEAD').strip())
        self.assertIn('BASIS_VERSION_UNVERIFIED', self.assess()['reason_codes'])

    def test_unique_sample_budget_refuses_before_passing(self):
        with patch.object(app, 'MAX_BYTES', 1):
            self.assertIn('RESOURCE_LIMIT', self.assess()['reason_codes'])

    def test_cleanliness_uses_checkout_configuration_without_index_writes(self):
        index = self.work / '.git' / 'index'
        before = index.read_bytes()
        with patch.object(app, '_run', wraps=app._run) as git_call:
            self.assertEqual(app._status(self.work.resolve()), b'')
        statuses = [call for call in git_call.call_args_list if 'status' in call.args]
        self.assertTrue(statuses)
        self.assertTrue(all(call.kwargs.get('configured') is True for call in statuses))
        self.assertEqual(index.read_bytes(), before)

    def test_exact_line_sample_is_checked_against_history_and_current(self):
        self.record['Basis'].update(line_start=1, line_end=1)
        self.publish(self.record)
        self.sync()
        self.observed = self.read()
        self.samples['repo:target'] = replace(self.samples['repo:target'], expected_head=self.git(self.work, 'rev-parse', 'HEAD').strip())
        self.assertTrue(self.assess()['preflight_passed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
