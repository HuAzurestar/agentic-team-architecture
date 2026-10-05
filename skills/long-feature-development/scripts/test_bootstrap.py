#!/usr/bin/env python3
"""Execute the documented first-record checkpoint with real Git, without bypasses."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
import task_context as tc
from test_task_context import git, make_git_repo

SKILL = Path(__file__).resolve().parent.parent


class BootstrapTests(unittest.TestCase):
    def test_entry_links_explicit_bootstrap_and_tracks_empty_gists(self):
        entry = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/bootstrap.md", entry)
        guide = (SKILL / "references/bootstrap.md").read_text(encoding="utf-8")
        self.assertIn("gists/.gitkeep", guide)
        self.assertIn("DERIVED:HEAD", guide)
        self.assertIn("task_context.py", guide)

    def test_initial_checkpoint_then_strict_recovery_preserves_dirty_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "project repo"
            baseline = make_git_repo(repo, "https://example.invalid/bootstrap.git", 1)[0]
            git(repo, "checkout", "-b", "feature/bootstrap")
            root = repo / "project" / "NO-FEAT"
            (root / "tasks").mkdir(parents=True)
            (root / "gists").mkdir()
            (root / "gists/.gitkeep").write_bytes(b"")
            replacements = {
                "<feature-key>": "NO-FEAT", "<point-title>": "Initial proposal",
                "<requirement-reference>": "REQUIREMENT.md",
            }
            for name in ("REQUIREMENT.md", "SOLUTION.md", "TASKS.md"):
                content = (SKILL / "templates" / name).read_text(encoding="utf-8")
                for old, new in replacements.items():
                    content = content.replace(old, new)
                (root / name).write_text(content, encoding="utf-8")
            status = (SKILL / "templates/STATUS.md").read_text(encoding="utf-8")
            # One management repository is sufficient; no invented implementation ref.
            status = "\n".join(line for line in status.splitlines()
                               if "<implementation-repo>" not in line
                               and "<task-branch>" not in line
                               and not line.startswith(("| Not created |", "| 待创建 |"))) + "\n"
            values = {
                "<feature-key>": "NO-FEAT", "NO-FEAT-<6-char-random>": "NO-FEAT",
                "<project-manage-repo>": "pm", "<remote>": "https://example.invalid/bootstrap.git",
                "<stable-branch>": "main", "<feature-management-branch>": "feature/bootstrap",
                "<branch>": "feature/bootstrap", "<path>": repo.as_posix(),
                "<task>": "REQ-001", "<observed-sha>": baseline, "<remote-or-none>": "none",
                "<feature-branch>": "feature/bootstrap",
            }
            for old, new in values.items():
                status = status.replace(old, new)
            (root / "STATUS.md").write_text(status, encoding="utf-8")
            for task_id in ("REQ-001", "SOL-001", "GATE-START"):
                detail = (SKILL / "templates/TASK.md").read_text(encoding="utf-8")
                detail = detail.split("## Repository refs", 1)[0]
                detail = detail.replace("<task-id>", task_id).replace("<task-name>", "Initial proposal")
                if task_id == "REQ-001":
                    detail = detail.replace("- Requirement points: none", "- Requirement points: REQ-001")
                elif task_id == "SOL-001":
                    detail = detail.replace("- Solution points: none", "- Solution points: SOL-001")
                detail += (
                    "## Repository refs\n\n"
                    "| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |\n"
                    "| --- | --- | --- | --- | --- | --- |\n"
                    f"| pm | feature/bootstrap | main@{baseline} | - | - | - |\n")
                if task_id == "GATE-START":
                    detail += (
                        "\n## Type contract\n\n| Field | Value |\n| --- | --- |\n"
                        "| From phase | PLANNING |\n| To phase | EXECUTING |\n"
                        "| Required tasks | SOL-001 |\n| Decision ref | - |\n")
                (root / "tasks" / (task_id + ".md")).write_text(detail, encoding="utf-8")
            overrides = {"pm": repo}
            git(repo, "add", "project/NO-FEAT")
            with self.assertRaisesRegex(tc.ContextError, "recovery required"):
                tc.build_context(root, repo_overrides=overrides)
            git(repo, "commit", "-m", "NO-FEAT: initial records; validation pending")
            result = tc.build_context(root, repo_overrides=overrides)
            self.assertEqual(result["trace"]["mode"], "VALIDATED")
            self.assertEqual(result["task"]["id"], "REQ-001")
            self.assertEqual(result["task"]["state"], "PENDING")
            self.assertEqual(result["gists"], [])
            self.assertEqual(git(repo, "status", "--porcelain"), "")
            # A clean clone must retain the empty gist directory.
            clone = Path(temp) / "clone"
            subprocess.run(["git", "clone", "--no-hardlinks", str(repo), str(clone)],
                           check=True, capture_output=True)
            self.assertTrue((clone / "project/NO-FEAT/gists").is_dir())
            self.assertEqual(git(clone, "ls-files", "project/NO-FEAT/gists/.gitkeep"),
                             "project/NO-FEAT/gists/.gitkeep")
            # Ordinary post-bootstrap edits still block recovery, staged or not.
            status_path = root / "STATUS.md"
            status_path.write_text(status + "\n", encoding="utf-8")
            for staged in (False, True):
                if staged:
                    git(repo, "add", "project/NO-FEAT/STATUS.md")
                with self.assertRaisesRegex(tc.ContextError, "recovery required"):
                    tc.build_context(root, repo_overrides=overrides)


if __name__ == "__main__":
    unittest.main(verbosity=2)
