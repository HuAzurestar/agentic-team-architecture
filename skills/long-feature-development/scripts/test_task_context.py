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
| Phase | `EXECUTING` | Gate controlled |
| Condition | `ACTIVE` | - |
| Next transition | GATE-ACCEPT | - |
| Current task | DEV-02 | Restore this task |
| Current gate | GATE-ACCEPT | - |
| Blocker | None | - |

## Working branches

| Repository | Local path | Working branch | Working HEAD SHA | Current task |
| --- | --- | --- | --- | --- |
| app | /work/app | task | 4444444 | DEV-02 |

## Integration opponents

| Repository | Integration branch | Integration SHA | Receives | Note |
| --- | --- | --- | --- | --- |
| app | feature | 4444444 | task branches | observed |

## PR/MR objects

| Object | Repository | Source branch | Source SHA | Target branch | Target SHA | Note |
| --- | --- | --- | --- | --- | --- | --- |
| Not created | app | feature | 4444444 | main | 1111111 | final target |
"""

TASKS = """# PIRC-23 Tasks

## Task index

| ID | Type | Name | State | Owner | Depends on | Started at | Completed at | HEAD SHA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-001 | Requirement | Confirm requirement | `DONE` | human | - | 2026-09-01T09:00:00Z | 2026-09-01T09:10:00Z | pm@2222222 |
| SOL-001 | Solution | Confirm solution | `DONE` | human | REQ-001 | 2026-09-01T09:11:00Z | 2026-09-01T09:20:00Z | pm@3333333 |
| DEV-02 | Development | Implement parser | `WIP` | codex | SOL-001 | 2026-09-01T09:21:00Z | - | app@4444444; pm@3333333 |
| GATE-ACCEPT | Gate | Complete feature | `PENDING` | - | DEV-02 | - | - | - |

## Dependency topology

<!-- task-topology:start -->
placeholder
<!-- task-topology:end -->
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

DETAILS = {
    "REQ-001": """# REQ-001 — Confirm requirement

- Goal: Confirm it.
- Requirement points: REQ-001
- Solution points: none
- Gists: none

## Repository refs

| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |
| --- | --- | --- | --- | --- | --- |
| pm | feature | main@1111111 | feature@1111111 | 2222222 | 2222222 |
""",
    "SOL-001": """# SOL-001 — Confirm solution

- Goal: Confirm it.
- Requirement points: REQ-001
- Solution points: SOL-001
- Gists: none

## Repository refs

| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |
| --- | --- | --- | --- | --- | --- |
| pm | feature | main@1111111 <= main@2222222 | feature@2222222 | 3333333 | 3333333 |
""",
    "DEV-02": """# DEV-02 — Implement parser

- Goal: Restore exactly one task.
- Inputs: TASKS.md
- Requirement points: REQ-001
- Solution points: SOL-001
- Work: Parse the task.
- Completion condition: Tests pass.
- Resume action: Continue parser.
- Blocker: none
- Gists: gists/parser.md

## Repository refs

| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |
| --- | --- | --- | --- | --- | --- |
| app | task | main@1111111 <= main@2222222 | task@3333333; task@4444444 | 4444444 | - |
| pm | feature | main@1111111 | feature@3333333 | 3333333 | - |
""",
    "GATE-ACCEPT": """# GATE-ACCEPT — Complete feature

- Goal: Complete the feature after acceptance.
- Requirement points: none
- Solution points: none
- Gists: none

## Repository refs

| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |
| --- | --- | --- | --- | --- | --- |
| pm | feature | main@1111111 | - | - | - |

## Type contract

| Field | Value |
| --- | --- |
| From phase | EXECUTING |
| To phase | DONE |
| Required tasks | DEV-02 |
| Decision ref | - |
""",
}


