---
name: long-feature-development
description: Help Codex resume and advance a multi-session software feature from a project-management directory, using compact Markdown state and Git refs across repositories or PRs/MRs. Use for work spanning sessions; do not use for an ordinary one-session change.
---

# Long Feature Development

The [quality host composition](scripts/quality_host.py) reads strict feature records, committed original report/test/checklist objects and actual delivery Git facts before assessing quality. Its [real-source regressions](scripts/test_quality_host.py) use synthetic identity transport; an authenticated provenance reader is still required. See [quality boundaries](references/quality.md).

Protected state writes use the [state evidence guard](scripts/state_guard.py), [writer tests](scripts/test_state_guard.py) and [quality boundary](references/quality.md). A human-looking actor label is not decision provenance; configured host readback is required.

For metadata prepared before a protected write, use the [exact prepared-state reader](scripts/state_prepared.py) and its [real-Git regressions](scripts/test_state_prepared.py). Capture the clean baseline before preparing files; never substitute an ignore-dirty flag. See the quality boundary for host composition and remaining authentication/UI work.

The [quality/selector composition tests](scripts/test_quality_selection.py) cover stage-specific policy consumption; a ready summary cannot replace complete quality inputs for delivery. See [quality integration](references/quality.md).

The [actual quality source reader](scripts/quality_source.py) and [real Git source tests](scripts/test_quality_source.py) bind complete policy objects to original documents. Source integrity alone never proves independent review or human authority; see [quality boundaries](references/quality.md).

For three-phase release evidence, read [quality boundaries](references/quality.md). The [actual Git correspondence reader](scripts/quality_git.py) and [real-repository tests](scripts/test_quality_git.py) establish local ancestry/tree facts only; they do not replace aggregate quality assessment, acceptance or host integration.

The [pure three-phase policy](scripts/quality_policy.py) and [policy tests](scripts/test_quality_policy.py) combine validated feature, detailed reports/tests, exact scope and host-verified observations. Its allowed result never grants an operation. Actual host source/authority adapters and task/UI wiring remain required; do not construct trusted observations from uploaded documents.

This Codex skill uses a small, versioned feature record to continue development without relying on previous chat history. The project chooses the concrete path represented by `<Project-Manage>`; never assume MPA or another fixed repository.

## Select the current purpose

The helper reads only the common section and the chosen section of [purpose prompts](references/prompts.md). For background/provider mutations, first read [capability boundaries](references/capability-boundaries.md); this reader does not supply a write engine.

Choose one purpose: `requirement`, `solution`, `development`, `review`, or `delivery`. Run `python <skill-root>/scripts/context.py --task-ref <feature-directory> --purpose <purpose>` for its prompt and common constraints. Optional environment material is selected through exact heading paths; read [context selection](references/context-selection.md) only when using background. The [background template](templates/BACKGROUND.md) is optional. A complete selection does not replace the task/Git recovery check below. Install a pinned version or upgrade/roll back using [Skill-only installation](references/installation.md); no SMMD or UI is required.

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
4. Create `gists/` at initialization; track an empty `gists/.gitkeep` until real gists exist so a clone retains the required directory. Gist content is optional and must remain bounded and trace-oriented.
5. If `<Project-Manage>` is a Git repository, verify that `TASKS.md`, `tasks/`, and `gists/` are not ignored and add them to version control with the other feature records.
6. Follow the [first-record bootstrap](references/bootstrap.md): inspect the initial records and observed refs, make a scoped local initialization commit explicitly pending validation, then run the [task context helper](scripts/task_context.py) as `python <skill-root>/scripts/task_context.py <feature-directory>`. Do not assign tasks, decide points or advance a Gate until strict recovery passes. Normal dirty-tree recovery is never bypassed.
7. Leave requirement and solution in `DRAFT`. Their overall states are derived from point states, never set by a global approval.

