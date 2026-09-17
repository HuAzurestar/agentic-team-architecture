---
name: long-feature-development
description: Resume and advance a multi-session software feature from a project-management directory, using compact Markdown state and Git refs across one or more repositories. Use when development spans multiple Codex sessions, tasks, branches, repositories, or PRs/MRs.
---

# Long Feature Development

Use a small, versioned feature record to continue development without relying on previous chat history. The project chooses the concrete path represented by `<Project-Manage>`; never assume MPA or another fixed repository.

## Required feature layout

```text
<Project-Manage>/<feature>/
├── REQUIREMENT.md
├── SOLUTION.md
├── STATUS.md
├── tasks/
│   └── summary.md
└── gists/
```

`REQUIREMENT.md`, `SOLUTION.md`, and `STATUS.md` are project-management records. `tasks/summary.md` and `gists/` are local agent working material by default and must not be uploaded unless the project explicitly changes that policy.

## Start or resume

1. Resolve the exact `<Project-Manage>` mapping and feature ID. Stop if either is ambiguous.
2. Read `STATUS.md`, `REQUIREMENT.md`, and `SOLUTION.md`.
3. Read only the selected row from `tasks/summary.md` and the gists explicitly named by that row. Do not load unrelated tasks or gists.
4. For every repository row in `STATUS.md`, verify the actual local path, branch, and `HEAD` SHA.
5. For every PR/MR row, verify its source branch/SHA and target branch/SHA when the forge is accessible. Mark unavailable remote state as unverified instead of guessing.
6. Compare recorded and observed refs. Resolve stale state before changing code.

For the project-management repository that contains `STATUS.md`, use the marker `SELF` instead of embedding the document's own commit SHA. Resolve `SELF` with `git rev-parse HEAD` at restore time. Other repositories and task pickup/completion refs use literal SHAs.

## Work on one task

- Tasks use only `TODO`, `WIP`, `BLOCKED`, and `DONE`.
- Requirement, solution, development, testing, and review are task types in the same summary; do not create separate state machines.
- On pickup, change the task to `WIP` and record every relevant `repo@branch@SHA` in `接取 refs`.
- Keep work inside the selected task. Put extra local context in a gist and reference it from the task row.
- Prefix implementation commit subjects with the feature and task, for example `PIRC-23/DEV-01: add feature templates`.
- A task may produce multiple commits. Do not merge implementation branches automatically.
- On completion, record every output `repo@branch@SHA` in `完成 refs`, set `DONE`, and name the next task or action.
- On interruption, keep `WIP` and write the exact next action. On blockage, set `BLOCKED` and write the cause and release condition.

Read [references/transitions.md](references/transitions.md) only when changing task state or the feature's next transition.

## Git and forge boundary

- Treat each repository independently. A feature may span several repositories.
- Use one feature integration branch and at most one final implementation PR/MR per affected repository.
- Record local task branches separately from the feature integration branch and the final PR/MR target branch.
- Code work is committed to implementation branches and is not merged automatically.
- Project-management changes are committed separately. Merge and upload them only when authorized.
- Invoke the available `git-collaboration` skill only at Git-policy boundaries such as creating branches, committing, synchronizing, opening PRs/MRs, reviewing, or configuring CI. Do not load its full references during ordinary context restoration.

## Context boundary

Treat the requirement as the approved intent, the solution as the current proposed implementation, Git as the implementation state, and `STATUS.md` as a compact index. If they disagree, report the conflict and update the stale project-management record before proceeding.

Do not preload repository-wide documentation. Discover code context from the current task, referenced gists, actual diffs, symbols, manifests, and repository instructions.

## End a run

Leave a resumable state containing:

- current task and state;
- observed local branches and SHAs;
- observed PR/MR source and target refs;
- commits produced in this run;
- exact next action;
- blockers and their release conditions.