class TaskContextTests(unittest.TestCase):
    def make_feature(
        self,
        parent: Path,
        *,
        status: str = STATUS,
        tasks: str = TASKS,
        sync: bool = True,
    ) -> Path:
        root = parent / "PIRC-23"
        (root / "gists").mkdir(parents=True)
        (root / "tasks").mkdir()
        (root / "STATUS.md").write_text(status, encoding="utf-8")
        (root / "TASKS.md").write_text(tasks, encoding="utf-8")
        (root / "REQUIREMENT.md").write_text(REQUIREMENT, encoding="utf-8")
        (root / "SOLUTION.md").write_text(SOLUTION, encoding="utf-8")
        (root / "gists" / "parser.md").write_text("Parser details.\n", encoding="utf-8")
        for task_id, detail in DETAILS.items():
            (root / "tasks" / f"{task_id}.md").write_text(detail, encoding="utf-8")
        if sync:
            task_context.sync_topology(root / "TASKS.md")
        return root

    def test_extracts_current_task_refs_dependencies_and_gist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            context = task_context.build_context(self.make_feature(Path(temp)))
            self.assertEqual(context["task"]["id"], "DEV-02")
            self.assertEqual(context["task"]["state"], "WIP")
            self.assertEqual([item["task"]["id"] for item in context["dependencies"]], ["SOL-001"])
            self.assertEqual(len(context["repository_refs"]), 2)
            self.assertEqual(context["gists"][0]["content"], "Parser details.\n")
            self.assertEqual(context["intent"]["requirement"]["points"][0]["id"], "REQ-001")
            self.assertNotIn("documents", context)

    def test_explicit_task_uses_external_detail_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            context = task_context.build_context(self.make_feature(Path(temp)), "REQ-001")
            self.assertIn("# REQ-001", context["task_detail"])
            self.assertEqual(context["gists"], [])

    def test_output_omits_unselected_document_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            marker = "UNSELECTED-LONG-TEXT"
            (root / "REQUIREMENT.md").write_text(
                REQUIREMENT.replace("## Disposition records", f"## Disposition records\n\n{marker}"),
                encoding="utf-8",
            )
            rendered = task_context.render_markdown(task_context.build_context(root))
            self.assertNotIn(marker, rendered)
            self.assertIn("Requirement point: REQ-001", rendered)
            self.assertIn("Direct dependency: SOL-001", rendered)

    def test_missing_or_unknown_point_selector_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            path = root / "tasks" / "DEV-02.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("- Requirement points: REQ-001\n", ""),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(task_context.ContextError, "exactly one '- Requirement points:'"):
                task_context.build_context(root)
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            path = root / "tasks" / "DEV-02.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("Requirement points: REQ-001", "Requirement points: REQ-999"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(task_context.ContextError, "unknown REQ points"):
                task_context.build_context(root)

    def test_legacy_table_backed_point_can_be_focused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            requirement = REQUIREMENT + """

## Correction proposals

| Point | State | Proposal |
| --- | --- | --- |
| CORR-REQ-02 | `CONFIRMED` | Load only focused context. |
"""
            (root / "REQUIREMENT.md").write_text(requirement, encoding="utf-8")
            detail_path = root / "tasks" / "DEV-02.md"
            detail_path.write_text(
                detail_path.read_text(encoding="utf-8").replace(
                    "Requirement points: REQ-001", "Requirement points: CORR-REQ-02"
                ),
                encoding="utf-8",
            )
            points = task_context.build_context(root)["intent"]["requirement"]["points"]
            self.assertEqual(points[0]["id"], "CORR-REQ-02")
            self.assertEqual(points[0]["state"], "CONFIRMED")

    def test_missing_current_task_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            status = STATUS.replace("| Current task | DEV-02 | Restore this task |\n", "")
            root = self.make_feature(Path(temp), status=status)
            with self.assertRaisesRegex(task_context.ContextError, "exactly one Current task"):
                task_context.build_context(root)

    def test_unknown_dependency_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tasks = TASKS.replace("| DEV-02 | Development | Implement parser | `WIP` | codex | SOL-001 |", "| DEV-02 | Development | Implement parser | `WIP` | codex | UNKNOWN |")
            root = self.make_feature(Path(temp), tasks=tasks, sync=False)
            with self.assertRaisesRegex(task_context.ContextError, "unknown dependencies"):
                task_context.build_context(root)

    def test_dependency_cycle_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tasks = TASKS.replace("| REQ-001 | Requirement | Confirm requirement | `DONE` | human | - |", "| REQ-001 | Requirement | Confirm requirement | `DONE` | human | DEV-02 |")
            root = self.make_feature(Path(temp), tasks=tasks, sync=False)
            with self.assertRaisesRegex(task_context.ContextError, "dependency cycle"):
                task_context.build_context(root)

    def test_active_task_requires_done_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tasks = TASKS.replace(
                "| SOL-001 | Solution | Confirm solution | `DONE` | human | REQ-001 | 2026-09-01T09:11:00Z | 2026-09-01T09:20:00Z | pm@3333333 |",
                "| SOL-001 | Solution | Confirm solution | `WIP` | human | REQ-001 | 2026-09-01T09:11:00Z | - | pm@3333333 |",
            )
            detail = DETAILS["SOL-001"].replace("| 3333333 | 3333333 |", "| 3333333 | - |")
            root = self.make_feature(Path(temp), tasks=tasks, sync=False)
            (root / "tasks" / "SOL-001.md").write_text(detail, encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "unfinished dependencies"):
                task_context.build_context(root)

    def test_stale_topology_fails_and_sync_repairs_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            path = root / "TASKS.md"
            path.write_text(path.read_text(encoding="utf-8").replace("Implement parser", "Implement strict parser", 1), encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "topology is stale"):
                task_context.build_context(root)
            task_context.sync_topology(path)
            self.assertEqual(task_context.build_context(root)["task"]["name"], "Implement strict parser")

    def test_missing_and_extra_task_details_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            (root / "tasks" / "DEV-02.md").unlink()
            with self.assertRaisesRegex(task_context.ContextError, "missing detail files"):
                task_context.build_context(root)
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            (root / "tasks" / "EXTRA.md").write_text("# EXTRA — extra\n", encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "absent from TASKS"):
                task_context.build_context(root)

    def test_head_must_match_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            path = root / "tasks" / "DEV-02.md"
            path.write_text(path.read_text(encoding="utf-8").replace("| 4444444 | - |", "| aaaaaaa | - |"), encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "HEAD SHA differs"):
                task_context.build_context(root)

    def test_done_requires_completion_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            path = root / "tasks" / "REQ-001.md"
            path.write_text(path.read_text(encoding="utf-8").replace("| 2222222 | 2222222 |", "| 2222222 | - |"), encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "completion SHA"):
                task_context.build_context(root)

    def test_decision_point_requires_matching_task(self) -> None:
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
            with self.assertRaisesRegex(task_context.ContextError, "missing TASKS tasks"):
                task_context.build_context(root)

    def test_derived_document_status_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            (root / "REQUIREMENT.md").write_text(REQUIREMENT.replace("| State | `CONFIRMED` |", "| State | `PROPOSED` |"), encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "status must be DRAFT"):
                task_context.build_context(root)

    def test_missing_gist_and_path_traversal_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            (root / "gists" / "parser.md").unlink()
            with self.assertRaisesRegex(task_context.ContextError, "declared gist is missing"):
                task_context.build_context(root)
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            path = root / "tasks" / "DEV-02.md"
            path.write_text(path.read_text(encoding="utf-8").replace("gists/parser.md", "gists/../secret.md"), encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "unsafe segment"):
                task_context.build_context(root)

    def test_legacy_status_table_fails_with_migration_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            legacy = STATUS + "\n| Task | Type | State | Pickup refs | Completion refs | Next action |\n| --- | --- | --- | --- | --- | --- |\n| DEV-02 | Development | WIP | app@task@4444444 | - | Continue |\n"
            root = self.make_feature(Path(temp), status=legacy)
            with self.assertRaisesRegex(task_context.ContextError, "migrate it explicitly"):
                task_context.build_context(root)

    def test_invalid_state_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp), tasks=TASKS.replace("`WIP`", "`RUNNING`"), sync=False)
            with self.assertRaisesRegex(task_context.ContextError, "invalid state"):
                task_context.build_context(root)

    def test_feature_phase_and_gate_contract_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            self.assertEqual(task_context.build_context(root, "GATE-ACCEPT")["type_contract"]["To phase"], "DONE")
            status_path = root / "STATUS.md"
            status_path.write_text(STATUS.replace("`EXECUTING`", "`UNKNOWN`"), encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "invalid feature phase"):
                task_context.build_context(root)
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            gate = root / "tasks" / "GATE-ACCEPT.md"
            gate.write_text(gate.read_text(encoding="utf-8").replace("Required tasks | DEV-02", "Required tasks | SOL-001"), encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "must match its direct dependencies"):
                task_context.build_context(root, "GATE-ACCEPT")

    def test_acceptance_cannot_be_completed_by_agent(self) -> None:
        record = {"id": "ACCEPT-01", "state": "DONE", "dependencies": []}
        detail = """# ACCEPT-01 — Accept

## Type contract

| Field | Value |
| --- | --- |
| Target SHA | 1111111 |
| Acceptance scope | Current feature |
| Decision | CONFIRMED |
| Decided by | Codex |
"""
        with self.assertRaisesRegex(task_context.ContextError, "requires a human"):
            task_context.validate_type_contract(record, detail, {"ACCEPT-01": record})

    def test_done_test_requires_honest_coverage_fields(self) -> None:
        record = {"id": "TEST-02", "state": "DONE", "dependencies": []}
        detail = """# TEST-02 — Test

## Type contract

| Field | Value |
| --- | --- |
| Target SHA | 1111111 |
| Environment | local |
| Planned checks | unit, integration |
| Executed | unit |
| Passed | unit |
| Failed | - |
| Skipped | integration |
| Unknown | - |
| Result gist | gists/TEST-02.md |
"""
        with self.assertRaisesRegex(task_context.ContextError, "incomplete field: Failed"):
            task_context.validate_type_contract(record, detail, {"TEST-02": record})

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
