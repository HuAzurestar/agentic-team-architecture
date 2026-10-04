"""One concentrated real-Git continuation check; human transport is synthetic."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
import acceptance_workflow as acceptance
import task_context as tc
import task_create as create
import task_dependencies as deps
import rework_workflow as rework
from decision_evidence import canonical
import test_state_acceptance as fixture
from test_quality_host import git


class ContinuationTests(unittest.TestCase):
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
