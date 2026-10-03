#!/usr/bin/env python3
"""Real Git ancestry/tree checks, not independent review or acceptance."""
import sys
sys.dont_write_bytecode = True
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import quality_git as quality


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('remote', 'add', 'origin', 'https://example.invalid/fixture.git')
        self.commit('base')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-qb', 'source')
        self.commit('candidate')
        self.source = self.git('rev-parse', 'HEAD')
        self.tree = self.git('rev-parse', 'HEAD^{tree}')
        self.binding = quality.IntegrationBinding(self.root, 'app', 'origin',
            'https://example.invalid/fixture.git', 'source', self.source, self.tree, 'main', self.base)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def commit(self, body):
        (self.root / 'file.txt').write_text(body, encoding='utf-8')
        self.git('add', 'file.txt')
        self.git('commit', '-qm', body)

    def test_pre_merge_actual_candidate_without_mutation_or_permission(self):
        before = self.git('show-ref')
        result = quality.observe_integration(self.binding, 'pre_merge')
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['facts']['source_tree'], self.tree)
        self.assertEqual(self.git('show-ref'), before)
        self.assertFalse(result['merge_authorized'])
        self.assertFalse(result['quality_assessed'])
        self.assertFalse(result['remote_target_verified'])

    def test_normal_merge_maps_accepted_source_to_new_result(self):
        self.git('checkout', '-q', 'main')
        self.git('merge', '--no-ff', 'source', '-m', 'integrate')
        result_sha = self.git('rev-parse', 'HEAD')
        self.assertNotEqual(result_sha, self.source)
        result = quality.observe_integration(self.binding, 'post_merge', result_sha=result_sha)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['facts']['result_tree'], self.tree)

    def test_fast_forward_is_valid_correspondence(self):
        self.git('checkout', '-q', 'main')
        self.git('merge', '--ff-only', 'source')
        self.assertTrue(quality.observe_integration(self.binding, 'post_merge', result_sha=self.source)['valid'])

    def test_moved_source_or_target_is_not_old_candidate(self):
        self.commit('new source')
        self.assertEqual(quality.observe_integration(self.binding, 'pre_merge')['reason_codes'], ['SOURCE_MOVED'])
        fresh = replace(self.binding, source_sha=self.git('rev-parse', 'HEAD'), source_tree=self.git('rev-parse', 'HEAD^{tree}'))
        self.git('checkout', '-q', 'main')
        self.commit('changed target')
        self.assertEqual(quality.observe_integration(fresh, 'pre_merge')['reason_codes'], ['TARGET_MOVED'])

    def test_target_not_integrated_into_candidate_is_rejected(self):
        self.git('checkout', '-q', 'main')
        self.commit('advanced base')
        current = replace(self.binding, target_before=self.git('rev-parse', 'HEAD'))
        self.assertEqual(quality.observe_integration(current, 'pre_merge')['reason_codes'], ['TARGET_NOT_IN_CANDIDATE'])

    def test_squash_identical_tree_does_not_inherit_acceptance(self):
        self.git('checkout', '-q', 'main')
        self.git('merge', '--squash', 'source')
        self.git('commit', '-qm', 'squash')
        result = self.git('rev-parse', 'HEAD')
        self.assertEqual(self.git('rev-parse', 'HEAD^{tree}'), self.tree)
        self.assertEqual(quality.observe_integration(self.binding, 'post_merge', result_sha=result)['reason_codes'],
                         ['RESULT_ANCESTRY_CHANGED'])

    def test_changed_result_tree_is_not_equivalent(self):
        self.git('checkout', '-q', 'main')
        self.git('merge', '--ff-only', 'source')
        self.commit('extra change')
        result = quality.observe_integration(self.binding, 'post_merge', result_sha=self.git('rev-parse', 'HEAD'))
        self.assertEqual(result['reason_codes'], ['RESULT_TREE_CHANGED'])

    def test_fabricated_tree_and_wrong_repository_fail_closed(self):
        self.assertFalse(quality.observe_integration(replace(self.binding, source_tree='a' * 40), 'pre_merge')['valid'])
        self.assertFalse(quality.observe_integration(replace(self.binding, expected_remote='other'), 'pre_merge')['valid'])
        self.assertFalse(quality.observe_integration(dict(), 'pre_merge')['valid'])
        self.assertFalse(quality.observe_integration(self.binding, 'post_merge')['valid'])

    def test_ref_race_after_first_snapshot_is_detected(self):
        original = quality._snapshot
        calls = []
        def observe(root, binding):
            snapshot = original(root, binding)
            calls.append(1)
            if len(calls) == 1:
                self.git('update-ref', 'refs/heads/main', self.source)
            return snapshot
        with patch.object(quality, '_snapshot', side_effect=observe):
            result = quality.observe_integration(self.binding, 'pre_merge')
        self.assertEqual(result['reason_codes'], ['REF_MOVED_DURING_READ'])

    def test_local_grafts_cannot_fabricate_ancestry(self):
        path = self.root / '.git/info/grafts'
        path.write_text(self.base + ' ' + self.source + '\n', encoding='ascii')
        self.assertEqual(quality.observe_integration(self.binding, 'pre_merge')['reason_codes'],
                         ['GRAFTED_HISTORY_UNSUPPORTED'])

    def test_unknown_phase_not_echoed_into_event(self):
        result = quality.observe_integration(self.binding, 'untrusted-secret')
        self.assertIsNone(result['event']['phase'])
        self.assertFalse(result['valid'])


if __name__ == '__main__':
    unittest.main()
