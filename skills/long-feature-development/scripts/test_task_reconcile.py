#!/usr/bin/env python3
"""Real Git migration, conditional repair and interruption regressions (F03)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
import task_context as tc
import task_reconcile as recovery
from test_task_context import DETAILS, REQUIREMENT, SOLUTION, STATUS, TASKS, git, make_git_repo


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pirc31-recovery-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.pm, self.app = self.workspace / "pm", self.workspace / "app"
        self.pm_base = make_git_repo(self.pm, "https://example.invalid/pm.git", 1)[0]
        self.app_base = make_git_repo(self.app, "https://example.invalid/app.git", 1)[0]
        git(self.pm, "checkout", "-b", "feature")
        git(self.app, "checkout", "-b", "task")
        (self.app / "owned.py").write_text("version = 1\n", encoding="utf-8")
        git(self.app, "add", "owned.py")
        git(self.app, "commit", "-m", "implement task")
        self.app_head = git(self.app, "rev-parse", "HEAD")
        self.root = self.pm / "project" / "PIRC-23"
        (self.root / "tasks").mkdir(parents=True)
        (self.root / "gists").mkdir()
        self.plan_ref = "gists/parser.md"
        (self.root / self.plan_ref).write_text("# Recovery plan\n", encoding="utf-8")
        status = STATUS.replace("| app | /work/app | task | 4444444 | DEV-02 |",
            f"| pm | {self.pm.as_posix()} | feature | DERIVED:HEAD | DEV-02 |\n"
            f"| app | {self.app.as_posix()} | task | {self.app_head} | DEV-02 |")
        status = status.replace("| app | feature | 4444444 | task branches | observed |",
            f"| pm | main | {self.pm_base} | records | observed |\n"
            f"| app | main | {self.app_base} | task branches | observed |")
        status = status.replace("| Not created | app | feature | 4444444 | main | 1111111 | final target |\n", "")
        status += ("\n## Repository registry\n\n"
            "| Repository | Role | Remote | Path hints | Stable branch | Integration branch |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| pm | project-management | https://example.invalid/pm.git | . | main | feature |\n"
            "| app | implementation | https://example.invalid/app.git | ../app | main | task |\n")
        (self.root / "STATUS.md").write_text(status, encoding="utf-8")
        tasks = TASKS
        for old in ("1111111", "2222222", "3333333"):
            tasks = tasks.replace(old, self.pm_base)
        tasks = tasks.replace("4444444", self.app_head)
        (self.root / "TASKS.md").write_text(tc.synchronized_topology(tasks), encoding="utf-8")
        (self.root / "REQUIREMENT.md").write_text(REQUIREMENT, encoding="utf-8")
        (self.root / "SOLUTION.md").write_text(SOLUTION, encoding="utf-8")
        for task_id, detail in DETAILS.items():
            if task_id == "DEV-02":
                detail = detail.replace("| app | task | main@1111111 <= main@2222222 | task@3333333; task@4444444 | 4444444 | - |",
                    f"| app | task | main@{self.app_base} | task@{self.app_base} | {self.app_head} | - |")
            for old in ("1111111", "2222222", "3333333"):
                detail = detail.replace(old, self.pm_base)
            (self.root / "tasks" / f"{task_id}.md").write_text(detail, encoding="utf-8")
        self.commit_records()

    def commit_records(self):
        git(self.pm, "add", "project/PIRC-23")
        git(self.pm, "commit", "-m", "persist fixture records")

    def inspect(self, **kwargs):
        return recovery.inspect(self.root, {"pm": self.pm, "app": self.app}, plan_gist=self.plan_ref, **kwargs)

    def record(self, plan):
        (self.root / self.plan_ref).write_text("# Recovery plan\n\n```json\n" + json.dumps(plan, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")

    def move_app(self):
        old = self.app
        self.app = self.workspace / "moved-app"
        old.rename(self.app)

    def test_F03_T01_path_migration_is_read_only_then_strictly_recoverable(self):
        tc.build_context(self.root, repo_overrides={"pm": self.pm, "app": self.app})
        before = (self.root / "STATUS.md").read_bytes()
        self.move_app()
        plan = self.inspect()
        self.assertTrue(plan["complete"], plan["blockers"])
        self.assertEqual((self.root / "STATUS.md").read_bytes(), before)
        self.assertEqual([e["path"] for e in plan["edits"]], ["STATUS.md"])
        self.record(plan)
        self.assertEqual(recovery.apply(plan)["conflicts"][0]["code"], "AUTHORITY_REQUIRED")
        applied = recovery.apply(plan, True)
        self.assertEqual(applied["effect"], "APPLIED", applied)
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)
        self.assertEqual(recovery.apply(plan, True)["effect"], "UNCHANGED")
        self.commit_records()
        restored = tc.build_context(self.root, repo_overrides={"pm": self.pm, "app": self.app})
        self.assertEqual(restored["task"]["id"], "DEV-02")

    def test_branch_migration_preserves_start_refs_and_appends_attempt(self):
        detail = self.root / "tasks/DEV-02.md"
        original = detail.read_text(encoding="utf-8")
        git(self.app, "checkout", "-b", "task-next")
        plan = self.inspect()
        self.assertTrue(plan["complete"], plan["blockers"])
        self.record(plan)
        applied = recovery.apply(plan, True)
        self.assertEqual(applied["effect"], "APPLIED", applied)
        changed = detail.read_text(encoding="utf-8")
        self.assertIn(f"task@{self.app_base}; task-next@{self.app_head}", changed)
        self.assertIn("Recovery attempt " + plan["plan_id"], changed)
        self.assertIn(f"main@{self.app_base}", changed)
        self.assertNotEqual(changed, original)
        self.commit_records()
        self.assertEqual(tc.build_context(self.root)["repositories"]["app"]["actual_branch"], "task-next")

    def test_F03_T02_wrong_identity_and_ambiguous_repository_are_rejected(self):
        git(self.app, "remote", "set-url", "origin", "https://credential@other.invalid/app.git")
        plan = self.inspect()
        self.assertEqual(plan["blockers"][0]["code"], "REPO_IDENTITY_MISMATCH")
        self.assertNotIn("credential", json.dumps(plan))
        git(self.app, "remote", "set-url", "origin", "https://example.invalid/app.git")
        duplicate = self.workspace / "duplicate"
        make_git_repo(duplicate, "https://example.invalid/app.git", 1)
        plan = recovery.inspect(self.root, {"pm": self.pm}, plan_gist=self.plan_ref)
        self.assertEqual(plan["blockers"][0]["code"], "AMBIGUOUS_REPOSITORY")

    def advance_main(self, filename):
        git(self.app, "checkout", "main")
        (self.app / filename).write_text("upstream change\n", encoding="utf-8")
        git(self.app, "add", filename)
        git(self.app, "commit", "-m", "advance integration target")
        head = git(self.app, "rev-parse", "HEAD")
        git(self.app, "checkout", "task")
        return head

    def test_F03_T03_unrelated_target_advance_is_observation_not_merge(self):
        baseline = (self.root / "tasks/DEV-02.md").read_bytes()
        next_head = self.advance_main("unrelated.txt")
        plan = self.inspect()
        self.assertTrue(plan["complete"], plan["blockers"])
        self.record(plan)
        applied = recovery.apply(plan, True)
        self.assertEqual(applied["effect"], "APPLIED", applied)
        self.assertEqual((self.root / "tasks/DEV-02.md").read_bytes(), baseline)
        self.assertEqual(git(self.app, "rev-parse", "HEAD"), self.app_head)
        self.assertFalse((self.app / "unrelated.txt").exists())
        status = (self.root / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn(next_head, status)
        self.assertIn(self.app_base, status)
        self.commit_records()
        tc.build_context(self.root)

    def test_target_overlap_and_nonancestor_rewrite_are_blockers(self):
        self.advance_main("owned.py")
        self.assertEqual(self.inspect()["blockers"][0]["code"], "INTEGRATION_SCOPE_CONFLICT")
        tree = git(self.app, "rev-parse", "main^{tree}")
        orphan = git(self.app, "commit-tree", tree, "-m", "unrelated history")
        git(self.app, "update-ref", "refs/heads/main", orphan)
        self.assertEqual(self.inspect()["blockers"][0]["code"], "REF_MOVED")

    def test_changed_bytes_or_refs_after_inspect_prevent_apply(self):
        self.move_app()
        plan = self.inspect()
        self.record(plan)
        status = self.root / "STATUS.md"
        changed = status.read_bytes() + b"external change\n"
        status.write_bytes(changed)
        self.assertEqual(recovery.apply(plan, True)["conflicts"][0]["code"], "CONTENT_CONFLICT")
        self.assertEqual(status.read_bytes(), changed)

    def test_changed_head_after_inspect_does_not_replay_plan(self):
        self.move_app()
        plan = self.inspect()
        self.record(plan)
        before = (self.root / "STATUS.md").read_bytes()
        git(self.app, "commit", "--allow-empty", "-m", "new candidate")
        self.assertEqual(recovery.apply(plan, True)["conflicts"][0]["code"], "PLAN_STALE")
        self.assertEqual((self.root / "STATUS.md").read_bytes(), before)

    def test_unowned_residue_and_concurrent_coordinator_are_rejected(self):
        (self.app / "user.txt").write_bytes(b"USER")
        plan = self.inspect()
        self.assertEqual(plan["blockers"][0]["code"], "UNOWNED_CHANGES")
        self.assertEqual((self.app / "user.txt").read_bytes(), b"USER")
        (self.app / "user.txt").unlink()
        self.move_app()
        plan = self.inspect()
        self.record(plan)
        (self.root / ".reconcile.lock").write_bytes(b"another coordinator")
        self.assertEqual(recovery.apply(plan, True)["conflicts"][0]["code"], "COORDINATOR_BUSY")
        self.assertEqual((self.root / ".reconcile.lock").read_bytes(), b"another coordinator")

    def test_partial_apply_reenters_without_repeating_successful_write(self):
        git(self.app, "checkout", "-b", "task-next")
        plan = self.inspect()
        self.assertGreaterEqual(len(plan["edits"]), 2)
        self.record(plan)
        real_write = recovery.atomic_replace
        calls = []
        def interrupt(path, raw):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("injected interrupted write")
            real_write(path, raw)
        with patch.object(recovery, "atomic_replace", side_effect=interrupt):
            result = recovery.apply(plan, True)
        self.assertEqual(result["effect"], "PARTIAL", result)
        repaired = recovery.apply(plan, True)
        self.assertEqual(repaired["effect"], "APPLIED", repaired)
        self.assertEqual(len(repaired["unchanged_files"]), 1)
        self.assertEqual(recovery.apply(plan, True)["effect"], "UNCHANGED")

    def test_tampered_plan_cannot_change_task_scope_or_escape_root(self):
        self.move_app()
        plan = self.inspect()
        plan["edits"][0]["path"] = "../outside.md"
        self.record(plan)
        self.assertEqual(recovery.apply(plan, True)["conflicts"][0]["code"], "INVALID_PLAN")
        self.assertFalse((self.root.parent / "outside.md").exists())

    def test_bom_crlf_are_preserved_outside_repaired_rows(self):
        status = self.root / "STATUS.md"
        raw = status.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        status.write_bytes(b"\xef\xbb\xbf" + raw)
        self.commit_records()
        self.move_app()
        plan = self.inspect()
        self.assertTrue(plan["complete"], plan["blockers"])
        self.record(plan)
        result = recovery.apply(plan, True)
        self.assertEqual(result["effect"], "APPLIED", result)
        current = status.read_bytes()
        self.assertTrue(current.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", current.replace(b"\r\n", b""))

    def test_management_repository_migration_preserves_identity(self):
        old = self.pm
        self.pm = self.workspace / "moved-pm"
        old.rename(self.pm)
        self.root = self.pm / "project/PIRC-23"
        plan = self.inspect()
        self.assertTrue(plan["complete"], plan["blockers"])
        self.record(plan)
        self.assertEqual(recovery.apply(plan, True)["effect"], "APPLIED")
        self.commit_records()
        tc.build_context(self.root, repo_overrides={"pm": self.pm, "app": self.app})

    def test_linked_worktree_is_verified_without_mutating_git_index(self):
        original_app = self.app
        self.app = self.workspace / "linked-app"
        git(original_app, "worktree", "add", "-b", "relocated-task", str(self.app), self.app_head)
        index = Path(git(self.app, "rev-parse", "--git-path", "index"))
        before = index.read_bytes()
        plan = self.inspect()
        self.assertTrue(plan["complete"], plan["blockers"])
        self.assertEqual(index.read_bytes(), before)
        self.record(plan)
        self.assertEqual(recovery.apply(plan, True)["effect"], "APPLIED")
        self.assertEqual(index.read_bytes(), before)
        self.assertEqual(git(original_app, "symbolic-ref", "--short", "HEAD"), "task")
        self.commit_records()
        tc.build_context(self.root, repo_overrides={"pm": self.pm, "app": self.app})

    def test_new_branch_with_retained_work_updates_matching_index(self):
        git(self.app, "checkout", "-b", "task-next")
        git(self.app, "commit", "--allow-empty", "-m", "retained descendant")
        new_head = git(self.app, "rev-parse", "HEAD")
        plan = self.inspect()
        self.assertTrue(plan["complete"], plan["blockers"])
        self.record(plan)
        applied = recovery.apply(plan, True)
        self.assertEqual(applied["effect"], "APPLIED", applied)
        self.assertIn("TASKS.md", applied["applied_files"])
        self.commit_records()
        restored = tc.build_context(self.root)
        self.assertEqual(restored["task"]["head_refs"]["app"], new_head)

    def test_document_limit_and_git_timeout_never_offer_edits(self):
        with patch.object(recovery, "MAX_FILES", 3):
            plan = self.inspect()
        self.assertEqual(plan["blockers"][0]["code"], "RESOURCE_LIMIT")
        self.assertEqual(plan["edits"], [])
        with patch.object(recovery.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 10)):
            plan = self.inspect()
        self.assertEqual(plan["blockers"][0]["code"], "GIT_TIMEOUT")
        self.assertFalse(plan["complete"])

    def test_missing_recorded_commit_is_not_a_valid_migration(self):
        status = self.root / "STATUS.md"
        status.write_text(status.read_text(encoding="utf-8").replace(self.app_head, "a" * 40), encoding="utf-8")
        self.commit_records()
        self.assertEqual(self.inspect()["blockers"][0]["code"], "MISSING_COMMIT")

    def test_apply_enforces_source_byte_limit_before_writes(self):
        self.move_app()
        plan = self.inspect()
        self.record(plan)
        before = (self.root / "STATUS.md").read_bytes()
        with patch.object(recovery, "MAX_BYTES", 8):
            result = recovery.apply(plan, True)
        self.assertEqual(result["effect"], "NOT_APPLIED")
        self.assertEqual(result["conflicts"][0]["code"], "RESOURCE_LIMIT")
        self.assertEqual((self.root / "STATUS.md").read_bytes(), before)
        self.assertFalse((self.root / ".reconcile.lock").exists())

    def test_forged_edit_is_recomputed_and_refused(self):
        self.move_app()
        plan = self.inspect()
        edit = plan["edits"][0]
        edit["operations"][0]["new_value"] = edit["operations"][0]["new_value"].replace("moved-app", "unauthorized-app")
        raw = (self.root / edit["path"]).read_bytes()
        after = recovery.encode(recovery.replace_operations(recovery.decode(raw), edit["operations"]), raw)
        edit["resulting_bytes_digest"] = recovery.digest(after)
        self.record(plan)
        self.assertEqual(recovery.apply(plan, True)["conflicts"][0]["code"], "PLAN_STALE")
        self.assertEqual((self.root / edit["path"]).read_bytes(), raw)

    def test_third_party_change_during_partial_apply_is_preserved(self):
        git(self.app, "checkout", "-b", "task-next")
        plan = self.inspect()
        self.record(plan)
        target = self.root / plan["edits"][1]["path"]
        replacement = target.read_bytes() + b"\nTHIRD-PARTY\n"
        real_write = recovery.atomic_replace
        def intervene(path, raw):
            real_write(path, raw)
            target.write_bytes(replacement)
        with patch.object(recovery, "atomic_replace", side_effect=intervene):
            result = recovery.apply(plan, True)
        self.assertEqual(result["effect"], "PARTIAL", result)
        self.assertEqual(result["conflicts"][0]["code"], "CONTENT_CONFLICT")
        self.assertEqual(target.read_bytes(), replacement)
        self.assertEqual(recovery.apply(plan, True)["effect"], "NOT_APPLIED")

    def test_cli_rejects_plan_rebound_to_a_different_feature(self):
        self.move_app()
        plan = self.inspect()
        plan["feature_root"] = str(self.workspace)
        self.record(plan)
        proc = subprocess.run([sys.executable, str(Path(recovery.__file__)), str(self.root),
                               "--plan-gist", self.plan_ref, "--apply", "--authorized"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(json.loads(proc.stdout)["complete"])

    def test_cli_inspect_envelope_contains_plan_and_bounded_event(self):
        self.move_app()
        proc = subprocess.run([sys.executable, str(Path(recovery.__file__)), str(self.root),
                               "--repo", f"pm={self.pm}", "--repo", f"app={self.app}",
                               "--plan-gist", self.plan_ref], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["complete"])
        self.assertEqual(result["event"]["name"], "reconcile.inspect")
        self.assertTrue(result["plan"]["comparisons"][-1]["edges"])

    def test_expired_total_budget_cannot_offer_a_plan(self):
        probe = recovery.GitProbe()
        probe.deadline = 0
        plan = self.inspect(_git=probe)
        self.assertFalse(plan["complete"])
        self.assertEqual(plan["edits"], [])
        self.assertEqual(plan["blockers"][0]["code"], "RESOURCE_LIMIT")


if __name__ == "__main__":
    unittest.main()
