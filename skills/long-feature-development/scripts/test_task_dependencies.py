#!/usr/bin/env python3
"""Dependency previews are bounded and never change their source documents."""
import sys
sys.dont_write_bytecode = True
import unittest
from unittest.mock import patch
import task_context as tc
import task_dependencies as deps
import task_reconcile as recovery
import test_task_context as fixtures


class DependencyPlanTests(unittest.TestCase):
    def setUp(self):
        self.index = tc.synchronized_topology(fixtures.TASKS).encode()
        self.detail = fixtures.DETAILS["GATE-ACCEPT"].encode()

    def plan(self, values=None, **kw):
        return deps.plan_dependencies(
            kw.pop("index", self.index), kw.pop("detail", self.detail),
            kw.pop("task_id", "GATE-ACCEPT"),
            kw.pop("expected", recovery.digest(self.index)),
            ["SOL-001"] if values is None else values, **kw)

    def test_gate_plan_updates_index_topology_and_contract(self):
        result = self.plan(["SOL-001", "REQ-001", "SOL-001"])
        self.assertEqual(result["new_dependencies"], ["SOL-001", "REQ-001"])
        self.assertEqual(result["old_dependencies"], ["DEV-02"])
        self.assertEqual(result["effect"], "NOT_APPLIED")
        records = tc.task_records(recovery.decode(result["after"]["TASKS.md"]))
        tc.validate_dependency_graph(records)
        tc.validate_topology(recovery.decode(result["after"]["TASKS.md"]), records)
        tc.validate_type_contract(records["GATE-ACCEPT"],
                                  recovery.decode(result["after"]["tasks/GATE-ACCEPT.md"]), records)
        self.assertEqual(records["GATE-ACCEPT"]["readiness"], "READY")
        self.assertEqual(result["before"]["TASKS.md"], self.index)

    def test_waiting_dependency_is_not_mistaken_for_ready(self):
        result = self.plan(["DEV-02"])
        self.assertEqual(result["readiness"], "WAITING")
        self.assertEqual(result["changed_paths"], [])

    def test_stale_digest_rejected(self):
        with self.assertRaisesRegex(deps.Error, "INDEX_CHANGED"):
            self.plan(expected="0" * 64)

    def test_unknown_and_self_dependencies_rejected(self):
        for values in (["MISSING-01"], ["GATE-ACCEPT"], ["DEV-02", 4], "SOL-001"):
            with self.subTest(values=values), self.assertRaises(deps.Error):
                self.plan(values)

    def test_cycle_in_other_part_of_graph_is_rejected(self):
        text = recovery.decode(self.index).replace(
            "| human | - | 2026-09-01T09:00:00Z",
            "| human | SOL-001 | 2026-09-01T09:00:00Z")
        raw = text.encode()
        with self.assertRaisesRegex(deps.Error, "INVALID_DEPENDENCY_GRAPH"):
            self.plan(index=raw, expected=recovery.digest(raw))

    def test_active_target_is_rejected_without_any_candidate(self):
        with self.assertRaisesRegex(deps.Error, "TASK_ALREADY_STARTED"):
            self.plan(task_id="DEV-02", detail=fixtures.DETAILS["DEV-02"].encode())

    def test_pending_with_retained_start_ref_is_rejected(self):
        detail = self.detail.replace(b"| - | - | - |", b"| feature@1111111 | - | - |")
        with self.assertRaisesRegex(deps.Error, "INVALID_TASK_DETAIL"):
            self.plan(detail=detail)

    def test_stale_gate_contract_not_silently_repaired(self):
        with self.assertRaisesRegex(deps.Error, "INVALID_TASK_DETAIL"):
            self.plan(detail=self.detail.replace(b"| Required tasks | DEV-02 |",
                                                b"| Required tasks | SOL-001 |"))

    def test_stale_topology_not_silently_repaired(self):
        raw = self.index.replace(b"flowchart LR", b"flowchart TD")
        with self.assertRaisesRegex(deps.Error, "INVALID_DEPENDENCY_GRAPH"):
            self.plan(index=raw, expected=recovery.digest(raw))

    def test_bom_and_crlf_preserved(self):
        raw = b"\xef\xbb\xbf" + self.index.replace(b"\n", b"\r\n")
        detail = b"\xef\xbb\xbf" + self.detail.replace(b"\n", b"\r\n")
        result = self.plan(index=raw, detail=detail, expected=recovery.digest(raw))
        for content in result["after"].values():
            self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\n", content.replace(b"\r\n", b""))

    def test_limits_fail_closed(self):
        for name, limit in (("MAX_NODES", 3), ("MAX_EDGES", 1), ("MAX_BYTES", 10)):
            with self.subTest(name=name), patch.object(deps, name, limit):
                with self.assertRaisesRegex(deps.Error, "RESOURCE_LIMIT"):
                    self.plan()

    def test_cpu_deadline_fails_closed(self):
        with patch.object(deps.time, "process_time", side_effect=[0, 3, 3, 3]):
            with self.assertRaisesRegex(deps.Error, "RESOURCE_LIMIT"):
                self.plan()

    def test_empty_dependencies_is_explicit_and_valid(self):
        result = self.plan([])
        self.assertEqual(result["new_dependencies"], [])
        self.assertIn(b"| Required tasks | - |", result["after"]["tasks/GATE-ACCEPT.md"])

    def test_pending_owner_is_not_unassigned(self):
        raw = self.index.replace(b"| `PENDING` | - |", b"| `PENDING` | someone |")
        with self.assertRaisesRegex(deps.Error, "TASK_ALREADY_STARTED"):
            self.plan(index=raw, expected=recovery.digest(raw))

    def test_new_cycle_between_pending_tasks_is_rejected(self):
        text = recovery.decode(self.index)
        row = "| DEV-03 | Development | Later task | `PENDING` | - | GATE-ACCEPT | - | - | - |\n"
        text = text.replace("## Dependency topology", row + "\n## Dependency topology")
        # Append inside the sole index table, not as a second Markdown table.
        text = text.replace("\n\n" + row, "\n" + row)
        raw = tc.synchronized_topology(text).encode()
        with self.assertRaisesRegex(deps.Error, "INVALID_DEPENDENCY_GRAPH"):
            self.plan(["DEV-03"], index=raw, expected=recovery.digest(raw))

    def test_large_linear_graph_has_no_recursive_depth_limit(self):
        rows = []
        for i in range(9999):
            dependencies = ", ".join(f"DEV-{j:05}" for j in range(max(0, i - 3), i)) or "-"
            rows.append(f"| DEV-{i:05} | Development | Node | `PENDING` | - | {dependencies} | - | - | - |")
        rows.append("| GATE-ACCEPT | Gate | Finish | `PENDING` | - | DEV-02 | - | - | - |")
        # Use the real gate's original edge so its contract is initially valid.
        rows[2] = rows[2].replace("DEV-00002", "DEV-02", 1)
        rows = [row.replace("DEV-00002", "DEV-02") for row in rows]
        text = "\n".join([
            "# Tasks", "", "| ID | Type | Name | State | Owner | Depends on | Started at | Completed at | HEAD SHA |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |", *rows, "",
            "<!-- task-topology:start -->", "placeholder", "<!-- task-topology:end -->", ""])
        raw = tc.synchronized_topology(text).encode()
        result = self.plan(["DEV-09998"], index=raw, expected=recovery.digest(raw))
        self.assertEqual(result["node_count"], 10000)
        self.assertLessEqual(result["edge_count"], 30000)
        self.assertEqual(result["readiness"], "WAITING")

    def test_non_gate_pending_task_leaves_detail_bytes_unchanged(self):
        text = recovery.decode(self.index).replace("GATE-ACCEPT", "DEV-03").replace("| Gate |", "| Development |")
        raw = tc.synchronized_topology(text).encode()
        detail = self.detail.replace(b"GATE-ACCEPT", b"DEV-03").split(b"## Type contract")[0]
        result = self.plan(task_id="DEV-03", index=raw, detail=detail,
                           expected=recovery.digest(raw))
        self.assertEqual(result["changed_paths"], ["TASKS.md"])
        self.assertEqual(result["after"]["tasks/DEV-03.md"], detail)

    def test_pending_gate_cannot_hide_inflight_acceptance(self):
        row = "| ACCEPT-01 | Acceptance | Actual attempt | `WIP` | human | SOL-001 | now | - | pm@3333333 |\n"
        text = recovery.decode(self.index).replace(
            "| - | DEV-02 | - | - | - |", "| - | ACCEPT-01 | - | - | - |")
        text = text.replace("\n\n## Dependency topology", "\n" + row + "\n## Dependency topology")
        raw = tc.synchronized_topology(text).encode()
        detail = self.detail.replace(b"| Required tasks | DEV-02 |", b"| Required tasks | ACCEPT-01 |")
        with self.assertRaisesRegex(deps.Error, "ACTIVE_ATTEMPT_WOULD_BE_HIDDEN"):
            self.plan(["SOL-001"], index=raw, detail=detail, expected=recovery.digest(raw))
        retained = self.plan(["ACCEPT-01", "DEV-02"], index=raw, detail=detail,
                             expected=recovery.digest(raw))
        self.assertEqual(retained["readiness"], "WAITING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
