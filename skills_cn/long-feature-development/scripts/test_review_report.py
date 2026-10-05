#!/usr/bin/env python3
"""Deterministic ledger tests, not independent reviewer or human decisions."""
import copy
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import io
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch
import review_report as rr


REF = {'path': 'gists/evidence.md', 'sha256': 'e' * 64}


def check(key='C1', outcome='PASS', findings=()):
    return {'id': key, 'outcome': outcome, 'required': True,
            'scope_ids': ['REQ-1'], 'evidence_refs': [copy.deepcopy(REF)] if outcome in ('PASS', 'FAIL') else [],
            'reason': 'Observed result' if outcome in ('PASS', 'FAIL') else 'Not applicable or evidence unavailable',
            'next_action': 'Obtain original evidence' if outcome in ('UNKNOWN', 'NOT-RUN') else '',
            'finding_ids': list(findings)}


def finding(key='F1', checks=('C1',), severity='P1'):
    return {'id': key, 'severity': severity, 'blocking': True, 'status': 'open',
            'description': 'A concrete failure', 'evidence_refs': [copy.deepcopy(REF)],
            'affected_check_ids': list(checks), 'resolution_ref': None,
            'verified_by': None, 'verified_ref': None, 'verified_target_refs': None,
            'nonblocking_reason': '', 'follow_up': 'Rework and independently recheck', 'violates_requirement': True,
            'severity_history': []}


def report(identity='report-1', attempt='attempt-1'):
    return {'schema': 'report-v1', 'report_ref': identity, 'feature': 'PIRC-31',
            'result': 'BLOCKED', 'reason': 'Synthetic report awaits real host verification',
            'review_task': 'REVIEW-1', 'packet_id': 'packet-1', 'attempt_id': attempt,
            'target_refs': {'app': 'a' * 40}, 'checklist_ref': copy.deepcopy(REF),
            'reviewer': 'reviewer-1',
            'context': {'source_ref': 'host:context-1', 'authority_ref': 'host:authorization-1',
                        'implementation_author': 'author-1'},
            'evidence_refs': [copy.deepcopy(REF)],
            'checks': [check()], 'findings': [], 'diagnostics': [], 'summary': {}}


