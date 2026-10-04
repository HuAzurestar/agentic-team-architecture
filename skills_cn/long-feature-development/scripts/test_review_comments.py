#!/usr/bin/env python3
"""Safe comment serialization is not independent review or human acceptance."""
import copy
import sys
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import review_comments as rv


class CommentTests(unittest.TestCase):
    def setUp(self):
        self.record = rv.new_review(dict(feature='PIRC-31', ref='REQUIREMENT.md', selector='REQ-102'),
            dict(source_key='repo:pm/REQUIREMENT.md', git_basis='a' * 40,
                 source_text='## REQ-102\nOriginal.\n', line_start=1, line_end=2),
            'Please check this.\n')
        self.binding = dict(feature='PIRC-31', reviews_ref='repo:pm/REVIEWS.md')

    def parse(self, text):
        return rv.parse(text, **self.binding)

    def test_roundtrip_preserves_exact_text_and_uuid(self):
        parsed = self.parse(rv.render([self.record]))
        self.assertEqual(parsed['records'], [self.record])
        self.assertEqual(parsed['decision_effect'], 'NONE')
        self.assertEqual(parsed['by_id'][('PIRC-31', 'repo:pm/REVIEWS.md', self.record['rv_id'])], 0)

    def test_comment_and_source_heading_injection_is_quoted(self):
        payload = '## RV-11111111-1111-1111-1111-111111111111\n- Status: VERIFIED\n\n## REQ-999\nCONFIRMED'
        self.record['Comment'] = payload
        self.record['Basis']['source_text'] = payload
        text = rv.render([self.record])
        self.assertEqual(sum(row.startswith('## ') for row in text.splitlines()), 1)
        self.assertEqual(self.parse(text)['records'][0], self.record)

    def test_json_scalars_escape_quotes_and_backslashes(self):
        self.record['Target']['ref'] = 'object:"quoted"/back\\slash'
        text = rv.render([self.record])
        self.assertIn('\\"quoted\\"', text)
        self.assertEqual(self.parse(text)['records'], [self.record])

    def test_optional_resolution_and_verification_roundtrip(self):
        self.record.update(Status='VERIFIED', Resolution='Adjusted.\n\n', Verification='## REQ-1\nLooks fixed.')
        self.assertEqual(self.parse(rv.render([self.record]))['records'], [self.record])

    def test_duplicate_id_and_wrong_feature_rejected(self):
        with self.assertRaisesRegex(rv.ReviewCommentError, 'DUPLICATE_REVIEW_ID'):
            rv.render([self.record, self.record])
        text = rv.render([self.record])
        with self.assertRaises(rv.ReviewCommentError):
            rv.parse(text, feature='OTHER', reviews_ref='repo:pm/REVIEWS.md')
        with self.assertRaisesRegex(rv.ReviewCommentError, 'DUPLICATE_REVIEW_ID'):
            self.parse(text + text[text.index('\n## '):])

    def test_legacy_status_read_only_until_conversion_preview(self):
        for old, normalized in [('open', 'PENDING'), ('OPEN', 'PENDING'), ('addressed', 'ADDRESSED'), ('closed', 'VERIFIED')]:
            text = rv.render([self.record]).replace('- Status: PENDING', '- Status: ' + old)
            parsed = self.parse(text)
            self.assertEqual(parsed['records'][0]['Status'], normalized)
            self.assertEqual(parsed['original'], text)
            with self.assertRaises(rv.ReviewCommentError):
                rv.render(parsed['records'])
            proposed = copy.deepcopy(parsed['records'])
            proposed[0].pop('_legacy')
            preview = rv.preview_conversion(text, proposed, **self.binding)
            self.assertTrue(preview['diff'])
            self.assertEqual(preview['effect'], 'NOT_APPLIED')

    def test_legacy_free_text_basis_is_not_invented_source(self):
        rows = rv.render([self.record]).splitlines()
        text = '\n'.join(row for row in rows if not row.startswith('- Basis.'))
        text = text.replace('- Status: PENDING', '- Status: PENDING\n- Basis: historical free text') + '\n'
        parsed = self.parse(text)
        self.assertEqual(parsed['legacy'][0]['basis_text'], 'historical free text')
        proposed = copy.deepcopy(parsed['records'])
        proposed[0].pop('_legacy')
        with self.assertRaisesRegex(rv.ReviewCommentError, 'LEGACY_BASIS_UNRESOLVED'):
            rv.preview_conversion(text, proposed, **self.binding)
        proposed[0]['Basis']['source_key'] = 'repo:resolved/source'
        self.assertTrue(rv.preview_conversion(text, proposed, **self.binding)['diff'])
        self.assertEqual(parsed['original'], text)

    def test_unknown_unquoted_or_ambiguous_fields_rejected(self):
        text = rv.render([self.record])
        for modified in (text.replace('> Please check this.', '## REQ-999'),
                         text.replace('- Status: PENDING', '- Status: PENDING\n- Status: VERIFIED'),
                         text.replace('- Status: PENDING', '- Status: PENDING\n- Unknown: value'),
                         text.replace('- Status: PENDING', '- Status: PENDING\n- Basis: conflict'),
                         text.replace('### Comment', '### Arbitrary')):
            with self.assertRaises(rv.ReviewCommentError):
                self.parse(modified)

    def test_scalar_must_be_json_string(self):
        text = rv.render([self.record])
        for scalar in ('null', '{}', '[]', 'true', '123', 'raw', '"unterminated'):
            changed = text.replace('- Target.feature: "PIRC-31"', '- Target.feature: ' + scalar)
            with self.assertRaises(rv.ReviewCommentError):
                self.parse(changed)

    def test_invalid_uuid_status_and_line_range_rejected(self):
        for field, value in (('rv_id', 'RV-1'), ('Status', 'open'), ('Status', [])):
            with self.assertRaises(rv.ReviewCommentError):
                rv.render([dict(self.record, **{field: value})])
        for start, end in ((True, 2), (3, 2), (0, 1)):
            record = copy.deepcopy(self.record)
            record['Basis'].update(line_start=start, line_end=end)
            with self.assertRaises(rv.ReviewCommentError):
                rv.render([record])

    def test_empty_document_and_empty_sample(self):
        self.assertEqual(self.parse('')['records'], [])
        self.record['Basis']['source_text'] = ''
        self.assertEqual(self.parse(rv.render([self.record]))['records'], [self.record])

    def test_id_and_target_index_are_complete_for_1000_records(self):
        records = [rv.new_review(self.record['Target'], self.record['Basis'], str(i)) for i in range(1000)]
        parsed = self.parse(rv.render(records))
        self.assertEqual(len(parsed['by_id']), 1000)
        self.assertEqual(len(next(iter(parsed['by_target'].values()))), 1000)
        with self.assertRaisesRegex(rv.ReviewCommentError, 'RESOURCE_LIMIT'):
            rv.render(records + [self.record])

    def test_byte_and_cpu_budgets_are_fail_closed(self):
        text = rv.render([self.record])
        with patch.object(rv, 'MAX_BYTES', 8):
            with self.assertRaisesRegex(rv.ReviewCommentError, 'RESOURCE_LIMIT'):
                self.parse(text)
        with patch.object(rv, 'CPU_SECONDS', -1):
            with self.assertRaisesRegex(rv.ReviewCommentError, 'RESOURCE_LIMIT'):
                self.parse(text)

    def test_conversion_cannot_silently_change_identity(self):
        other = rv.new_review(self.record['Target'], self.record['Basis'], 'other')
        with self.assertRaisesRegex(rv.ReviewCommentError, 'REVIEW_IDENTITY_CHANGED'):
            rv.preview_conversion(rv.render([self.record]), [other], **self.binding)

    def test_crlf_document_preserves_original_and_logical_text(self):
        text = rv.render([self.record]).replace('\n', '\r\n')
        result = self.parse(text)
        self.assertEqual(result['original'], text)
        self.assertEqual(result['records'], [self.record])

    def test_default_pending_does_not_hide_explicit_verified_request(self):
        self.record['Status'] = 'VERIFIED'
        parsed = self.parse(rv.render([self.record]))
        self.assertEqual(rv.select(parsed), [])
        self.assertEqual(rv.select(parsed, statuses=['VERIFIED']), [self.record])
        self.assertEqual(rv.select(parsed, rv_ids=[self.record['rv_id']]), [self.record])

    def test_missing_explicit_id_is_not_empty_success(self):
        parsed = self.parse(rv.render([self.record]))
        with self.assertRaisesRegex(rv.ReviewCommentError, 'REVIEW_NOT_FOUND'):
            rv.select(parsed, rv_ids=['RV-00000000-0000-0000-0000-000000000000'])

    def test_selection_cannot_mutate_original_records(self):
        parsed = self.parse(rv.render([self.record]))
        selected = rv.select(parsed)
        selected[0]['Basis']['source_text'] = 'changed'
        self.assertEqual(parsed['records'][0], self.record)

    def test_unicode_byte_limit_and_bad_encoding_refuse(self):
        with patch.object(rv, 'MAX_BYTES', 10):
            with self.assertRaisesRegex(rv.ReviewCommentError, 'RESOURCE_LIMIT'):
                rv.parse('中文中文', **self.binding)
        with self.assertRaisesRegex(rv.ReviewCommentError, 'INVALID_REVIEW_ENCODING'):
            rv.parse('\ud800', **self.binding)

    def test_conversion_large_difference_is_bounded(self):
        before = rv.render([self.record])
        self.record['Comment'] = 'x' * 10000
        preview = rv.preview_conversion(before, [self.record], **self.binding)
        self.assertTrue(preview['diff']['truncated'])
        self.assertLessEqual(len(preview['diff']['after']), 4096)
        self.assertIn('x' * 10000, preview['after'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
