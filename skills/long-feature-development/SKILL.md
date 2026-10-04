---
name: long-feature-development
description: Help Codex resume and advance a multi-session software feature from a project-management directory, using compact Markdown state and Git refs across repositories or PRs/MRs. Use for work spanning sessions; do not use for an ordinary one-session change.
---

# Long Feature Development

Paths such as `scripts/...` refer to the assembled skill root. For a repository checkout, first combine this locale's content with the same-named shared runtime directory; installed packages already include it. Development tests remain outside the skill.

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

All six entries are shared project-management records when `<Project-Manage>` is inside a Git repository. `REQUIREMENT.md`, `SOLUTION.md`, and `STATUS.md` are the primary entry; `TASKS.md`, `tasks/`, and `gists/` are short, focus-loaded trace records. Do not hide the latter three with `.gitignore`, `.git/info/exclude`, or an equivalent mechanism. Keep raw logs, large artifacts, and secrets outside this tree and store only bounded summaries and safe references.

## Initialize a feature

1. Resolve `<Project-Manage>`. If the developer has not assigned a feature ID, use `NO-FEAT` when unique or `NO-FEAT-<6-char-random>` when collision is possible. Do not delay initialization to invent an official ID.
2. Copy the four matching files from `templates/`, then copy `templates/TASK.md` once per initial task into local `tasks/<task-id>.md`.
3. Replace or remove every angle-bracket placeholder. Keep exactly one `TASKS.md` index row and one `tasks/<task-id>.md` detail file per task; the supplied `REQ-001` and `SOL-001` point tasks are mandatory until replaced by real point IDs.
4. Create `gists/` only when a task needs one; keep every gist bounded and trace-oriented.
5. If `<Project-Manage>` is a Git repository, verify that `TASKS.md`, `tasks/`, and `gists/` are not ignored and add them to version control with the other feature records.
6. Run the [task context helper](scripts/task_context.py) as `python <skill-root>/scripts/task_context.py <feature-directory>` before the first project-management commit. Fix every reported mismatch.
7. Leave requirement and solution in `DRAFT`. Their overall states are derived from point states, never set by a global approval.

The Agent owns initial task IDs, types, dependencies, and selectors. The user supplies business intent and decisions, not internal bookkeeping labels.

## Feature identity

`NO-FEAT` and `NO-FEAT-<6-char-random>` are valid temporary feature keys. Use six lowercase alphanumeric characters for the random suffix. The developer alone chooses when to assign an official ID; feasibility confirmation is common but not required. When the ID changes, rename the feature directory, update the document titles and `STATUS.md` feature ID in one project-management change, and append the old key to `Previous IDs`. Never rewrite old commits or remote history to hide the temporary key.

## Start or resume

1. Resolve the exact `<Project-Manage>` mapping and feature ID. Stop if either is ambiguous.
2. Run `python <skill-root>/scripts/task_context.py <feature-directory>`. For an initial or repeated blind REVIEW, the first call must instead include `--review-phase blind` and only explicitly prepared `--review-input gists/raw-input.md` packets; never print ordinary recovery first. See the review integration below. Use `--task <task-id>` only when the user explicitly selects a non-current task. If a repository moved or a path hint is unavailable, pass an explicit `--repo NAME=PATH` for each override. The command is the single recovery reader: it validates the task index, topology, repository identities, real Git refs and required trace closure, then prints the focused feature/task context.
3. From that output, verify the requirement and solution confirmation states before treating them as fixed boundaries.
4. For every repository, separately verify the working branch/HEAD, the integration branch/SHA used for ongoing task merges, and the final PR/MR source/target refs.
5. Mark unavailable remote state as unverified instead of guessing.
6. Compare recorded and observed refs. Resolve stale state before changing code.

Treat a nonzero `task_context.py` exit as a hard stop. Do not infer a missing current-task field, `TASKS.md` row, task detail file, dependency, Git ref, or declared gist. An old task table in `STATUS.md` is not silently migrated.

The recovery command is an internal Skill action, not an instruction the user must put in a prompt. It also checks relevant staged, unstaged, and untracked changes. A dirty implementation repository, or residue inside this feature's project-management directory, enters recovery-required mode before any new edits. Read [references/checkpoints.md](references/checkpoints.md) when that happens.

The project-management repository containing `STATUS.md` cannot embed the SHA of the commit that contains that same file. Its working-HEAD cell therefore uses `DERIVED:HEAD`, meaning the checked-out Git HEAD is the source of truth. Resolve it only when `STATUS.md` is tracked, matches HEAD, and has no staged or unstaged changes; otherwise stop. Every integration-opponent SHA, PR/MR SHA, task pickup ref, and task completion ref must be a literal observed SHA, never a moving branch alias.

