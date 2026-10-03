#!/usr/bin/env python3
"""Real-Git review recovery and original-source preservation tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import task_context as tc
import review_resume as rr
import test_task_reconcile as fixture


class ReviewParsingTests(unittest.TestCase):
    def setUp(self):
        self.schema = 'review-resume-v1'
        self.raw = json.dumps({'schema': self.schema, 'attempt_id': 'one'})

    def rejected(self, text):
        with self.assertRaises(rr.LoaderError) as caught:
            rr._object(text, self.schema)
        self.assertEqual(caught.exception.code, 'INVALID_REVIEW_REFERENCE')

    def test_outer_example_fence_is_not_control(self):
        self.rejected('````md\n```review-resume-v1\n' + self.raw + '\n```\n````\n')

    def test_commented_fence_is_not_control(self):
        self.rejected('<!--\n```review-resume-v1\n' + self.raw + '\n```\n-->\n')

    def test_quote_and_indented_fences_are_not_control(self):
        for prefix in ('> ', '    '):
            text = '```review-resume-v1\n' + self.raw + '\n```'
            self.rejected('\n'.join(prefix + line for line in text.splitlines()))

    def test_single_top_level_fence_or_raw_object(self):
        expected = json.loads(self.raw)
        self.assertEqual(rr._object(self.raw, self.schema), expected)
        self.assertEqual(rr._object('# Record\n```review-resume-v1\n' + self.raw + '\n```\n', self.schema), expected)

    def test_duplicate_unclosed_or_nonfinite_json_rejected(self):
        block = '```review-resume-v1\n' + self.raw + '\n```\n'
        for text in (block + block, block[:-4],
                     '{"schema":"review-resume-v1","x":NaN}',
                     '{"schema":"review-resume-v1","x":1,"x":2}'):
            self.rejected(text)

    def test_commented_task_field_does_not_enable_recovery(self):
        self.assertIsNone(rr.declaration('<!--\n- Review recovery: gists/example.md\n-->'))


class ReviewRecoveryTests(unittest.TestCase):
    commit_records = fixture.RecoveryTests.commit_records

    def setUp(self):
        fixture.RecoveryTests.setUp(self)
        old = self.root / 'tasks/DEV-02.md'
        old.rename(self.root / 'tasks/REVIEW-01.md')
        for path in self.root.rglob('*.md'):
            text = path.read_text(encoding='utf-8').replace('DEV-02', 'REVIEW-01')
            text = text.replace('| REVIEW-01 | Development |', '| REVIEW-01 | Review |')
            path.write_text(text, encoding='utf-8')
        self.detail = self.root / 'tasks/REVIEW-01.md'
        text = self.detail.read_text(encoding='utf-8')
        text = text.replace('- Gists: gists/parser.md', '- Gists: ' + ', '.join(
            'gists/' + name + '.md' for name in ('parser', 'resume', 'packet', 'report', 'checklist')))
        text += ('\n- Review recovery: gists/resume.md\n\n## Type contract\n\n'
                 '| Field | Value |\n| --- | --- |\n'
                 f'| Target SHA | {self.app_head} |\n| Blocking findings | - |\n'
                 '| Deferred findings | - |\n| Result gist | gists/report.md |\n')
        self.detail.write_text(text, encoding='utf-8')
        (self.root / 'gists/checklist.md').write_text('Check the implementation.\n', encoding='utf-8')
        self.packet = {'schema': 'review-packet-v1', 'feature': 'PIRC-23',
                       'review_task': 'REVIEW-01', 'attempt_id': 'attempt-1',
                       'packet_id': 'packet-1', 'target_refs': {'app': self.app_head},
                       'checklist_ref': self.ref('checklist')}
        self.report = {**self.packet, 'schema': 'report-v1',
                       'evidence_refs': [self.ref('parser')],
                       'findings': [{'id': 'F-1', 'status': 'addressed'},
                                    {'id': 'F-2', 'status': 'closed'}],
                       'summary': {'open_finding_ids': ['F-1']}}
        self.request = {**self.packet, 'schema': 'review-resume-v1'}
        self.save()

    def ref(self, name):
        path = 'gists/' + name + '.md'
        return {'path': path, 'sha256': hashlib.sha256((self.root / path).read_bytes()).hexdigest()}

    def save(self):
        for name, obj in (('packet', self.packet), ('report', self.report)):
            (self.root / f'gists/{name}.md').write_text(json.dumps(obj), encoding='utf-8')
        self.request.update(packet_ref=self.ref('packet'), report_ref=self.ref('report'))
        (self.root / 'gists/resume.md').write_text(json.dumps(self.request), encoding='utf-8')
        tc.sync_topology(self.root / 'TASKS.md')
        self.commit_records()

    def assert_code(self, code):
        with self.assertRaises(tc.ContextError) as caught:
            tc.build_context(self.root)
        self.assertEqual(caught.exception.code, code)

    def transition(self, task_id, state, **values):
        import task_state
        args = [str(self.root), task_id, '--to', state]
        for name, value in values.items():
            args += ['--' + name.replace('_', '-'), value]
        task_state.update(self.root, task_state.parse_args(args))

    def complete(self, task_id):
        self.transition(task_id, 'RECORDING')
        path = self.root / ('tasks/' + task_id + '.md')
        text = path.read_text(encoding='utf-8')
        # Completion refs retain the task's own observed head, not a moving alias.
        for sha in (self.app_head, self.pm_base):
            text = text.replace(f'| {sha} | - |', f'| {sha} | {sha} |')
        path.write_text(text, encoding='utf-8')
        self.transition(task_id, 'DONE', completed_at='2026-10-03T10:00:00Z')

    def begin_rework(self):
        text = self.detail.read_text(encoding='utf-8')
        text = text.replace('| Blocking findings | - |', '| Blocking findings | 1 |')
        text = text.replace('| Deferred findings | - |', '| Deferred findings | 0 |')
        self.detail.write_text(text, encoding='utf-8')
        self.complete('REVIEW-01')
        base = text.split('## Type contract', 1)[0]
        rework = base.replace('REVIEW-01', 'REWORK-01')
        rework += ('## Type contract\n\n| Field | Value |\n| --- | --- |\n'
                   '| Source findings | F-1 |\n'
                   f'| Target SHA | {self.app_head} |\n| Output SHA | - |\n'
                   '| Result gist | gists/parser.md |\n')
        (self.root / 'tasks/REWORK-01.md').write_text(rework, encoding='utf-8')
        test = base.replace('REVIEW-01', 'TEST-02')
        test = test.replace('- Review recovery: gists/resume.md\n', '')
        test = '\n'.join('- Gists: gists/parser.md' if line.startswith('- Gists:') else line
                         for line in test.splitlines()) + '\n'
        test += ('## Type contract\n\n| Field | Value |\n| --- | --- |\n'
                 f'| Target SHA | {self.app_head} |\n| Environment | local |\n'
                 '| Planned checks | regression |\n| Executed | none |\n| Passed | none |\n'
                 '| Failed | none |\n| Skipped | none |\n| Unknown | none |\n'
                 '| Result gist | gists/parser.md |\n')
        self.test_template = test
        pending = []
        for line in test.splitlines():
            if line.startswith(('| app |', '| pm |')):
                fields = tc.split_row(line)
                fields[3:] = ['-', '-', '-']
                line = '| ' + ' | '.join(fields) + ' |'
            pending.append(line)
        (self.root / 'tasks/TEST-02.md').write_text('\n'.join(pending) + '\n', encoding='utf-8')
        path = self.root / 'TASKS.md'
        lines = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('| GATE-ACCEPT |'):
                lines.extend([
                    '| REWORK-01 | Rework | Correct finding | `PENDING` | - | REVIEW-01 | - | - | - |',
                    '| TEST-02 | Test | Retest new candidate | `PENDING` | - | REWORK-01 | - | - | - |'])
                line = line.replace('REVIEW-01', 'TEST-02')
            lines.append(line)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        tc.sync_topology(path)
        gate = self.root / 'tasks/GATE-ACCEPT.md'
        gate.write_text(gate.read_text(encoding='utf-8').replace('REVIEW-01', 'TEST-02'), encoding='utf-8')
        status = self.root / 'STATUS.md'
        status.write_text(status.read_text(encoding='utf-8').replace('REVIEW-01', 'REWORK-01'), encoding='utf-8')
        self.transition('REWORK-01', 'WIP', owner='fixture-author',
                        started_at='2026-10-03T09:00:00Z',
                        head=f'app@{self.app_head}; pm@{self.pm_base}')
        self.commit_records()

    def advance_candidate(self, owner):
        old = self.app_head
        (self.app / 'owned.py').write_text('version = 2\n', encoding='utf-8')
        fixture.git(self.app, 'add', 'owned.py')
        fixture.git(self.app, 'commit', '-m', 'correct implementation')
        self.app_head = fixture.git(self.app, 'rev-parse', 'HEAD')
        status = self.root / 'STATUS.md'
        status.write_text(status.read_text(encoding='utf-8').replace(old, self.app_head), encoding='utf-8')
        detail = self.root / ('tasks/' + owner + '.md')
        detail.write_text(detail.read_text(encoding='utf-8').replace(
            f'| {old} | - |', f'| {self.app_head} | - |'), encoding='utf-8')
        tasks = self.root / 'TASKS.md'
        lines = [line.replace('app@' + old, 'app@' + self.app_head)
                 if line.startswith('| ' + owner + ' |') else line
                 for line in tasks.read_text(encoding='utf-8').splitlines()]
        tasks.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.commit_records()

    def start_retest(self):
        rework = self.root / 'tasks/REWORK-01.md'
        rework.write_text(rework.read_text(encoding='utf-8').replace(
            '| Output SHA | - |', f'| Output SHA | {self.app_head} |'), encoding='utf-8')
        self.complete('REWORK-01')
        test = self.root / 'tasks/TEST-02.md'
        text = self.test_template
        text = text.replace(self.packet['target_refs']['app'], self.app_head)
        test.write_text(text, encoding='utf-8')
        status = self.root / 'STATUS.md'
        status.write_text(status.read_text(encoding='utf-8').replace('REWORK-01', 'TEST-02'), encoding='utf-8')
        self.transition('TEST-02', 'WIP', owner='fixture-tester',
                        started_at='2026-10-03T10:01:00Z',
                        head=f'app@{self.app_head}; pm@{self.pm_base}')
        self.commit_records()

    def test_historical_report_survives_rework_and_new_candidate_retest(self):
        self.begin_rework()
        before = {name: (self.root / ('gists/' + name + '.md')).read_bytes()
                  for name in ('packet', 'report', 'checklist', 'resume', 'parser')}
        self.assertEqual(tc.build_context(self.root)['review_recovery']['next_review_action'], 'resume-rework')
        old = self.app_head
        self.advance_candidate('REWORK-01')
        review = tc.build_context(self.root)['review_recovery']
        self.assertEqual(review['evidence_scope'], 'historical')
        self.assertEqual(review['target_refs'], {'app': old})
        self.assertEqual(review['current_target_refs'], {'app': self.app_head})
        self.assertEqual(review['next_review_action'], 'needs-recheck')
        self.assertFalse(review['quality_assessed'])
        self.assertEqual(review['diagnostics'][0]['code'], 'STALE_REVIEW')
        self.start_retest()
        context = tc.build_context(self.root)
        self.assertEqual(context['task']['id'], 'TEST-02')
        self.assertNotIn('review_recovery', context)
        self.assertEqual([gist['path'] for gist in context['gists']], ['gists/parser.md'])
        historical = tc.build_context(self.root, 'REWORK-01')
        self.assertEqual(historical['review_recovery']['evidence_scope'], 'historical')
        rendered = tc.render_markdown(historical)
        self.assertIn('Historical target:', rendered)
        self.assertIn('Current candidate:', rendered)
        command = [sys.executable, '-X', 'utf8', '-B', str(Path(tc.__file__)),
                   str(self.root), '--task', 'REWORK-01', '--format', 'json']
        process = subprocess.run(command, capture_output=True, check=True)
        recovered = json.loads(process.stdout)['review_recovery']
        self.assertEqual(recovered['target_refs'], {'app': old})
        self.assertEqual(recovered['current_target_refs'], {'app': self.app_head})
        self.assertEqual(recovered['next_review_action'], 'needs-recheck')
        self.assertEqual(json.loads(process.stderr)['error_code'], 'STALE_REVIEW')
        self.assertEqual(before, {name: (self.root / ('gists/' + name + '.md')).read_bytes()
                                  for name in before})

    def test_active_review_cannot_reuse_old_target_after_head_advances(self):
        self.advance_candidate('REVIEW-01')
        self.request['historical'] = True  # Untrusted payload cannot waive freshness.
        self.save()
        self.assert_code('STALE_REVIEW')

    def test_historical_summary_mismatch_is_still_rejected(self):
        self.begin_rework()
        self.advance_candidate('REWORK-01')
        self.start_retest()
        self.report['summary']['open_finding_ids'] = []
        self.save()
        self.assert_code('REVIEW_SUMMARY_MISMATCH')

    def test_historical_report_digest_is_still_checked(self):
        self.begin_rework()
        self.advance_candidate('REWORK-01')
        self.start_retest()
        path = self.root / 'gists/report.md'
        path.write_bytes(path.read_bytes() + b'\n')
        self.commit_records()
        self.assert_code('STALE_REVIEW')

    def test_historical_missing_evidence_is_still_rejected(self):
        self.begin_rework()
        self.advance_candidate('REWORK-01')
        self.start_retest()
        (self.root / 'gists/report.md').unlink()
        self.commit_records()
        self.assert_code('EVIDENCE_MISSING')

    def test_F03_T11_fresh_process_recovers_without_source_writes(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*.md')}
        command = [sys.executable, '-X', 'utf8', '-B', str(Path(tc.__file__)), str(self.root), '--format', 'json']
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        review = json.loads(result.stdout)['review_recovery']
        self.assertEqual(review['attempt_id'], 'attempt-1')
        self.assertEqual(review['open_finding_ids'], ['F-1'])
        self.assertEqual(review['open_findings'][0]['report_ref'], self.ref('report'))
        self.assertEqual(review['next_review_action'], 'resume-rework')
        self.assertFalse(review['quality_assessed'])
        event = json.loads(result.stderr)
        self.assertEqual(event['event'], 'review.resume')
        self.assertEqual(event['open_count'], 1)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*.md')})

    def test_F03_T12_old_attempt_rejected(self):
        self.report['attempt_id'] = 'attempt-old'
        self.save()
        self.assert_code('STALE_REVIEW')

    def test_F03_T12_old_target_rejected(self):
        self.report['target_refs'] = {'app': self.app_base}
        self.save()
        self.assert_code('STALE_REVIEW')

    def test_F03_T12_summary_mismatch_rejected(self):
        self.report['summary']['open_finding_ids'] = []
        self.save()
        self.assert_code('REVIEW_SUMMARY_MISMATCH')

    def test_missing_original_evidence_rejected(self):
        self.report['evidence_refs'] = [{'path': 'gists/absent.md', 'sha256': '0' * 64}]
        self.save()
        self.assert_code('EVIDENCE_MISSING')

    def test_changed_report_digest_rejected(self):
        path = self.root / 'gists/report.md'
        path.write_text(path.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        self.commit_records()
        self.assert_code('STALE_REVIEW')

    def test_missing_report_file_rejected(self):
        (self.root / 'gists/report.md').unlink()
        self.commit_records()
        self.assert_code('EVIDENCE_MISSING')

    def test_closed_report_never_grants_acceptance(self):
        self.report['findings'][0]['status'] = 'closed'
        self.report['summary']['open_finding_ids'] = []
        self.save()
        review = tc.build_context(self.root)['review_recovery']
        self.assertEqual(review['next_review_action'], 'needs-independent-recheck')
        self.assertFalse(review['quality_assessed'])

    def test_examples_do_not_enable_recovery(self):
        for text in ('> - Review recovery: gists/evil.md\n',
                     '```md\n- Review recovery: gists/evil.md\n```\n',
                     '    - Review recovery: gists/evil.md\n'):
            self.assertIsNone(rr.declaration(text))

    def test_git_move_during_recovery_is_rejected(self):
        original = rr.recover

        def move_after_recovery(*args):
            result = original(*args)
            if result is not None:
                fixture.git(self.app, 'commit', '--allow-empty', '-m', 'move during recovery')
            return result

        with patch.object(rr, 'recover', side_effect=move_after_recovery):
            self.assert_code('SOURCE_CHANGED')

    def test_missing_actual_commit_rejected(self):
        self.request['target_refs'] = {'app': 'f' * 40}
        self.save()
        self.assert_code('EVIDENCE_MISSING')

    def test_exact_duplicate_finding_is_scoped_and_deduplicated(self):
        self.report['findings'].append(dict(self.report['findings'][0]))
        self.save()
        resumed = tc.build_context(self.root)['review_recovery']
        self.assertEqual(resumed['open_finding_ids'], ['F-1'])
        self.assertEqual(resumed['open_findings'][0]['attempt_id'], 'attempt-1')

    def test_contradictory_duplicate_finding_rejected(self):
        self.report['findings'].append({'id': 'F-1', 'status': 'closed'})
        self.save()
        self.assert_code('INVALID_REVIEW_REFERENCE')


if __name__ == '__main__':
    unittest.main()
