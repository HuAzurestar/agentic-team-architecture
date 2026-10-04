#!/usr/bin/env python3
"""Behavioral tests for the pure selector (not independent review/acceptance)."""
from __future__ import annotations
from dataclasses import replace
import copy
import unittest
from unittest.mock import patch
import task_next as n

SHA = "a" * 40
PLAN = "read-set:fixed-plan-and-observed-heads"


def grant(operation="work", capabilities=None, outside=False):
    return n.Grant(operation, frozenset(capabilities or ["execute"]), "host:instruction-1", outside)


def ready(**kw):
    return n.GateEvidence("ready", ("observation:checks-budget-contracts",), **kw)


def inputs(tasks=None, current="OLD", gate="GATE"):
    if tasks is None:
        tasks = (n.Task("OLD", "DONE"), n.Task("B", "PENDING", ("OLD",)),
                 n.Task("A", "PENDING", ("OLD",)),
                 n.Task("GATE", "PENDING", ("A", "B"), "Gate"),
                 n.Task("M2", "PENDING"))
    context = n.ValidatedContext(PLAN, current, gate, tuple(tasks))
    auth = n.Authorization(PLAN, {task.id: grant("gate" if task.kind == "Gate" else "work")
                                  for task in tasks})
    observations = n.ObservedGateEvidence(PLAN, {task.id: ready() for task in tasks})
    return context, auth, observations


