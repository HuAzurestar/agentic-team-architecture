#!/usr/bin/env python3
"""Decision applicability fixtures, never actual human authorization."""
import copy
import sys
sys.dont_write_bytecode = True
import unittest
from unittest.mock import patch
import decision_evidence as decision


def evidence():
    return dict(schema="decision-evidence-v1", decision_id="decision-1", feature="PIRC-31",
                human_source_ref="conversation:message-1", actor="person-1",
                received_at="2026-10-03T01:00:00+00:00", decision_kind="point",
                target_ref={"source_key": "repo:pm/REQUIREMENT.md", "version_kind": "git", "version": "a" * 40},
                exact_scope=["REQ-102"], outcome="CONFIRMED",
                original_reply="Confirm REQ-102 exactly as quoted.", approved_body="Original requirement.\n")


def current(raw):
    return {key: copy.deepcopy(raw[key]) for key in ("feature", "decision_kind", "target_ref", "exact_scope")} | {"body": raw["approved_body"]}


def verified(raw):
    return decision.VerifiedDecisionSource(decision.decision_digest(raw),
        raw["human_source_ref"], raw["actor"], raw["received_at"],
        "conversation", "host:readback-1")


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.raw = evidence()
        self.current = current(self.raw)

    def test_untrusted_human_label_is_not_authority(self):
        result = decision.check_decision(self.raw, self.current)
        self.assertFalse(result["applicable"])
        self.assertIn("HUMAN_SOURCE_UNVERIFIED", result["reason_codes"])

    def test_exact_verified_point_is_applicable_but_not_applied(self):
        result = decision.check_decision(self.raw, self.current, verified=verified(self.raw))
        self.assertTrue(result["applicable"], result)
        self.assertEqual(result["effect"], "NOT_APPLIED")
        self.assertFalse(result["merge_authorized"])

    def test_point_approval_cannot_expand_to_feature(self):
        self.current["decision_kind"] = "acceptance"
        self.current["exact_scope"].append("REQ-101")
        result = decision.check_decision(self.raw, self.current, verified=verified(self.raw))
        self.assertFalse(result["applicable"])
        self.assertIn("DECISION_SCOPE_MISMATCH", result["reason_codes"])

    def test_changed_body_is_stale_with_diff_and_preserved_original(self):
        before = copy.deepcopy(self.raw)
        self.current["body"] = "Revised requirement.\n"
        result = decision.check_decision(self.raw, self.current, verified=verified(self.raw))
        self.assertFalse(result["applicable"])
        self.assertIn("DECISION_STALE", result["reason_codes"])
        self.assertTrue(result["diff"])
        self.assertEqual(self.raw, before)

    def test_same_body_different_version_is_stale(self):
        self.current["target_ref"]["version"] = "b" * 40
        result = decision.check_decision(self.raw, self.current, verified=verified(self.raw))
        self.assertIn("DECISION_STALE", result["reason_codes"])
        self.assertEqual(result["diff"], None)

    def test_other_document_or_decision_kind_does_not_inherit_approval(self):
        for key, value in (("feature", "PIRC-32"), ("decision_kind", "acceptance"),
                           ("target_ref", dict(self.raw["target_ref"], source_key="repo:other"))):
            candidate = copy.deepcopy(self.current)
            candidate[key] = value
            self.assertFalse(decision.check_decision(self.raw, candidate, verified=verified(self.raw))["applicable"])

    def test_host_facts_are_bound_to_whole_record(self):
        host = verified(self.raw)
        for field, changed in (("original_reply", "Actually rejected."), ("outcome", "REJECTED"),
                               ("actor", "person-2"), ("received_at", "2026-10-04T01:00:00Z")):
            raw = dict(self.raw, **{field: changed})
            result = decision.check_decision(raw, current(raw), verified=host)
            self.assertFalse(result["applicable"], result)

    def test_json_claim_cannot_be_imported_as_verified_host(self):
        self.assertFalse(decision.check_decision(self.raw, self.current,
            verified=verified(self.raw).__dict__)["applicable"])

    def test_single_point_and_explicit_scope_only(self):
        for scope in ([], ["REQ-102", "REQ-101"], ["*"], ["REQ-102", "REQ-102"]):
            raw = dict(self.raw, exact_scope=scope)
            self.assertFalse(decision.check_decision(raw, current(raw))["schema_valid"])

    def test_negative_acceptance_is_recordable_not_merge_authority(self):
        for outcome in ("REJECTED", "REWORK", "CONFIRMED"):
            raw = dict(self.raw, decision_kind="acceptance", outcome=outcome)
            result = decision.check_decision(raw, current(raw), verified=verified(raw))
            self.assertTrue(result["applicable"], result)
            self.assertFalse(result["merge_authorized"])

    def test_native_conditional_version_is_not_fabricated_git_sha(self):
        raw = dict(self.raw, target_ref={"source_key": "provider:object-1", "version_kind": "native", "version": "etag-7"})
        self.assertTrue(decision.check_decision(raw, current(raw), verified=verified(raw))["applicable"])

    def test_malformed_schema_is_controlled(self):
        for raw in (None, [], {}, dict(self.raw, received_at="yesterday"),
                    dict(self.raw, received_at="2026-10-03T01:00:00"),
                    dict(self.raw, target_ref=True), dict(self.raw, original_reply=""),
                    dict(self.raw, approved_body=5), dict(self.raw, Source="human")):
            result = decision.check_decision(raw, self.current)
            self.assertFalse(result["schema_valid"], result)
            self.assertFalse(result["applicable"])

    def test_diff_is_bounded_for_large_changed_body(self):
        raw = dict(self.raw, approved_body="a" * 100000)
        candidate = current(raw)
        candidate["body"] = "b" * 100000
        result = decision.check_decision(raw, candidate, verified=verified(raw))
        self.assertTrue(result["diff"]["truncated"])
        self.assertLessEqual(len(result["diff"]["before"]) + len(result["diff"]["after"]), 8192)

    def test_budget_is_fail_closed(self):
        with patch.object(decision.time, "process_time", side_effect=[0, 3, 3]):
            result = decision.check_decision(self.raw, self.current, verified=verified(self.raw))
        self.assertIn("RESOURCE_LIMIT", result["reason_codes"])
        self.assertFalse(result["applicable"])

    def test_size_bound_rejects_without_applicability(self):
        with patch.object(decision, "MAX_BYTES", 32):
            result = decision.check_decision(self.raw, self.current)
        self.assertFalse(result["applicable"])
        self.assertIn("RESOURCE_LIMIT", result["reason_codes"])

    def test_scope_exception_is_separate_from_point_approval(self):
        raw = dict(self.raw, decision_kind="scope-exception", outcome="APPROVED",
                   exact_scope=["REQ-102", "finding:report-1/attempt-1/F1"])
        result = decision.check_decision(raw, current(raw), verified=verified(raw))
        self.assertTrue(result["applicable"], result)
        self.assertFalse(result["merge_authorized"])
        changed = current(raw)
        changed["exact_scope"] = ["REQ-102"]
        self.assertFalse(decision.check_decision(raw, changed, verified=verified(raw))["applicable"])

    def test_unknown_host_transport_or_missing_readback_is_unverified(self):
        for kind, ref in (("markdown", "host:readback"), ("conversation", "")):
            host = decision.VerifiedDecisionSource(decision.decision_digest(self.raw),
                self.raw["human_source_ref"], self.raw["actor"], self.raw["received_at"], kind, ref)
            self.assertFalse(decision.check_decision(self.raw, self.current, verified=host)["applicable"])

    def test_event_does_not_leak_reply_or_diff(self):
        self.current["body"] = "Changed confidential body."
        result = decision.check_decision(self.raw, self.current, verified=verified(self.raw))
        self.assertNotIn(self.raw["original_reply"], str(result["event"]))
        self.assertNotIn(self.current["body"], str(result["event"]))
        self.assertNotIn("diff", result["event"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
