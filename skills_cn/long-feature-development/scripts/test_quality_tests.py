#!/usr/bin/env python3
"""Concentrated real-Git semantic applicability; host coverage is synthetic."""
from dataclasses import replace
from pathlib import Path
import tempfile
import sys
import unittest
sys.dont_write_bytecode = True
import quality_tests as qt
from test_task_context import git


class ImpactTests(unittest.TestCase):
    def test_content_and_used_dependency_changes_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, 'init', '-q')
            git(root, 'config', 'user.name', 'Fixture')
            git(root, 'config', 'user.email', 'fixture@example.invalid')
            (root / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
            (root / 'requirements.txt').write_text('', encoding='utf-8')
            (root / 'plugins').mkdir()
            (root / 'plugins/initial.py').write_text('VALUE = 1\n', encoding='utf-8')
            git(root, 'add', '.')
            git(root, 'commit', '-qm', 'baseline')
            baseline = git(root, 'rev-parse', 'HEAD')
            git(root, 'commit', '--allow-empty', '-qm', 'metadata-only commit')
            empty = git(root, 'rev-parse', 'HEAD')
            self.assertNotEqual(baseline, empty)
            self.assertEqual('UNCHANGED_TREE', qt.observe_impact(root, baseline, empty))

            # Added but neither imported nor discovered: not a semantic change.
            (root / 'unused.py').write_text('VALUE = 2\n', encoding='utf-8')
            git(root, 'add', 'unused.py')
            git(root, 'commit', '-qm', 'unused addition')
            unused = git(root, 'rev-parse', 'HEAD')
            self.assertEqual('UNVERIFIED_TEST_IMPACT', qt.observe_impact(root, baseline, unused))
            coverage = qt.TestCoverage('synthetic-test-digest', 'app',
                                       ('app.py', 'requirements.txt', 'plugins', 'optional-config.json'),
                                       'fixture:verified-closure-and-runtime')
            self.assertEqual('UNCHANGED_VERIFIED_INPUTS',
                             qt.observe_impact(root, baseline, unused, coverage=coverage))

            # The same module becomes used: the import changes the input closure.
            (root / 'app.py').write_text('from unused import VALUE\n', encoding='utf-8')
            git(root, 'add', 'app.py')
            git(root, 'commit', '-qm', 'used dependency')
            used = git(root, 'rev-parse', 'HEAD')
            self.assertEqual('TEST_INPUTS_CHANGED', qt.observe_impact(root, unused, used, coverage=coverage))

            # Discovery additions and previously absent config inputs also count.
            for relative in ('plugins/new.py', 'optional-config.json'):
                before = git(root, 'rev-parse', 'HEAD')
                (root / relative).write_text('{}\n', encoding='utf-8')
                git(root, 'add', relative)
                git(root, 'commit', '-qm', 'semantic input addition')
                after = git(root, 'rev-parse', 'HEAD')
                self.assertEqual('TEST_INPUTS_CHANGED', qt.observe_impact(root, before, after, coverage=coverage))
            with self.assertRaises(ValueError):
                qt.observe_impact(root, baseline, used, coverage=coverage.__dict__)
            with self.assertRaises(ValueError):
                qt.observe_impact(root, baseline, used, coverage=replace(coverage, paths=('../app.py',)))


if __name__ == '__main__':
    unittest.main()
