"""Coordinator-only oracle. NEVER give this file to a blind reviewer."""

import importlib.util
import unittest
from pathlib import Path


path = Path(__file__).parent / "original/candidate.py"
spec = importlib.util.spec_from_file_location("replay_candidate", path)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class SeededCandidatesTests(unittest.TestCase):
    def test_declared_delivery_without_required_conditions_is_accepted(self):
        delivery = {"qualified": True, "closed": True, "same_source": True}
        self.assertTrue(candidate.usable_delivery(delivery))  # Required behavior: False.
        self.assertFalse(candidate.usable_delivery({**delivery, "closed": False}))

    def test_cash_duplicate_cycle_disappears_but_unrelated_cash_is_preserved(self):
        records = [{"id": "a", "amount": 100}, {"id": "b", "amount": 100}, {"id": "c", "amount": 50}]
        self.assertEqual(candidate.cash_total(records, {"a": ["b"], "b": ["a"]}), 50)  # Required: 150.
        self.assertEqual(candidate.cash_total([records[-1]], {}), 50)

    def test_batch_form_requires_one_hundred_internal_ids_despite_metadata(self):
        records = [{"id": str(index), "source_id": "known-source"} for index in range(100)]
        html = candidate.import_preview(records)
        self.assertEqual(html.count('required value=""'), 100)  # Required: metadata-backed defaults.
        self.assertNotIn("known-source", html)
        self.assertIn("Import all", html)

    def test_single_export_and_download_share_a_restricted_data_bypass(self):
        row = {"id": "r1", "title": "Public title", "amount": 100, "allowed": {"owner"}}
        with self.assertRaises(PermissionError):
            candidate.export_package([row], "guest")
        self.assertEqual(candidate.export_single(row, "guest")["amount"], 100)
        self.assertEqual(candidate.download_single(row, "guest")["amount"], 100)
        self.assertEqual(candidate.export_package([row], "owner")[0]["amount"], 100)

    def test_public_title_is_an_intentional_nonfinding_control(self):
        row = {"id": "r1", "title": "Public title", "amount": 100, "allowed": {"owner"}}
        self.assertEqual(candidate.public_summary(row), {"title": "Public title"})


if __name__ == "__main__":
    unittest.main()
