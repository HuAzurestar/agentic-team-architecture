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

For review/v1, reference the design's short `Review scope` source/version; an optional identical `- Review scope:` snapshot and ledger path belong in the task detail. Keep legacy fields, and distinguish mandatory blockers from optional scored findings. P0 requires closure; retained P1/P2/P3 can deduct score without automatically creating REWORK. This does not waive required checks or human acceptance.

Use blind recovery before loading existing findings. Declare original input gists and the per-attempt result/snapshot in `Gists`; original packets carry `- Evidence type: original`. After saving the blind report with `Review phase`, `Review task`, `Target SHA`, `Review scope`, and the blind view's exact `Review refs` JSON lines, use reconcile with its declared path. Each repository's current candidate/source refs must match; unbound or stale reports need a new blind attempt, not retroactive editing. For blocked/waiting actions, original packets separate `Action boundary` and `Release condition` from historical conclusions; a missing clean boundary is explicitly incomplete, not permission to resume. The root `REVIEW.md` ledger is a shared state index; it does not replace `Result gist` or immutable attempt reports. A report can complete with findings; score and acceptance remain separate. Full contract/ref validations are unchanged.

## REWORK

Required fields: `Source findings`, `Target SHA`, `Output SHA`, and `Result gist`. The task depends on the review that found the issue. Retesting is a separate dependent `TEST-*` task so the tested SHA remains explicit.

## ACCEPT

Required fields for newly created tasks: `Target SHA`, `Acceptance scope`, `Decision`, `Decided by`, and `Acceptance brief`. The brief is a declared `gists/` path created from `templates/ACCEPTANCE.md`; legacy completed tasks without this field remain readable. The Agent proposes scope, prepares and proactively shows the plain-language brief, but only the developer supplies the final decision. Keep `Decision` as `WAITING` through WIP. In RECORDING, persist the developer's `CONFIRMED`, `REJECTED`, or `REWORK` decision before completing refs.

## GATE

Required fields: `From phase`, `To phase`, `Required tasks`, and `Decision ref`. The required task list must match the gate's direct dependencies. `Decision ref` is the project-management commit that records the transition; before recording, use `-`.