class SelectorTests(unittest.TestCase):
    def test_t08_stable_order_scope_and_no_input_mutation(self):
        args = inputs()
        original = copy.deepcopy(args)
        for _ in range(10):
            result = n.select_next(*args)
            self.assertEqual(("assign", "B"), (result.action, result.task_id))
        self.assertEqual(original, args)
        # Even a ready, authorized M2 is excluded unless scope expansion is explicit.
        context, auth, evidence = inputs((n.Task("OLD", "DONE"),
            n.Task("M2", "PENDING"), n.Task("B", "PENDING"),
            n.Task("GATE", "PENDING", ("B",), "Gate")))
        self.assertEqual("B", n.select_next(context, auth, evidence).task_id)
        auth.grants["M2"] = grant(outside=True)
        self.assertEqual("M2", n.select_next(context, auth, evidence).task_id)

    def test_priority_then_original_row_order(self):
        args = inputs()
        args[1].grants["A"] = grant("retest")
        self.assertEqual("A", n.select_next(*args).task_id)
        args[1].grants["B"] = grant("rereview")
        self.assertEqual("B", n.select_next(*args).task_id)

    def test_current_wip_and_recording_resume_before_ready_tasks(self):
        for state in ("WIP", "RECORDING"):
            args = inputs((n.Task("M2", "PENDING"), n.Task("OLD", state),
                           n.Task("GATE", "PENDING", ("OLD",), "Gate")))
            result = n.select_next(*args)
            self.assertEqual(("resume", "OLD"), (result.action, result.task_id))

    def test_current_outside_scope_is_not_implicitly_authorized(self):
        args = inputs((n.Task("OLD", "WIP"), n.Task("GATE", "PENDING", (), "Gate")))
        self.assertEqual("stop-scope", n.select_next(*args).action)

    def test_t09_wait_reasons_are_distinct_and_not_completion(self):
        for verdict, code in (("wait-human", "HUMAN_REQUIRED"),
                              ("wait-external", "EXTERNAL_REQUIRED"),
                              ("repair-plan", "PLAN_REPAIR_REQUIRED")):
            args = inputs((n.Task("OLD", "BLOCKED", release_condition="service restored"),
                           n.Task("GATE", "PENDING", ("OLD",), "Gate")))
            args[2].tasks["OLD"] = n.GateEvidence(verdict, ("evidence:1",))
            result = n.select_next(*args)
            self.assertEqual((verdict, code), (result.action, result.reason_code))

    def test_blocked_requires_exact_release_evidence(self):
        args = inputs((n.Task("OLD", "BLOCKED", release_condition="service restored"),
                       n.Task("GATE", "PENDING", ("OLD",), "Gate")))
        self.assertEqual("RELEASE_UNPROVEN", n.select_next(*args).reason_code)
        args[2].tasks["OLD"] = ready(release_condition="another service", release_satisfied=True)
        self.assertEqual("RELEASE_UNPROVEN", n.select_next(*args).reason_code)
        args[2].tasks["OLD"] = ready(release_condition="service restored", release_satisfied=True)
        self.assertEqual("resume", n.select_next(*args).action)
        self.assertEqual("BLOCKED", args[0].tasks[0].state)

    def delivery(self, decision="CONFIRMED"):
        args = inputs((n.Task("ACCEPT", "DONE", (), "Acceptance",
                             {"Decision": decision, "Target SHA": SHA}),
                       n.Task("MERGE", "PENDING", ("ACCEPT",)),
                       n.Task("GATE", "PENDING", ("MERGE",), "Gate")),
                      current="ACCEPT")
        args[1].grants["MERGE"] = grant("merge", ["execute", "merge"])
        args[2].tasks["MERGE"] = ready(target_sha=SHA, acceptance_task="ACCEPT")
        return args

    def test_t10_rejected_done_acceptance_never_allows_merge(self):
        for decision in ("REJECTED", "REWORK", "WAITING", ""):
            result = n.select_next(*self.delivery(decision))
            self.assertEqual(("wait-human", "ACCEPTANCE_NOT_CONFIRMED"),
                             (result.action, result.reason_code))

    def test_rejected_acceptance_can_lead_to_explicit_rework(self):
        context, auth, evidence = self.delivery("REJECTED")
        context = replace(context, tasks=context.tasks[:-1] + (
            n.Task("FIX", "PENDING", ("ACCEPT",), "Rework"),
            n.Task("GATE", "PENDING", ("MERGE", "FIX"), "Gate")))
        auth.grants["FIX"] = grant("rework")
        evidence.tasks["FIX"] = ready()
        self.assertEqual("FIX", n.select_next(context, auth, evidence).task_id)

    def test_merge_publish_require_separate_authority(self):
        for operation in ("merge", "publish"):
            args = self.delivery()
            args[1].grants["MERGE"] = grant(operation)
            result = n.select_next(*args)
            self.assertEqual("wait-human", result.action)
            self.assertEqual((operation,), result.required_authority)
            args[1].grants["MERGE"] = grant(operation, ["execute", operation])
            self.assertEqual("LEGACY_EVIDENCE_INCOMPLETE", n.select_next(*args).reason_code)

    def test_acceptance_version_and_missing_task_rejected(self):
        args = self.delivery()
        args[2].tasks["MERGE"] = ready(target_sha="b" * 40, acceptance_task="ACCEPT")
        self.assertEqual("ACCEPTANCE_TARGET_MISMATCH", n.select_next(*args).reason_code)
        args[2].tasks["MERGE"] = ready(target_sha=SHA)
        self.assertEqual("ACCEPTANCE_TASK_MISSING", n.select_next(*args).reason_code)

    def test_raw_failed_tests_override_positive_summary(self):
        contract = {"Executed": "3", "Passed": "2", "Failed": "1",
                    "Skipped": "0", "Unknown": "0"}
        args = inputs((n.Task("OLD", "DONE", (), "Test", contract),
                       n.Task("B", "PENDING", ("OLD",)),
                       n.Task("GATE", "PENDING", ("B",), "Gate")))
        self.assertEqual("TEST_FAILED", n.select_next(*args).reason_code)
        args[1].grants["B"] = grant("retest")
        self.assertEqual("assign", n.select_next(*args).action)

    def test_unknown_skipped_zero_or_inconsistent_tests_not_pass(self):
        for contract in ({}, {"Executed": "0", "Passed": "0", "Failed": "0", "Skipped": "0", "Unknown": "0"},
                         {"Executed": "3", "Passed": "2", "Failed": "0", "Skipped": "1", "Unknown": "0"},
                         {"Executed": "3", "Passed": "2", "Failed": "0", "Skipped": "0", "Unknown": "1"}):
            args = inputs((n.Task("OLD", "DONE", (), "Test", contract),
                           n.Task("B", "PENDING", ("OLD",)),
                           n.Task("GATE", "PENDING", ("B",), "Gate")))
            self.assertEqual("TEST_EVIDENCE_INCOMPLETE", n.select_next(*args).reason_code)

    def test_review_blocker_not_success(self):
        args = inputs((n.Task("OLD", "DONE", (), "Review", {"Blocking findings": "1"}),
                       n.Task("B", "PENDING", ("OLD",)),
                       n.Task("GATE", "PENDING", ("B",), "Gate")))
        self.assertEqual("REVIEW_NOT_CLEAR", n.select_next(*args).reason_code)

    def test_authority_and_evidence_are_not_taken_from_markdown(self):
        args = inputs((n.Task("OLD", "WIP", contract={"approved": "true"}),
                       n.Task("GATE", "PENDING", ("OLD",), "Gate")))
        args[1].grants.clear()
        self.assertEqual("AUTHORITY_MISSING", n.select_next(*args).reason_code)
        args[1].grants["OLD"] = grant()
        args[2].tasks.clear()
        self.assertEqual("EVIDENCE_MISSING", n.select_next(*args).reason_code)

    def test_stale_plan_or_heads_invalidates_selection(self):
        context, auth, evidence = inputs()
        for args in ((context, replace(auth, source_ref="old"), evidence),
                     (context, auth, replace(evidence, source_ref="old"))):
            self.assertEqual("STALE_INPUT", n.select_next(*args).reason_code)

    def test_invalid_graph_even_outside_closure_prevents_partial_selection(self):
        for extra in ((n.Task("X", "PENDING", ("MISSING",)),),
                      (n.Task("X", "PENDING", ("Y",)), n.Task("Y", "PENDING", ("X",))),
                      (n.Task("B", "PENDING"),),
                      (n.Task("X", "PENDING", ("OLD", "OLD")),)):
            context, auth, evidence = inputs()
            result = n.select_next(replace(context, tasks=context.tasks + extra), auth, evidence)
            self.assertEqual(("repair-plan", "INVALID_GRAPH"),
                             (result.action, result.reason_code))

    def test_active_task_with_unfinished_dependency_is_invalid(self):
        args = inputs((n.Task("B", "PENDING"), n.Task("OLD", "WIP", ("B",)),
                       n.Task("GATE", "PENDING", ("OLD",), "Gate")))
        self.assertEqual("ACTIVE_DEPENDENCY_UNFINISHED", n.select_next(*args).reason_code)

    def test_other_assigned_task_not_silently_abandoned(self):
        args = inputs((n.Task("OLD", "DONE"), n.Task("B", "WIP"),
                       n.Task("GATE", "PENDING", ("B",), "Gate")))
        self.assertEqual("CURRENT_TASK_MISMATCH", n.select_next(*args).reason_code)

    def test_task_and_edge_limits_refuse_entire_graph(self):
        context, auth, evidence = inputs()
        with patch.object(n, "MAX_TASKS", 4):
            self.assertEqual("RESOURCE_LIMIT", n.select_next(context, auth, evidence).reason_code)
        with patch.object(n, "MAX_EDGES", 3):
            self.assertEqual("RESOURCE_LIMIT", n.select_next(context, auth, evidence).reason_code)

    def test_time_budget_refuses_even_a_ready_current_task(self):
        args = inputs()
        with patch.object(n.time, "monotonic", side_effect=[0.0, 2.01, 2.02]):
            self.assertEqual("RESOURCE_LIMIT", n.select_next(*args).reason_code)

    def test_ten_thousand_node_chain_is_iterative(self):
        tasks = tuple(n.Task(f"T{i}", "DONE" if i == 0 else "PENDING",
                             () if i == 0 else (f"T{i-1}",)) for i in range(9999))
        args = inputs(tasks + (n.Task("GATE", "PENDING", ("T9998",), "Gate"),), current="T0")
        self.assertEqual("T1", n.select_next(*args).task_id)

    def test_completed_scope_is_not_feature_acceptance(self):
        args = inputs((n.Task("OLD", "DONE"),
                       n.Task("GATE", "DONE", ("OLD",), "Gate", {"Decision ref": SHA})))
        result = n.select_next(*args)
        self.assertEqual(("stop-scope", None, "SCOPE_EXHAUSTED"),
                         (result.action, result.task_id, result.reason_code))
        context, auth, evidence = args
        context = replace(context, tasks=(context.tasks[0], replace(context.tasks[1], contract={})))
        self.assertEqual("GATE_EVIDENCE_MISSING", n.select_next(context, auth, evidence).reason_code)

    def test_accept_task_requests_human_not_auto_confirmation(self):
        args = inputs((n.Task("OLD", "DONE"),
                       n.Task("ACCEPT", "PENDING", ("OLD",), "Acceptance"),
                       n.Task("GATE", "PENDING", ("ACCEPT",), "Gate")))
        self.assertEqual("OPERATION_KIND_MISMATCH", n.select_next(*args).reason_code)
        args[1].grants["ACCEPT"] = grant("accept")
        self.assertEqual(("request-acceptance",), n.select_next(*args).required_authority)
        args[1].grants["ACCEPT"] = grant("accept", ["execute", "request-acceptance"])
        self.assertEqual("ACCEPT", n.select_next(*args).task_id)
        self.assertEqual("PENDING", args[0].tasks[1].state)

    def test_final_gate_requires_acceptance_but_start_gate_does_not(self):
        args = inputs((n.Task("OLD", "DONE"),
                       n.Task("GATE", "PENDING", ("OLD",), "Gate", {"To phase": "DONE"})))
        self.assertEqual("ACCEPTANCE_TASK_MISSING", n.select_next(*args).reason_code)
        context, auth, evidence = args
        context = replace(context, tasks=(context.tasks[0], replace(context.tasks[1],
                          contract={"To phase": "EXECUTING"})))
        self.assertEqual("assign", n.select_next(context, auth, evidence).action)

    def test_no_io_or_task_writer_calls(self):
        # Disallow accidental filesystem, Git/process, network or writer delegation.
        import builtins
        import socket
        import subprocess
        args = self.delivery()
        before = copy.deepcopy(args)
        with patch.object(builtins, "open", side_effect=AssertionError("file IO")), \
             patch.object(subprocess, "Popen", side_effect=AssertionError("process")), \
             patch.object(socket, "socket", side_effect=AssertionError("network")):
            self.assertEqual("LEGACY_EVIDENCE_INCOMPLETE", n.select_next(*args).reason_code)
        self.assertEqual(before, args)


if __name__ == "__main__":
    unittest.main()
