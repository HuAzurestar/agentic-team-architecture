#!/usr/bin/env python3
"""Regression tests for task_context.py."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import task_context
import task_state


def git(path: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return process.stdout.strip()


def make_git_repo(path: Path, remote: str, commits: int = 3) -> list[str]:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, stdout=subprocess.DEVNULL)
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "remote", "add", "origin", remote)
    result: list[str] = []
    for index in range(commits):
        git(path, "commit", "--allow-empty", "-m", f"commit {index}")
        result.append(git(path, "rev-parse", "HEAD"))
    return result


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
- Impact: none
- Release condition: none
- Reopen reason: none
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

    def test_level_two_point_owns_nested_headings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            requirement = REQUIREMENT.replace(
                "### REQ-001 — Confirmed requirement",
                "## REQ-001 — Confirmed requirement",
            ).replace(
                "Confirmed requirement.\n\n## Disposition records",
                "### Acceptance\n\nNested point content.\n\n## Disposition records",
            )
            (root / "REQUIREMENT.md").write_text(requirement, encoding="utf-8")
            context = task_context.build_context(root)
            content = context["intent"]["requirement"]["points"][0]["content"]
            self.assertIn("### Acceptance", content)
            self.assertIn("Nested point content.", content)
            self.assertNotIn("## Disposition records", content)

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

    def test_task_heading_accepts_one_leading_bom_without_rewriting_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            path = root / "tasks/DEV-02.md"
            raw = b"\xef\xbb\xbf" + path.read_bytes()
            path.write_bytes(raw)
            context = task_context.build_context(root)
            self.assertTrue(context["task_detail"].startswith("\ufeff# DEV-02"))
            self.assertEqual(path.read_bytes(), raw)
            path.write_bytes(b"\xef\xbb\xbf" + raw)
            with self.assertRaisesRegex(task_context.ContextError, "level-one task heading"):
                task_context.build_context(root)

    def test_nonfocused_tasks_must_have_valid_point_selectors(self) -> None:
        for task_id in ("REQ-001", "SOL-001", "GATE-ACCEPT"):
            for label, value in (("Requirement points", "REQ-999"),
                                 ("Solution points", "SOL-999"),
                                 ("Requirement points", "SOL-001"),
                                 ("Requirement points", "REQ-001, REQ-001")):
                with self.subTest(task=task_id, label=label, value=value), tempfile.TemporaryDirectory() as temp:
                    root = self.make_feature(Path(temp))
                    path = root / "tasks" / (task_id + ".md")
                    text = path.read_text(encoding="utf-8")
                    lines = [f"- {label}: {value}" if line.startswith(f"- {label}:") else line
                             for line in text.splitlines()]
                    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    with self.assertRaises(task_context.ContextError):
                        task_context.build_context(root)
        for mode in ("missing", "duplicate"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = self.make_feature(Path(temp))
                path = root / "tasks/GATE-ACCEPT.md"
                text = path.read_text(encoding="utf-8")
                text = (text.replace("- Solution points: none\n", "") if mode == "missing"
                        else text + "\n- Solution points: none\n")
                path.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(task_context.ContextError, "exactly one"):
                    task_context.build_context(root)

    def test_remote_identity_preserves_repository_path_case(self) -> None:
        import task_reconcile
        for remote in ("https://host.test/Owner/Repo.git", "git@host.test:Owner/Repo.git",
                       "C:/Repos/Repo.git", "https://host.test/Repo.GIT"):
            with self.subTest(remote=remote):
                self.assertEqual(task_context.normalize_remote(remote),
                                 task_reconcile.remote_identity(remote))
                self.assertNotEqual(task_context.normalize_remote(remote),
                                    task_context.normalize_remote(remote.replace("Repo", "repo")))
        self.assertEqual(task_context.normalize_remote(" https://host.test/Owner/Repo.git/ "),
                         "https://host.test/Owner/Repo")

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

    def test_pending_readiness_is_derived_from_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            records = task_context.task_records((root / "TASKS.md").read_text(encoding="utf-8"))
            task_context.validate_dependency_graph(records)
            self.assertEqual(records["GATE-ACCEPT"]["readiness"], "WAITING")
            tasks = (root / "TASKS.md").read_text(encoding="utf-8").replace(
                "| DEV-02 | Development | Implement parser | `WIP` | codex | SOL-001 | 2026-09-01T09:21:00Z | - | app@4444444; pm@3333333 |",
                "| DEV-02 | Development | Implement parser | `DONE` | codex | SOL-001 | 2026-09-01T09:21:00Z | 2026-09-01T09:30:00Z | app@4444444; pm@3333333 |",
            )
            (root / "TASKS.md").write_text(tasks, encoding="utf-8")
            detail = (root / "tasks" / "DEV-02.md").read_text(encoding="utf-8")
            detail = detail.replace("| 4444444 | - |", "| 4444444 | 4444444 |").replace(
                "| 3333333 | - |", "| 3333333 | 3333333 |"
            )
            (root / "tasks" / "DEV-02.md").write_text(detail, encoding="utf-8")
            task_context.sync_topology(root / "TASKS.md")
            records = task_context.task_records((root / "TASKS.md").read_text(encoding="utf-8"))
            task_context.validate_dependency_graph(records)
            self.assertEqual(records["GATE-ACCEPT"]["readiness"], "READY")

    def test_blocked_task_requires_blocker_impact_and_release_condition(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tasks = TASKS.replace("| DEV-02 | Development | Implement parser | `WIP` |", "| DEV-02 | Development | Implement parser | `BLOCKED` |")
            root = self.make_feature(Path(temp), tasks=tasks)
            detail_path = root / "tasks" / "DEV-02.md"
            detail_path.write_text(
                detail_path.read_text(encoding="utf-8").replace("- Blocker: none", "- Blocker: service unavailable"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(task_context.ContextError, "non-empty Impact"):
                task_context.build_context(root)
            detail_path.write_text(
                detail_path.read_text(encoding="utf-8")
                .replace("- Impact: none", "- Impact: integration test cannot run")
                .replace("- Release condition: none", "- Release condition: service restored"),
                encoding="utf-8",
            )
            blocked_status = STATUS.replace("| Condition | `ACTIVE` |", "| Condition | `BLOCKED` |")
            (root / "STATUS.md").write_text(blocked_status, encoding="utf-8")
            self.assertEqual(task_context.build_context(root)["task"]["state"], "BLOCKED")

    def test_state_writer_rejects_waiting_assignment_and_syncs_topology(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            args = task_state.parse_args([
                str(root), "GATE-ACCEPT", "--to", "WIP", "--owner", "codex",
                "--started-at", "2026-09-01T09:31:00Z", "--head", "pm@3333333",
            ])
            with self.assertRaisesRegex(task_context.ContextError, "not READY"):
                task_state.update(root, args)

    def test_state_writer_updates_row_and_mermaid_together(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            detail_path = root / "tasks" / "DEV-02.md"
            detail_path.write_text(
                detail_path.read_text(encoding="utf-8").replace("- Blocker: none", "- Blocker: service unavailable").replace("- Impact: none", "- Impact: integration test cannot run").replace("- Release condition: none", "- Release condition: service restored"),
                encoding="utf-8",
            )
            args = task_state.parse_args([str(root), "DEV-02", "--to", "BLOCKED"])
            task_state.update(root, args)
            text = (root / "TASKS.md").read_text(encoding="utf-8")
            self.assertIn("| DEV-02 | Development | Implement parser | `BLOCKED` |", text)
            self.assertRegex(text, r'\["DEV-02 . Implement parser"\]:::blocked')
            records = task_context.task_records(text)
            task_context.validate_topology(text, records)

    def test_repository_resolution_uses_registry_and_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            pm = parent / "pm"
            app = parent / "renamed-app"
            make_git_repo(pm, "https://example.invalid/pm.git", 1)
            make_git_repo(app, "https://example.invalid/app.git", 1)
            feature = pm / "project" / "PIRC-23"
            feature.mkdir(parents=True)
            registry = {
                "pm": {
                    "repository": "pm", "role": "project-management",
                    "remote": "https://example.invalid/pm.git", "path_hints": ".",
                    "stable_branch": "main", "integration_branch": "main",
                },
                "app": {
                    "repository": "app", "role": "implementation",
                    "remote": "https://example.invalid/app.git", "path_hints": "../missing",
                    "stable_branch": "main", "integration_branch": "main",
                },
            }
            resolved = task_context.resolve_repositories(feature, registry, {"app": app})
            self.assertEqual(Path(resolved["pm"]["path"]), pm.resolve())
            self.assertEqual(Path(resolved["app"]["path"]), app.resolve())
            git(app, "remote", "set-url", "origin", "https://example.invalid/App.git")
            with self.assertRaisesRegex(task_context.ContextError, "cannot be located"):
                task_context.resolve_repositories(feature, registry, {"app": app})
            git(app, "remote", "set-url", "origin", "https://example.invalid/app.git")
            with self.assertRaisesRegex(task_context.ContextError, "cannot be located"):
                task_context.resolve_repositories(feature, registry, {"app": parent / "absent"})
            duplicate = parent / "duplicate-app"
            make_git_repo(duplicate, "https://example.invalid/app.git", 1)
            with self.assertRaisesRegex(task_context.ContextError, "location is ambiguous"):
                task_context.resolve_repositories(feature, registry, {})

    def test_case_distinct_local_repositories_are_not_collapsed(self) -> None:
        if Path("Repo") == Path("repo"):
            self.skipTest("platform Path semantics are case-insensitive")
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            pm, upper, lower = parent / "pm", parent / "Repo", parent / "repo"
            make_git_repo(pm, "https://example.invalid/pm.git", 1)
            make_git_repo(upper, "https://example.invalid/app.git", 1)
            make_git_repo(lower, "https://example.invalid/app.git", 1)
            feature = pm / "project/PIRC-23"
            feature.mkdir(parents=True)
            registry = {
                "pm": dict(repository="pm", role="project-management",
                           remote="https://example.invalid/pm.git", path_hints=".",
                           stable_branch="main", integration_branch="main"),
                "app": dict(repository="app", role="implementation",
                            remote="https://example.invalid/app.git", path_hints="../Repo",
                            stable_branch="main", integration_branch="main"),
            }
            with self.assertRaisesRegex(task_context.ContextError, "location is ambiguous"):
                task_context.resolve_repositories(feature, registry, {})
            import task_reconcile
            with self.assertRaisesRegex(task_reconcile.RecoveryError, "AMBIGUOUS_REPOSITORY"):
                task_reconcile.resolve_repositories(feature, registry, {}, task_reconcile.GitProbe())

    def test_trace_graph_rejects_missing_ancestry_and_disconnected_pending_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "app"
            commits = make_git_repo(repo, "https://example.invalid/app.git", 3)
            tree = git(repo, "rev-parse", "HEAD^{tree}")
            orphan = git(repo, "commit-tree", tree, "-m", "orphan")
            resolved = {
                "app": {
                    "repository": "app", "role": "project-management",
                    "remote": "https://example.invalid/app.git", "path_hints": ".",
                    "stable_branch": "main", "integration_branch": "main",
                    "path": str(repo), "actual_branch": "main", "actual_head": commits[-1],
                }
            }
            records = {
                "DEV-02": {"id": "DEV-02", "state": "WIP", "dependencies": []},
                "GATE-ACCEPT": {"id": "GATE-ACCEPT", "state": "PENDING", "dependencies": ["DEV-02"]},
                "ORPHAN": {"id": "ORPHAN", "state": "PENDING", "dependencies": []},
            }
            refs = [{
                "repository": "app", "branch": "main",
                "baseline_history": f"main@{commits[0]}",
                "start_refs": f"main@{commits[1]}", "head_sha": commits[2],
                "completion_sha": "-",
            }]
            details = {
                "DEV-02": ("- Disposition: required\n", refs),
                "GATE-ACCEPT": ("- Disposition: required\n", []),
                "ORPHAN": ("- Disposition: -\n", []),
            }
            with self.assertRaisesRegex(task_context.ContextError, "explicit Disposition"):
                task_context.validate_trace_graph(STATUS, records, details, resolved, [])
            details["ORPHAN"] = ("- Disposition: superseded\n", [])
            trace = task_context.validate_trace_graph(STATUS, records, details, resolved, [])
            self.assertEqual(trace["mode"], "VALIDATED")
            self.assertIn(
                {"from": "task:DEV-02", "to": "task:GATE-ACCEPT", "kind": "task-dependency"},
                trace["edges"],
            )
            refs[0]["start_refs"] = f"main@{orphan}"
            with self.assertRaisesRegex(task_context.ContextError, "disconnected from its baselines"):
                task_context.validate_trace_graph(STATUS, records, details, resolved, [])
            refs[0]["start_refs"] = f"main@{commits[1]}"
            refs[0]["head_sha"] = "f" * 40
            with self.assertRaisesRegex(task_context.ContextError, "missing HEAD"):
                task_context.validate_trace_graph(STATUS, records, details, resolved, [])

    def test_shared_project_records_must_be_tracked_and_not_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "pm"
            commits = make_git_repo(repo, "https://example.invalid/pm.git", 1)
            feature = repo / "project" / "PIRC-23"
            (feature / "tasks").mkdir(parents=True)
            (feature / "gists").mkdir()
            for name in ("REQUIREMENT.md", "SOLUTION.md", "STATUS.md", "TASKS.md"):
                (feature / name).write_text(name, encoding="utf-8")
            (feature / "tasks" / "T.md").write_text("task", encoding="utf-8")
            resolved = {"pm": {
                "repository": "pm", "role": "project-management", "path": str(repo),
                "actual_branch": "main", "actual_head": commits[-1],
            }}
            with self.assertRaisesRegex(task_context.ContextError, "not tracked"):
                task_context.validate_shared_records(feature, resolved)
            git(repo, "add", "project/PIRC-23")
            git(repo, "commit", "-m", "track feature")
            task_context.validate_shared_records(feature, resolved)
            ignored = feature / "gists" / "ignored.log"
            ignored.write_text("ignored", encoding="utf-8")
            (repo / ".git" / "info" / "exclude").write_text(
                "project/PIRC-23/gists/ignored.log\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(task_context.ContextError, "is ignored"):
                task_context.validate_shared_records(feature, resolved)

    def test_done_reopen_reason_must_be_persisted_and_match_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            tasks_path = root / "TASKS.md"
            tasks_path.write_text(
                tasks_path.read_text(encoding="utf-8").replace(
                    "| DEV-02 | Development | Implement parser | `WIP` | codex | SOL-001 | 2026-09-01T09:21:00Z | - | app@4444444; pm@3333333 |",
                    "| DEV-02 | Development | Implement parser | `DONE` | codex | SOL-001 | 2026-09-01T09:21:00Z | 2026-09-01T09:30:00Z | app@4444444; pm@3333333 |",
                ),
                encoding="utf-8",
            )
            detail_path = root / "tasks" / "DEV-02.md"
            missing = task_state.parse_args([
                str(root), "DEV-02", "--to", "WIP", "--reason", "review found a trace gap",
            ])
            with self.assertRaisesRegex(task_context.ContextError, "persisted Reopen reason"):
                task_state.update(root, missing)
            detail = detail_path.read_text(encoding="utf-8").replace(
                "- Reopen reason: none", "- Reopen reason: review found a trace gap"
            )
            detail_path.write_text(detail, encoding="utf-8")
            task_context.sync_topology(tasks_path)
            mismatch = task_state.parse_args([
                str(root), "DEV-02", "--to", "WIP", "--reason", "different reason",
            ])
            with self.assertRaisesRegex(task_context.ContextError, "exactly match"):
                task_state.update(root, mismatch)
            accepted = task_state.parse_args([
                str(root), "DEV-02", "--to", "WIP", "--reason", "review found a trace gap",
            ])
            task_state.update(root, accepted)
            self.assertIn("Reopen reason: review found a trace gap", detail_path.read_text(encoding="utf-8"))

    def test_task_state_cli_does_not_generate_bytecode_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            scripts = Path(temp) / "scripts"
            scripts.mkdir()
            shutil.copy2(Path(task_state.__file__), scripts / "task_state.py")
            shutil.copy2(Path(task_context.__file__), scripts / "task_context.py")
            process = subprocess.run(
                [sys.executable, str(scripts / "task_state.py"), "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
            self.assertFalse((scripts / "__pycache__").exists())

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

    def test_done_review_requires_finding_values(self) -> None:
        record = {"id": "REVIEW-02", "state": "DONE", "dependencies": []}
        detail = """# REVIEW-02 — Review