def key_of(value, finding_id):
    return {'feature': value['feature'], 'report_ref': value['report_ref'],
            'attempt_id': value['attempt_id'], 'finding_id': finding_id}


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.report = report()

    def compute(self, **kwargs):
        return rr.compute_report(self.report, **kwargs)

    def assert_invalid(self, code=None, **kwargs):
        result = self.compute(**kwargs)
        self.assertFalse(result['summary']['valid'], result)
        self.assertIsNone(result['ratio'])
        self.assertIsNone(result['counts'])
        if code:
            self.assertIn(code, [d['code'] for d in result['diagnostics']])

    def fail_report(self):
        self.report['checks'] = [check(outcome='FAIL', findings=['F1'])]
        self.report['findings'] = [finding()]

    def test_five_outcomes_one_quarter(self):
        self.report['checks'] = [check('C' + str(i), outcome, ['F1'] if outcome == 'FAIL' else [])
                                 for i, outcome in enumerate(rr.OUTCOMES)]
        self.report['findings'] = [finding(checks=('C1',))]
        result = self.compute()
        self.assertTrue(result['summary']['valid'], result)
        self.assertEqual(result['ratio'], .25)
        self.assertEqual(result['counts']['all'], 4)
        self.assertEqual(result['counts']['total'], 5)
        self.assertEqual(result['counts']['by_outcome'], {x: 1 for x in rr.OUTCOMES})
        self.assertFalse(result['quality_assessed'])

    def test_all_na_has_null_ratio(self):
        self.report['checks'] = [check(outcome='N/A')]
        result = self.compute()
        self.assertTrue(result['summary']['valid'])
        self.assertIsNone(result['ratio'])
        self.assertEqual(result['counts']['all'], 0)

    def test_duplicate_check_and_unknown_outcome_rejected(self):
        self.report['checks'] *= 2
        self.assert_invalid('DUPLICATE_CHECK')
        self.report['checks'] = [check(outcome='SKIPPED')]
        self.assert_invalid('INVALID_OUTCOME')

    def test_missing_fields_not_a_complete_report(self):
        for field in self.report:
            with self.subTest(field=field):
                raw = copy.deepcopy(self.report)
                del raw[field]
                self.assertFalse(rr.compute_report(raw)['summary']['valid'])

    def test_pass_fail_need_evidence_and_unknown_needs_next_step(self):
        self.report['checks'][0]['evidence_refs'] = []
        self.assert_invalid('EVIDENCE_MISSING')
        self.report['checks'] = [check(outcome='UNKNOWN')]
        self.report['checks'][0]['next_action'] = ''
        self.assert_invalid('EVIDENCE_MISSING')

    def test_na_requires_reason(self):
        self.report['checks'] = [check(outcome='N/A')]
        self.report['checks'][0]['reason'] = ''
        self.assert_invalid('EVIDENCE_MISSING')

    def test_same_finding_two_checks_counts_once(self):
        self.report['checks'] = [check('C1', 'FAIL', ['F1']), check('C2', 'FAIL', ['F1'])]
        self.report['findings'] = [finding(checks=('C1', 'C2'))]
        result = self.compute()
        self.assertEqual(result['counts']['findings_total'], 1)
        self.assertEqual(result['counts']['open_by_severity']['P1'], 1)

    def test_identical_finding_repeat_deduplicates_conflict_rejects(self):
        self.fail_report()
        self.report['findings'].append(copy.deepcopy(self.report['findings'][0]))
        self.assertEqual(self.compute()['counts']['findings_total'], 1)
        self.report['findings'][1]['description'] = 'Different event'
        self.assert_invalid('CONFLICTING_FINDING')

    def test_same_name_in_different_reports_not_merged(self):
        self.fail_report()
        old = copy.deepcopy(self.report)
        old.update(report_ref='old-report', attempt_id='old-attempt')
        result = self.compute(related_reports=[old])
        self.assertEqual(result['counts']['findings_total'], 2)
        self.assertEqual(result['counts']['discovered_current'], 1)
        self.assertEqual(result['counts']['historical_only'], 1)

    def test_cross_report_duplicate_preserves_root_and_unrelated_event(self):
        self.fail_report()
        old = copy.deepcopy(self.report)
        old.update(report_ref='old-report', attempt_id='old-attempt')
        self.report['findings'][0].update(duplicate_of=key_of(old, 'F1'),
            duplicate_reason='Same reproduced root cause', duplicate_evidence_refs=[REF])
        self.report['checks'].append(check('C2', 'FAIL', ['F2']))
        self.report['findings'].append(finding('F2', ('C2',)))
        result = self.compute(related_reports=[old])
        self.assertTrue(result['summary']['valid'], result)
        self.assertEqual(result['counts']['findings_total'], 2)
        self.assertEqual(result['counts']['inherited_current'], 1)
        self.assertEqual(result['counts']['discovered_current'], 1)

    def test_duplicate_requires_full_key_and_proof(self):
        self.fail_report()
        self.report['findings'][0]['duplicate_of'] = 'F1'
        self.assert_invalid('INVALID_FINDING_KEY')
        self.report['findings'][0]['duplicate_of'] = key_of(self.report, 'F2')
        self.assert_invalid('EVIDENCE_MISSING')

    def test_duplicate_cycle_and_missing_target(self):
        self.fail_report()
        self.report['findings'][0].update(duplicate_of=key_of(self.report, 'F1'),
            duplicate_reason='Claimed duplicate', duplicate_evidence_refs=[REF])
        self.assert_invalid('DUPLICATE_CYCLE')
        self.report['findings'][0]['duplicate_of']['finding_id'] = 'missing'
        self.assert_invalid('FINDING_MISSING')

    def test_p0_nonblocking_and_truthy_booleans_rejected(self):
        self.fail_report()
        self.report['findings'][0].update(severity='P0', blocking=False)
        self.assert_invalid('INVALID_BLOCKING')
        self.report['findings'][0]['blocking'] = 'true'
        self.assert_invalid('INVALID_BLOCKING')

    def test_required_failure_cannot_be_nonblocking_without_real_exception(self):
        self.fail_report()
        self.report['findings'][0].update(blocking=False, nonblocking_reason='defer')
        self.assert_invalid('EXCEPTION_UNVERIFIED')

    def test_nonblocking_advice_requires_reason(self):
        self.report['checks'][0]['finding_ids'] = ['F1']
        self.report['findings'] = [finding(severity='P2')]
        self.report['findings'][0].update(blocking=False, violates_requirement=False)
        self.assert_invalid('EVIDENCE_MISSING')
        self.report['findings'][0]['nonblocking_reason'] = 'Naming preference, no requirement failure'
        result = self.compute()
        self.assertTrue(result['summary']['valid'])
        self.assertEqual(result['counts']['open_blockers'], 0)

    def test_author_cannot_close_and_unverified_closure_stays_open(self):
        self.fail_report()
        f = self.report['findings'][0]
        f.update(status='closed', resolution_ref=REF, verified_ref=REF,
                 verified_by='author-1', verified_target_refs=self.report['target_refs'])
        self.assert_invalid('INVALID_CLOSURE')
        f['verified_by'] = 'independent-reviewer'
        result = self.compute()
        self.assertTrue(result['summary']['valid'], result)
        self.assertEqual(result['counts']['open_blockers'], 1)
        self.assertIn('CLOSURE_UNVERIFIED', [d['code'] for d in result['diagnostics']])

    def test_p2_duplicate_cannot_hide_p0_root(self):
        self.fail_report()
        old = copy.deepcopy(self.report)
        old.update(report_ref='old-report', attempt_id='old-attempt')
        old['findings'][0]['severity'] = 'P0'
        self.report['findings'][0].update(severity='P2', duplicate_of=key_of(old, 'F1'),
            duplicate_reason='Same issue', duplicate_evidence_refs=[REF])
        result = self.compute(related_reports=[old])
        self.assertEqual(result['counts']['open_by_severity']['P0'], 1)

    def trusted(self, category, finding_id='F1'):
        identity = (self.report['feature'], self.report['report_ref'], self.report['attempt_id'])
        return rr.VerifiedReportEvidence(report_digests=frozenset({(identity, rr.report_digest(self.report))}),
            **{category: frozenset({(*identity, finding_id)})})

    def test_host_bound_current_closure_and_stale_digest(self):
        self.fail_report()
        f = self.report['findings'][0]
        f.update(status='closed', resolution_ref=REF, verified_ref=REF,
                 verified_by='independent-reviewer', verified_target_refs=self.report['target_refs'])
        trusted = self.trusted('closures')
        self.assertEqual(self.compute(verified=trusted)['counts']['open_blockers'], 0)
        self.report['target_refs'] = {'app': 'b' * 40}
        f['verified_target_refs'] = self.report['target_refs']
        self.assertEqual(self.compute(verified=trusted)['counts']['open_blockers'], 1)

    def test_real_exception_can_make_current_p1_nonblocking(self):
        self.fail_report()
        self.report['findings'][0].update(blocking=False, nonblocking_reason='Host verified exact scope exception',
                                         exception_ref=REF)
        result = self.compute(verified=self.trusted('exceptions'))
        self.assertTrue(result['summary']['valid'], result)
        self.assertEqual(result['counts']['open_blockers'], 0)
        self.assertEqual(result['counts']['open_by_severity']['P1'], 1)

    def test_verified_severity_change_retains_history(self):
        self.fail_report()
        f = self.report['findings'][0]
        f['severity'] = 'P2'
        f['severity_history'] = [{'from': 'P0', 'to': 'P2', 'reason': 'Impact rechecked',
            'verified_by': 'independent-reviewer', 'verified_ref': REF, 'target_refs': self.report['target_refs']}]
        self.assertEqual(self.compute()['counts']['by_severity']['P0'], 1)
        result = self.compute(verified=self.trusted('severity_changes'))
        self.assertEqual(result['counts']['by_severity']['P2'], 1)
        self.assertEqual(f['severity_history'][0]['from'], 'P0')

    def test_unverified_downgrade_cannot_make_effective_p0_nonblocking(self):
        self.report['checks'][0]['finding_ids'] = ['F1']
        f = finding(severity='P2')
        f.update(blocking=False, violates_requirement=False, nonblocking_reason='Claimed lower impact')
        f['severity_history'] = [{'from': 'P0', 'to': 'P2', 'reason': 'Claimed recheck',
            'verified_by': 'reviewer', 'verified_ref': REF, 'target_refs': self.report['target_refs']}]
        self.report['findings'] = [f]
        result = self.compute()
        self.assertEqual(result['counts']['open_by_severity']['P0'], 1)
        self.assertEqual(result['counts']['open_blockers'], 1)

    def test_verified_history_closure_requires_exact_current_target(self):
        old = report('old-report', 'old-attempt')
        old['checks'] = [check(outcome='FAIL', findings=['F1'])]
        old['findings'] = [finding()]
        old['findings'][0].update(status='closed', resolution_ref=REF, verified_ref=REF,
            verified_by='independent-reviewer', verified_target_refs=old['target_refs'])
        identity = (old['feature'], old['report_ref'], old['attempt_id'])
        trusted = rr.VerifiedReportEvidence(
            report_digests=frozenset({(identity, rr.report_digest(old))}),
            closures=frozenset({(*identity, 'F1')}))
        self.assertEqual(self.compute(related_reports=[old], verified=trusted)['counts']['open_blockers'], 0)
        self.report['target_refs'] = {'app': 'b' * 40}
        self.assertEqual(self.compute(related_reports=[old], verified=trusted)['counts']['open_blockers'], 1)

    def test_json_claim_is_not_host_verification(self):
        self.fail_report()
        f = self.report['findings'][0]
        f.update(status='closed', resolution_ref=REF, verified_ref=REF,
                 verified_by='independent-reviewer', verified_target_refs=self.report['target_refs'])
        self.assertEqual(self.compute(verified={'closures': ['F1']})['counts']['open_blockers'], 1)

    def test_one_way_finding_links_rejected(self):
        self.fail_report()
        self.report['checks'].append(check('C2', 'PASS', ['F1']))
        self.assert_invalid('FINDING_LINK_MISMATCH')

    def test_reuse_keeps_explicit_source_and_diff_without_granting_quality(self):
        self.report['checks'][0]['reuse'] = {
            'prior_check_ref': {'feature': 'PIRC-31', 'report_ref': 'old-report',
                                'attempt_id': 'old-attempt', 'check_id': 'C1'},
            'diff_refs': [REF], 'dependency_refs': [REF], 'reviewer_basis': 'Actual diff reviewed'}
        result = self.compute()
        self.assertTrue(result['summary']['valid'])
        self.assertFalse(result['quality_assessed'])
        self.report['checks'][0]['reuse']['diff_refs'] = []
        self.assert_invalid('EVIDENCE_MISSING')

    def test_resource_bounds_bytes_and_links(self):
        with patch.object(rr, 'MAX_BYTES', 8):
            self.assert_invalid('RESOURCE_LIMIT')
        with patch.object(rr, 'MAX_LINKS', 1):
            self.assert_invalid('RESOURCE_LIMIT')

    def test_long_duplicate_chain_is_iterative(self):
        length = 1500
        self.report['checks'] = [check(findings=['F' + str(i) for i in range(length)])]
        self.report['findings'] = [finding('F' + str(i), severity='P2') for i in range(length)]
        for i, value in enumerate(self.report['findings'][1:], 1):
            value.update(duplicate_of=key_of(self.report, 'F' + str(i - 1)),
                         duplicate_reason='Same event', duplicate_evidence_refs=[REF])
        result = self.compute()
        self.assertTrue(result['summary']['valid'], result)
        self.assertEqual(result['counts']['findings_total'], 1)

    def test_ten_thousand_checks_within_declared_bound(self):
        self.report['checks'] = [check('C' + str(i)) for i in range(10000)]
        result = self.compute()
        self.assertTrue(result['summary']['valid'], result)
        self.assertEqual(result['counts']['all'], 10000)
        self.report['checks'].append(check('overflow'))
        self.assert_invalid('RESOURCE_LIMIT')

    def test_summary_is_recomputed_and_stale_claim_rejected(self):
        result = self.compute()
        self.report['summary'] = result['summary']
        self.assertTrue(self.compute()['summary']['valid'])
        self.report['summary']['counts']['all'] = 100
        self.assert_invalid('SUMMARY_MISMATCH')

    def test_success_requires_no_known_blockers_or_required_unknowns(self):
        self.report['result'] = 'SUCCESS'
        self.assertTrue(self.compute()['summary']['valid'])
        self.report['checks'] = [check(outcome='UNKNOWN')]
        self.assert_invalid('RESULT_MISMATCH')
        self.fail_report()
        self.assert_invalid('RESULT_MISMATCH')
        self.report['result'] = 'FAILED'
        self.assertTrue(self.compute()['summary']['valid'])

    def test_all_na_cannot_claim_success(self):
        self.report['result'] = 'SUCCESS'
        self.report['checks'] = [check(outcome='N/A')]
        self.assert_invalid('RESULT_MISMATCH')

    def test_nonblocking_requires_follow_up_not_just_reason(self):
        self.report['checks'][0]['finding_ids'] = ['F1']
        self.report['findings'] = [finding(severity='P2')]
        self.report['findings'][0].update(blocking=False, violates_requirement=False,
                                         nonblocking_reason='Naming suggestion', follow_up='')
        self.assert_invalid('EVIDENCE_MISSING')

    def test_result_is_not_task_state_and_reason_must_exist(self):
        self.report['result'] = 'DONE'
        self.assert_invalid('INVALID_RESULT')
        self.report['result'] = 'BLOCKED'
        self.report['reason'] = ''
        self.assert_invalid('INVALID_RESULT')

    def test_input_is_unchanged(self):
        before = copy.deepcopy(self.report)
        self.compute()
        self.assertEqual(self.report, before)

    def test_installed_deterministic_fixtures(self):
        source = Path(__file__).parent / 'fixtures/review-report.json'
        fixtures = json.loads(source.read_text(encoding='utf-8'))
        for case in fixtures['cases']:
            with self.subTest(case=case['id']):
                result = rr.compute_report(case['report'], related_reports=case['related'])
                self.assertTrue(result['summary']['valid'], result)
                self.assertEqual(result['ratio'], case['expected']['ratio'])
                for name in ('all', 'total', 'findings_total'):
                    self.assertEqual(result['counts'][name], case['expected'][name])

    def test_nonblocking_diagnostic_does_not_invent_a_quality_failure(self):
        self.report['result'] = 'SUCCESS'
        self.report['diagnostics'] = [{'code': 'INFORMATIONAL', 'reason': 'Optional detail', 'blocking': False}]
        self.assertTrue(self.compute()['summary']['valid'])
        self.report['diagnostics'][0]['code'] = 'MISSING_SCOPE'
        self.assert_invalid('INVALID_DIAGNOSTIC')

    def test_reported_diagnostics_are_preserved_without_prose_in_cli_metadata(self):
        self.report['diagnostics'] = [{'code': 'MISSING_SCOPE', 'reason': 'SENTINEL original prose'}]
        result = self.compute()
        self.assertTrue(result['summary']['valid'])
        self.assertEqual(result['diagnostics'][0]['code'], 'MISSING_SCOPE')
        self.assertEqual(result['diagnostics'][0]['evidence_scope'], 'current')
        self.assertNotIn('SENTINEL', json.dumps(result))

    def test_counts_and_time_budget_fail_closed(self):
        with patch.object(rr, 'MAX_CHECKS', 0):
            self.assert_invalid('RESOURCE_LIMIT')
        with patch.object(rr, 'MAX_SECONDS', -1):
            self.assert_invalid('RESOURCE_LIMIT')

    def test_json_duplicate_keys_and_nonfinite_values_rejected(self):
        for raw in ('{"schema":"report-v1","schema":"report-v1"}', '{"value":NaN}'):
            self.assertFalse(rr.compute_report(raw)['summary']['valid'])

    def test_malformed_types_controlled_without_prose_leak(self):
        for field in self.report:
            for value in (None, True, 1, ['SENTINEL'], {'bad': 'SENTINEL'}):
                raw = copy.deepcopy(self.report)
                raw[field] = value
                result = rr.compute_report(raw)
                self.assertFalse(result['summary']['valid'], (field, value))
                self.assertNotIn('SENTINEL', json.dumps(result))


class ReportCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'gists').mkdir()
        (self.root / 'tasks').mkdir()
        self.source = self.root / 'gists/report.md'
        self.source.write_text(json.dumps(report()), encoding='utf-8')
        (self.root / 'tasks/REVIEW-1.md').write_text('- Gists: gists/report.md', encoding='utf-8')

    def run_cli(self, expected, *args):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        proc = subprocess.run([sys.executable, '-B', rr.__file__, str(self.root),
                               'gists/report.md', *args], capture_output=True)
        self.assertEqual(proc.returncode, expected, proc.stderr.decode(errors='replace'))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(proc.stderr, b'')
        return json.loads(proc.stdout)

    def test_read_only_real_file_cli(self):
        result = self.run_cli(0)
        self.assertEqual(result['ratio'], 1.0)
        self.assertFalse(result['source_evidence_verified'])
        self.assertFalse(result['quality_assessed'])

    def test_native_readonly_clis_do_not_create_bytecode(self):
        from test_review_packet import fixture
        packet, documents = fixture()
        packet_root = self.root / 'packet-feature'
        for name, data in documents.items():
            path = packet_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (packet_root / 'tasks').mkdir()
        (packet_root / 'tasks/REVIEW-1.md').write_text('- Gists: gists/packet.md, ' + ', '.join(
            name for name in documents if name.startswith('gists/')), encoding='utf-8')
        (packet_root / 'gists/packet.md').write_text(json.dumps(packet), encoding='utf-8')
        env = dict(os.environ)
        env.pop('PYTHONDONTWRITEBYTECODE', None)
        for script, root, path in (('review_report.py', self.root, 'gists/report.md'),
                                   ('review_packet.py', packet_root, 'gists/packet.md')):
            with self.subTest(script=script):
                installed = self.root / ('installed-' + script)
                shutil.copytree(Path(rr.__file__).parent.parent, installed,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                before = {str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file()}
                proc = subprocess.run([sys.executable, str(installed / 'scripts' / script),
                                       str(root), path], capture_output=True, env=env)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors='replace'))
                after = {str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file()}
                self.assertEqual(sorted(after - before), [])

    def test_report_and_control_file_must_not_alias(self):
        data = json.loads(self.source.read_text(encoding='utf-8'))
        self.source.write_text('- Gists: gists/report.md\n```report-v1\n' + json.dumps(data) + '\n```\n', encoding='utf-8')
        detail = self.root / 'tasks/REVIEW-1.md'
        detail.unlink()
        os.link(self.source, detail)
        self.assertEqual(self.run_cli(2)['diagnostics'][0]['code'], 'DUPLICATE_REPORT')

    def test_undeclared_history_is_not_opened(self):
        result = self.run_cli(2, '--related', 'gists/does-not-exist.md')
        self.assertEqual(result['diagnostics'][0]['code'], 'UNDECLARED_REPORT')

    def test_legacy_and_duplicate_json_are_rejected_without_upgrading(self):
        self.source.write_text('{"schema":"report-v1"}', encoding='utf-8')
        self.assertEqual(self.run_cli(2)['diagnostics'][0]['code'], 'LEGACY_EVIDENCE_INCOMPLETE')
        self.source.write_text('{"schema":"report-v1","schema":"report-v1"}', encoding='utf-8')
        self.assertFalse(self.run_cli(2)['summary']['valid'])

    def test_read_set_changes_rejected(self):
        original = rr.LocalMarkdownLoader._read_raw
        reads = {}
        def changed(loader, name, allowance):
            data, identity = original(loader, name, allowance)
            reads[name] = reads.get(name, 0) + 1
            if name == 'gists/report.md' and reads[name] == 2:
                return data + b' ', identity
            return data, identity
        output = io.StringIO()
        with patch.object(rr.LocalMarkdownLoader, '_read_raw', changed), redirect_stdout(output):
            self.assertEqual(rr.main([str(self.root), 'gists/report.md']), 2)
        self.assertEqual(json.loads(output.getvalue())['diagnostics'][0]['code'], 'SOURCE_CHANGED')


if __name__ == '__main__':
    unittest.main()
