#!/usr/bin/env python3
"""Real repository source tests, not independent reviewer/human authentication."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import quality_source as source


class SourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'core.autocrlf', 'false')
        self.path = self.root / 'report.md'
        self.body = b'# Report\n\n```report-v1\n{"schema":"report-v1","checks":[]}\n```\n'
        self.path.write_bytes(self.body)
        self.git('add', 'report.md')
        self.git('commit', '-qm', 'fixture')
        self.binding = source.GitDocument('gists/report.md', self.root, 'report.md', self.git('rev-parse', 'HEAD').strip())

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL, text=True)

    def read(self, *bindings):
        return source.read_git_documents(bindings or (self.binding,))

    def test_actual_bytes_versions_and_no_writes(self):
        index = (self.root / '.git/index').read_bytes()
        refs = self.git('show-ref')
        result = self.read()
        self.assertEqual(result.documents[self.binding.logical_path], self.body)
        self.assertEqual(result.versions[self.binding.logical_path][0], self.binding.expected_head)
        self.assertIn((self.binding.logical_path, hashlib.sha256(self.body).hexdigest()), result.source_refs)
        self.assertEqual(result.object(self.binding.logical_path, 'report-v1')['checks'], [])
        self.assertEqual(index, (self.root / '.git/index').read_bytes())
        self.assertEqual(refs, self.git('show-ref'))
        self.assertFalse((self.root / '.git/FETCH_HEAD').exists())
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_snapshot_is_immutable_and_parsed_objects_are_fresh(self):
        result = self.read()
        with self.assertRaises(TypeError):
            result.documents['gists/report.md'] = b'fake'
        parsed = result.object('gists/report.md', 'report-v1')
        parsed['checks'].append('fake PASS')
        self.assertEqual(result.object('gists/report.md', 'report-v1')['checks'], [])
        self.assertFalse(hasattr(result, 'independent_reports'))

    def test_worktree_change_refuses(self):
        self.path.write_bytes(b'changed')
        with self.assertRaisesRegex(source.SourceError, 'SOURCE_DIRTY'):
            self.read()

    def test_complete_policy_object_must_equal_actual_source(self):
        result = self.read()
        actual = result.object('gists/report.md', 'report-v1')
        self.assertEqual(result.require_object('gists/report.md', 'report-v1', actual), actual)
        actual['checks'] = [{'outcome': 'PASS'}]
        with self.assertRaisesRegex(source.SourceError, 'SOURCE_OBJECT_MISMATCH'):
            result.require_object('gists/report.md', 'report-v1', actual)

    def test_multiple_sources_use_one_aggregate_budget(self):
        second = self.root / 'second.md'
        second.write_bytes(b'x' * 1024)
        self.git('add', 'second.md')
        self.git('commit', '-qm', 'second')
        head = self.git('rev-parse', 'HEAD').strip()
        first = replace(self.binding, expected_head=head)
        other = replace(first, logical_path='gists/second.md', relative_path='second.md')
        self.assertEqual(len(self.read(first, other).source_refs), 2)
        with patch.object(source, 'MAX_BYTES', 1050), self.assertRaisesRegex(source.SourceError, 'RESOURCE_LIMIT'):
            self.read(first, other)

    def test_index_change_during_read_is_detected(self):
        original = source.LocalMarkdownLoader._read_raw
        def raced(loader, name, limit):
            value = original(loader, name, limit)
            self.path.write_bytes(b'new staged material')
            self.git('add', 'report.md')
            self.path.write_bytes(self.body)
            return value
        with patch.object(source.LocalMarkdownLoader, '_read_raw', raced), self.assertRaisesRegex(source.SourceError, 'SOURCE_CHANGED'):
            self.read()

    def test_index_only_change_refuses(self):
        self.path.write_bytes(b'changed')
        self.git('add', 'report.md')
        self.path.write_bytes(self.body)
        with self.assertRaisesRegex(source.SourceError, 'SOURCE_DIRTY'):
            self.read()

    def test_stale_head_refuses(self):
        self.git('commit', '--allow-empty', '-qm', 'moved')
        with self.assertRaisesRegex(source.SourceError, 'SOURCE_CHANGED'):
            self.read()

    def test_checkout_crlf_has_exact_working_byte_digest(self):
        changed = self.body.replace(b'\n', b'\r\n')
        self.path.write_bytes(changed)
        result = self.read()
        self.assertIn(('gists/report.md', hashlib.sha256(changed).hexdigest()), result.source_refs)
        self.assertEqual(result.object('gists/report.md', 'report-v1')['checks'], [])

    def test_duplicate_logical_or_physical_source_refuses(self):
        for second in (self.binding, replace(self.binding, logical_path='gists/alias.md')):
            with self.subTest(second=second.logical_path), self.assertRaisesRegex(source.SourceError, 'DUPLICATE_SOURCE'):
                self.read(self.binding, second)

    def test_untrusted_dict_or_bad_paths_refuse(self):
        with self.assertRaises(source.SourceError):
            self.read(vars(self.binding))
        for path in ('../outside', '.git/config', 'x/../report.md', '/report.md', 'x\\report.md'):
            with self.subTest(path=path), self.assertRaises(source.SourceError):
                self.read(replace(self.binding, relative_path=path))

    def test_missing_source_is_error_not_empty(self):
        with self.assertRaises(source.SourceError):
            self.read(replace(self.binding, relative_path='missing.md'))

    def test_hardlinked_source_refuses(self):
        os.link(self.path, self.root / 'alias.md')
        with self.assertRaisesRegex(source.SourceError, 'UNSAFE_PATH'):
            self.read()

    def test_git_environment_cannot_redirect_repository(self):
        with patch.dict(os.environ, {'GIT_DIR': str(self.root / 'absent'), 'GIT_WORK_TREE': str(self.root / 'absent')}):
            self.assertEqual(self.read().documents['gists/report.md'], self.body)

    def test_duplicate_json_or_multiple_fences_refuse(self):
        for body in (b'{"schema":"report-v1","schema":"report-v1"}', self.body + self.body):
            self.path.write_bytes(body)
            self.git('add', 'report.md')
            self.git('commit', '-qm', 'invalid source')
            binding = replace(self.binding, expected_head=self.git('rev-parse', 'HEAD').strip())
            result = self.read(binding)
            with self.assertRaisesRegex(source.SourceError, 'INVALID_SOURCE_OBJECT'):
                result.object('gists/report.md', 'report-v1')

    def test_whole_set_reread_detects_change(self):
        original, calls = source.LocalMarkdownLoader._read_raw, []
        def raced(loader, name, limit):
            value = original(loader, name, limit)
            calls.append(name)
            if len(calls) == 1:
                self.path.write_bytes(self.body.replace(b'Report', b'Change'))
            return value
        with patch.object(source.LocalMarkdownLoader, '_read_raw', raced), self.assertRaisesRegex(source.SourceError, 'SOURCE_CHANGED'):
            self.read()

    def test_aggregate_byte_and_document_limits(self):
        with patch.object(source, 'MAX_BYTES', 8), self.assertRaisesRegex(source.SourceError, 'RESOURCE_LIMIT'):
            self.read()
        with patch.object(source, 'MAX_DOCUMENTS', 0), self.assertRaises(source.SourceError):
            self.read()

    def test_actual_symlink_blob_refuses_without_following(self):
        blob = subprocess.check_output(['git', '-C', str(self.root), 'hash-object', '-w', '--stdin'], input=b'outside').decode().strip()
        self.git('update-index', '--cacheinfo', '120000', blob, 'report.md')
        self.git('commit', '-qm', 'link blob')
        binding = replace(self.binding, expected_head=self.git('rev-parse', 'HEAD').strip())
        with self.assertRaisesRegex(source.SourceError, 'UNSAFE_PATH'):
            self.read(binding)


if __name__ == '__main__':
    unittest.main()
