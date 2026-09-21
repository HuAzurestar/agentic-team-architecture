#!/usr/bin/env python3
"""Regression tests for task_context.py."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import task_context


STATUS = """# PIRC-23 Status

| Item | Current value | Note |
| --- | --- | --- |
| Phase | Development | Display only |
| Next transition | Test | Read only when changing |
| Current task | DEV-02 | Restore this task |
| Blocker | None | - |

## Task state

| Task | Type | State | Pickup refs | Completion refs | Next action |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | Requirement | `DONE` | repo@main@1111111 | repo@main@2222222 | SOL-001 |
| SOL-001 | Solution | `DONE` | repo@main@2222222 | repo@main@3333333 | DEV-02 |
| DEV-02 | Development | `WIP` | app@task@3333333 | - | Implement parser |
"""

TASKS = """# PIRC-23 Tasks

## REQ-001 — Confirm requirement point

- Goal: Confirm it.
- Gists: none

## SOL-001 — Confirm solution point

- Goal: Confirm it.
- Gists: none

## DEV-02 — Implement parser

- Goal: Restore exactly one task.
- Inputs: STATUS.md
- Work: Parse the task.
- Completion condition: Tests pass.
- Gists: gists/parser.md
"""

REQUIREMENT = """# PIRC-23 Requirement

## Derived document state

| Item | Value |
| --- | --- |
| Status | `CONFIRMED` |

## Requirement points

### REQ-001 — Confirmed requirement

| Item | Value |
| --- | --- |
| Class | `ACTIVE` |
| State | `CONFIRMED` |

Confirmed requirement.

## Disposition records
"""

SOLUTION = """# PIRC-23 Solution

## Derived document state

| Item | Value |
| --- | --- |
| Status | `BASELINED` |

## Solution points

### SOL-001 — Confirmed solution

| Item | Value |
| --- | --- |
| Class | `ACTIVE` |
| State | `CONFIRMED` |
| Requirement points | `REQ-001` |

Baselined solution.

## Disposition records
"""


class TaskContextTests(unittest.TestCase):
    def make_feature(self, parent: Path, status: str = STATUS, tasks: str = TASKS) -> Path:
        root = parent / "PIRC-23"
        (root / "gists").mkdir(parents=True)
        (root / "STATUS.md").write_text(status, encoding="utf-8")
        (root / "TASKS.md").write_text(tasks, encoding="utf-8")
        (root / "REQUIREMENT.md").write_text(REQUIREMENT, encoding="utf-8")
        (root / "SOLUTION.md").write_text(SOLUTION, encoding="utf-8")
        (root / "gists" / "parser.md").write_text("Parser details.\n", encoding="utf-8")
        return root

    def test_extracts_current_task_and_declared_gist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            context = task_context.build_context(root)
            self.assertEqual(context["task"]["id"], "DEV-02")
            self.assertEqual(context["task"]["state"], "WIP")
            self.assertEqual(context["documents"]["requirement"], REQUIREMENT)
            self.assertEqual(context["documents"]["solution"], SOLUTION)
            self.assertEqual(context["gists"][0]["path"], "gists/parser.md")
            self.assertEqual(context["gists"][0]["content"], "Parser details.\n")

    def test_explicit_task_must_exist_in_status_and_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            context = task_context.build_context(root, "REQ-001")
            self.assertEqual(context["task"]["id"], "REQ-001")
            self.assertEqual(context["gists"], [])

    def test_missing_current_task_row_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp), STATUS.replace("| Current task | DEV-02 | Restore this task |\n", ""))
            with self.assertRaisesRegex(task_context.ContextError, "exactly one Current task"):
                task_context.build_context(root)

    def test_chinese_table_headers_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            status = (
                STATUS.replace("| Item | Current value | Note |", "| 项目 | 当前值 | 备注 |")
                .replace("| Current task |", "| 当前任务 |")
                .replace(
                    "| Task | Type | State | Pickup refs | Completion refs | Next action |",
                    "| Task | 类型 | 状态 | 接取 refs | 完成 refs | 下一步 |",
                )
            )
            tasks = TASKS.replace("- Gists: none", "- Gists：无。", 1)
            root = self.make_feature(Path(temp), status=status, tasks=tasks)
            requirement = (
                REQUIREMENT.replace("## Derived document state", "## 派生文档状态")
                .replace("| Item | Value |", "| 项目 | 值 |")
                .replace("| Status |", "| 状态 |")
                .replace("| Class |", "| 类别 |")
                .replace("| State |", "| 状态 |")
            )
            solution = (
                SOLUTION.replace("## Derived document state", "## 派生文档状态")
                .replace("| Item | Value |", "| 项目 | 值 |")
                .replace("| Status |", "| 状态 |")
                .replace("| Class |", "| 类别 |")
                .replace("| State |", "| 状态 |")
            )
            (root / "REQUIREMENT.md").write_text(requirement, encoding="utf-8")
            (root / "SOLUTION.md").write_text(solution, encoding="utf-8")
            context = task_context.build_context(root, "REQ-001")
            self.assertEqual(context["task"]["id"], "REQ-001")
            self.assertEqual(context["gists"], [])

    def test_decision_point_requires_matching_status_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            extra = REQUIREMENT.replace(
                "## Disposition records",
                """### REQ-002 — Another confirmed point

| Item | Value |
| --- | --- |
| Class | `ACTIVE` |
| State | `CONFIRMED` |

