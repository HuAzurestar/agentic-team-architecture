#!/usr/bin/env python3
"""Packet contract tests; synthetic host facts are NOT an independent review."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import io
from contextlib import redirect_stdout
import review_packet as rp


def fixture():
    documents = {p: value.encode() for p, value in {
        'REQUIREMENT.md': '## REQ-1\nRequired behaviour, including a new case.',
        'SOLUTION.md': '## SOL-1\nImplementation plan.',
        'gists/checklist.md': 'C-1: inspect original requirement and implementation',
        'gists/test.md': 'Actual fixed-candidate test record',
        'gists/contract.md': 'C1/0.1',
        'gists/source.md': 'Fixed-candidate source snapshot',
    }.items()}
    def ref(path):
        return {'path': path, 'sha256': hashlib.sha256(documents[path]).hexdigest()}
    packet = {
        'schema': 'review-packet-v1', 'packet_id': 'packet-1', 'attempt_id': 'attempt-1',
        'reviewer_assignment': 'reviewer-1', 'feature': 'PIRC-31',
        'review_task': 'REVIEW-1', 'mode': 'review',
        'target_refs': {'app': 'a' * 40},
        'repositories': {'app': {'identity': 'https://example.org/org/app.git',
                                 'source_refs': [ref('gists/source.md')]}},
        'scope': {'requirement_ids': ['REQ-1'], 'solution_ids': ['SOL-1'],
                  'requirement_ref': ref('REQUIREMENT.md'),
                  'solution_ref': ref('SOLUTION.md'),
                  'acceptance_scope': 'Required behaviour', 'exclusions': []},
        'checklist_ref': ref('gists/checklist.md'), 'checklist_reason': 'Required scope',
        'required_check_ids': ['C-1'],
        'evidence_refs': [{**ref('gists/test.md'), 'kind': 'test'},
                          {**ref('gists/contract.md'), 'kind': 'contract'}],
        'authority': {'source_ref': 'host:authorization-1', 'read_only': True,
                      'allowed_tools': ['read', 'diff']},
        'limits': {'max_files': 1000, 'max_bytes': 67108864,
                   'max_file_bytes': 4194304, 'max_checks': 10000},
        'prior_report_refs': [],
        'expected_output': {'schema': 'report-v1', 'path': 'review-output/report-1.md',
                            'coordinator': 'author', 'missing_policy': 'UNKNOWN/NOT-RUN'},
    }
    return packet, documents


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.packet, self.docs = fixture()

    def build(self, **kwargs):
        return rp.build_packet(self.packet, documents=self.docs, **kwargs)

    def test_complete_material_is_not_independence_or_dispatch(self):
        result = self.build()
        self.assertTrue(result['complete'])
        self.assertFalse(result['handoff_allowed'])
        self.assertIn('INDEPENDENCE_UNVERIFIED', result['reason_codes'])
        self.assertEqual(result['independent_executed'], 0)

    def test_missing_original_not_replaced_by_summary(self):
        del self.docs['REQUIREMENT.md']
        result = self.build()
        self.assertFalse(result['complete'])
        self.assertIn('INCOMPLETE_PACKET', result['reason_codes'])
        self.assertTrue(any(x['field'].startswith('scope.requirement_ref') for x in result['missing']))

    def test_stale_source(self):
        self.docs['REQUIREMENT.md'] += b' changed'
        self.assertIn('SOURCE_CHANGED', self.build()['reason_codes'])

    def test_scope_must_be_present_in_original_not_example(self):
        for source in ('# Summary\nREQ-1 exists', '```md\n## REQ-1\n```',
                       '<!--\n## REQ-1\n-->'):
            self.docs['REQUIREMENT.md'] = source.encode()
            self.packet['scope']['requirement_ref']['sha256'] = hashlib.sha256(source.encode()).hexdigest()
            self.assertIn('SCOPE_MISSING', self.build()['reason_codes'])

    def test_summary_file_cannot_replace_requirement_original(self):
        self.packet['scope']['requirement_ref'] = self.packet['checklist_ref']
        self.assertFalse(self.build()['complete'])

    def test_required_fields(self):
        for key in self.packet:
            with self.subTest(key=key):
                changed = copy.deepcopy(self.packet)
                del changed[key]
                self.assertFalse(rp.build_packet(changed, documents=self.docs)['complete'])

    def test_no_bool_integer_or_nonfinite_limits(self):
        for value in (True, 0, -1, 1001, float('nan')):
            self.packet['limits']['max_files'] = value
            self.assertFalse(self.build()['complete'])

    def test_duplicate_ids_and_sources(self):
        self.packet['required_check_ids'] *= 2
        self.assertFalse(self.build()['complete'])
        self.packet['required_check_ids'] = ['C-1']
        self.packet['evidence_refs'] *= 2
        self.assertFalse(self.build()['complete'])

    def test_unsafe_paths_and_output_overwrite(self):
        for path in ('../outside', '/absolute', 'https://example.org/private',
                     'C:/secret', 'tasks/REVIEW-1.md', 'REQUIREMENT.md',
                     'gists/test.md'):
            with self.subTest(path=path):
                self.packet['expected_output']['path'] = path
                self.assertFalse(self.build()['complete'])

    def test_single_and_aggregate_byte_limits(self):
        self.packet['limits']['max_file_bytes'] = 8
        self.assertIn('RESOURCE_LIMIT', self.build()['reason_codes'])
        self.packet['limits']['max_file_bytes'] = 4194304
        self.packet['limits']['max_bytes'] = 8
        self.assertIn('RESOURCE_LIMIT', self.build()['reason_codes'])

    def test_prior_reports_remain_unexpanded(self):
        self.packet['prior_report_refs'] = [{'path': 'gists/old.md', 'sha256': 'b' * 64}]
        self.assertTrue(self.build()['complete'])
        self.assertNotIn('gists/old.md', self.build()['initial_source_paths'])

    def test_schema_rejects_unknown_credentials_and_claimed_host(self):
        self.packet['host_verified'] = True
        self.assertFalse(self.build()['complete'])
        del self.packet['host_verified']
        self.packet['authority']['token'] = 'SENTINEL-DO-NOT-LOG'
        result = self.build()
        self.assertFalse(result['complete'])
        self.assertNotIn('SENTINEL', str(result['missing']))

    def test_input_unchanged_and_result_detached(self):
        before = copy.deepcopy(self.packet)
        result = self.build()
        result['packet']['scope']['requirement_ids'].append('REQ-2')
        self.assertEqual(self.packet, before)

    def test_attempt_reuse_after_sha_or_checklist_change(self):
        prior = copy.deepcopy(self.packet)
        self.packet['target_refs']['app'] = 'b' * 40
        self.assertIn('ATTEMPT_REUSED', self.build(previous_packets=[prior])['reason_codes'])
        self.packet['attempt_id'] = 'attempt-2'
        self.packet['packet_id'] = 'packet-2'
        self.packet['reviewer_assignment'] = 'reviewer-2'
        self.assertTrue(self.build(previous_packets=[prior])['complete'])

    def test_host_facts_bound_to_packet_and_readonly_output(self):
        result = self.build()
        host = rp.HandoffEvidence(result['packet_digest'], 'host:authorization-1',
                                  'reviewer-1', 'context:fresh-1', True, True,
                                  'review-output/report-1.md', 'host:provenance-1')
        allowed = self.build(host=host)
        self.assertTrue(allowed['handoff_allowed'])
        self.assertEqual(allowed['independent_executed'], 0)
        self.packet['attempt_id'] = 'other'
        self.assertFalse(self.build(host=host)['handoff_allowed'])

    def test_same_context_no_authority_and_dict_claim_rejected(self):
        digest = self.build()['packet_digest']
        for fresh, authorized in ((False, True), (True, False), (False, False)):
            host = rp.HandoffEvidence(digest, 'host:authorization-1', 'reviewer-1',
                                      'context:one', fresh, authorized,
                                      'review-output/report-1.md', 'host:provenance-1')
            self.assertFalse(self.build(host=host)['handoff_allowed'])
        self.assertFalse(self.build(host={'fresh_context': True})['handoff_allowed'])

    def test_partial_results_preserve_execution_and_fill_missing(self):
        rows = [{'id': 'C-1', 'outcome': 'PASS', 'evidence_refs': ['actual:1']}]
        result = rp.remaining_checks(['C-1', 'C-2'], rows, 'budget exhausted', 'new attempt')
        self.assertEqual(result[0], rows[0])
        self.assertEqual(result[1]['outcome'], 'NOT-RUN')
        self.assertEqual(rows, [{'id': 'C-1', 'outcome': 'PASS', 'evidence_refs': ['actual:1']}])

    def test_malformed_types_never_raise_or_pass(self):
        for key in self.packet:
            for value in (None, True, 1, [], {}, ['bad'], {'bad': []}):
                with self.subTest(key=key, value=value):
                    candidate = copy.deepcopy(self.packet)
                    candidate[key] = value
                    # An empty list is the correct no-history representation.
                    if key == 'prior_report_refs' and value == []:
                        continue
                    if key == 'required_check_ids' and value == ['bad']:
                        continue  # Check IDs are local identifiers, not a fixed prefix.
                    self.assertFalse(rp.build_packet(candidate, documents=self.docs)['complete'])

    def test_duplicate_prior_and_original_alias_rejected(self):
        self.packet['prior_report_refs'] = [self.packet['checklist_ref']]
        self.assertFalse(self.build()['complete'])
        self.packet['prior_report_refs'] *= 2
        self.assertFalse(self.build()['complete'])

    def test_same_packet_history_is_not_new_dispatch(self):
        digest = self.build()['packet_digest']
        host = rp.HandoffEvidence(digest, 'host:authorization-1', 'reviewer-1',
                                  'context:one', True, True,
                                  'review-output/report-1.md', 'host:provenance-1')
        result = self.build(host=host, previous_packets=[copy.deepcopy(self.packet)])
        self.assertTrue(result['complete'])
        self.assertFalse(result['handoff_allowed'])
        self.assertIn('ALREADY_DISPATCHED', result['reason_codes'])

    def test_all_na_and_duplicate_partial_inventory_not_fabricated(self):
        for rows in ([{'id': 'C-1'}, {'id': 'C-1'}], [{'id': 'unknown'}]):
            with self.assertRaises(rp.LoaderError):
                rp.remaining_checks(['C-1'], rows, 'missing evidence', 'rerun')
        row = {'id': 'C-1', 'outcome': 'UNKNOWN', 'reason': 'missing original'}
        self.assertEqual(rp.remaining_checks(['C-1'], [row], 'budget', 'resume'), [row])


class PacketCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.packet, self.docs = fixture()
        for name, raw in self.docs.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (self.root / 'tasks').mkdir()
        self.detail = self.root / 'tasks/REVIEW-1.md'
        self.detail.write_text('- Gists: gists/packet.md, ' + ', '.join(
            name for name in self.docs if name.startswith('gists/')), encoding='utf-8')
        self.save()

    def save(self):
        (self.root / 'gists/packet.md').write_text(json.dumps(self.packet), encoding='utf-8')

    def run_cli(self, expected):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        run = subprocess.run([sys.executable, '-B', str(Path(rp.__file__)),
                              str(self.root), 'gists/packet.md'], capture_output=True)
        self.assertEqual(run.returncode, expected, run.stderr.decode(errors='replace'))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(run.stderr, b'')
        return json.loads(run.stdout)

    def test_real_files_complete_without_independence(self):
        result = self.run_cli(0)
        self.assertTrue(result['complete'])
        self.assertFalse(result['handoff_allowed'])
        self.assertNotIn('packet', result)

    def test_undeclared_packet(self):
        self.detail.write_text('- Gists: none', encoding='utf-8')
        self.assertFalse(self.run_cli(2)['complete'])

    def test_undeclared_source_not_read(self):
        self.detail.write_text('- Gists: gists/packet.md', encoding='utf-8')
        self.assertFalse(self.run_cli(2)['complete'])

    def test_missing_source_and_stale_source(self):
        (self.root / 'REQUIREMENT.md').unlink()
        self.assertIn('INCOMPLETE_PACKET', self.run_cli(2)['reason_codes'])
        (self.root / 'REQUIREMENT.md').write_bytes(b'changed')
        self.assertIn('SOURCE_CHANGED', self.run_cli(2)['reason_codes'])

    def test_prior_report_is_never_opened(self):
        self.packet['prior_report_refs'] = [{'path': 'gists/private-old.md', 'sha256': 'b' * 64}]
        self.save()
        self.assertTrue(self.run_cli(0)['complete'])

    def test_no_summary_or_credential_leak(self):
        self.packet['authority']['token'] = 'SENTINEL-SECRET'
        self.save()
        self.assertNotIn('SENTINEL', str(self.run_cli(2)))

    def test_changed_selected_source_during_read_rejected(self):
        original = rp.LocalMarkdownLoader._read_raw
        reads = {}
        def changing(loader, name, allowance):
            reads[name] = reads.get(name, 0) + 1
            value, identity = original(loader, name, allowance)
            if name == 'REQUIREMENT.md' and reads[name] == 2:
                return b'X' + value[1:], identity
            return value, identity
        output = io.StringIO()
        with patch.object(rp.LocalMarkdownLoader, '_read_raw', changing), redirect_stdout(output):
            self.assertEqual(rp.main([str(self.root), 'gists/packet.md']), 2)
        self.assertIn('SOURCE_CHANGED', json.loads(output.getvalue())['reason_codes'])

    def test_linked_source_is_rejected(self):
        target = self.root / 'REQUIREMENT.md'
        original = target.read_bytes()
        target.unlink()
        outside = self.root / 'outside.md'
        outside.write_bytes(original)
        try:
            target.symlink_to(outside)
        except OSError:
            self.skipTest('host does not allow symlink creation')
        self.assertIn('UNSAFE_PATH', self.run_cli(2)['reason_codes'])

    def test_hardlinked_source_alias_is_rejected(self):
        contract = self.root / 'gists/contract.md'
        contract.unlink()
        os.link(self.root / 'gists/test.md', contract)
        self.packet['evidence_refs'][1]['sha256'] = self.packet['evidence_refs'][0]['sha256']
        self.save()
        self.assertIn('DUPLICATE_IDENTITY', self.run_cli(2)['reason_codes'])

    def test_packet_and_control_file_must_not_alias(self):
        source = self.root / 'gists/packet.md'
        header = self.detail.read_text(encoding='utf-8')
        source.write_text(header + '\n```review-packet-v1\n' + json.dumps(self.packet) + '\n```\n', encoding='utf-8')
        self.detail.unlink()
        os.link(source, self.detail)
        self.assertIn('DUPLICATE_IDENTITY', self.run_cli(2)['reason_codes'])

    def test_duplicate_json_and_oversize_manifest(self):
        path = self.root / 'gists/packet.md'
        path.write_text('{"schema":"review-packet-v1","schema":"review-packet-v1"}', encoding='utf-8')
        self.assertFalse(self.run_cli(2)['complete'])
        path.write_bytes(b' ' * (rp.MAX_FILE_BYTES + 1))
        self.assertIn('RESOURCE_LIMIT', self.run_cli(2)['reason_codes'])


if __name__ == '__main__':
    unittest.main()
