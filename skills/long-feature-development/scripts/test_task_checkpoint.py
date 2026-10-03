#!/usr/bin/env python3
"""Regression tests for durable scoped checkpoints."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import task_checkpoint
import task_context
from test_task_context import git, make_git_repo


class TaskCheckpointTests(unittest.TestCase):
    def make_fixture(self, parent: Path) -> tuple[Path, Path, str]:
        pm = parent / "pm"
        app = parent / "app"
        make_git_repo(pm, "https://example.invalid/pm.git", 1)
        commits = make_git_repo(app, "https://example.invalid/app.git", 1)
        git(app, "branch", "feature")
        git(app, "checkout", "feature")
        (app / "work.txt").write_text("baseline\n", encoding="utf-8")
        git(app, "add", "work.txt")
        git(app, "commit", "-m", "baseline file")
        start = git(app, "rev-parse", "HEAD")
        feature = pm / "project" / "PIRC-23"
        (feature / "tasks").mkdir(parents=True)
        status = f"""# Status

## Repository registry

| Repository | Role | Remote | Path hints | Stable branch | Integration branch |
| --- | --- | --- | --- | --- | --- |
| pm | project-management | `https://example.invalid/pm.git` | `.` | `main` | `main` |
| app | implementation | `https://example.invalid/app.git` | `../app` | `main` | `feature` |
"""
        tasks = f"""# Tasks

## Task index

| ID | Type | Name | State | Owner | Depends on | Started at | Completed at | HEAD SHA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV-01 | Development | Work | `WIP` | Codex | - | now | - | app@{start} |

## Dependency topology

<!-- task-topology:start -->
placeholder
<!-- task-topology:end -->
"""
        detail = f"""# DEV-01 — Work

- Goal: Work safely.
- Inputs: feature intent
- Requirement points: none
- Solution points: none
- Work: Edit one file.
- Completion condition: Checkpoint exists.
- Resume action: Continue work.
- Blocker: none
- Impact: none
- Release condition: none
- Reopen reason: none
- Disposition: required
- Gists: none

## Repository refs

| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |
| --- | --- | --- | --- | --- | --- |
| app | feature | main@{commits[0]} | feature@{start} | {start} | - |

## Attempt notes

- Started.
"""
        (feature / "STATUS.md").write_text(status, encoding="utf-8")
        (feature / "TASKS.md").write_text(tasks, encoding="utf-8")
        (feature / "tasks" / "DEV-01.md").write_text(detail, encoding="utf-8")
        task_context.sync_topology(feature / "TASKS.md")
        return feature, app, start

    def args(self, feature: Path, pm: Path, app: Path):
        return task_checkpoint.parse_args([
            str(feature), "DEV-01", "app",
            "--include", "work.txt",
            "--summary", "save parser progress",
            "--resume-action", "Run the focused tests",
            "--repo", f"pm={pm}",
            "--repo", f"app={app}",
        ])

    def test_checkpoint_commits_owned_file_and_updates_resume_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            feature, app, start = self.make_fixture(Path(temp))
            (app / "work.txt").write_text("checkpoint\n", encoding="utf-8")
            sha = task_checkpoint.checkpoint(self.args(feature, feature.parents[1], app))
            self.assertNotEqual(sha, start)
            self.assertEqual(git(app, "rev-parse", "HEAD"), sha)
            self.assertIn("checkpoint save parser progress", git(app, "log", "-1", "--pretty=%s"))
            detail = (feature / "tasks" / "DEV-01.md").read_text(encoding="utf-8")
            self.assertIn(f"| {sha} | - |", detail)
            self.assertIn("- Resume action: Run the focused tests", detail)
            self.assertIn(f"Checkpoint `{sha}`", detail)
            tasks = (feature / "TASKS.md").read_text(encoding="utf-8")
            self.assertIn(f"app@{sha}", tasks)

    def test_checkpoint_rejects_unowned_and_sensitive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            feature, app, start = self.make_fixture(Path(temp))
            (app / "work.txt").write_text("checkpoint\n", encoding="utf-8")
            (app / "extra.txt").write_text("unowned\n", encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "unowned changes"):
                task_checkpoint.checkpoint(self.args(feature, feature.parents[1], app))
            self.assertEqual(git(app, "rev-parse", "HEAD"), start)
            with self.assertRaisesRegex(task_context.ContextError, "sensitive path"):
                task_checkpoint.safe_include("secrets/token.txt")

    def test_invalid_resume_metadata_is_rejected_before_any_git_write(self):
        for damaged in ("attempt-notes", "index-repository"):
            with self.subTest(damaged=damaged), tempfile.TemporaryDirectory() as temp:
                feature, app, start = self.make_fixture(Path(temp))
                (app / "work.txt").write_text("keep this user work\n", encoding="utf-8")
                path = feature / ("tasks/DEV-01.md" if damaged == "attempt-notes" else "TASKS.md")
                text = path.read_text(encoding="utf-8")
                text = text.replace("## Attempt notes", "## Other notes") if damaged == "attempt-notes" else text.replace("app@" + start, "pm@" + start)
                path.write_text(text, encoding="utf-8")
                before = {p: p.read_bytes() for p in feature.rglob("*.md")}
                with self.assertRaises(task_context.ContextError):
                    task_checkpoint.checkpoint(self.args(feature, feature.parents[1], app))
                self.assertEqual(git(app, "rev-parse", "HEAD"), start)
                self.assertEqual(git(app, "diff", "--cached", "--name-only"), "")
                self.assertEqual((app / "work.txt").read_text(encoding="utf-8"), "keep this user work\n")
                self.assertEqual(before, {p: p.read_bytes() for p in before})


if __name__ == "__main__":
    unittest.main(verbosity=2)
