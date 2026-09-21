---
name: long-feature-development
description: Help Codex resume and advance a multi-session software feature from a project-management directory, using compact Markdown state and Git refs across repositories or PRs/MRs. Use for work spanning sessions; do not use for an ordinary one-session change.
---

# Long Feature Development

This Codex skill uses a small, versioned feature record to continue development without relying on previous chat history. The project chooses the concrete path represented by `<Project-Manage>`; never assume MPA or another fixed repository.

## Required feature layout

```text
<Project-Manage>/<feature-key>/
├── REQUIREMENT.md
├── SOLUTION.md
├── STATUS.md
├── TASKS.md
├── tasks/
│   └── <task-id>.md
└── gists/
```

`REQUIREMENT.md`, `SOLUTION.md`, and `STATUS.md` are project-management records. `TASKS.md`, `tasks/`, and `gists/` are local agent working material by default and must not be uploaded unless the project explicitly changes that policy.

## Initialize a feature

1. Resolve `<Project-Manage>`. If the developer has not assigned a feature ID, use `NO-FEAT` when unique or `NO-FEAT-<6-char-random>` when collision is possible. Do not delay initialization to invent an official ID.
2. Copy the four matching files from `templates/`, then copy `templates/TASK.md` once per initial task into local `tasks/<task-id>.md`.
3. Replace or remove every angle-bracket placeholder. Keep exactly one `TASKS.md` index row and one `tasks/<task-id>.md` detail file per task; the supplied `REQ-001` and `SOL-001` point tasks are mandatory until replaced by real point IDs.
4. Create local `gists/` only when a task needs one.
5. Add exact, feature-scoped local exclude entries for `TASKS.md`, `tasks/`, and `gists/`; do not add a repository-wide ignore rule without authorization.
6. Run the [task context helper](scripts/task_context.py) as `python <skill-root>/scripts/task_context.py <feature-directory>` before the first project-management commit. Fix every reported mismatch.
7. Leave requirement and solution in `DRAFT`. Their overall states are derived from point states, never set by a global approval.

## Feature identity

`NO-FEAT` and `NO-FEAT-<6-char-random>` are valid temporary feature keys. Use six lowercase alphanumeric characters for the random suffix. The developer alone chooses when to assign an official ID; feasibility confirmation is common but not required. When the ID changes, rename the feature directory, update the document titles and `STATUS.md` feature ID in one project-management change, and append the old key to `Previous IDs`. Never rewrite old commits or remote history to hide the temporary key.

## Start or resume

1. Resolve the exact `<Project-Manage>` mapping and feature ID. Stop if either is ambiguous.
2. Run `python <skill-root>/scripts/task_context.py <feature-directory>`. Use `--task <task-id>` only when the user explicitly selects a non-current task. The command is the single recovery reader: it validates the task index and topology, then prints the selected task detail and only its declared gists. The focused requirement and solution slices are added by the context rules below.
3. From that output, verify the requirement and solution confirmation states before treating them as fixed boundaries.
4. For every repository, separately verify the working branch/HEAD, the integration branch/SHA used for ongoing task merges, and the final PR/MR source/target refs.
5. Mark unavailable remote state as unverified instead of guessing.
6. Compare recorded and observed refs. Resolve stale state before changing code.

Treat a nonzero `task_context.py` exit as a hard stop. Do not infer a missing current-task field, `TASKS.md` row, task detail file, dependency, Git ref, or declared gist. An old task table in `STATUS.md` is not silently migrated.

The project-management repository containing `STATUS.md` cannot embed the SHA of the commit that contains that same file. Its working-HEAD cell therefore uses `DERIVED:HEAD`, meaning the checked-out Git HEAD is the source of truth. Resolve it only when `STATUS.md` is tracked, matches HEAD, and has no staged or unstaged changes; otherwise stop. Every integration-opponent SHA, PR/MR SHA, task pickup ref, and task completion ref must be a literal observed SHA, never a moving branch alias.

## Confirmation boundaries

- Give every decision point a stable `REQ-*` or `SOL-*` ID. A broad statement such as "approve all" never changes point state.
- An LLM may propose likely confirmable points only when authorized. It must then restate each exact ID and content for a second human confirmation.
- A confirmed point is locked until a human explicitly reopens it. Preserve its content and decision history; never silently replace it.
- A rejected point may be revised and reopened without a separate withdrawal. Reconfirmation still requires an explicit human decision.
- Requirement `CONFIRMED` and solution `BASELINED` are derived states: every active point is individually `CONFIRMED`, and no active point is `PROPOSED` or `REOPENED`.