## Type contract

| Field | Value |
| --- | --- |
| Target SHA | 1111111 |
| Blocking findings | - |
| Deferred findings | 0 |
| Result gist | gists/REVIEW-02.md |
"""
        with self.assertRaisesRegex(task_context.ContextError, "incomplete field: Blocking findings"):
            task_context.validate_type_contract(record, detail, {"REVIEW-02": record})

    def test_nonselected_quality_contract_is_still_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp))
            gate = root / "tasks" / "GATE-ACCEPT.md"
            gate.write_text(
                gate.read_text(encoding="utf-8").replace("| Decision ref | - |\n", ""),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(task_context.ContextError, "type contract is missing fields: Decision ref"):
                task_context.build_context(root)

    def test_complete_condition_is_reserved_for_done_phase(self) -> None:
        records = {"GATE-ACCEPT": {"type": "Gate", "state": "DONE"}}
        done = """# Status

| Item | Current value | Note |
| --- | --- | --- |
| Phase | `DONE` | - |
| Condition | `COMPLETE` | - |
| Next transition | GATE-ACCEPT | - |
| Current task | GATE-ACCEPT | - |
| Current gate | GATE-ACCEPT | - |
"""
        task_context.validate_feature_state(done, records)
        with self.assertRaisesRegex(task_context.ContextError, "DONE feature requires condition COMPLETE"):
            task_context.validate_feature_state(done.replace("`COMPLETE`", "`ACTIVE`"), records)
        with self.assertRaisesRegex(task_context.ContextError, "valid only when feature phase is DONE"):
            task_context.validate_feature_state(done.replace("`DONE`", "`EXECUTING`"), records)

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

    def test_cli_unicode_output_does_not_depend_on_console_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_feature(Path(temp) / "中文 space")
            gist = root / "gists" / "parser.md"
            gist.write_text("中文正文 😀\n", encoding="utf-8")
            env = dict(os.environ)
            env.pop("PYTHONUTF8", None)
            env["PYTHONIOENCODING"] = "gbk"
            for output_format in ("json", "markdown"):
                with self.subTest(format=output_format):
                    run = subprocess.run(
                        [sys.executable, "-X", "utf8=0", "-B", task_context.__file__,
                         str(root), "--format", output_format], capture_output=True, env=env)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    output = run.stdout.decode("utf-8")
                    self.assertIn("中文正文 😀", output)
                    self.assertNotIn("\r\n", output)
                    if output_format == "json":
                        self.assertEqual(json.loads(output)["task"]["id"], "DEV-02")
            run = subprocess.run(
                [sys.executable, "-X", "utf8=0", "-B", task_context.__file__,
                 str(root / "缺失 😀")], capture_output=True, env=env)
            self.assertEqual(run.returncode, 1)
            self.assertIn("ERROR:", run.stderr.decode("utf-8"))
            self.assertNotIn(b"Traceback", run.stderr)

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

    def test_recording_acceptance_can_persist_human_decision(self) -> None:
        detail = """# ACCEPT-01 — Accept

