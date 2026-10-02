#!/usr/bin/env python3
"""Raw loader and full-validation boundary behavior; all sources are temporary."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import context_loader as cl
import task_context as tc
import test_task_context as fixture
import test_task_reconcile as git_fixture


class MemoryLoader:
    """Comparison provider supplies raw documents, never Git facts."""
    def __init__(self, root):
        self.root = root
        self.raw = {p.relative_to(root).as_posix(): p.read_bytes()
                    for p in root.rglob('*.md')}
        self.tasks = tuple(sorted(p for p in self.raw if p.startswith('tasks/')))
        self.reads = {}

    def list_task_paths(self, cursor=None, limit=200):
        offset = int(cursor or 0)
        end = min(offset + min(limit, 2), len(self.tasks))
        return cl.TaskPage(self.tasks[offset:end], str(end) if end < len(self.tasks) else None)

    def read(self, name):
        raw = self.raw[name]
        record = cl.DocumentRecord(name, raw.decode('utf-8'), 'memory:' + name,
                                   hashlib.sha256(raw).hexdigest(), len(raw))
        self.reads[name] = record
        return record

    def finish(self):
        return cl.ReadSetEvidence(self.tasks, tuple(sorted(
            (name, r.content_digest) for name, r in self.reads.items())),
            sum(r.byte_count for r in self.reads.values()))


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = fixture.TaskContextTests().make_feature(Path(self.temp.name))

    def error(self, code, action):
        with self.assertRaises(cl.LoaderError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_local_and_comparison_full_context_equivalent(self):
        before = self.snapshot()
        outputs = []
        for loader in (cl.LocalMarkdownLoader(self.root), MemoryLoader(self.root)):
            documents = cl.load_feature(loader)
            validated = tc.validate_feature(documents, tc.LocalGitProbe(self.root))
            outputs.append(tc.focus_context(validated))
            self.assertEqual(len(documents.records), 9)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(before, self.snapshot())

    def test_noncurrent_bad_dependency_fails_both_loaders(self):
        path = self.root / 'TASKS.md'
        path.write_text(path.read_text(encoding='utf-8').replace(
            '| human | REQ-001 |', '| human | UNKNOWN |'), encoding='utf-8')
        messages = []
        for loader in (cl.LocalMarkdownLoader(self.root), MemoryLoader(self.root)):
            with self.assertRaises(tc.ContextError) as caught:
                tc.validate_feature(cl.load_feature(loader), tc.LocalGitProbe(self.root))
            messages.append(str(caught.exception))
        self.assertEqual(messages[0], messages[1])
        self.assertIn('UNKNOWN', messages[0])

    def test_noncurrent_missing_detail_fails_both_loaders(self):
        (self.root / 'tasks/REQ-001.md').unlink()
        for loader in (cl.LocalMarkdownLoader(self.root), MemoryLoader(self.root)):
            self.error('INCOMPLETE_CONTEXT', lambda: cl.load_feature(loader))

    def test_comparison_provider_cannot_replace_local_authority(self):
        loader = MemoryLoader(self.root)
        loader.raw['gists/parser.md'] = b'Invented evidence.\n'
        documents = cl.load_feature(loader)
        self.error('SOURCE_MISMATCH', lambda: tc.validate_feature(
            documents, tc.LocalGitProbe(self.root)))

    def test_focus_performs_no_io(self):
        validated = tc.validate_feature(cl.load_feature(cl.LocalMarkdownLoader(self.root)),
                                        tc.LocalGitProbe(self.root))
        with patch.object(Path, 'open', side_effect=AssertionError('file I/O')), \
                patch.object(subprocess, 'run', side_effect=AssertionError('process I/O')):
            output = tc.focus_context(validated, structured=True)
        self.assertEqual(output['task']['id'], 'DEV-02')
        self.assertEqual(output['context_schema'], cl.SCHEMA)

    def test_raw_unicode_newline_bom_preserved(self):
        for raw in ('中文\r\nnext\rfinal\n', '\ufeff中文\r\n'):
            path = self.root / 'gists/parser.md'
            path.write_bytes(raw.encode('utf-8'))
            before = self.snapshot()
            record = cl.LocalMarkdownLoader(self.root).read('gists/parser.md')
            self.assertEqual(record.text, raw)
            self.assertEqual(record.legacy_text, path.read_text(encoding='utf-8'))
            local = tc.build_context(self.root)
            alternate = tc.focus_context(tc.validate_feature(
                cl.load_feature(MemoryLoader(self.root)), tc.LocalGitProbe(self.root)))
            self.assertEqual(local, alternate)
            self.assertEqual(before, self.snapshot())

    def test_invalid_utf8_rejected_without_rewrite(self):
        path = self.root / 'gists/parser.md'
        path.write_bytes(b'\xff')
        self.error('INVALID_ENCODING', lambda: cl.load_feature(cl.LocalMarkdownLoader(self.root)))
        self.assertEqual(path.read_bytes(), b'\xff')

    def test_paged_listing_covers_every_task_once(self):
        loader = cl.LocalMarkdownLoader(self.root)
        first = loader.list_task_paths(limit=2)
        second = loader.list_task_paths(first.next_cursor, limit=2)
        self.assertEqual(first.paths + second.paths, cl.enumerate_tasks(loader))
        self.assertIsNone(second.next_cursor)

    def test_invalid_cursor_and_page_size(self):
        loader = cl.LocalMarkdownLoader(self.root)
        for cursor in ('wrong', 'offset:9999', 'offset:-1'):
            self.error('INVALID_CURSOR', lambda: loader.list_task_paths(cursor))
        for limit in (0, 201, True):
            self.error('INVALID_CURSOR', lambda: loader.list_task_paths(limit=limit))

    def test_duplicate_and_nonadvancing_listing(self):
        loader = MemoryLoader(self.root)
        with patch.object(loader, 'list_task_paths', return_value=cl.TaskPage(
                ('tasks/REQ-001.md', 'tasks/REQ-001.md'), None)):
            self.error('DUPLICATE_IDENTITY', lambda: cl.enumerate_tasks(loader))
        with patch.object(loader, 'list_task_paths', return_value=cl.TaskPage((), 'same')):
            self.error('INCOMPLETE_CONTEXT', lambda: cl.enumerate_tasks(loader))

    def test_missing_finish_evidence_rejected(self):
        loader = MemoryLoader(self.root)
        with patch.object(loader, 'finish', return_value=cl.ReadSetEvidence((), (), 0, False)):
            self.error('INCOMPLETE_CONTEXT', lambda: cl.load_feature(loader))

    def test_forged_record_digest_rejected(self):
        loader = MemoryLoader(self.root)
        original = loader.read
        with patch.object(loader, 'read', side_effect=lambda name: replace(
                original(name), content_digest='0' * 64)):
            self.error('INCOMPLETE_CONTEXT', lambda: cl.load_feature(loader))

    def test_membership_change_before_finish_rejected(self):
        loader = cl.LocalMarkdownLoader(self.root)
        for name in cl.enumerate_tasks(loader):
            loader.read(name)
        (self.root / 'tasks/NEW.md').write_text('new', encoding='utf-8')
        self.error('SOURCE_CHANGED', loader.finish)

    def test_same_size_content_change_before_finish_rejected(self):
        loader = cl.LocalMarkdownLoader(self.root)
        for name in cl.enumerate_tasks(loader):
            loader.read(name)
        loader.read('gists/parser.md')
        path = self.root / 'gists/parser.md'
        path.write_bytes(b'X' * path.stat().st_size)
        self.error('SOURCE_CHANGED', loader.finish)

    def test_unread_enumerated_task_rejected(self):
        loader = cl.LocalMarkdownLoader(self.root)
        cl.enumerate_tasks(loader)
        self.error('INCOMPLETE_CONTEXT', loader.finish)

    def test_duplicate_hardlink_identity_rejected(self):
        path = self.root / 'gists/alias.md'
        os.link(self.root / 'gists/parser.md', path)
        loader = cl.LocalMarkdownLoader(self.root)
        loader.read('gists/parser.md')
        self.error('DUPLICATE_IDENTITY', lambda: loader.read('gists/alias.md'))

    def test_unsafe_paths_rejected(self):
        for name in ('../outside', '/absolute', 'C:/absolute', 'gists\\x',
                     'gists//x', './TASKS.md', '/'.join(['x'] * 9), 'gists/\x00.md'):
            with self.subTest(name=name):
                self.error('UNSAFE_PATH', lambda: cl.safe_relative(name))

    def test_document_and_byte_limits(self):
        with patch.object(cl, 'MAX_DOCUMENTS', 2):
            self.error('RESOURCE_LIMIT', lambda: cl.load_feature(MemoryLoader(self.root)))
        with patch.object(cl, 'MAX_BYTES', 5):
            self.error('RESOURCE_LIMIT', lambda: cl.LocalMarkdownLoader(self.root).read('TASKS.md'))

    def test_unknown_schema_rejected(self):
        documents = replace(cl.load_feature(cl.LocalMarkdownLoader(self.root)),
                            context_schema='lfd-context-v999')
        self.error('UNSUPPORTED_SCHEMA', lambda: tc.validate_feature(
            documents, tc.LocalGitProbe(self.root)))

    def test_malformed_provider_fields_fail_with_diagnostic(self):
        for fields, code in (({'text': None}, 'INCOMPLETE_CONTEXT'),
                             ({'source_key': []}, 'INCOMPLETE_CONTEXT'),
                             ({'text': '\ud800'}, 'INVALID_ENCODING')):
            loader = MemoryLoader(self.root)
            original = loader.read
            with self.subTest(fields=fields), patch.object(
                    loader, 'read', side_effect=lambda name: replace(original(name), **fields)):
                self.error(code, lambda: cl.load_feature(loader))
        loader = MemoryLoader(self.root)
        for page in (cl.TaskPage(None, None), cl.TaskPage((), [])):
            with patch.object(loader, 'list_task_paths', return_value=page):
                self.error('INCOMPLETE_CONTEXT', lambda: cl.enumerate_tasks(loader))

    def test_finish_computation_is_included_in_budget(self):
        loader = MemoryLoader(self.root)
        original = loader.finish
        elapsed = [0.0]

        def expensive_finish():
            elapsed[0] = cl.MAX_COMPUTE_SECONDS + 1
            return original()

        with patch.object(loader, 'finish', side_effect=expensive_finish), \
                patch.object(cl.time, 'process_time', side_effect=lambda: elapsed[0]):
            self.error('RESOURCE_LIMIT', lambda: cl.load_feature(loader))


class GitLoaderTests(unittest.TestCase):
    setUp = git_fixture.RecoveryTests.setUp
    commit_records = git_fixture.RecoveryTests.commit_records

    def test_comparison_loader_uses_actual_git_refs(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*.md')}
        outputs = []
        for loader in (cl.LocalMarkdownLoader(self.root), MemoryLoader(self.root)):
            outputs.append(tc.focus_context(tc.validate_feature(
                cl.load_feature(loader), tc.LocalGitProbe(self.root))))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1]['repositories']['app']['actual_head'], self.app_head)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*.md')})
        self.assertEqual(fixture.git(self.pm, 'status', '--porcelain'), '')
        self.assertEqual(fixture.git(self.app, 'status', '--porcelain'), '')

    def test_actual_git_advance_is_not_hidden_by_cached_documents(self):
        documents = cl.load_feature(MemoryLoader(self.root))
        fixture.git(self.app, 'commit', '--allow-empty', '-m', 'advance after loading')
        with self.assertRaises(tc.ContextError):
            tc.validate_feature(documents, tc.LocalGitProbe(self.root))

    def test_source_change_during_git_validation_is_rejected(self):
        documents = cl.load_feature(MemoryLoader(self.root))
        original = tc.validate_trace_graph

        def change_after_probe(*args, **kwargs):
            result = original(*args, **kwargs)
            path = self.root / 'gists/parser.md'
            path.write_bytes(b'X' * path.stat().st_size)
            return result

        with patch.object(tc, 'validate_trace_graph', side_effect=change_after_probe):
            with self.assertRaises(cl.LoaderError) as caught:
                tc.validate_feature(documents, tc.LocalGitProbe(self.root))
        self.assertEqual(caught.exception.code, 'SOURCE_CHANGED')


if __name__ == '__main__':
    unittest.main()
