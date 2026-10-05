# Quality task contracts

Read only for a quality, acceptance, or gate task. Every task still uses the universal lifecycle in `transitions.md`; these are additional minimum fields in a `## Type contract` table inside `tasks/<task-id>.md`.

## TEST

Required fields: `Target SHA`, `Environment`, `Planned checks`, `Executed`, `Passed`, `Failed`, `Skipped`, `Unknown`, and `Result gist`.

- Bind the report to its literal actually tested SHA, not the current candidate or bookkeeping HEAD. Semantic changes affecting the tested functionality/dependency closure require a new test attempt or task. An unchanged tree or freshly host-verified unchanged complete input closure may reuse the original result in a current quality attempt; never retarget the old task/report. See [quality applicability](quality.md).
- Counts and short check names belong in the contract; commands, logs, screenshots, failure causes, and coverage detail belong in `gists/TEST-*.md`.
- `Executed`, `Passed`, `Failed`, `Skipped`, and `Unknown` are separate. Never turn partial execution into “all passed.”
- Prefer an existing supported Docker test environment. Do not introduce Docker only to satisfy this rule.
- Commit deterministic mock data only when the project already has an accepted location and the data contains no secrets; otherwise keep it in the test gist or ephemeral test setup.

## REVIEW

Required fields: `Target SHA`, `Blocking findings`, `Deferred findings`, and `Result gist`. Put individual comments and long reasoning in `gists/REVIEW-*.md`. A blocking finding creates a dependent `REWORK-*` task; do not mutate the completed development task.

## REWORK

Required fields: `Source findings`, `Target SHA`, `Output SHA`, and `Result gist`. The task depends on the review that found the issue. Retesting is a separate dependent `TEST-*` task so the tested SHA remains explicit.

## ACCEPT

Required fields for newly created tasks: `Target SHA`, `Acceptance scope`, `Decision`, `Decided by`, and `Acceptance brief`. The brief is a declared `gists/` path created from `templates/ACCEPTANCE.md`; legacy completed tasks without this field remain readable. The Agent proposes scope, prepares and proactively shows the plain-language brief, but only the developer supplies the final decision. Keep `Decision` as `WAITING` through WIP. In RECORDING, persist the developer's `CONFIRMED`, `REJECTED`, or `REWORK` decision before completing refs.

## GATE

Required fields: `From phase`, `To phase`, `Required tasks`, and `Decision ref`. The required task list must match the gate's direct dependencies. `Decision ref` is the project-management commit that records the transition; before recording, use `-`.

For an unstarted PENDING Gate, change dependencies only through the controlled
dependency helper described in [review](review.md); it synchronizes Required
tasks and records partial effects. An active acceptance/Gate cannot be rewired
or hidden by a new task. REVIEW DONE means report delivery, not absence of
blockers; actual findings create a new REWORK → TEST → REVIEW chain.
