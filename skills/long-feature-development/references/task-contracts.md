# Test, review and rework records

Read when assigning or reporting TEST, REVIEW or REWORK work. These are task-specific fields and body sections under tasks/, not additional directories or state machines. For common lifecycle changes, read [transitions.md](transitions.md).

Use the fields needed by the actual assignment; the shared YAML format permits specialized metadata. The structural checker does not enforce these report semantics or verify that work ran.

## DEV and developer testing

DEV includes implementation-related testing such as TDD, unit tests, local integration and debugging in its own development context. DEV-REFINE, DEV-BUG-FIX and DEV-REFACTOR remain development tasks, optionally distinguished by `development kind: refine|bug-fix|refactor`; these labels do not create Git branches. Independent TEST targets business, regression and unified/system validation of a frozen candidate. Reusing a test tool does not equate these responsibilities, and developer self-checks do not substitute for an independent TEST result.

## TEST

Identify the scope, exact candidate (Project-qualified SHA for code or a versioned non-code artifact), environment and limitations, planned checks and actual checks. Separate executed, passed, failed, skipped and unknown results. Counts alone do not establish coverage; retain meaningful check names and a substantive verification summary.

Record commands or procedures, failure causes and sufficient reproduction information in the task's durable report. Keep secrets out. Raw logs may be disposable gists annotations but are not the only evidence. Do not report skipped, unavailable or unexecuted checks as passes.

A changed candidate needs a new attempt or task with its own target; the old report stays bound to the old point. Use an existing supported test setup; introducing infrastructure or committing mock data requires an in-scope project need and a safe accepted location, not a universal Docker rule.

## REVIEW

Identify target points/versions, review scope, findings and their effect, blocking versus deferred items, and the review conclusion. Record deferred-item disposition and the responsible follow-up. Comments need enough context to locate and understand the issue; keep the authoritative findings in the task, not only in raw attachments.

Do not rewrite a completed development result to make a finding disappear. Track follow-up through a linked REWORK task or an explicitly reopened attempt as selected by the external workflow. A review of one SHA is not a review of a later SHA.

## REWORK and verification

Preserve source findings and their target, the requested change, the new output points and remaining findings. Link the originating review/feedback and dependent work. The revised candidate needs the applicable retest or rereview; record its actual scope and evidence separately, using a new task or a distinct retained attempt.

Completion of the rework task alone does not prove that retesting passed, acceptance was granted or a GATE is satisfied.

For user-facing acceptance, read [acceptance.md](acceptance.md). For policy checks and later permission, read [gates.md](gates.md).

## FEEDBACK from TEST and REVIEW

Preserve reported findings as FEEDBACK, not automatically as INT. Use the existing feedback task record and lifecycle; identify the reporting task, exact candidate, observations, expected/actual behavior, environment and evidence. Handling may derive advice/bug points when supported by the loaded protocol, decline/defer an item with reasons, or address an environment blocker without DEV. A genuine new external intent remains INT. Where the host uses the ADVICE/BUG path, accepted items feed an explicit SOL and the required authorization before DEV refinement/bug-fix/refactoring; unchanged requirements can be referenced without artificial revisions. A completed feedback-handling task records disposition and follow-up, not proof that linked defects are fixed.
