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
from test_task_reconcile import RecoveryTests
from test_quality_host import git


class ContinuationTests(unittest.TestCase):
    def test_final_permission_hidden_index_edit_is_preserved(self):
        # Plan/disposition and identity are synthetic; repository resolution,
        # Git/index, control files and task creation are real. No flag cleanup
        # is used to obtain a success: each case owns a fresh temporary repo.
        for flag in (None, 'assume-unchanged', 'skip-worktree'):
            with self.subTest(flag=flag):
                c = RecoveryTests()
                c.setUp()
                self.addCleanup(c.doCleanups)
                argv = (str(c.root), '--type', 'Acceptance', '--name', 'Successor guard fixture',
                    '--depends-on', 'SOL-001', '--requirement-points', 'REQ-001',
                    '--solution-points', 'SOL-001', '--goal', 'New acceptance',
                    '--work', 'Prepare a new brief', '--completion-condition', 'Actual human decision',
                    '--resume-action', 'Wait for review', '--repo-ref', f'app|task|main@{c.app_base}')
                plan = rework.SuccessorPlan('ACCEPT-OLD', 'REVIEW-NEW', 'ACCEPT-01',
                    'synthetic-source', 'synthetic-decision', argv, 'synthetic-detail')
                workflow = rework.ReworkWorkflow.__new__(rework.ReworkWorkflow)
                workflow.root = c.root
                workflow.overrides = {'pm': c.pm, 'app': c.app}
                workflow.preview_successor = lambda *args, **kwargs: plan
                before = rework.file_snapshot(c.root)
                pm_head = git(c.pm, 'rev-parse', 'HEAD')
                product = c.app / 'owned.py'
                changed = product.read_bytes() + b'\nversion = 3  # hidden external edit\n'
                reads = 0
                retained_index = None

                def authorize(request):
                    nonlocal reads, retained_index
                    reads += 1
                    if reads == 2 and flag is not None:
                        git(c.app, 'update-index', '--' + flag, 'owned.py')
                        product.write_bytes(changed)
                        retained_index = (c.app / '.git/index').read_bytes()
                    return rework.OperationPermission(
                        hashlib.sha256(canonical(request)).hexdigest(), 'synthetic:current-operation')

                workflow.authorize = authorize
                if flag is None:
                    result = workflow.create_successor(plan)
                    self.assertEqual(result['effect'], 'APPLIED_PENDING_CHECKPOINT')
                    self.assertFalse(result['merge_authorized'])
                    self.assertTrue((c.root / 'tasks/ACCEPT-01.md').exists())
                else:
                    with self.assertRaisesRegex(tc.ContextError, '^HIDDEN_INDEX_STATE$'):
                        workflow.create_successor(plan)
                    self.assertEqual(git(c.app, 'status', '--porcelain'), '')
                    self.assertEqual(product.read_bytes(), changed)
                    self.assertEqual((c.app / '.git/index').read_bytes(), retained_index)
                    self.assertEqual(rework.file_snapshot(c.root), before)
                    self.assertFalse((c.root / 'tasks/ACCEPT-01.md').exists())
                    with self.assertRaisesRegex(tc.ContextError, '^HIDDEN_INDEX_STATE$'):
                        tc.build_context(c.root, repo_overrides=workflow.overrides)
                    self.assertEqual(product.read_bytes(), changed)
                    self.assertEqual((c.app / '.git/index').read_bytes(), retained_index)
                self.assertEqual(reads, 2)
                self.assertEqual(git(c.app, 'rev-parse', 'HEAD'), c.app_head)
                self.assertEqual(git(c.pm, 'rev-parse', 'HEAD'), pm_head)
                self.assertFalse((c.root / '.operation.lock').exists())

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
            workflow._repositories = lambda: {}  # synthetic source observation
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
        # The retained human disposition is not the current operation grant.
        # Reject before durable intent if authority is withdrawn during either
        # its later readback or the actual dependency writer's preparation.
        disposition_reader = workflow.acceptance.verify_disposition
        prepare_context = deps.checked_context
        before_rewire = rework.file_snapshot(c.root)
        for window in ('disposition-readback', 'writer-preparation'):
            permitted = True
            operation_reads = 0

            def operation_authorize(request):
                nonlocal operation_reads
                operation_reads += 1
                return valid_authorize(request) if permitted else None

            def read_disposition(*args, **kwargs):
                nonlocal permitted
                value = disposition_reader(*args, **kwargs)
                if window == 'disposition-readback' and operation_reads:
                    permitted = False
                return value

            def prepare_dependencies(*args, **kwargs):
                nonlocal permitted
                value = prepare_context(*args, **kwargs)
                if window == 'writer-preparation':
                    permitted = False
                return value

            workflow.authorize = operation_authorize
            with self.subTest(window=window), patch.object(
                    workflow.acceptance, 'verify_disposition', read_disposition), patch.object(
                    deps, 'checked_context', prepare_dependencies):
                denied = workflow.rewire_pending(c.task, plan.task_id, 'GATE-ACCEPT',
                    expected_index_digest=deps.recovery.digest((c.root / 'TASKS.md').read_bytes()),
                    operation_gist=c.case.plan_ref, **binding)
                self.assertEqual(denied['effect'], 'NOT_APPLIED', denied)
                self.assertEqual(denied['conflicts'][0]['code'], 'OPERATION_AUTHORITY_UNVERIFIED')
                self.assertEqual(operation_reads, 2)
                self.assertEqual(rework.file_snapshot(c.root), before_rewire)
                self.assertFalse((c.root / '.operation.lock').exists())
        workflow.authorize = valid_authorize
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
        # Another new review still targets the current product. Both grants
        # stay valid, but an external editor commits implementation source during the
        # second host read. Keep that commit, and publish no stale successor.
        next_review = create.create(c.root, args)
        c.case.commit_records()
        stale_plan = workflow.preview_successor(c.task, next_review, **binding)
        before = rework.file_snapshot(c.root)
        management_head = git(c.case.pm, 'rev-parse', 'HEAD')
        authority_reads = 0
        product = c.case.app / 'owned.py'
        changed_source = product.read_bytes() + b'\nversion = 2  # external implementation change\n'
        external_head = None

        def committing_authorize(request):
            nonlocal authority_reads, external_head
            authority_reads += 1
            if authority_reads == 2:
                product.write_bytes(changed_source)
                git(c.case.app, 'add', 'owned.py')
                git(c.case.app, 'commit', '-m', 'external source change during host read')
                external_head = git(c.case.app, 'rev-parse', 'HEAD')
            return valid_authorize(request)

        workflow.authorize = committing_authorize
        with self.assertRaisesRegex(tc.ContextError, '^SUCCESSOR_SOURCE_CHANGED$'):
            workflow.create_successor(stale_plan, **binding)
        self.assertEqual(authority_reads, 2)
        self.assertIsNotNone(external_head)
        self.assertNotEqual(external_head, c.case.app_head)
        self.assertEqual(git(c.case.app, 'rev-parse', 'HEAD'), external_head)
        # git() decodes stdout with universal newlines; the working bytes below
        # remain exact, including the checkout's configured CRLF conversion.
        committed_text = changed_source.decode().replace('\r\n', '\n').replace('\r', '\n').strip()
        self.assertEqual(git(c.case.app, 'show', 'HEAD:owned.py'), committed_text)
        self.assertEqual(product.read_bytes(), changed_source)
        self.assertEqual(git(c.case.pm, 'rev-parse', 'HEAD'), management_head)
        self.assertEqual(rework.file_snapshot(c.root), before)
        self.assertFalse((c.root / f'tasks/{stale_plan.task_id}.md').exists())
        self.assertFalse((c.root / '.operation.lock').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
