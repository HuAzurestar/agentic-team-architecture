#!/usr/bin/env python3
"""Point application in real disposable repos; all human claims are synthetic."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import decision_apply as apply
import decision_commit as commits
import decision_host as human
from decision_evidence import decision_digest
import test_decision_commit as fixture
from test_decision_point import evidence
from decision_source import _point
import task_context as tc
from test_task_context import git


class PointApplyTests(unittest.TestCase):
    def setUp(self):
        self.case = c = fixture.PointCommitTests()
        c.setUp()
        self.addCleanup(c.doCleanups)
        self.root, self.pm, self.app, self.base = c.root, c.pm, c.app, c.base
        # A confirmed leaf point: its only consumer is still PENDING. The
        # original SOL-001 remains the completed prerequisite of active DEV-02.
        path = self.root / "SOLUTION.md"
        sol = path.read_text(encoding="utf-8")
        insert = sol.index("## Disposition records") if "## Disposition records" in sol else sol.index("## 处置记录")
        sol = sol[:insert] + _point(sol, "SOL-001").replace("SOL-001", "SOL-002") + sol[insert:]
        path.write_text(sol, encoding="utf-8")
        tasks = (self.root / "TASKS.md").read_text(encoding="utf-8")
        row = next(line for line in tasks.splitlines() if line.startswith("| SOL-001 |"))
        tasks = tasks.replace(row, row + "\n" + row.replace("SOL-001", "SOL-002"))
        tasks = tasks.replace("| DEV-02 | - | - | - |", "| DEV-02, SOL-002 | - | - | - |")
        (self.root / "TASKS.md").write_text(tc.synchronized_topology(tasks), encoding="utf-8")
        detail = (self.root / "tasks/SOL-001.md").read_text(encoding="utf-8")
        (self.root / "tasks/SOL-002.md").write_text(detail.replace("SOL-001", "SOL-002"), encoding="utf-8")
        gate = self.root / "tasks/GATE-ACCEPT.md"
        gate.write_text(gate.read_text(encoding="utf-8").replace("| Required tasks | DEV-02 |",
                       "| Required tasks | DEV-02, SOL-002 |"), encoding="utf-8")
        c.case.commit_records()
        self.base = c.base = git(self.pm, "rev-parse", "HEAD")
        self.point = "SOL-002"
        c.record = evidence(sol, self.point, "REOPENED")
        c.record["target_ref"].update(source_key="pm:solution", version=self.base)
        c.grant = replace(c.grant, exact_scope=(self.point,))
        c.reply = replace(c.reply, text=c.record["original_reply"])

    def prepare(self):
        return commits.PointCommit(self.root, self.point, self.case.record, **self.case.options)

    def observe(self):
        return apply.observe_application(self.root, self.pm, self.point, decision_digest(self.case.record))

    def test_actual_application_is_one_commit_and_requires_status_followup(self):
        tasks = (self.root / "TASKS.md").read_bytes()
        result = apply.apply_point(self.prepare())
        self.assertEqual(result["effect"], "APPLIED")
        self.assertEqual(result["status"], "APPLIED_PENDING_STATUS")
        self.assertFalse(result["task_status_recorded"])
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), result["commit"])
        self.assertEqual(git(self.pm, "show", "-s", "--format=%P", "HEAD"), self.base)
        self.assertEqual((self.root / "TASKS.md").read_bytes(), tasks)
        self.assertIn("| REOPENED |", (self.root / "SOLUTION.md").read_text(encoding="utf-8"))
        self.assertEqual(git(self.pm, "status", "--porcelain"), "")
        self.assertEqual(self.observe()["effect"], "APPLIED")

    def test_reopen_with_assigned_consumers_requires_task_graph_coordination(self):
        self.point = "SOL-001"
        self.case.record = evidence((self.root / "SOLUTION.md").read_text(encoding="utf-8"), self.point, "REOPENED")
        self.case.record["target_ref"].update(source_key="pm:solution", version=self.base)
        self.case.grant = replace(self.case.grant, exact_scope=(self.point,))
        self.case.reply = replace(self.case.reply, text=self.case.record["original_reply"])
        with self.assertRaisesRegex(commits.CommitError, "POINT_TASK_GRAPH_RECONCILIATION_REQUIRED"):
            apply.apply_point(self.prepare())
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.base)
        self.assertEqual(git(self.pm, "for-each-ref", "--format=%(refname)", "refs/lfd/point-applications/"), "")

    def test_lost_merge_response_is_read_back_without_repeating_merge(self):
        operation = self.prepare()
        real = apply.git
        calls = []
        def lost(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "merge":
                calls.append(args)
                raise commits.CommitError("POINT_GIT_UNAVAILABLE")
            return result
        with patch.object(apply, "git", side_effect=lost):
            result = apply.apply_point(operation)
        self.assertEqual(result["effect"], "APPLIED")
        self.assertEqual(len(calls), 1)

    def test_lost_dispatch_response_does_not_launch_merge(self):
        real = apply.git
        calls = []
        def lost(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "update-ref":
                calls.append(args)
                raise commits.CommitError("POINT_GIT_UNAVAILABLE")
            if args[0] == "merge":
                self.fail("must not dispatch after unknown marker response")
            return result
        with patch.object(apply, "git", side_effect=lost):
            result = apply.apply_point(self.prepare())
        self.assertEqual(result["status"], "DISPATCHED_UNCONFIRMED")
        self.assertEqual(result["effect"], "UNKNOWN")
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.base)
        self.assertEqual(len(calls), 1)
        # Fresh process/object semantics: observe again; never repeat the effect.
        with patch.object(apply, "git", side_effect=lost):
            again = apply.apply_point(self.prepare())
        self.assertEqual(again["status"], "DISPATCHED_UNCONFIRMED")
        self.assertEqual(len(calls), 1)

    def test_existing_divergent_head_is_not_reset(self):
        operation = self.prepare()
        prepared = operation.prepare_commit()
        git(self.pm, "commit", "--allow-empty", "-m", "external branch change")
        moved = git(self.pm, "rev-parse", "HEAD")
        observed = self.observe()
        self.assertEqual(observed["status"], "HEAD_DIVERGED")
        self.assertEqual(observed["effect"], "UNKNOWN")
        with self.assertRaises(commits.CommitError):
            apply.apply_point(operation)
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), moved)
        self.assertNotEqual(moved, prepared["commit"])

    def test_foreign_point_edit_after_dispatch_is_not_overwritten(self):
        real = apply.git
        external = self.root / "SOLUTION.md"
        def edit(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "update-ref":
                external.write_text(external.read_text(encoding="utf-8") + "\nForeign edit\n", encoding="utf-8")
            return result
        with patch.object(apply, "git", side_effect=edit), self.assertRaises(commits.CommitError):
            apply.apply_point(self.prepare())
        self.assertTrue(external.read_text(encoding="utf-8").endswith("\nForeign edit\n"))
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.base)
        self.assertEqual(self.observe()["status"], "DISPATCHED_UNCONFIRMED")

    def test_revoked_grant_after_dispatch_marker_does_not_apply(self):
        real = apply.git
        def revoke(repo, *args, **kwargs):
            result = real(repo, *args, **kwargs)
            if args[0] == "update-ref":
                self.case.grant = replace(self.case.grant, outcomes=())
            return result
        with patch.object(apply, "git", side_effect=revoke), self.assertRaises(commits.CommitError):
            apply.apply_point(self.prepare())
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), self.base)

    def test_observation_detects_dirty_applied_point(self):
        apply.apply_point(self.prepare())
        path = self.root / "SOLUTION.md"
        path.write_text("foreign replacement", encoding="utf-8")
        self.assertEqual(self.observe()["status"], "APPLICATION_CONFLICT")
        self.assertEqual(path.read_text(encoding="utf-8"), "foreign replacement")

    def test_observation_allows_later_unrelated_commit_but_not_point_replacement(self):
        first = apply.apply_point(self.prepare())
        (self.pm / "unrelated.txt").write_text("later", encoding="utf-8")
        git(self.pm, "add", "unrelated.txt")
        git(self.pm, "commit", "-m", "later unrelated commit")
        self.assertEqual(self.observe()["status"], "APPLIED_PENDING_STATUS")
        path = self.root / "SOLUTION.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nChanged point\n", encoding="utf-8")
        git(self.pm, "add", "project/PIRC-23/SOLUTION.md")
        git(self.pm, "commit", "-m", "later point changed")
        self.assertEqual(self.observe()["status"], "APPLICATION_CONFLICT")
        self.assertNotEqual(git(self.pm, "rev-parse", "HEAD"), first["commit"])

    def test_process_exit_after_merge_is_recovered_without_reapplication(self):
        child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--crash-worker",
                                str(self.root), json.dumps(self.case.record)], capture_output=True, timeout=300)
        self.assertEqual(child.returncode, 74, child.stderr.decode("utf-8", errors="replace"))
        observed = self.observe()
        self.assertEqual(observed["status"], "APPLIED_PENDING_STATUS")
        self.assertEqual(git(self.pm, "rev-parse", "HEAD"), observed["commit"])
        self.assertFalse(observed["task_status_recorded"])


def crash_worker(root, record):
    root = Path(root)
    pm = root.parents[1]
    reply = human.HumanReply(record["human_source_ref"], record["actor"], "human", record["received_at"],
                             record["original_reply"], "conversation", "fixture-version", "fixture:verified")
    grant = human.HumanGrant(record["actor"], record["feature"], "point", "pm:solution", tuple(record["exact_scope"]), ("REOPENED",))
    operation = commits.PointCommit(root, record["exact_scope"][0], record, source_key="pm:solution",
        read_reply=lambda ref: reply,
        interpret=lambda reply, raw: human.HumanInterpretation(decision_digest(raw), "fixture:exact"),
        read_grant=lambda request, raw: grant, repo_overrides={"pm": pm, "app": pm.parent / "app"})
    real = apply.git
    def crash(repo, *args, **kwargs):
        result = real(repo, *args, **kwargs)
        if args[0] == "merge":
            os._exit(74)
        return result
    with patch.object(apply, "git", side_effect=crash):
        apply.apply_point(operation)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--crash-worker":
        crash_worker(sys.argv[2], json.loads(sys.argv[3]))
    else:
        unittest.main(verbosity=2)
