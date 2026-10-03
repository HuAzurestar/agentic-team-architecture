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

    def delivery_remote(self):
        remote = tempfile.TemporaryDirectory()
        self.addCleanup(remote.cleanup)
        subprocess.check_call(['git', 'init', '--bare', '-q', remote.name])
        self.git('remote', 'set-url', 'origin', remote.name)
        self.git('push', '-q', 'origin', 'main')
        return replace(self.binding, expected_remote=remote.name)

    def test_delivery_reads_actual_remote_without_fetch_or_index_write(self):
        binding = self.delivery_remote()
        before = self.git('show-ref'), (self.root / '.git/index').read_bytes()
        result = quality.observe_delivery(binding, 'pre_accept')
        self.assertTrue(result['valid'], result)
        self.assertTrue(result['remote_target_verified'])
        self.assertTrue(result['worktree_verified'])
        self.assertEqual(result['facts']['remote_target'], self.base)
        self.assertFalse(result['merge_authorized'])
        self.assertFalse(result['quality_assessed'])
        self.assertEqual(before, (self.git('show-ref'), (self.root / '.git/index').read_bytes()))
        self.assertFalse((self.root / '.git/FETCH_HEAD').exists())

    def test_delivery_remote_movement_not_hidden_by_stale_local_branch(self):
        binding = self.delivery_remote()
        self.git('push', '-q', 'origin', 'source:main')
        result = quality.observe_delivery(binding, 'pre_merge')
        self.assertEqual(result['reason_codes'], ['REMOTE_TARGET_MOVED'])
        self.assertFalse(result['remote_target_verified'])
        self.assertIsNone(result['facts'])

    def test_delivery_missing_remote_branch_is_not_empty_success(self):
        binding = self.delivery_remote()
        subprocess.check_call(['git', '--git-dir', binding.expected_remote, 'update-ref', '-d', 'refs/heads/main'])
        self.assertEqual(quality.observe_delivery(binding, 'pre_merge')['reason_codes'],
                         ['REMOTE_TARGET_UNAVAILABLE'])

    def test_delivery_unreachable_remote_does_not_echo_private_url(self):
        self.git('remote', 'set-url', 'origin', str(self.root / 'secret-unreachable'))
        binding = replace(self.binding, expected_remote=str(self.root / 'secret-unreachable'))
        result = quality.observe_delivery(binding, 'pre_merge')
        self.assertFalse(result['valid'])
        self.assertNotIn('secret-unreachable', str(result))

    def test_delivery_dirty_staged_and_untracked_preserved(self):
        binding = self.delivery_remote()
        for kind in ('unstaged', 'staged', 'untracked'):
            with self.subTest(kind=kind):
                path = self.root / ('new.txt' if kind == 'untracked' else 'file.txt')
                path.write_text('uncommitted', encoding='utf-8')
                if kind == 'staged':
                    self.git('add', 'file.txt')
                before = self.git('status', '--porcelain'), (self.root / '.git/index').read_bytes()
                result = quality.observe_delivery(binding, 'pre_merge')
                self.assertEqual(result['reason_codes'], ['WORKTREE_DIRTY'])
                self.assertEqual(path.read_text(), 'uncommitted')
                self.assertEqual(before, (self.git('status', '--porcelain'), (self.root / '.git/index').read_bytes()))
                if kind == 'untracked':
                    path.unlink()
                else:
                    self.git('restore', '--source=HEAD', '--staged', '--worktree', 'file.txt')

    def test_delivery_hidden_tracked_edits_are_not_clean(self):
        binding = self.delivery_remote()
        for flag in ('assume-unchanged', 'skip-worktree'):
            with self.subTest(flag=flag):
                self.git('update-index', '--' + flag, 'file.txt')
                (self.root / 'file.txt').write_text('hidden', encoding='utf-8')
                self.assertEqual(quality.observe_delivery(binding, 'pre_merge')['reason_codes'], ['HIDDEN_INDEX_STATE'])
                self.git('update-index', '--no-' + flag, 'file.txt')
                self.git('restore', 'file.txt')

    def test_delivery_wrong_checkout_or_detached_head_rejected(self):
        binding = self.delivery_remote()
        self.git('checkout', '-qb', 'other')
        self.assertEqual(quality.observe_delivery(binding, 'pre_merge')['reason_codes'], ['WORKING_BRANCH_MISMATCH'])
        self.git('checkout', '--detach', '-q', self.source)
        self.assertFalse(quality.observe_delivery(binding, 'pre_merge')['valid'])

    def test_delivery_clean_sequencer_is_still_in_progress(self):
        binding = self.delivery_remote()
        (self.root / '.git/sequencer').mkdir()
        self.assertEqual(quality.observe_delivery(binding, 'pre_merge')['reason_codes'], ['GIT_OPERATION_IN_PROGRESS'])

    def test_delivery_post_merge_requires_published_result(self):
        binding = self.delivery_remote()
        self.git('checkout', '-q', 'main')
        self.git('merge', '--no-ff', 'source', '-m', 'integrate')
        sha = self.git('rev-parse', 'HEAD')
        self.assertEqual(quality.observe_delivery(binding, 'post_merge', result_sha=sha)['reason_codes'], ['REMOTE_TARGET_MOVED'])
        self.git('push', '-q', 'origin', 'main')
        result = quality.observe_delivery(binding, 'post_merge', result_sha=sha)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['facts']['result_tree'], self.tree)

    def test_delivery_workspace_and_remote_races_fail_closed(self):
        binding = self.delivery_remote()
        original = quality._delivery_snapshot
        for kind in ('workspace', 'remote'):
            calls = []
            def observe(*args):
                snapshot = original(*args)
                calls.append(1)
                if len(calls) == 1:
                    if kind == 'workspace':
                        (self.root / 'file.txt').write_text('raced', encoding='utf-8')
                    else:
                        self.git('push', '-q', 'origin', 'source:main')
                return snapshot
            with self.subTest(kind=kind), patch.object(quality, '_delivery_snapshot', side_effect=observe):
                result = quality.observe_delivery(binding, 'pre_merge')
                self.assertFalse(result['valid'], result)
                self.assertFalse(result['worktree_verified'])
            if kind == 'workspace':
                self.git('restore', 'file.txt')

    def test_delivery_edit_during_last_remote_call_is_detected(self):
        binding = self.delivery_remote()
        original = quality._run
        calls = []
        def run(root, *args, **kwargs):
            result = original(root, *args, **kwargs)
            if args[0] == 'ls-remote':
                calls.append(1)
                if len(calls) == 2:
                    (self.root / 'file.txt').write_text('late edit', encoding='utf-8')
            return result
        with patch.object(quality, '_run', side_effect=run):
            result = quality.observe_delivery(binding, 'pre_merge')
        self.assertEqual(result['reason_codes'], ['WORKTREE_DIRTY'])

    def test_delivery_respects_crlf_checkout_without_refreshing_index(self):
        binding = self.delivery_remote()
        self.git('config', 'core.autocrlf', 'true')
        # Force a fresh configured checkout of a file containing a newline.
        self.commit('candidate\n')
        binding = replace(binding, source_sha=self.git('rev-parse', 'HEAD'),
                          source_tree=self.git('rev-parse', 'HEAD^{tree}'))
        (self.root / 'file.txt').unlink()
        self.git('checkout-index', '-f', '--', 'file.txt')
        before = (self.root / '.git/index').read_bytes()
        self.assertIn(b'\r\n', (self.root / 'file.txt').read_bytes())
        result = quality.observe_delivery(binding, 'pre_merge')
        self.assertTrue(result['valid'], result)
        self.assertEqual(before, (self.root / '.git/index').read_bytes())


if __name__ == '__main__':
    unittest.main()
