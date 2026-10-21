#!/usr/bin/env python3
"""Runtime profile IO and unchanged-instruction migration experiments."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
sys.dont_write_bytecode = True
import runtime_state as state


def pm_profile(root, runtime='A', revision='r1'):
    return {'profile': 'pm', 'revision': revision, 'runtime identity': runtime,
            'management roots': {'main': str(root / 'pm')}, 'selected root': 'main',
            'project registry': str(root / 'pm' / 'project'), 'state writer reference': 'filesystem',
            'commit policy reference': 'policy/no-implicit-commit', 'environment references': {}}


def notify_profile(root, runtime='A', revision='r1'):
    return {'profile': 'notify', 'revision': revision, 'runtime identity': runtime,
            'adapter tool reference': 'fixture-delivery', 'routes': {'review': {'receiver': 'fixture'}},
            'credential references': [], 'workflow event bindings': {'*': 'review'},
            'delivery state reference': str(root / 'delivery'), 'reply correlation contract': 'event-and-version',
            'failure handling reference': 'retain-without-retry'}


class RuntimeStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'runtime'

    def test_explicit_bootstrap_no_guessed_root_or_identity(self):
        with self.assertRaises(state.StateError):
            state.configure('relative', 'A', 'project-management', pm_profile(self.root))
        with self.assertRaises(state.StateError):
            state.configure(self.config, 'B', 'project-management', pm_profile(self.root))
        self.assertFalse(self.config.exists())

    def test_roundtrip_history_and_revision_compare_and_swap(self):
        first = pm_profile(self.root)
        state.configure(self.config, 'A', 'project-management', first)
        self.assertEqual(state.resolve(self.config, 'A', 'project-management')['profile'], first)
        second = pm_profile(self.root, revision='r2')
        with self.assertRaisesRegex(state.StateError, 'revision conflict'):
            state.configure(self.config, 'A', 'project-management', second, 'stale')
        state.configure(self.config, 'A', 'project-management', second, 'r1')
        self.assertEqual(state.read_yaml(self.config / 'history/project-management/r1.yaml'), first)
        with self.assertRaises(state.StateError):
            state.configure(self.config, 'A', 'project-management', first, 'r2')
        self.assertEqual(state.resolve(self.config, 'A', 'project-management')['profile'], second)

    def test_same_revision_cannot_overwrite_and_exact_replay_is_noop(self):
        record = pm_profile(self.root)
        state.configure(self.config, 'A', 'project-management', record)
        self.assertFalse(state.configure(self.config, 'A', 'project-management', record, 'r1')['changed'])
        modified = copy.deepcopy(record)
        modified['commit policy reference'] = 'other'
        with self.assertRaisesRegex(state.StateError, 'same revision'):
            state.configure(self.config, 'A', 'project-management', modified, 'r1')

    def test_same_revision_json_boolean_and_integer_are_distinct(self):
        record = pm_profile(self.root)
        record['environment references'] = {'fixture flag': True}
        state.configure(self.config, 'A', 'project-management', record)
        changed = copy.deepcopy(record)
        changed['environment references']['fixture flag'] = 1
        with self.assertRaisesRegex(state.StateError, 'same revision'):
            state.configure(self.config, 'A', 'project-management', changed, 'r1')
        self.assertIs(state.resolve(self.config, 'A', 'project-management')['profile']['environment references']['fixture flag'], True)

    def test_lock_conflict_does_not_change_existing_data(self):
        record = pm_profile(self.root)
        state.configure(self.config, 'A', 'project-management', record)
        original = (self.config / 'project-management.yaml').read_bytes()
        with state.locked(self.config):
            with self.assertRaisesRegex(state.StateError, 'concurrent writer'):
                state.configure(self.config, 'A', 'project-management', pm_profile(self.root, revision='r2'), 'r1')
        self.assertEqual((self.config / 'project-management.yaml').read_bytes(), original)

    def test_independent_missing_profiles_do_not_fallback(self):
        state.configure(self.config, 'A', 'notification', notify_profile(self.root))
        with self.assertRaises(state.StateError):
            state.resolve(self.config, 'A', 'project-management')
        self.assertEqual(state.resolve(self.config, 'A', 'notification')['profile']['profile'], 'notify')

    def test_instruction_migration_uses_destination_bindings(self):
        instruction = b'Resolve explicit runtime profiles; perform assigned work.'
        before = instruction[:]
        for name in ('A', 'B'):
            location = self.root / name
            state.configure(location, name, 'project-management', pm_profile(location, name))
            state.configure(location, name, 'notification', notify_profile(location, name))
        a = state.resolve(self.root / 'A', 'A', 'project-management')['profile']
        b = state.resolve(self.root / 'B', 'B', 'project-management')['profile']
        self.assertNotEqual(a['management roots'], b['management roots'])
        self.assertEqual(instruction, before)
        with self.assertRaises(state.StateError):
            state.resolve(self.root / 'A', 'B', 'notification')

    def test_paths_and_revision_cannot_escape(self):
        for field in ('project registry',):
            record = pm_profile(self.root)
            record[field] = './guess'
            with self.assertRaises(state.StateError):
                state.configure(self.config, 'A', 'project-management', record)
        record = pm_profile(self.root)
        record['revision'] = '../escape'
        with self.assertRaises(state.StateError):
            state.configure(self.config, 'A', 'project-management', record)

    def test_duplicate_yaml_keys_rejected(self):
        path = self.root / 'bad.yaml'
        path.write_text('profile: a\nprofile: b\n', encoding='utf-8')
        with self.assertRaises(state.StateError):
            state.read_yaml(path)

    def test_interrupted_profile_writes_recover_without_overwriting_history(self):
        first = pm_profile(self.root)
        state.configure(self.config, 'A', 'project-management', first)
        for failure_name in ('r2.yaml', 'project-management.yaml'):
            with self.subTest(failure_name=failure_name):
                root = self.root / failure_name.replace('.', '-')
                state.configure(root, 'A', 'project-management', first)
                second = pm_profile(self.root, revision='r2')
                writer = state.atomic_write
                def interrupted(path, text):
                    if path.name == failure_name:
                        raise OSError('fixture interrupted write')
                    writer(path, text)
                with patch.object(state, 'atomic_write', side_effect=interrupted):
                    with self.assertRaises(OSError):
                        state.configure(root, 'A', 'project-management', second, 'r1')
                self.assertEqual(state.resolve(root, 'A', 'project-management')['profile'], first)
                state.configure(root, 'A', 'project-management', second, 'r1')
                self.assertEqual(state.resolve(root, 'A', 'project-management')['profile'], second)
                self.assertEqual(state.read_yaml(root / 'history/project-management/r1.yaml'), first)

    def test_cli_configure_then_restart_resolve(self):
        source = self.root / 'profile.yaml'
        source.write_text(yaml.safe_dump(pm_profile(self.root)), encoding='utf-8')
        command = [sys.executable, '-B', str(Path(state.__file__).resolve()), '--state-root', str(self.config), '--runtime-id', 'A']
        configured = subprocess.run(command + ['configure', '--kind', 'project-management', '--input', str(source)], capture_output=True, text=True)
        self.assertEqual(configured.returncode, 0, configured.stdout + configured.stderr)
        result = subprocess.run(command + ['resolve', '--kind', 'project-management'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['profile'], pm_profile(self.root))
        self.assertEqual(json.loads(result.stdout)['access'], 'not checked')

if __name__ == '__main__':
    unittest.main()