Read [references/confirmation.md](references/confirmation.md) only when adding, deciding, revising, or reopening a requirement or solution point.

## Work on one task

- Tasks use only `PENDING`, `WIP`, `BLOCKED`, `RECORDING`, and `DONE`.
- `TASKS.md` is the only task-state and dependency index. `STATUS.md` stores feature state and points to the current task; it never duplicates the task table.
- Requirement, solution, development, testing, review, rework, acceptance, and gate are task types in the same `TASKS.md` table; do not create per-type state machines.
- Give each requirement or solution point a task with the same ID. Set it to `DONE` only after its individual decision commit SHA is recorded; rejection, out-of-scope, and infeasible decisions also complete the point task.
- On assignment, require every dependency to be `DONE`, change `PENDING` to `WIP`, record the start time, and record every relevant start ref plus current HEAD in `tasks/<task-id>.md`.
- Read scope and completion conditions from `tasks/<task-id>.md`. Put extra local context in a gist and reference it there.
- Prefix implementation commit subjects with the feature and task, for example `PIRC-23/DEV-01: add feature templates`.
- Use one decision point per decision commit. The subject is `<feature-key>/<point-id>: <RESULT> <summary>`, where `RESULT` is `CONFIRMED`, `REJECTED`, `OUT-OF-SCOPE`, `INFEASIBLE`, or `REOPENED`.
- A task may produce multiple commits. Do not merge implementation branches automatically.
- When work is complete, move `WIP` to `RECORDING`, create the final task commit or record the accepted existing commit, then write exactly one completion SHA per affected repository before moving to `DONE`.
- On interruption, keep `WIP` and update the task detail's resume action. On blockage, set `BLOCKED` and write the cause and release condition. A failed or abandoned attempt remains in history; reopening creates new start refs instead of rewriting old ones.
- Keep the Mermaid graph in `TASKS.md` derived from its rows. Run `task_context.py <feature-directory> --sync-topology` after changing task rows, then validate normally.

Read [references/transitions.md](references/transitions.md) only when changing task state or the feature's next transition.

## Git and forge boundary

- Treat each repository independently. A feature may span several repositories.
- Use one feature integration branch and at most one final implementation PR/MR per affected repository.
- Record three different refs separately:
  - **working HEAD**: the branch and SHA currently checked out for a task; only the project-management repository may use `DERIVED:HEAD` under the clean-file rule above;
  - **integration opponent**: the branch and literal observed SHA that task branches merge/rebase against during development;
  - **final PR/MR refs**: the source and target branches and literal observed SHAs used for final review and merge.
- Never use one generic "current SHA" field for all three meanings.
- When an integration or PR/MR branch moves, retain the previously recorded SHA until comparison is complete, then update it to the newly observed literal SHA. Do not use `LIVE:<branch>`, `latest`, or another moving token.
- Code work is committed to implementation branches and is not merged automatically.
- Project-management changes are committed separately. Merge and upload them only when authorized.
- Invoke the available `git-collaboration` skill only at Git-policy boundaries such as creating branches, committing, synchronizing, opening PRs/MRs, reviewing, or configuring CI. Do not load its full references during ordinary context restoration.

## Context boundary

Treat individually confirmed requirement points as approved intent, individually confirmed solution points as the retained implementation plan, Git as implementation state, `STATUS.md` as feature state, `TASKS.md` as the task/ref index, and `tasks/` as focused task detail. If they disagree, report the conflict; do not rewrite a decided point to hide it.

Do not preload repository-wide documentation. Discover code context from the current task, referenced gists, actual diffs, symbols, manifests, and repository instructions.

## End a run

Leave a resumable state containing:

- current task and state;
- observed local branches and SHAs;
- observed PR/MR source and target refs;
- commits produced in this run;
- exact next action;
- blockers and their release conditions.

Before ending, rerun `task_context.py` for the current task. A failed context check means the state is not resumable.

## Validate this Skill

After changing its context rules or helper, run the [context regression tests](scripts/test_task_context.py) and deterministic audit:

```text
python scripts/test_task_context.py
python <skill-quality-reviewer>/scripts/skill-audit.py <skill-root> --format json
```
