---
name: long-feature-development
description: Help Codex resume and advance a multi-session software feature from a project-management directory, using compact Markdown state and Git refs across repositories or PRs/MRs. Use for work spanning sessions; do not use for an ordinary one-session change.
---

# Long Feature Development

This Codex skill uses a small, versioned feature record to continue development without relying on previous chat history. The project chooses the concrete path represented by `<Project-Manage>`; never assume MPA or another fixed repository.

## Required feature layout

```text
<Project-Manage>/<feature>/
├── REQUIREMENT.md
├── SOLUTION.md
├── STATUS.md
├── TASKS.md
└── gists/
```

`REQUIREMENT.md`, `SOLUTION.md`, and `STATUS.md` are project-management records. `TASKS.md` and `gists/` are local agent working material by default and must not be uploaded unless the project explicitly changes that policy.

## Initialize a feature

1. Resolve `<Project-Manage>` and the feature ID before creating files.
2. Copy only the four matching files from `templates/`: `REQUIREMENT.md`, `SOLUTION.md`, `STATUS.md`, and local `TASKS.md`.
3. Create local `gists/` only when a task needs one.
4. Add exact, feature-scoped local exclude entries for `TASKS.md` and `gists/`; do not add a repository-wide ignore rule without authorization.
5. Leave requirement and solution in `PROPOSED` until a human confirms or baselines them.

## Start or resume

1. Resolve the exact `<Project-Manage>` mapping and feature ID. Stop if either is ambiguous.
2. Read `STATUS.md`, then read `REQUIREMENT.md` and `SOLUTION.md`. Verify their confirmation state before treating them as fixed boundaries.
3. Select the current task from the only task-state table in `STATUS.md`. Read only that task's section in `TASKS.md` and the gists explicitly named there.
4. For every repository, separately verify the working branch/HEAD, the integration branch/SHA used for ongoing task merges, and the final PR/MR source/target refs.
5. Mark unavailable remote state as unverified instead of guessing.
6. Compare recorded and observed refs. Resolve stale state before changing code.

For the project-management repository containing `STATUS.md`, use `SELF` for its working HEAD and `LIVE:<branch>` for a branch changed by the same status update. Resolve both at restore time. Other repositories and task pickup/completion refs use literal SHAs.

## Confirmation boundaries

- `REQUIREMENT.md` is editable while `PROPOSED`. A human changes it to `CONFIRMED`.
- After `CONFIRMED`, do not delete the requirement file or delete/overwrite confirmed text. Append a dated amendment; mark obsolete text `SUPERSEDED` and point to its replacement.
- `SOLUTION.md` is editable while `PROPOSED`. A human changes it to `BASELINED`.
- After `BASELINED`, do not delete the solution file or delete/overwrite baselined text. Append a dated revision and preserve superseded design history.
- Never interpret an LLM proposal or an implementation commit as human confirmation.

## Work on one task

- Tasks use only `TODO`, `WIP`, `BLOCKED`, and `DONE`.
- Requirement, solution, development, testing, and review are task types in the same `STATUS.md` table; do not create separate state machines.
- Set the requirement task to `DONE` only when `REQUIREMENT.md` is `CONFIRMED`; set the solution task to `DONE` only when `SOLUTION.md` is `BASELINED`.
- On pickup, change the task to `WIP` in `STATUS.md` and record every relevant `repo@branch@SHA` in `接取 refs`.
- Read scope and completion conditions from the matching `TASKS.md` section. Put extra local context in a gist and reference it there.
- Prefix implementation commit subjects with the feature and task, for example `PIRC-23/DEV-01: add feature templates`.
- A task may produce multiple commits. Do not merge implementation branches automatically.
- On completion, update the `STATUS.md` row with every output `repo@branch@SHA`, set `DONE`, and name the next task or action.
- On interruption, keep `WIP` and write the exact next action. On blockage, set `BLOCKED` and write the cause and release condition.

Read [references/transitions.md](references/transitions.md) only when changing task state or the feature's next transition.

## Git and forge boundary

- Treat each repository independently. A feature may span several repositories.
- Use one feature integration branch and at most one final implementation PR/MR per affected repository.
- Record three different refs separately:
  - **working HEAD**: the branch and SHA currently checked out for a task;
  - **integration opponent**: the branch and SHA that task branches merge/rebase against during development;
  - **final PR/MR refs**: the source and target branches and SHAs used for final review and merge.
- Never use one generic "current SHA" field for all three meanings.
- Code work is committed to implementation branches and is not merged automatically.
- Project-management changes are committed separately. Merge and upload them only when authorized.
- Invoke the available `git-collaboration` skill only at Git-policy boundaries such as creating branches, committing, synchronizing, opening PRs/MRs, reviewing, or configuring CI. Do not load its full references during ordinary context restoration.

## Context boundary

Treat a confirmed requirement as approved intent, a baselined solution as the retained implementation plan, Git as implementation state, `STATUS.md` as the task/ref index, and `TASKS.md` as local task detail. If they disagree, report the conflict; do not rewrite a confirmed/baselined document to hide it.

Do not preload repository-wide documentation. Discover code context from the current task, referenced gists, actual diffs, symbols, manifests, and repository instructions.

## End a run

Leave a resumable state containing:

- current task and state;
- observed local branches and SHAs;
- observed PR/MR source and target refs;
- commits produced in this run;
- exact next action;
- blockers and their release conditions.
