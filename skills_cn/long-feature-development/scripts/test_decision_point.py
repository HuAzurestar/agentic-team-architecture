#!/usr/bin/env python3
"""Draft transformation fixtures: deliberately no authenticated human transport."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import decision_point as point
from decision_source import _point
import task_context as context

ROOT = Path(__file__).resolve().parents[1]


def documents():
    return tuple((ROOT / "templates" / name).read_text(encoding="utf-8").replace("<feature-key>", "PIRC-23")
                 for name in ("REQUIREMENT.md", "SOLUTION.md"))


def evidence(document, point_id="REQ-001", outcome="CONFIRMED"):
    return dict(schema="decision-evidence-v1", decision_id="decision-1", feature="PIRC-23",
                human_source_ref="synthetic:reply/1", actor="Synthetic human", received_at="2026-10-03T10:00:00Z",
                decision_kind="point", target_ref=dict(source_key="pm:requirement", version_kind="git", version="a" * 40),
                exact_scope=[point_id], outcome=outcome, original_reply=point_id + " " + outcome,
                approved_body=_point(document, point_id))


class PointDraftTests(unittest.TestCase):
    def setUp(self):
        self.req, self.sol = documents()

    def draft(self, outcome="CONFIRMED"):
        return point.render_decision(self.req, self.sol, evidence(self.req, outcome=outcome))

    def test_confirm_updates_derived_state_and_keeps_statement(self):
        draft = self.draft()
        self.assertEqual(draft.effect, "DRAFT_ONLY")
        self.assertEqual(draft.document, "REQUIREMENT.md")
        self.assertEqual(context.document_status_value(draft.after, "REQ"), "CONFIRMED")
        self.assertEqual(context.metadata_value(_point(draft.after, "REQ-001"), {"State", "状态"}, "p"), "CONFIRMED")
        self.assertIn("### Acceptance" if "### Acceptance" in self.req else "### 验收", draft.after)
        self.assertEqual(draft.before, self.req)

    def test_each_negative_outcome_moves_point_before_amendments(self):
        for outcome in ("REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"):
            with self.subTest(outcome=outcome):
                draft = self.draft(outcome)
                headings = point.headings(draft.after)
                dpos = next(item[2] for item in headings if item[1] in point.DISPOSITION)
                ppos = next(item[2] for item in headings if item[1].startswith("REQ-001"))
                apos = next(item[2] for item in headings if item[1] in {"Amendments", "修订记录"})
                self.assertLess(dpos, ppos)
                self.assertLess(ppos, apos)
                self.assertEqual(context.document_status_value(draft.after, "REQ"), "DRAFT")

    def test_reopen_disposition_moves_back_and_retains_history(self):
        old = self.draft("REJECTED").after
        record = evidence(old, outcome="REOPENED")
        record["decision_id"] = "decision-2"
        draft = point.render_decision(old, self.sol, record)
        self.assertLess(draft.after.index("## REQ-001"), min(item[2] for item in point.headings(draft.after)
                                                          if item[1] in point.DISPOSITION))
        self.assertIn('"decision_id":"decision-1"', draft.after)
        self.assertIn('"decision_id":"decision-2"', draft.after)
        self.assertEqual(context.document_status_value(draft.after, "REQ"), "DRAFT")

    def test_reopen_confirmed_point_returns_document_to_draft(self):
        old = self.draft().after
        draft = point.render_decision(old, self.sol, evidence(old, outcome="REOPENED"))
        self.assertEqual(context.document_status_value(draft.after, "REQ"), "DRAFT")

    def test_decided_point_cannot_be_confirmed_again(self):
        for outcome in ("CONFIRMED", "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"):
            old = self.draft(outcome).after
            with self.subTest(outcome=outcome), self.assertRaisesRegex(point.DraftError, "POINT_TRANSITION_INVALID"):
                point.render_decision(old, self.sol, evidence(old))

    def test_proposed_cannot_be_reopened(self):
        with self.assertRaisesRegex(point.DraftError, "POINT_TRANSITION_INVALID"):
            self.draft("REOPENED")

    def test_stale_body_rejected_without_mutating_inputs(self):
        record = evidence(self.req)
        original = copy.deepcopy(record)
        record["approved_body"] += "changed"
        with self.assertRaisesRegex(point.DraftError, "DECISION_STALE"):
            point.render_decision(self.req, self.sol, record)
        self.assertEqual(record["approved_body"], original["approved_body"] + "changed")

    def test_solution_confirmation_requires_confirmed_requirement(self):
        with self.assertRaises(point.DraftError):
            point.render_decision(self.req, self.sol, evidence(self.sol, "SOL-001"))
        req = self.draft().after
        draft = point.render_decision(req, self.sol, evidence(self.sol, "SOL-001"))
        self.assertEqual(draft.document, "SOLUTION.md")
        self.assertEqual(context.document_status_value(draft.after, "SOL"), "BASELINED")

    def test_requirement_reopen_cannot_silently_reopen_confirmed_solution(self):
        req = self.draft().after
        sol = point.render_decision(req, self.sol, evidence(self.sol, "SOL-001")).after
        with self.assertRaises(point.DraftError):
            point.render_decision(req, sol, evidence(req, outcome="REOPENED"))

    def test_other_point_unchanged_and_document_stays_draft(self):
        other = _point(self.req, "REQ-001").replace("REQ-001", "REQ-002")
        insertion = point.section(self.req, point.DISPOSITION, 2)[0]
        req = self.req[:insertion] + other + self.req[insertion:]
        draft = point.render_decision(req, self.sol, evidence(req))
        self.assertEqual(_point(draft.after, "REQ-002"), other)
        self.assertEqual(context.document_status_value(draft.after, "REQ"), "DRAFT")

    def test_raw_reply_and_actor_cannot_inject_markdown_structure(self):
        record = evidence(self.req)
        record["original_reply"] += "\n~~~\n## REQ-999\n| State | CONFIRMED |"
        record["actor"] = "human|<script>" + chr(96)
        draft = point.render_decision(self.req, self.sol, record)
        self.assertEqual(set(context.point_sections(draft.after, "REQ")), {"REQ-001"})
        self.assertIn("human&#124;&lt;script&gt;&#96;", draft.after)
        history_line = next(line for line in draft.after.splitlines() if line.startswith('{"actor":'))
        self.assertEqual(json.loads(history_line), record)

    def test_missing_decision_history_fails_closed(self):
        req = self.req.replace("### Decision history", "### Missing history").replace("### 决定历史", "### 缺失")
        with self.assertRaisesRegex(point.DraftError, "POINT_LAYOUT_AMBIGUOUS"):
            point.render_decision(req, self.sol, evidence(req))

    def test_missing_decision_actor_row_fails_closed(self):
        req = self.req.replace("| Decided by |", "| Other |").replace("| 决定人 |", "| 其他 |")
        with self.assertRaisesRegex(point.DraftError, "POINT_METADATA_AMBIGUOUS"):
            point.render_decision(req, self.sol, evidence(req))

    def test_legacy_h3_requires_explicit_migration_not_silent_write(self):
        req = self.req.replace("## REQ-001", "### REQ-001")
        record = evidence(self.req)
        with self.assertRaises(point.DraftError):
            point.render_decision(req, self.sol, record)

    def test_disposition_class_in_active_region_is_rejected(self):
        req = self.req.replace("ACTIVE", "DISPOSITION").replace("PROPOSED", "REJECTED")
        with self.assertRaisesRegex(point.DraftError, "POINT_LOCATION_MISMATCH"):
            point.render_decision(req, self.sol, evidence(req, outcome="REOPENED"))

    def test_nonpoint_decision_cannot_mutate_point(self):
        record = evidence(self.req)
        record["decision_kind"] = "acceptance"
        with self.assertRaisesRegex(point.DraftError, "POINT_DECISION_REQUIRED"):
            point.render_decision(self.req, self.sol, record)

    def test_disposition_point_in_amendments_is_not_relocated_silently(self):
        req = self.draft("REJECTED").after
        body = _point(req, "REQ-001")
        req = req.replace(body, "") + body
        with self.assertRaisesRegex(point.DraftError, "POINT_LOCATION_MISMATCH"):
            point.render_decision(req, self.sol, evidence(req, outcome="REOPENED"))

    def test_missing_disposition_region_fails_instead_of_inventing_layout(self):
        req = self.req.replace("## Disposition records", "## Missing").replace("## 处置记录", "## 缺失")
        with self.assertRaisesRegex(point.DraftError, "POINT_LAYOUT_AMBIGUOUS"):
            point.render_decision(req, self.sol, evidence(req))

    def test_cpu_budget_expiry_refuses_draft(self):
        with patch.object(point.time, "process_time", side_effect=(0, 3)):
            with self.assertRaisesRegex(point.DraftError, "RESOURCE_LIMIT"):
                self.draft()

    def test_resource_budget_is_not_ignored(self):
        with patch.object(point, "MAX_BYTES", 10), self.assertRaisesRegex(point.DraftError, "RESOURCE_LIMIT"):
            self.draft()

    def test_draft_does_not_authenticate_uploaded_actor_or_claim_applied(self):
        record = evidence(self.req)
        record["actor"] = "unverified claim"
        draft = point.render_decision(self.req, self.sol, record)
        self.assertEqual(draft.effect, "DRAFT_ONLY")
        self.assertFalse(hasattr(draft, "source_verified"))

    def test_statement_acceptance_and_prior_history_bytes_are_preserved(self):
        for outcome in ("CONFIRMED", "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"):
            draft = self.draft(outcome)
            old = _point(self.req, "REQ-001")
            new = _point(draft.after, "REQ-001")
            body_start = next(item[2] for item in point.headings(old) if item[0] == 3)
            self.assertIn(old[body_start:], new)

    def test_fenced_statement_examples_remain_exact_content(self):
        marker = "### Decision history" if "### Decision history" in self.req else "### 决定历史"
        example = "~~~markdown\n## REQ-999\n# Boundary\n~~~\n\n"
        req = self.req.replace(marker, example + marker)
        draft = point.render_decision(req, self.sol, evidence(req))
        self.assertIn(example, draft.after)
        self.assertEqual(set(context.point_sections(draft.after, "REQ")), {"REQ-001"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
