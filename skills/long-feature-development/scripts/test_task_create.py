#!/usr/bin/env python3
"""Regression tests for Agent-owned task creation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import task_context
import task_create
import test_task_context as fixtures


REGISTRY = """

## Repository registry

| Repository | Role | Remote | Path hints | Stable branch | Integration branch |
| --- | --- | --- | --- | --- | --- |
| pm | project-management | `https://example.invalid/pm.git` | `.` | `main` | `main` |
| app | implementation | `https://example.invalid/app.git` | `../app` | `main` | `feature` |
"""


class TaskCreateTests(unittest.TestCase):
    def make_feature(self, parent: Path) -> Path:
        root = parent / "PIRC-23"
        (root / "gists").mkdir(parents=True)
        (root / "tasks").mkdir()
        (root / "STATUS.md").write_text(fixtures.STATUS + REGISTRY, encoding="utf-8")
        (root / "TASKS.md").write_text(fixtures.TASKS, encoding="utf-8")
        (root / "REQUIREMENT.md").write_text(fixtures.REQUIREMENT, encoding="utf-8")
        (root / "SOLUTION.md").write_text(fixtures.SOLUTION, encoding="utf-8")
        (root / "gists" / "parser.md").write_text("Parser details.\n", encoding="utf-8")
        for task_id, detail in fixtures.DETAILS.items():
            (root / "tasks" / f"{task_id}.md").write_text(detail, encoding="utf-8")
        task_context.sync_topology(root / "TASKS.md")
        return root

    def args(self, root: Path, *extra: str):
        return task_create.parse_args([
            str(root),
            "--type", "Development",
            "--name", "Add strict creation",
            "--depends-on", "SOL-001",
            "--requirement-points", "REQ-001",
            "--solution-points", "SOL-001",
            "--goal", "Create tasks without user bookkeeping",
            "--work", "Add a controlled writer and tests",
            "--completion-condition", "Creation is validated and atomic",
            "--resume-action", "Implement the writer",
            "--repo-ref", "app|feature|main@1111111",
            *extra,
        ])

    def test_allocates_id_creates_detail_and_syncs_topology(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            task_id = task_create.create(root, self.args(root))
            self.assertEqual(task_id, "DEV-03")
            detail = (root / "tasks" / "DEV-03.md").read_text(encoding="utf-8")
            self.assertIn("- Requirement points: REQ-001", detail)
            self.assertIn("Agent-owned task planner", detail)
            tasks = (root / "TASKS.md").read_text(encoding="utf-8")
            self.assertIn("| DEV-03 | Development | Add strict creation | `PENDING` |", tasks)
            records = task_context.task_records(tasks)
            task_context.validate_topology(tasks, records)

    def test_invalid_dependency_or_selector_leaves_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            before = (root / "TASKS.md").read_text(encoding="utf-8")
            bad_dep = self.args(root)
            bad_dep.depends_on = "MISSING-01"
            with self.assertRaisesRegex(task_context.ContextError, "unknown dependencies"):
                task_create.create(root, bad_dep)
            bad_point = self.args(root)
            bad_point.requirement_points = "REQ-999"
            with self.assertRaisesRegex(task_context.ContextError, "unknown REQ points"):
                task_create.create(root, bad_point)
            self.assertEqual((root / "TASKS.md").read_text(encoding="utf-8"), before)
            self.assertFalse((root / "tasks" / "DEV-03.md").exists())

    def test_acceptance_creation_includes_user_brief_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            args = self.args(root)
            args.type = "Acceptance"
            args.name = "User acceptance"
            task_id = task_create.create(root, args)
            self.assertEqual(task_id, "ACCEPT-01")
            detail = (root / "tasks" / f"{task_id}.md").read_text(encoding="utf-8")
            self.assertIn("| Acceptance brief | - |", detail)
            self.assertIn("| Decision | WAITING |", detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
