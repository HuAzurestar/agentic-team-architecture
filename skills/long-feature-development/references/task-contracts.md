# Quality task contracts

Read only for a quality, acceptance, or gate task. Every task still uses the universal lifecycle in `transitions.md`; these are additional minimum fields in a `## Type contract` table inside `tasks/<task-id>.md`.

## TEST

Required fields: `Target SHA`, `Environment`, `Planned checks`, `Executed`, `Passed`, `Failed`, `Skipped`, `Unknown`, and `Result gist`.

- Bind the report to one literal tested SHA. A new implementation SHA requires a new test attempt or task.
- Counts and short check names belong in the contract; commands, logs, screenshots, failure causes, and coverage detail belong in `gists/TEST-*.md`.
- `Executed`, `Passed`, `Failed`, `Skipped`, and `Unknown` are separate. Never turn partial execution into “all passed.”
- Prefer an existing supported Docker test environment. Do not introduce Docker only to satisfy this rule.
- Commit deterministic mock data only when the project already has an accepted location and the data contains no secrets; otherwise keep it in the test gist or ephemeral test setup.

## REVIEW

Required fields: `Target SHA`, `Blocking findings`, `Deferred findings`, and `Result gist`. Put individual comments and long reasoning in `gists/REVIEW-*.md`. A blocking finding creates a dependent `REWORK-*` task; do not mutate the completed development task.

## REWORK

Required fields: `Source findings`, `Target SHA`, `Output SHA`, and `Result gist`. The task depends on the review that found the issue. Retesting is a separate dependent `TEST-*` task so the tested SHA remains explicit.

## ACCEPT

Required fields: `Target SHA`, `Acceptance scope`, `Decision`, and `Decided by`. The Agent may propose scope and summarize evidence, but only the developer supplies the final decision. Before that response, keep `Decision` as `WAITING` and the feature condition as `WAITING_HUMAN`.

## GATE

Required fields: `From phase`, `To phase`, `Required tasks`, and `Decision ref`. The required task list must match the gate's direct dependencies. `Decision ref` is the project-management commit that records the transition; before recording, use `-`.