## Type contract

| Field | Value |
| --- | --- |
| Target SHA | 1111111 |
| Acceptance scope | Current feature |
| Decision | REWORK |
| Decided by | developer |
"""
        recording = {"id": "ACCEPT-01", "state": "RECORDING", "dependencies": []}
        fields = task_context.validate_type_contract(recording, detail, {"ACCEPT-01": recording})
        self.assertEqual(fields["Decision"], "REWORK")
        wip = {**recording, "state": "WIP"}
        with self.assertRaisesRegex(task_context.ContextError, "must keep Decision as WAITING"):
            task_context.validate_type_contract(wip, detail, {"ACCEPT-01": wip})

    def test_acceptance_brief_is_complete_and_renders_without_internal_trace(self) -> None:
        brief = """# Acceptance

## What changed
Visible behavior.

## How to check
Run one check.

## Evidence
Tests passed.

## Out of scope
Deployment.

## Known limitations
None known.

## Decision options
Accept or request changes.
"""
        task_context.validate_acceptance_brief(brief, "gists/acceptance.md")
        rendered = task_context.render_acceptance({
            "task": {"id": "ACCEPT-03"},
            "acceptance_brief": {"path": "gists/acceptance.md", "content": brief},
        })
        self.assertEqual(rendered, brief)
        self.assertNotIn("ACCEPT-03", rendered)
        with self.assertRaisesRegex(task_context.ContextError, "Known limitations"):
            task_context.validate_acceptance_brief(
                brief.replace("None known.", "-"), "gists/acceptance.md"
            )

    def test_recovery_cleanliness_scopes_management_and_blocks_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            pm = parent / "pm"
            app = parent / "app"
            make_git_repo(pm, "https://example.invalid/pm.git", 1)
            make_git_repo(app, "https://example.invalid/app.git", 1)
            feature = pm / "project" / "PIRC-23"
            feature.mkdir(parents=True)
            resolved = {
                "pm": {"role": "project-management", "path": str(pm)},
                "app": {"role": "implementation", "path": str(app)},
            }
            unrelated = pm / "project" / "PIRC-14" / "TASKS.md"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("unrelated", encoding="utf-8")
            task_context.validate_recovery_cleanliness(feature, resolved)
            relevant = feature / "STATUS.md"
            relevant.write_text("residue", encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "recovery required"):
                task_context.validate_recovery_cleanliness(feature, resolved)
            relevant.unlink()
            (app / "unfinished.py").write_text("unfinished", encoding="utf-8")
            with self.assertRaisesRegex(task_context.ContextError, "repository app"):
                task_context.validate_recovery_cleanliness(feature, resolved)

    def test_hidden_index_flags_are_rejected_without_touching_other_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            pm, app = parent / 'pm', parent / 'app'
            make_git_repo(pm, 'https://example.invalid/pm.git', 1)
            make_git_repo(app, 'https://example.invalid/app.git', 1)
            feature = pm / 'project/PIRC-23'
            feature.mkdir(parents=True)
            unrelated = pm / 'project/PIRC-14/TASKS.md'
            unrelated.parent.mkdir(parents=True)
            for path in (feature / 'STATUS.md', unrelated, app / 'source.py'):
                path.write_text('original\n', encoding='utf-8')
            for repo in (pm, app):
                git(repo, 'add', '.')
                git(repo, 'commit', '-m', 'persist source fixture')
            resolved = {'pm': {'role': 'project-management', 'path': str(pm)},
                        'app': {'role': 'implementation', 'path': str(app)}}
            git(pm, 'update-index', '--skip-worktree', 'project/PIRC-14/TASKS.md')
            unrelated.write_text('other feature work\n', encoding='utf-8')
            task_context.validate_recovery_cleanliness(feature, resolved)
            for repo, relative in ((pm, 'project/PIRC-23/STATUS.md'), (app, 'source.py')):
                for flag in ('assume-unchanged', 'skip-worktree'):
                    with self.subTest(repo=repo.name, flag=flag):
                        git(repo, 'update-index', '--' + flag, relative)
                        try:
                            (repo / relative).write_text('hidden edit\n', encoding='utf-8')
                            self.assertEqual(git(repo, 'status', '--porcelain'), '')
                            before = (repo / '.git/index').read_bytes()
                            with self.assertRaisesRegex(task_context.ContextError, '^HIDDEN_INDEX_STATE$'):
                                task_context.validate_recovery_cleanliness(feature, resolved)
                            self.assertEqual(before, (repo / '.git/index').read_bytes())
                            self.assertEqual((repo / relative).read_text(), 'hidden edit\n')
                        finally:
                            git(repo, 'update-index', '--no-' + flag, relative)
                            (repo / relative).write_text('original\n', encoding='utf-8')
            self.assertEqual(unrelated.read_text(), 'other feature work\n')


if __name__ == "__main__":
    unittest.main(verbosity=2)
