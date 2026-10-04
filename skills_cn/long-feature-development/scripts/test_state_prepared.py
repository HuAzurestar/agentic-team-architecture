"""Real Git prepared-state integration; reviewer identity remains synthetic."""
from dataclasses import replace
from pathlib import Path
import os
import unittest
import task_context as tc
import task_state as writer
import state_guard as guard
import state_prepared as prepared
import quality_host as host
import test_quality_host as host_fixture
from test_quality_host import git


class PreparedTests(unittest.TestCase):
    def setUp(self):
        self.case = c = host_fixture.HostTests()
        c.setUp()
        self.addCleanup(c.doCleanups)
        self.root = c.root
        self.task = 'ACCEPT-01'
        detail = (self.root / 'tasks/DEV-02.md').read_text(encoding='utf-8').replace('DEV-02', self.task)
        detail += ('\n## Type contract\n\n| Field | Value |\n| --- | --- |\n'
                   f'| Target SHA | {c.app_head} |\n| Acceptance scope | Current feature |\n'
                   '| Decision | WAITING |\n| Decided by | - |\n')
        pending_detail = detail.replace(f'| task@{c.app_base} | {c.app_head} | - |', '| - | - | - |')
        pending_detail = pending_detail.replace(f'| feature@{c.pm_base} | {c.pm_base} | - |', '| - | - | - |')
        (self.root / f'tasks/{self.task}.md').write_text(pending_detail, encoding='utf-8')
        tasks = (self.root / 'TASKS.md').read_text(encoding='utf-8')
        row = (f'| {self.task} | Acceptance | Fixture acceptance | `PENDING` | - | SOL-001 | '
               '- | - | - |\n')
        tasks = tasks.replace('| GATE-ACCEPT |', row + '| GATE-ACCEPT |', 1)
        tasks = tasks.replace('| DEV-02 | - | - | - |', '| DEV-02, ACCEPT-01 | - | - | - |')
        (self.root / 'TASKS.md').write_text(tc.synchronized_topology(tasks), encoding='utf-8')
        gate = self.root / 'tasks/GATE-ACCEPT.md'
        gate.write_text(gate.read_text(encoding='utf-8').replace('| Required tasks | DEV-02 |',
                       '| Required tasks | DEV-02, ACCEPT-01 |'), encoding='utf-8')
        c.save()
        self.args = writer.parse_args([str(self.root), self.task, '--to', 'WIP', '--owner', 'fixture',
            '--started-at', '2026-10-03T12:00:00Z', '--head', f'app@{c.app_head}; pm@{c.pm_base}'])
        status = (self.root / 'STATUS.md').read_text(encoding='utf-8')
        self.changes = {'STATUS.md': status.replace('| Current task | DEV-02 |',
                            '| Current task | ACCEPT-01 |').encode('utf-8'),
                        f'tasks/{self.task}.md': (detail + '\n- Prepared by fixture.\n').encode('utf-8')}

    def capture(self):
        return prepared.PreparedTransition(self.root, self.args, self.changes,
            repo_overrides={'app': self.case.app, 'pm': self.case.pm})

    def apply_metadata(self):
        for name, raw in self.changes.items():
            (self.root / name).write_bytes(raw)

    def evaluate(self, plan, request, reader=None):
        return host.evaluate_prepared(plan, request, documents=self.case.documents, roles=self.case.roles,
            repositories=(self.case.binding,), read_provenance=reader or self.case.provenance)

    def test_actual_quality_reader_supports_protected_write_and_owned_temporary(self):
        plan = self.capture()
        self.apply_metadata()
        calls = []
        def reader(request):
            assessment = self.evaluate(plan, request)
            self.assertTrue(assessment.result['allowed'], assessment.result)
            calls.append(guard._TEMPORARY.get() is not None)
            return guard.TransitionEvidence(request.digest, assessment.for_task(request.digest, request.task_id))
        writer.update(self.root, self.args, evidence_reader=reader)
        self.assertEqual(calls, [False, True])
        self.assertIsNone(guard._TEMPORARY.get())
        self.assertEqual(tc.task_records(tc.read_utf8(self.root / 'TASKS.md'))[self.task]['state'], 'WIP')
        self.assertFalse(list(self.root.glob('TASKS.*.tmp')))
        self.case.commit_records()
        tc.build_context(self.root, repo_overrides={'app': self.case.app, 'pm': self.case.pm})

    def test_only_exact_declared_changes_are_accepted(self):
        plan = self.capture()
        self.apply_metadata()
        path = self.root / f'tasks/{self.task}.md'
        path.write_bytes(path.read_bytes() + b'external')
        with self.assertRaisesRegex(tc.ContextError, 'STATE_SOURCE_CHANGED'):
            plan.read(plan.request)
        self.assertTrue(path.read_bytes().endswith(b'external'))

    def test_untracked_temporary_lookalike_is_not_ignored(self):
        plan = self.capture()
        self.apply_metadata()
        (self.root / 'TASKS.foreign.tmp').write_text(plan.candidate, encoding='utf-8')
        with self.assertRaisesRegex(tc.ContextError, 'STATE_UNEXPECTED_WORKSPACE'):
            plan.read(plan.request)

    def test_staged_preparation_is_not_accepted(self):
        plan = self.capture()
        self.apply_metadata()
        git(self.case.pm, 'add', 'project/PIRC-23/STATUS.md')
        with self.assertRaisesRegex(tc.ContextError, 'STATE_REPOSITORY_CHANGED'):
            plan.read(plan.request)

    def test_projected_invalid_status_is_not_a_dirty_exception(self):
        self.changes['STATUS.md'] = self.changes['STATUS.md'].replace(b'| `ACTIVE` |', b'| `COMPLETE` |')
        plan = self.capture()
        self.apply_metadata()
        with self.assertRaises(tc.ContextError):
            plan.read(plan.request)

    def test_repository_columns_cannot_be_prepared(self):
        self.changes['STATUS.md'] = self.changes['STATUS.md'].replace(b'DERIVED:HEAD', b'0' * 40)
        plan = self.capture()
        self.apply_metadata()
        with self.assertRaisesRegex(tc.ContextError, 'STATE_REPOSITORY_CHANGED'):
            plan.read(plan.request)

    def test_other_operation_binding_cannot_reuse_preparation(self):
        plan = self.capture()
        self.apply_metadata()
        with self.assertRaisesRegex(tc.ContextError, 'STATE_PREPARATION_MISMATCH'):
            plan.read(replace(plan.request, target='DONE'))

    def test_dirty_baseline_cannot_be_sealed(self):
        (self.root / 'gists/parser.md').write_text('uncommitted', encoding='utf-8')
        with self.assertRaises(tc.ContextError):
            self.capture()

    def test_hidden_index_change_is_not_expected_metadata(self):
        plan = self.capture()
        self.apply_metadata()
        git(self.case.pm, 'update-index', '--assume-unchanged', 'project/PIRC-23/REQUIREMENT.md')
        with self.assertRaisesRegex(tc.ContextError, 'STATE_REPOSITORY_CHANGED'):
            plan.read(plan.request)

    def test_repository_head_move_invalidates_captured_baseline(self):
        plan = self.capture()
        self.apply_metadata()
        git(self.case.app, 'commit', '--allow-empty', '-m', 'external head move')
        with self.assertRaisesRegex(tc.ContextError, 'STATE_REPOSITORY_CHANGED'):
            plan.read(plan.request)

    def test_missing_provenance_still_blocks_prepared_write(self):
        plan = self.capture()
        self.apply_metadata()
        original = (self.root / 'TASKS.md').read_bytes()
        def reader(request):
            assessment = host.evaluate_prepared(plan, request, documents=self.case.documents,
                roles=self.case.roles, repositories=(self.case.binding,))
            return guard.TransitionEvidence(request.digest, assessment.for_task(request.digest, request.task_id))
        with self.assertRaisesRegex(tc.ContextError, 'INDEPENDENCE_UNVERIFIED'):
            writer.update(self.root, self.args, evidence_reader=reader)
        self.assertEqual((self.root / 'TASKS.md').read_bytes(), original)

    def test_late_external_change_denies_without_overwriting(self):
        plan = self.capture()
        self.apply_metadata()
        original = (self.root / 'TASKS.md').read_bytes()
        def proof(probe):
            if guard._TEMPORARY.get() is not None:
                (self.root / 'gists/parser.md').write_text('external evidence edit', encoding='utf-8')
            return self.case.provenance(probe)
        def reader(request):
            assessment = self.evaluate(plan, request, proof)
            return guard.TransitionEvidence(request.digest, assessment.for_task(request.digest, request.task_id))
        with self.assertRaises(tc.ContextError):
            writer.update(self.root, self.args, evidence_reader=reader)
        self.assertEqual((self.root / 'TASKS.md').read_bytes(), original)
        self.assertEqual((self.root / 'gists/parser.md').read_text(), 'external evidence edit')
        self.assertFalse(list(self.root.glob('TASKS.*.tmp')))

    def test_replaced_writer_temporary_is_preserved_and_never_published(self):
        plan = self.capture()
        self.apply_metadata()
        original = (self.root / 'TASKS.md').read_bytes()
        replaced = []
        def reader(request):
            temporary = guard._TEMPORARY.get()
            if temporary is not None:
                replacement = self.root.parent / 'external-file'
                replacement.write_bytes(b'foreign replacement')
                os.replace(replacement, temporary[1])
                replaced.append(temporary[1])
            assessment = self.evaluate(plan, request)
            return guard.TransitionEvidence(request.digest, assessment.for_task(request.digest, request.task_id))
        with self.assertRaises(tc.ContextError):
            writer.update(self.root, self.args, evidence_reader=reader)
        self.assertEqual((self.root / 'TASKS.md').read_bytes(), original)
        self.assertEqual(len(replaced), 1)
        self.assertEqual(replaced[0].read_bytes(), b'foreign replacement')


if __name__ == '__main__':
    unittest.main()
