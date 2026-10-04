"""One concentrated real-Git continuation check; human transport is synthetic."""
import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import acceptance_workflow as acceptance
import task_context as tc
import task_create as create
import task_dependencies as deps
import rework_workflow as rework
from decision_evidence import canonical
import test_state_acceptance as fixture
from test_task_create import TaskCreateTests
from test_quality_host import git


class ContinuationTests(unittest.TestCase):
    def test_revocation_inside_writer_preparation_prevents_first_write(self):
        # Source/identity is stubbed here; actual task creation and files are
        # real. The integration case below covers retained human disposition.
        with tempfile.TemporaryDirectory() as tmp:
            root = TaskCreateTests().make_feature(Path(tmp))
            argv = (str(root), '--type', 'Acceptance', '--name', 'Acceptance successor fixture',
                '--depends-on', 'SOL-001', '--requirement-points', 'REQ-001',
                '--solution-points', 'SOL-001', '--goal', 'New acceptance',
                '--work', 'Prepare a new brief', '--completion-condition', 'Actual human decision',
                '--resume-action', 'Wait for review', '--repo-ref', 'app|feature|main@1111111')
            plan = rework.SuccessorPlan('ACCEPT-OLD', 'REVIEW-NEW', 'ACCEPT-01',
                                       'synthetic-source', 'synthetic-decision', argv, 'synthetic-detail')
            workflow = rework.ReworkWorkflow.__new__(rework.ReworkWorkflow)
            workflow.root = root
            workflow.preview_successor = lambda *args, **kwargs: plan
            prepared = False
            authority_reads = []

            def authorize(request):
                authority_reads.append(prepared)
                return None if prepared else rework.OperationPermission(
                    hashlib.sha256(canonical(request)).hexdigest(), 'synthetic:current-operation')

            original_validate = create.task_context.validate_type_contract

            def validate(*args, **kwargs):
                nonlocal prepared
                value = original_validate(*args, **kwargs)
                prepared = True
                return value

            workflow.authorize = authorize
            before = rework.file_snapshot(root)
            with patch.object(create.task_context, 'validate_type_contract', validate):
                with self.assertRaisesRegex(tc.ContextError, 'OPERATION_AUTHORITY_UNVERIFIED'):
                    workflow.create_successor(plan)
            self.assertEqual(authority_reads, [False, True])
            self.assertEqual(rework.file_snapshot(root), before)
            self.assertFalse((root / '.operation.lock').exists())

    def test_negative_disposition_successor_and_pending_gate_preserve_old_attempt(self):
        c = fixture.AcceptanceTests()
        c.setUp()
        self.addCleanup(c.doCleanups)
        c.prepare('REWORK', 'DONE')
        reader = c.reader()
        session = SimpleNamespace(feature=c.root.name, source_key='acceptance:app',
            read_reply=reader.read_reply, interpret=reader.interpret, read_grant=reader.read_grant)
        overrides = {'pm': c.case.pm, 'app': c.case.app}
        host = acceptance.AcceptanceWorkflow(c.root, session=session, repo_overrides=overrides)
        result = host.record(c.plan, decision_document=c.document,
            candidate_repository='app', exact_scope=('feature:' + c.root.name,))
        self.assertEqual(result['state'], 'DONE')
        c.case.commit_records()
        detail = (c.root / f'tasks/{c.task}.md').read_text(encoding='utf-8')
        req = tc.point_selectors(detail, 'Requirement points', ('Requirement points', '需求点'))
        sol = tc.point_selectors(detail, 'Solution points', ('Solution points', '方案点'))
        args = create.parse_args([str(c.root), '--type', 'Review', '--name', 'New review fixture',
            '--depends-on', 'SOL-001', '--goal', 'Review new candidate', '--work', 'Synthetic pending fixture',
            '--completion-condition', 'Actual review required', '--resume-action', 'Review not performed',
            '--requirement-points', ','.join(req) or 'none', '--solution-points', ','.join(sol) or 'none',
            '--repo-ref', f'app|task|main@{c.case.app_base}', '--contract', 'Target SHA=' + c.case.app_head])
        review_id = create.create(c.root, args)
        c.case.commit_records()
        result = deps.replace_dependencies(c.root, 'GATE-ACCEPT',
            deps.recovery.digest((c.root / 'TASKS.md').read_bytes()), ['DEV-02', c.task],
            operation_gist=c.case.plan_ref, repo_overrides=overrides, authority=True,
            authority_source_ref='synthetic:fixture-setup')
        self.assertIn(result['effect'], {'APPLIED', 'UNCHANGED'}, result)
        if result['effect'] == 'APPLIED':
            c.case.commit_records()
        originals = {p: (c.root / p).read_bytes() for p in
                     (f'tasks/{c.task}.md', 'gists/decision.md', 'gists/acceptance.md')}
        binding = dict(decision_path='gists/decision.md', candidate_repository='app',
                       exact_scope=('feature:' + c.root.name,))
        workflow = rework.ReworkWorkflow(c.root, session=session, repo_overrides=overrides)
        plan = workflow.preview_successor(c.task, review_id, **binding)
        head = git(c.case.pm, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(tc.ContextError, 'OPERATION_AUTHORITY_REQUIRED'):
            workflow.create_successor(plan, **binding)
        self.assertEqual(git(c.case.pm, 'rev-parse', 'HEAD'), head)
        self.assertFalse((c.root / f'tasks/{plan.task_id}.md').exists())
        workflow.authorize = lambda request: rework.OperationPermission(
            hashlib.sha256(canonical(request)).hexdigest(), 'synthetic:host-operation')
        valid_authorize = workflow.authorize
        snapshot = rework.file_snapshot(c.root)
        original_preview = workflow.preview_successor
        for window in ('source-recheck',):
            authorized = True
            preview_calls = 0

            def authorize(request):
                return valid_authorize(request) if authorized else None

            def preview(*args, **kwargs):
                nonlocal authorized, preview_calls
                value = original_preview(*args, **kwargs)
                preview_calls += 1
                if window == 'source-recheck' and preview_calls == 2:
                    authorized = False
                return value

            workflow.authorize = authorize
            with self.subTest(window=window), patch.object(workflow, 'preview_successor', preview):
                with self.assertRaisesRegex(tc.ContextError, 'OPERATION_AUTHORITY_UNVERIFIED'):
                    workflow.create_successor(plan, **binding)
            self.assertEqual(rework.file_snapshot(c.root), snapshot)
            self.assertEqual(git(c.case.pm, 'rev-parse', 'HEAD'), head)
            self.assertEqual(git(c.case.app, 'rev-parse', 'HEAD'), c.case.app_head)
        workflow.authorize = valid_authorize
        # Both grants stay valid. A separate editor changes the write basis
        # during the final host read; denial must preserve that exact edit.
        index = c.root / 'TASKS.md'
        edited_index = index.read_bytes() + b'\n<!-- concurrent editor: preserve this note -->\n'
        authority_reads = 0

        def editing_authorize(request):
            nonlocal authority_reads
            authority_reads += 1
            if authority_reads == 2:
                index.write_bytes(edited_index)
            return valid_authorize(request)

        workflow.authorize = editing_authorize
        conflict = None
        try:
            workflow.create_successor(plan, **binding)
        except tc.ContextError as exc:
            conflict = str(exc)
        self.assertEqual(index.read_bytes(), edited_index, 'concurrent edit was overwritten')
        self.assertEqual(authority_reads, 2)
        self.assertEqual(conflict, 'SUCCESSOR_SOURCE_CHANGED')
        expected = dict(snapshot)
        expected['TASKS.md'] = hashlib.sha256(edited_index).hexdigest()
        self.assertEqual(rework.file_snapshot(c.root), expected)
        self.assertEqual(git(c.case.pm, 'rev-parse', 'HEAD'), head)
        self.assertEqual(git(c.case.app, 'rev-parse', 'HEAD'), c.case.app_head)
        self.assertFalse((c.root / f'tasks/{plan.task_id}.md').exists())
        # Retain the editor's change in the fixture history, then build a fresh
        # plan. No reset/rollback is permitted to erase it for a successful retry.
        c.case.commit_records()
        plan = workflow.preview_successor(c.task, review_id, **binding)
        workflow.authorize = valid_authorize
        created = workflow.create_successor(plan, **binding)
        self.assertEqual(created['effect'], 'APPLIED_PENDING_CHECKPOINT')
        c.case.commit_records()
        again = workflow.preview_successor(c.task, review_id, **binding)
        self.assertTrue(again.existing)
        self.assertEqual(workflow.create_successor(again, **binding)['effect'], 'UNCHANGED')
        changed = workflow.rewire_pending(c.task, plan.task_id, 'GATE-ACCEPT',
            expected_index_digest=deps.recovery.digest((c.root / 'TASKS.md').read_bytes()),
            operation_gist=c.case.plan_ref, **binding)
        self.assertEqual(changed['effect'], 'APPLIED', changed)
        c.case.commit_records()
        feature = host._feature()
        self.assertIn(plan.task_id, feature.records['GATE-ACCEPT']['dependencies'])
        self.assertNotIn(c.task, feature.records['GATE-ACCEPT']['dependencies'])
        fields = feature.type_contracts[plan.task_id]
        self.assertEqual(fields['Decision'], 'WAITING')
        self.assertEqual(fields['Decided by'], '-')
        self.assertEqual(fields['Acceptance brief'], '-')
        self.assertEqual(feature.records[plan.task_id]['state'], 'PENDING')
        self.assertEqual(feature.records[review_id]['state'], 'PENDING')
        for p, original in originals.items():
            self.assertEqual((c.root / p).read_bytes(), original)
        self.assertEqual(git(c.case.app, 'rev-parse', 'HEAD'), c.case.app_head)
        self.assertFalse(created['merge_authorized'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