## Confirmation boundaries

- Give every decision point a stable level-two `## REQ-*` or `## SOL-*` heading. A broad statement such as "approve all" never changes point state. Level-three headings inside a point are point-local content, not new points.
- An LLM may propose likely confirmable points only when authorized. It must then restate each exact ID and content for a second human confirmation.
- A confirmed point is locked until a human explicitly reopens it. Preserve its content and decision history; never silently replace it.
- A rejected point may be revised and reopened without a separate withdrawal. Reconfirmation still requires an explicit human decision.
- Requirement `CONFIRMED` and solution `BASELINED` are derived states: every active point is individually `CONFIRMED`, and no active point is `PROPOSED` or `REOPENED`.

Read [references/confirmation.md](references/confirmation.md) only when adding, deciding, revising, or reopening a requirement or solution point.

## Work on one task

- The Agent creates and connects internal tasks. Use `scripts/task_create.py` for normal additions, and never ask the user to supply an internal task ID, dependency, or selector. Ask only about real business ambiguity, authorization, or unsafe-to-infer scope. Read [references/task-planning.md](references/task-planning.md) when planning new work.
- Tasks use only `PENDING`, `WIP`, `BLOCKED`, `RECORDING`, and `DONE`.
- `STATUS.md` is the primary control entry: it stores feature state, the current task/gate summary, and repository/object registries. `TASKS.md` is the only complete task-state and dependency index; STATUS never duplicates its full table.
- Requirement, solution, development, testing, review, rework, acceptance, and gate are task types in the same `TASKS.md` table; do not create per-type state machines.
- Give each requirement or solution point a task with the same ID. Set it to `DONE` only after its individual decision commit SHA is recorded; rejection, out-of-scope, and infeasible decisions also complete the point task.
- `PENDING` means unassigned. A pending task with all dependencies `DONE` is derived as `READY`; one with unfinished dependencies is derived as `WAITING`. Neither is a stored task state.
- On assignment, require `READY`, record the owner, start time, every relevant start ref, and current HEAD in `tasks/<task-id>.md`, then use `python <skill-root>/scripts/task_state.py <feature-directory> <task-id> --to WIP ...` to update the index.
- Read scope and completion conditions from `tasks/<task-id>.md`. Put bounded trace material in a gist and reference it there; never use a gist as an unbounded context dump.
- Declare related intent with exactly one `- Requirement points:` and one `- Solution points:` line. Use comma-separated point IDs or `none`; missing, ambiguous, or unknown selectors are hard errors.
- Prefix implementation commit subjects with the feature and task, for example `PIRC-23/DEV-01: add feature templates`.
- Use one decision point per decision commit. The subject is `<feature-key>/<point-id>: <RESULT> <summary>`, where `RESULT` is `CONFIRMED`, `REJECTED`, `OUT-OF-SCOPE`, `INFEASIBLE`, or `REOPENED`.
- A task may produce multiple commits. Do not merge implementation branches automatically.
- Create a scoped local checkpoint after each coherent work unit, before long or risky operations, and before handoff. Use `scripts/task_checkpoint.py` with explicit Agent-owned files; never auto-push or absorb unrelated or sensitive paths. Read [references/checkpoints.md](references/checkpoints.md) before recording or recovering a checkpoint.
- When work is complete, move `WIP` to `RECORDING`, create the final task commit or record the accepted existing commit, then write exactly one completion SHA per affected repository before moving to `DONE`.
- On interruption, keep `WIP` and update the task detail's resume action. Use `BLOCKED` only for an assigned task stopped by a concrete obstacle; record its blocker, impact, and release condition before the state transition. Ordinary waiting on dependencies remains `PENDING`. A failed or abandoned attempt remains in history; reopening creates new start refs instead of rewriting old ones.
- For a normal cross-file transition: first prepare the task detail and any changed `STATUS.md` current-task/condition fields, then run `task_state.py`, then run read-only `task_context.py` and commit the project-management files together. The writer's atomic guarantee covers the `TASKS.md` row plus Mermaid block, not the other files; a temporarily inconsistent working tree during these three steps is expected but must never be committed.
- Change normal task states only through `task_state.py`. On `DONE -> WIP`, persist a non-empty `Reopen reason` in the task detail and pass the exact same text with `--reason`. Use `task_context.py <feature-directory> --sync-topology` only to repair or import legacy/manual state. A stale diagram is always an error during read-only recovery.

Read [references/transitions.md](references/transitions.md) only when changing task state or the feature's next transition.

Read [references/task-contracts.md](references/task-contracts.md) only when creating, assigning, recording, or completing a `TEST-*`, `REVIEW-*`, `REWORK-*`, `ACCEPT-*`, or `GATE-*` task. Detailed test output and review comments belong in the declared result gist, not in `STATUS.md`, `TASKS.md`, or the short task contract.

