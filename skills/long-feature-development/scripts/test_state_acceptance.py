"""Acceptance writes with real originals/Git; identity transport is synthetic."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
import decision_host as human
import decision_evidence as decision
import quality_source as sources
import state_acceptance as acceptance
import state_prepared as prepared
import task_context as tc
import task_state as writer
import test_state_prepared as fixture
import test_decision_evidence as evidence
from test_quality_host import git


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = f = fixture.PreparedTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.root, self.task, self.case = f.root, f.task, f.case

    def prepare(self, outcome='REJECTED', target='RECORDING', *, target_version=None, scope_after=None):
        f, c = self.fixture, self.case
        source = 'WIP' if target == 'RECORDING' else 'RECORDING'
        brief = f'# Acceptance\n\nTarget version: `{c.app_head}`\n'
        for title in ('What changed', 'How to check', 'Evidence', 'Out of scope', 'Known limitations', 'Decision options'):
            brief += '\n## ' + title + '\n\nSynthetic acceptance fixture only.\n'
        self.body = brief
        (self.root / 'gists/acceptance.md').write_text(brief, encoding='utf-8')
        raw = evidence.evidence()
        raw.update(feature=self.root.name, decision_kind='acceptance', exact_scope=['feature:' + self.root.name],
            target_ref=dict(source_key='acceptance:app', version_kind='git', version=target_version or c.app_head),
            outcome=outcome, approved_body=brief, original_reply='Synthetic original reply: ' + outcome)
        self.record = raw
        (self.root / 'gists/decision.md').write_text(json.dumps(raw), encoding='utf-8')
        detail = f.changes[f'tasks/{self.task}.md'].decode('utf-8')
        detail = detail.replace('- Gists: ', '- Gists: gists/acceptance.md, gists/decision.md, ')
        detail = detail.replace('| Decided by | - |',
            '| Decided by | - |\n| Acceptance brief | gists/acceptance.md |')
        if source == 'RECORDING':
            detail = detail.replace('| Decision | WAITING |', f'| Decision | {outcome} |').replace(
                '| Decided by | - |', '| Decided by | person-1 |')
        (self.root / f'tasks/{self.task}.md').write_text(detail, encoding='utf-8')
        tasks = tc.read_utf8(self.root / 'TASKS.md')
        tasks = writer.replace_task_row(tasks, self.task, [self.task, 'Acceptance', 'Historical fixture',
            f'`{source}`', 'fixture', 'SOL-001', '2026-10-03T12:00:00Z', '-',
            f'app@{c.app_head}; pm@{c.pm_base}'])
        (self.root / 'TASKS.md').write_text(tc.synchronized_topology(tasks), encoding='utf-8')
        (self.root / 'STATUS.md').write_bytes(f.changes['STATUS.md'])
        c.commit_records()
        after = detail.replace('| Decision | WAITING |', f'| Decision | {outcome} |').replace(
            '| Decided by | - |', '| Decided by | person-1 |')
        if scope_after is not None:
            after = after.replace('| Acceptance scope | Current feature |',
                                  '| Acceptance scope | ' + scope_after + ' |')
        if target == 'DONE':
            for sha in (c.app_head, c.pm_base):
                after = after.replace(f'| {sha} | - |', f'| {sha} | {sha} |')
        args = writer.parse_args([str(self.root), self.task, '--to', target,
                                  '--completed-at', '2026-10-03T13:00:00Z'])
        changes = {f'tasks/{self.task}.md': after.encode('utf-8')}
        if target == 'DONE':
            changes['STATUS.md'] = (self.root / 'STATUS.md').read_bytes().replace(
                b'| Current task | ACCEPT-01 |', b'| Current task | DEV-02 |')
        self.plan = prepared.PreparedTransition(self.root, args, changes,
            repo_overrides={'pm': c.pm, 'app': c.app})
        self.args = args
        self.document = sources.GitDocument('gists/decision.md', c.pm, 'project/PIRC-23/gists/decision.md',
                                            git(c.pm, 'rev-parse', 'HEAD'))
        self.reply = human.HumanReply(raw['human_source_ref'], raw['actor'], 'human', raw['received_at'],
            raw['original_reply'], 'conversation', 'fixture-version', 'fixture:readback')
        self.grant = human.HumanGrant(raw['actor'], raw['feature'], 'acceptance', 'acceptance:app',
                                     tuple(raw['exact_scope']), ('CONFIRMED', 'REJECTED', 'REWORK'))
        for name, content in changes.items():
            (self.root / name).write_bytes(content)

    def reader(self, **overrides):
        return acceptance.AcceptanceReader(self.plan, **(dict(decision_document=self.document,
            candidate_repository='app', source_key='acceptance:app', exact_scope=('feature:' + self.root.name,),
            read_reply=lambda ref: self.reply,
            interpret=lambda reply, raw: human.HumanInterpretation(decision.decision_digest(raw), 'fixture:interpretation'),
            read_grant=lambda request, raw: self.grant) | overrides))

    def test_actual_rejection_is_recorded_without_quality_promotion(self):
        self.prepare()
        writer.update(self.root, self.args, evidence_reader=self.reader())
        self.assertEqual(tc.task_records(tc.read_utf8(self.root / 'TASKS.md'))[self.task]['state'], 'RECORDING')
        self.case.commit_records()
        tc.build_context(self.root, repo_overrides={'pm': self.case.pm, 'app': self.case.app})

    def test_rework_can_complete_without_quality_assessment_or_merge_grant(self):
        self.prepare('REWORK', 'DONE')
        with patch('quality_host.evaluate_prepared', side_effect=AssertionError('quality is not required to record rework')):
            writer.update(self.root, self.args, evidence_reader=self.reader())
        self.assertEqual(tc.task_records(tc.read_utf8(self.root / 'TASKS.md'))[self.task]['state'], 'DONE')
        self.assertEqual(git(self.case.app, 'rev-parse', 'HEAD'), self.case.app_head)

    def test_confirmed_decision_can_complete_but_does_not_merge(self):
        self.prepare('CONFIRMED', 'DONE')
        before = git(self.case.app, 'rev-parse', 'main')
        writer.update(self.root, self.args, evidence_reader=self.reader())
        self.assertEqual(git(self.case.app, 'rev-parse', 'main'), before)

    def test_unverified_grant_or_uploaded_dict_cannot_record(self):
        self.prepare()
        original = (self.root / 'TASKS.md').read_bytes()
        with self.assertRaises(tc.ContextError):
            writer.update(self.root, self.args, evidence_reader=self.reader(read_grant=lambda request, raw: {}))
        self.assertEqual((self.root / 'TASKS.md').read_bytes(), original)

    def test_reply_actor_must_be_actual_human(self):
        self.prepare()
        with self.assertRaisesRegex(tc.ContextError, 'HUMAN_SOURCE_MISMATCH'):
            writer.update(self.root, self.args, evidence_reader=self.reader(
                read_reply=lambda ref: replace(self.reply, actor_kind='agent')))

    def test_undeclared_copy_cannot_replace_original(self):
        self.prepare()
        with self.assertRaises(tc.ContextError):
            writer.update(self.root, self.args, evidence_reader=self.reader(
                decision_document=replace(self.document, logical_path='gists/other.md')))

    def test_authority_revoked_after_human_reads_stops_write(self):
        self.prepare()
        calls = []
        def grant(request, raw):
            calls.append(1)
            return self.grant if len(calls) == 1 else replace(self.grant, outcomes=())
        before = (self.root / 'TASKS.md').read_bytes()
        with self.assertRaisesRegex(tc.ContextError, 'HUMAN_AUTHORITY_CHANGED'):
            writer.update(self.root, self.args, evidence_reader=self.reader(read_grant=grant))
        self.assertEqual((self.root / 'TASKS.md').read_bytes(), before)

    def test_late_human_callback_repository_change_is_not_missed(self):
        self.prepare()
        calls = []
        def reply(ref):
            calls.append(1)
            if len(calls) == 4:
                git(self.case.app, 'commit', '--allow-empty', '-m', 'external move after final reply')
            return self.reply
        before = (self.root / 'TASKS.md').read_bytes()
        with self.assertRaises(tc.ContextError):
            writer.update(self.root, self.args, evidence_reader=self.reader(read_reply=reply))
        self.assertEqual((self.root / 'TASKS.md').read_bytes(), before)
        self.assertNotEqual(git(self.case.app, 'rev-parse', 'HEAD'), self.case.app_head)
        self.assertFalse(list(self.root.glob('TASKS.*.tmp')))

    def test_old_candidate_version_is_stale_even_with_same_brief(self):
        self.prepare(target_version=self.case.app_base)
        with self.assertRaisesRegex(tc.ContextError, 'DECISION_STALE'):
            writer.update(self.root, self.args, evidence_reader=self.reader())

    def test_recording_cannot_expand_retained_acceptance_scope(self):
        self.prepare(scope_after='All other features as well')
        with self.assertRaisesRegex(tc.ContextError, 'ACCEPTANCE_SCOPE_CHANGED'):
            self.reader()(self.plan.request)

    def test_late_grant_callback_original_change_is_preserved(self):
        self.prepare()
        calls = []
        def grant(request, raw):
            calls.append(1)
            if len(calls) == 2:
                (self.root / 'gists/acceptance.md').write_text('externally replaced brief', encoding='utf-8')
            return self.grant
        before = (self.root / 'TASKS.md').read_bytes()
        with self.assertRaises(tc.ContextError):
            writer.update(self.root, self.args, evidence_reader=self.reader(read_grant=grant))
        self.assertEqual((self.root / 'TASKS.md').read_bytes(), before)
        self.assertEqual((self.root / 'gists/acceptance.md').read_text(), 'externally replaced brief')


if __name__ == '__main__':
    unittest.main()
