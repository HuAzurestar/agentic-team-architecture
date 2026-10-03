#!/usr/bin/env python3
"""Actual Git/files/strict feature composition; identity transport is synthetic."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.dont_write_bytecode = True
import quality_host as host
import quality_source as source
import quality_git as integration
import review_report as reports
import task_context as tc
import test_task_reconcile as fixture
import test_review_report as report_fixture
from test_task_context import git


class HostTests(unittest.TestCase):
    commit_records = fixture.RecoveryTests.commit_records

    def setUp(self):
        fixture.RecoveryTests.setUp(self)
        remote = self.workspace / 'remote.git'
        subprocess.check_call(['git', 'init', '--bare', '-q', str(remote)])
        git(self.app, 'remote', 'set-url', 'origin', str(remote))
        git(self.app, 'push', '-q', 'origin', 'main')
        status = self.root / 'STATUS.md'
        status.write_text(status.read_text(encoding='utf-8').replace(
            'https://example.invalid/app.git', str(remote)), encoding='utf-8')
        self.binding = integration.IntegrationBinding(self.app, 'app', 'origin', str(remote),
            'task', self.app_head, git(self.app, 'rev-parse', 'HEAD^{tree}'), 'main', self.app_base)
        paths = ['parser', 'quality-request', 'report', 'tests', 'checklist']
        self.paths = tuple('gists/' + name + '.md' for name in paths)
        detail_path = self.root / 'tasks/DEV-02.md'
        base = detail_path.read_text(encoding='utf-8').replace('- Gists: gists/parser.md',
                '- Gists: ' + ', '.join(self.paths))
        detail_path.write_text(base, encoding='utf-8')
        table = (self.root / 'TASKS.md').read_text(encoding='utf-8')
        rows = []
        for task, kind, contract in [
            ('REVIEW-1', 'Review', '| Blocking findings | 0 |\n| Deferred findings | 0 |\n| Result gist | gists/report.md |\n'),
            ('TEST-1', 'Test', '| Environment | fixture |\n| Planned checks | T1 |\n| Executed | 1 |\n'
             '| Passed | 1 |\n| Failed | 0 |\n| Skipped | 0 |\n| Unknown | 0 |\n| Result gist | gists/tests.md |\n')]:
            text = base.replace('DEV-02', task)
            for sha in (self.app_head, self.pm_base):
                text = text.replace(f'| {sha} | - |', f'| {sha} | {sha} |')
            text += '\n## Type contract\n\n| Field | Value |\n| --- | --- |\n' + f'| Target SHA | {self.app_head} |\n' + contract
            (self.root / f'tasks/{task}.md').write_text(text, encoding='utf-8')
            rows.append(f'| {task} | {kind} | Fixture completed | `DONE` | reviewer-fixture | SOL-001 | '
                        f'2026-10-03T09:00:00Z | 2026-10-03T10:00:00Z | pm@{self.pm_base}; app@{self.app_head} |')
        table = table.replace('| GATE-ACCEPT |', '\n'.join(rows) + '\n| GATE-ACCEPT |', 1)
        (self.root / 'TASKS.md').write_text(tc.synchronized_topology(table), encoding='utf-8')
        required = [dict(id='C1', scope_ids=['REQ-001', 'SOL-001'])]
        self.write('checklist', dict(schema='quality-checklist-v1', required_checks=required))
        report = report_fixture.report()
        report.update(feature='PIRC-23', review_task='REVIEW-1', result='SUCCESS',
                      target_refs={'app': self.app_head}, checklist_ref=self.ref('checklist'),
                      evidence_refs=[self.ref('parser')])
        report['checks'][0].update(scope_ids=['REQ-001', 'SOL-001'], evidence_refs=[self.ref('parser')])
        tests = dict(schema='test-results-v1', test_task='TEST-1', target_refs={'app': self.app_head},
            attempt_id='attempt-1', checks=[dict(id='T1', required=True, outcome='PASS',
                scope_ids=['REQ-001', 'SOL-001'], evidence_refs=[self.ref('parser')], reason='Synthetic test result')])
        self.request = dict(schema='quality-request-v1', feature='PIRC-23', phase='pre_accept',
            target_refs={'app': self.app_head}, attempt_id='attempt-1', checklist_ref=self.ref('checklist'),
            required_checks=required, report=report, related_reports=[], tests=tests, result_tests=None,
            frozen={'app': dict(source_tree=self.binding.source_tree, target_before=self.app_base, result=None)}, acceptance=None)
        self.write('report', report)
        self.write('tests', tests)
        self.save()
        self.roles = host.SourceRoles('gists/quality-request.md', 'gists/report.md', 'gists/tests.md', 'gists/checklist.md')

    def write(self, name, obj):
        (self.root / f'gists/{name}.md').write_text(json.dumps(obj), encoding='utf-8')

    def ref(self, name):
        path = f'gists/{name}.md'
        return dict(path=path, sha256=hashlib.sha256((self.root / path).read_bytes()).hexdigest())

    def save(self):
        self.write('quality-request', self.request)
        self.commit_records()
        head = git(self.pm, 'rev-parse', 'HEAD')
        self.documents = tuple(source.GitDocument(path, self.pm, 'project/PIRC-23/' + path, head) for path in self.paths)

    def provenance(self, probe):
        # Explicit synthetic host fixture: not evidence of real reviewer identity.
        obj = json.loads(probe.request)
        digest = reports.report_digest(obj['report'])
        return host.HostProvenance(probe.digest, independent_reports=frozenset({digest}), current_review_digest=digest)

    def evaluate(self, **kwargs):
        return host.evaluate(self.root, **(dict(documents=self.documents, roles=self.roles,
            repositories=(self.binding,), read_provenance=self.provenance,
            repo_overrides={'app': self.app, 'pm': self.pm}) | kwargs))

    def test_actual_originals_and_git_compose_policy_without_writes(self):
        before = {str(p): p.read_bytes() for repo in (self.app, self.pm) for p in repo.rglob('*') if p.is_file()}
        result = self.evaluate()
        self.assertTrue(result.result['allowed'], result.result)
        self.assertFalse(result.result['merge_authorized'])
        self.assertEqual(before, {str(p): p.read_bytes() for repo in (self.app, self.pm) for p in repo.rglob('*') if p.is_file()})
        inputs = result.for_task('host:current-selection', 'DEV-02')
        self.assertEqual(inputs.observations.source_refs, frozenset((p, hashlib.sha256((self.root/p).read_bytes()).hexdigest()) for p in self.paths))

    def test_no_provenance_cannot_promote_real_originals(self):
        result = self.evaluate(read_provenance=None)
        self.assertFalse(result.result['allowed'])
        self.assertIn('INDEPENDENCE_UNVERIFIED', result.result['reason_codes'])

    def test_real_hash_cannot_pair_with_fabricated_pass_details(self):
        self.request['tests']['checks'][0]['reason'] = 'fabricated summary'
        self.save()
        result = self.evaluate()
        self.assertFalse(result.result['allowed'])
        self.assertIsNone(result.observations)

    def test_original_must_match_declared_task_result(self):
        self.write('other-report', self.request['report'])
        self.paths += ('gists/other-report.md',)
        path = self.root / 'tasks/DEV-02.md'
        path.write_text(path.read_text(encoding='utf-8').replace('- Gists: ',
            '- Gists: gists/other-report.md, '), encoding='utf-8')
        self.save()
        result = self.evaluate(roles=replace(self.roles, report='gists/other-report.md'))
        self.assertEqual(result.result['reason_codes'], ['TASK_SOURCE_MISMATCH'])
        # Identical bytes at a second tracked path cannot alias the declared source.
        bindings = tuple(replace(d, relative_path='project/PIRC-23/gists/other-report.md')
                         if d.logical_path == self.roles.report else d for d in self.documents)
        self.assertEqual(self.evaluate(documents=bindings).result['reason_codes'], ['TASK_SOURCE_MISMATCH'])

    def test_checklist_catalog_cannot_be_self_selected_by_request(self):
        self.request['required_checks'][0]['scope_ids'] = ['REQ-001']
        self.save()
        self.assertEqual(self.evaluate().result['reason_codes'], ['CHECKLIST_SOURCE_MISMATCH'])

    def test_wrong_provenance_binding_and_json_proof_rejected(self):
        for reader in (lambda p: host.HostProvenance('old'), lambda p: dict(allowed=True)):
            result = self.evaluate(read_provenance=reader)
            self.assertEqual(result.result['reason_codes'], ['PROVENANCE_BINDING_MISMATCH'])

    def test_source_changes_during_provenance_are_preserved_and_deny(self):
        def reader(probe):
            (self.root / 'gists/tests.md').write_text('changed externally', encoding='utf-8')
            return self.provenance(probe)
        result = self.evaluate(read_provenance=reader)
        self.assertFalse(result.result['allowed'])
        self.assertEqual((self.root / 'gists/tests.md').read_text(), 'changed externally')

    def test_second_provenance_read_cannot_revoke_silently(self):
        calls = []
        def reader(probe):
            calls.append(1)
            return self.provenance(probe) if len(calls) == 1 else host.HostProvenance(probe.digest)
        self.assertEqual(self.evaluate(read_provenance=reader).result['reason_codes'], ['QUALITY_PROVENANCE_CHANGED'])

    def test_last_provenance_callback_cannot_change_sources_unnoticed(self):
        calls = []
        def reader(probe):
            calls.append(1)
            if len(calls) == 2:
                (self.root / 'gists/tests.md').write_text('late edit', encoding='utf-8')
            return self.provenance(probe)
        result = self.evaluate(read_provenance=reader)
        self.assertFalse(result.result['allowed'])
        self.assertIsNone(result.observations)

    def test_reader_error_is_redacted(self):
        def reader(probe):
            raise RuntimeError('secret user reply and credential')
        result = self.evaluate(read_provenance=reader)
        self.assertEqual(result.result['reason_codes'], ['PROVENANCE_UNAVAILABLE'])
        self.assertNotIn('secret', str(result))

    def test_remote_move_blocks_real_aggregation(self):
        git(self.app, 'push', '-q', 'origin', 'task:main')
        self.assertEqual(self.evaluate().result['reason_codes'], ['DELIVERY_NOT_READY'])

    def test_dirty_metadata_is_not_a_transition_bypass(self):
        with (self.root / 'STATUS.md').open('a', encoding='utf-8') as stream:
            stream.write('\nPrepared but not reconciled\n')
        self.assertFalse(self.evaluate().result['allowed'])

    def test_completed_test_with_actual_failure_denies(self):
        self.request['tests']['checks'][0]['outcome'] = 'FAIL'
        self.write('tests', self.request['tests'])
        self.save()
        result = self.evaluate()
        self.assertFalse(result.result['allowed'])
        self.assertIn('REQUIRED_TEST_NOT_PASSED', result.result['reason_codes'])

    def test_pre_merge_still_requires_actual_acceptance(self):
        self.request['phase'] = 'pre_merge'
        self.save()
        result = self.evaluate()
        self.assertFalse(result.result['allowed'])
        self.assertIn('ACCEPTANCE_REQUIRED', result.result['reason_codes'])


if __name__ == '__main__':
    unittest.main()