For an acceptance task, create and validate the plain-language brief described in [references/acceptance.md](references/acceptance.md). When waiting for a decision, proactively show `task_context.py ... --format acceptance`; do not make the user interpret `ACCEPT-*`, point IDs, contracts, or internal commands.

## Review scope and blind recovery

During design, record one short `- Review scope: review/v1 mode=strong exclude=ui` line in `SOLUTION.md`. Optional `topics` selects a subset, and `focus` adds specific promises; absence defaults to all applicable topics. The task may record the identical short snapshot plus source/version and ledger path. Do not copy topic checklists into feature records. Unknown/duplicate configuration is an error; a differing task snapshot is stale, not a new scope decision. Existing records without this metadata remain recoverable.

The optional `code-review` skill provides topic-based strong review, weak-mode details and the shared finding/score protocol. This skill's recovery views work without that skill, SM-MD or a service. See [review_context.py](scripts/review_context.py) for configuration and view mechanics.

Initial blind input includes current candidate refs, point IDs/statuses, dependency metadata and only explicitly declared raw packets marked `- Evidence type: original`. The coordinator prepares current normative requirement/design excerpts, real authorization and original evidence. The marker routes a packet; it does not certify clean content. Blind recovery withholds arbitrary management prose, task/dependency conclusions, old scores and ledger/review bodies before Markdown or JSON serialization. Full structural/ref/cleanliness validations still run. Missing packets, active action blockers or an empty topic selection are diagnosed as incomplete; do not claim PASS or independent execution.

After saving the blind result, use `--review-phase reconcile --review-report gists/blind-01.md`. The declared snapshot must contain exactly one `Review phase: blind`, `Review task: REVIEW-*`, `Target SHA` matching the selected contract, and `Review scope` matching the current configuration, each as a `- Field: value` line. Reconcile records the snapshot digest and may then expose history and the feature-root `REVIEW.md` ledger. Preserve immutable attempt reports under declared gists; normal recovery does not preload the root ledger. A saved snapshot alone proves neither independent context nor authenticity of a human decision.

Keep REVIEW DONE, score, mandatory rework and final acceptance separate. review/v1 computes `max(0,100-100*P0-10*P1-2*P2-P3)`, with PASS at 60 and no open P0. P0 must be fixed/rechecked or disproved by explicit project design and technical evidence. P1/P2/P3 fixes are optional and retained issues still deduct points; score FAIL alone does not create automatic endless rework. Existing required checks, authorization and final human acceptance remain applicable. Do not silently replace legacy review severity/blocking contracts with this versioned scoring protocol.

Read [references/feature-gates.md](references/feature-gates.md) only when creating or executing a gate or changing feature phase/condition. A gate checks refs and dependencies; it does not replace a human acceptance decision.

## Git and forge boundary

- Treat each repository independently. A feature may span several repositories.
- Resolve repositories from `STATUS.md` in this order: explicit `--repo NAME=PATH`, registered path hints relative to the project-management repository root, then sibling/workspace discovery by registered remote identity. Never trust a historical absolute working path as the locator. Missing or ambiguous matches stop recovery.
- Verify registered stable/integration branches, observed working heads, integration opponents, PR/MR endpoints, task baseline ordering, start-to-head ancestry, completion SHAs, and dependency ancestry against the actual Git object databases. The recovery output includes a derived trace graph; missing commits or disconnected required paths are errors.
- A pending task outside the current gate's dependency closure must declare an explicit disposition in its task detail. Do not silently abandon an old branch of work.
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

Treat individually confirmed requirement points as approved intent, individually confirmed solution points as the retained implementation plan, Git as implementation state, `STATUS.md` as the primary feature/repository entry, `TASKS.md` as the task/ref index, and `tasks/` plus `gists/` as shared focused trace records. If they disagree, report the conflict; do not rewrite a decided point to hide it.

Do not preload repository-wide documentation. Discover code context from the current task, referenced gists, actual diffs, symbols, manifests, and repository instructions.

The built-in Markdown focus functions are the standalone behavior and do not require PIRC-14. A future PIRC-14 adapter may produce the same focused-context schema, but it must not broaden selectors, bypass validation, or become mandatory for recovery.

## End a run

Leave a resumable state containing:

- current task and state;
- observed local branches and SHAs;
- observed PR/MR source and target refs;
- commits produced in this run;
- exact next action;
- blockers and their release conditions.

Before ending, rerun `task_context.py` for the current task. A failed context check means the state is not resumable.

Before that final recovery check, checkpoint every coherent owned implementation change. Unexpected power loss can recover through the last successful checkpoint; do not claim zero-loss recovery beyond that boundary.