The Agent owns initial task IDs, types, dependencies, and selectors. The user supplies business intent and decisions, not internal bookkeeping labels.

## Feature identity

`NO-FEAT` and `NO-FEAT-<6-char-random>` are valid temporary feature keys. Use six lowercase alphanumeric characters for the random suffix. The developer alone chooses when to assign an official ID; feasibility confirmation is common but not required. When the ID changes, rename the feature directory, update the document titles and `STATUS.md` feature ID in one project-management change, and append the old key to `Previous IDs`. Never rewrite old commits or remote history to hide the temporary key.

## Start or resume

1. Resolve the exact `<Project-Manage>` mapping and feature ID. Stop if either is ambiguous.
2. Run `python <skill-root>/scripts/task_context.py <feature-directory>`. Use `--task <task-id>` only when the user explicitly selects a non-current task. If a repository moved or a path hint is unavailable, pass an explicit `--repo NAME=PATH` for each override. The command is the single recovery reader: it validates the task index, topology, repository identities, real Git refs and required trace closure, then prints the focused feature/task context.
3. From that output, verify the requirement and solution confirmation states before treating them as fixed boundaries.
4. For every repository, separately verify the working branch/HEAD, the integration branch/SHA used for ongoing task merges, and the final PR/MR source/target refs.
5. Mark unavailable remote state as unverified instead of guessing.
6. Compare recorded and observed refs. Resolve stale state before changing code.

Treat a nonzero `task_context.py` exit as a hard stop. Do not infer a missing current-task field, `TASKS.md` row, task detail file, dependency, Git ref, or declared gist. An old task table in `STATUS.md` is not silently migrated.

For verified workspace relocation or integration-observation drift, read [reconciliation](references/reconciliation.md) and use its read-only inspector before a scoped repair. This repairs the recorded facts under existing session authority; it does not bypass the strict recovery check or authorize Git side effects.

For a checkpoint interrupted between commit and bookkeeping, read [operation recovery](references/operations.md). Preserve the successful commit; reconcile its recorded intent before any retry.

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

Read [references/feature-gates.md](references/feature-gates.md) only when creating or executing a gate or changing feature phase/condition. A gate checks refs and dependencies; it does not replace a human acceptance decision.

For decision applicability work, read [decision evidence](references/decision-evidence.md)
and use the pure [checker](scripts/decision_evidence.py) with its [tests](scripts/test_decision_evidence.py).
Read local current material using the [Git source reader](scripts/decision_source.py), covered by [real Git tests](scripts/test_decision_source.py).
Use the [host readback gateway](scripts/decision_host.py) and its [contract tests](scripts/test_decision_host.py) to connect authenticated reply reads, host policy and exact interpretation to the checker.
Live host transports, writers and quality policy still need integration; file claims cannot authenticate a human decision.

## Git and forge boundary

For editable RV comments, read [comment format and compatibility](references/review-comments.md),
then use the [codec](scripts/review_comments.py) and [regressions](scripts/test_review_comments.py).
Before review work or an explicit review-read request, invoke the foreground [source reader](scripts/review_source.py) with the registered binding; see its [real Git regressions](scripts/test_review_source.py).
Git reading does not merge, publish, authorize application or change point decisions; native providers and conditional publication remain pending.
Use the [application preflight](scripts/review_application.py) and [real Git tests](scripts/test_review_application.py) before application; passing still requires F03 intent/writer integration, not an unjournaled merge.
For an authorized repository sync, use the [F03 journaled writer](scripts/review_sync.py) and [interruption/conflict tests](scripts/test_review_sync.py). The [management-repository protocol](scripts/review_sync_management.py) and [same-repository tests](scripts/test_review_sync_management.py) cover its journal-only commit. For explicitly authorized Git publication use the [conditional publisher](scripts/review_publish.py) and [lease/unknown tests](scripts/test_review_publish.py). Read the review-comments reference before using these; host/UI integration remains pending.