## Disposition records""",
            )
            root = self.make_feature(Path(temp))
            (root / "REQUIREMENT.md").write_text(extra, encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "missing STATUS tasks"):
                task_context.build_context(root)

    def test_derived_document_status_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            proposed = REQUIREMENT.replace("| State | `CONFIRMED` |", "| State | `PROPOSED` |")
            root = self.make_feature(Path(temp))
            (root / "REQUIREMENT.md").write_text(proposed, encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "status must be DRAFT"):
                task_context.build_context(root)

    def test_rejected_point_can_be_reopened(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            rejected_requirement = (
                REQUIREMENT.replace("| Status | `CONFIRMED` |", "| Status | `DRAFT` |")
                .replace("| Class | `ACTIVE` |", "| Class | `DISPOSITION` |")
                .replace("| State | `CONFIRMED` |", "| State | `REJECTED` |")
            )
            pending_solution = (
                SOLUTION.replace("| Status | `BASELINED` |", "| Status | `DRAFT` |")
                .replace("| State | `CONFIRMED` |", "| State | `PROPOSED` |")
            )
            pending_status = STATUS.replace(
                "| SOL-001 | Solution | `DONE` |",
                "| SOL-001 | Solution | `WIP` |",
            )
            root = self.make_feature(Path(temp), status=pending_status)
            (root / "REQUIREMENT.md").write_text(rejected_requirement, encoding="utf-8")
            (root / "SOLUTION.md").write_text(pending_solution, encoding="utf-8")
            rejected = task_context.build_context(root, "REQ-001")
            self.assertEqual(rejected["task"]["state"], "DONE")

            reopened_requirement = (
                rejected_requirement.replace("| Class | `DISPOSITION` |", "| Class | `ACTIVE` |")
                .replace("| State | `REJECTED` |", "| State | `REOPENED` |")
            )
            reopened_status = pending_status.replace(
                "| REQ-001 | Requirement | `DONE` |",
                "| REQ-001 | Requirement | `WIP` |",
            )
            (root / "STATUS.md").write_text(reopened_status, encoding="utf-8")
            (root / "REQUIREMENT.md").write_text(reopened_requirement, encoding="utf-8")
            context = task_context.build_context(root, "REQ-001")
            self.assertEqual(context["task"]["state"], "WIP")

    def test_done_task_rejects_reopened_point(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            reopened_requirement = (
                REQUIREMENT.replace("| Status | `CONFIRMED` |", "| Status | `DRAFT` |")
                .replace("| State | `CONFIRMED` |", "| State | `REOPENED` |")
            )
            root = self.make_feature(Path(temp))
            (root / "REQUIREMENT.md").write_text(reopened_requirement, encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "requires a decided point state"):
                task_context.build_context(root)

    def test_confirmed_solution_rejects_unconfirmed_requirement_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            reopened_requirement = (
                REQUIREMENT.replace("| Status | `CONFIRMED` |", "| Status | `DRAFT` |")
                .replace("| State | `CONFIRMED` |", "| State | `REOPENED` |")
            )
            reopened_status = STATUS.replace(
                "| REQ-001 | Requirement | `DONE` |",
                "| REQ-001 | Requirement | `WIP` |",
            )
            root = self.make_feature(Path(temp), status=reopened_status)
            (root / "REQUIREMENT.md").write_text(reopened_requirement, encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "unconfirmed requirements"):
                task_context.build_context(root)

    def test_duplicate_task_state_row_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            duplicate = STATUS + "| DEV-02 | Development | `WIP` | app@task@4444444 | - | Duplicate |\n"
            root = self.make_feature(Path(temp), duplicate)
            with self.assertRaisesRegex(task_context.ContextError, "exactly one task-state row"):
                task_context.build_context(root)

    def test_missing_task_section_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp), tasks=TASKS.replace("## DEV-02", "## DEV-03"))
            with self.assertRaisesRegex(task_context.ContextError, "missing task sections"):
                task_context.build_context(root)

    def test_duplicate_task_section_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp), tasks=TASKS + "\n## DEV-02 — Duplicate\n\n- Gists: none\n")
            with self.assertRaisesRegex(task_context.ContextError, "duplicate task sections"):
                task_context.build_context(root)

    def test_extra_task_section_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp), tasks=TASKS + "\n## DEV-03 — Extra\n\n- Gists: none\n")
            with self.assertRaisesRegex(task_context.ContextError, "absent from STATUS"):
                task_context.build_context(root)

    def test_missing_gist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            (root / "gists" / "parser.md").unlink()
            with self.assertRaisesRegex(task_context.ContextError, "declared gist is missing"):
                task_context.build_context(root)

    def test_missing_required_document_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            (root / "REQUIREMENT.md").unlink()
            with self.assertRaisesRegex(task_context.ContextError, "required file is missing"):
                task_context.build_context(root)

    def test_gist_path_traversal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            unsafe = TASKS.replace("gists/parser.md", "gists/../secret.md")
            root = self.make_feature(Path(temp), tasks=unsafe)
            with self.assertRaisesRegex(task_context.ContextError, "unsafe segment"):
                task_context.build_context(root)

    def test_invalid_state_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp), STATUS.replace("| `WIP` |", "| `RUNNING` |"))
            with self.assertRaisesRegex(task_context.ContextError, "invalid state"):
                task_context.build_context(root)

    def test_cli_json_success_and_failure_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(task_context.main([str(root), "--format", "json"]), 0)
            self.assertEqual(json.loads(stdout.getvalue())["task"]["id"], "DEV-02")

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(task_context.main([str(root), "--task", "UNKNOWN"]), 1)
            self.assertIn("ERROR:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
