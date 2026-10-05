#!/usr/bin/env python3
"""Real Git source tests; synthetic host evidence is never human approval."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import decision_source as source
import decision_evidence as decision


class GitDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'core.autocrlf', 'false')
        self.path = self.repo / 'REQUIREMENT.md'
        self.body = '# Requirements\n\n## REQ-1\n\nOriginal body.\n\n## REQ-2\n\nOther body.\n'
        self.path.write_bytes(self.body.encode())
        self.git('add', 'REQUIREMENT.md')
        self.git('commit', '-qm', 'fixture')
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.kw = dict(source_key='repo:fixture/REQUIREMENT.md', feature='FEATURE-1',
                       decision_kind='point', exact_scope=['REQ-1'], expected_head=self.head)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL, text=True)

    def read(self, **changes):
        return source.read_git_current(self.repo, 'REQUIREMENT.md', **(self.kw | changes))

    def record(self, material):
        return dict(schema='decision-evidence-v1', decision_id='D1',
                    **{k: copy.deepcopy(material[k]) for k in ('feature', 'decision_kind', 'target_ref', 'exact_scope')},
                    human_source_ref='conversation:fixture', actor='fixture-human',
                    received_at='2026-10-03T00:00:00Z', outcome='CONFIRMED',
                    original_reply='Confirm REQ-1.', approved_body=material['body'])

    def test_real_head_and_exact_point(self):
        material = self.read()
        self.assertEqual(material['target_ref']['version'], self.head)
        self.assertIn('Original body.', material['body'])
        self.assertNotIn('Other body.', material['body'])
        self.assertEqual(material['exact_scope'], ['REQ-1'])

    def test_actual_read_does_not_mint_human_authority(self):
        material = self.read()
        result = decision.check_decision(self.record(material), material)
        self.assertIn('HUMAN_SOURCE_UNVERIFIED', result['reason_codes'])

    def test_worktree_change_refuses_old_committed_material(self):
        self.path.write_text(self.body.replace('Original', 'Changed'), encoding='utf-8')
        with self.assertRaisesRegex(source.SourceError, 'SOURCE_DIRTY'):
            self.read()

    def test_staged_change_is_not_old_current_material(self):
        self.path.write_text('different', encoding='utf-8')
        self.git('add', 'REQUIREMENT.md')
        with self.assertRaises(source.SourceError):
            self.read()

    def test_new_head_requires_fresh_observation_and_stales_old_decision(self):
        raw = self.record(self.read())
        self.path.write_bytes(self.body.replace('Original', 'Changed').encode())
        self.git('add', 'REQUIREMENT.md')
        self.git('commit', '-qm', 'changed')
        with self.assertRaisesRegex(source.SourceError, 'SOURCE_CHANGED'):
            self.read()
        material = self.read(expected_head=self.git('rev-parse', 'HEAD').strip())
        result = decision.check_decision(raw, material)
        self.assertIn('DECISION_STALE', result['reason_codes'])
        self.assertTrue(result['diff'])

    def test_missing_or_duplicate_point_refuses(self):
        with self.assertRaises(source.SourceError):
            self.read(exact_scope=['REQ-404'])
        self.path.write_bytes((self.body + '\n## REQ-1\nDuplicate.\n').encode())
        self.git('add', 'REQUIREMENT.md')
        self.git('commit', '-qm', 'duplicate')
        with self.assertRaises(source.SourceError):
            self.read(expected_head=self.git('rev-parse', 'HEAD').strip())

    def test_parent_absolute_and_git_metadata_paths_refused(self):
        for name in ('../REQUIREMENT.md', str(self.path), '.git/config', 'a/../REQUIREMENT.md'):
            with self.subTest(name=name), self.assertRaises(source.SourceError):
                source.read_git_current(self.repo, name, **self.kw)

    def test_crlf_checkout_has_same_logical_body(self):
        before = self.read()
        self.path.write_bytes(self.body.replace('\n', '\r\n').encode())
        self.assertEqual(self.read(), before)

    def test_whole_acceptance_document_still_exact_scope(self):
        material = self.read(decision_kind='acceptance', exact_scope=['REQ-1', 'REQ-2'])
        self.assertEqual(material['body'], self.body)

    def test_missing_worktree_file_not_silently_read_from_history(self):
        self.path.unlink()
        with self.assertRaises(source.SourceError):
            self.read()

    def test_oversize_is_rejected(self):
        with patch.object(source, 'MAX_BYTES', 8):
            with self.assertRaisesRegex(source.SourceError, 'RESOURCE_LIMIT'):
                self.read()

    def test_source_read_is_non_mutating(self):
        before = self.git('status', '--porcelain=v1'), self.git('rev-parse', 'HEAD'), self.path.read_bytes()
        self.read()
        self.assertEqual(before, (self.git('status', '--porcelain=v1'), self.git('rev-parse', 'HEAD'), self.path.read_bytes()))

    def test_index_only_edit_cannot_hide_behind_restored_worktree(self):
        self.path.write_bytes(b'staged other content')
        self.git('add', 'REQUIREMENT.md')
        self.path.write_bytes(self.body.encode())
        with self.assertRaisesRegex(source.SourceError, 'SOURCE_DIRTY'):
            self.read()

    def test_git_environment_cannot_redirect_source(self):
        with patch.dict(os.environ, {'GIT_DIR': str(self.repo / 'missing-git'), 'GIT_INDEX_FILE': str(self.repo / 'missing-index')}):
            self.assertEqual(self.read()['target_ref']['version'], self.head)

    def test_mid_read_head_movement_is_refused(self):
        actual = source._git
        observations = 0
        def moved(repo, *args):
            nonlocal observations
            value = actual(repo, *args)
            if args == ('rev-parse', '--verify', 'HEAD'):
                observations += 1
                if observations == 2:
                    return b'f' * 40 + b'\n'
            return value
        with patch.object(source, '_git', side_effect=moved):
            with self.assertRaisesRegex(source.SourceError, 'SOURCE_CHANGED'):
                self.read()

    def test_fenced_and_quoted_headings_do_not_select_fake_point(self):
        text = '```md\n## REQ-1\nFake.\n```\n> ## REQ-1\n\n## REQ-1\nReal.\n\n## REQ-2\nOther.\n'
        self.assertEqual(source._point(text, 'REQ-1'), '## REQ-1\nReal.\n\n')

    def test_wildcard_path_is_not_expanded(self):
        with self.assertRaises(source.SourceError):
            source.read_git_current(self.repo, '*.md', **self.kw)

    def test_hardlink_is_not_an_independent_source(self):
        os.link(self.path, self.repo / 'alias.md')
        with self.assertRaises(source.SourceError):
            self.read()


if __name__ == '__main__':
    unittest.main(verbosity=2)