The [native raw-document transport](scripts/review_native.py) and [loopback HTTP tests](scripts/test_review_native.py) preserve actual strong ETag conditions. It is a transport primitive; use the journaled publisher below for durable publication.

For journaled native publication, use the [native F03 publisher](scripts/review_native_publish.py) and [durability tests](scripts/test_review_native_publish.py). Supply the actual host endpoint independently on each call; never reconstruct credentials or authority from the journal. Host/UI wiring and decision/quality integration remain required.

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

Recovery shares one two-second computation budget across loading, complete validation (including review-reference checks), and focused projection. Exhaustion returns RESOURCE_LIMIT with no partial context or next action. Only the concrete Git subprocess call is excluded as external execution/I/O; parsing and checks before/after it are counted. This is a cooperative computation bound, not a two-second wall-clock deadline for Git. Reusing exhausted loaded documents cannot reset the budget.

For an interrupted review with declared source materials, use the optional recovery branch in [checkpoints](references/checkpoints.md). The [review reference helper](scripts/review_resume.py) and [real Git/process tests](scripts/test_review_resume.py) restore attempt/target-bound references; they do not assess quality or grant acceptance.

For a new review or recheck handoff, read [review](references/review.md), prepare the [packet template](templates/REVIEW-PACKET.md), and validate it with [review_packet.py](scripts/review_packet.py). Material completeness is not independent execution: actual host authorization, verified fresh context and enforced read-only access are required; this helper never dispatches a reviewer. Run the [packet regressions](scripts/test_review_packet.py) when changing this boundary.

For complete reports, read [report semantics](references/review-report.md), use the [report template](templates/REVIEW-REPORT.md), and run the pure [report calculator](scripts/review_report.py). It keeps unknown/not-run checks and historical blockers visible; schema/count validity is not source verification or quality approval. Validate changes with [report tests](scripts/test_review_report.py) and the bundled [synthetic fixtures](scripts/fixtures/review-report.json).

Use the [dependency helper](scripts/task_dependencies.py) only for unstarted PENDING tasks, following [review](references/review.md). Preview first; authorized writes record intent before per-file replacement and use F03 reconciliation after interruption. Run [planner tests](scripts/test_task_dependencies.py) and [real-file writer tests](scripts/test_dependency_write.py). Dependency READY is not quality approval.

Run the [real-Git rework-chain fixtures](scripts/test_rework_chain.py) for report delivery, versioned repair/retest/recheck, active-attempt protection and abrupt-process recovery. Their synthetic reviewer claims do not constitute independent review or human acceptance.

The [local document loader](scripts/context_loader.py) reads complete raw task and declared-gist sources before validation. `task_context.py` separates full validation with the host-selected local Git probe from focused projection; a comparison loader cannot replace local repository facts. When changing this boundary, run the [loader and actual-Git regressions](scripts/test_context_loader.py) as well as the existing context tests. Structured envelope output uses `lfd-context-v1`; default CLI output remains compatible. This interface does not supply review-breakpoint recovery by itself.

For next-action selection after recovery, read [references/selection.md](references/selection.md). The [pure core/CLI](scripts/task_next.py) uses a [strict-reader adapter](scripts/selection_context.py); validate with [core tests](scripts/test_task_next.py) and [real Git/CLI tests](scripts/test_selection_context.py). Selection never grants execution authority or changes task state.

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

## Validate this Skill

After changing initialization instructions or templates, run the real-Git [bootstrap regression](scripts/test_bootstrap.py).

After changing task orchestration, recovery, or checkpoint behavior, run the [context regression tests](scripts/test_task_context.py), [task creation tests](scripts/test_task_create.py), [checkpoint tests](scripts/test_task_checkpoint.py), and deterministic audit:

```text
python scripts/test_task_context.py
python scripts/test_task_create.py
python scripts/test_task_checkpoint.py
python <skill-quality-reviewer>/scripts/skill-audit.py <skill-root> --format json
```
