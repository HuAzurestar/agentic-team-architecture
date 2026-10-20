# Feature continuity and feedback

Resolve the Feature key and externally supplied management root. STATUS is the integrated management entry for repository, Feature and development state, including repository bindings and synchronization/integration status, progress, current focus, state/authority access, blockers and next actions, not just resumption. DESIGN, TASKS and VERBAL retain their own indexes and content; STATUS summarizes state and links needed details without copying those modules. On resumption, read the selected YAML-frontmatter details and necessary versioned inputs.

A Project is a Repository's local/remote synchronization and basic management rule record; a Feature can span several Projects. Resolve local machine locations through supplied configuration. Resuming a Feature does not require its management folder to be a Git repository.

## Start or resume

1. Use the explicitly supplied external Feature key, location mapping, assignment and state/authority interfaces; do not allocate a key. Return missing identity to the external orchestrator rather than guessing ownership with a temporary directory. Read STATUS for overall context, then selected details and necessary versioned inputs, not every repository document or disposable attachment.
2. Check input decisions, candidate identity, completion conditions, current owner and prior resume action. Report missing/conflicting facts rather than inventing approval or silently migrating an old record layout.
3. For implementation work, read [repository-context.md](repository-context.md) and compare relevant actual refs and dirty work with the recorded points. Interrupted or partial writes use [checkpoints.md](checkpoints.md) before affected mutations.
4. Follow [SKILL.md](../SKILL.md): run the read-only checker before operations, then synchronize indexes and check again after content/state changes. For first initialization, use the entrypoint exception to have the agent prepare records first. Checks do not prove business readiness, Git objects or authority; failure is not successful recovery. Report scope and retain usable read-only context.

Preserve partial context while reporting missing or conflicting facts. The state maintainer owns persistence, synchronization and write coordination. The checker is read-only; index updates use the [generator](generated-indexes.md), which writes derived regions only, not detail state.

If no records exist yet, use [initialization](initialization.md) instead of treating an empty directory as resumable. After recovery, execute the selected task under supplied orchestration or the [default task loop](task-workflow.md); resumption alone does not assign new scope or change task state.

## Feedback and correction

Record feedback in a FEEDBACK task or another task's feedback section. Preserve the observation, affected revision, requested change, handling decision and resolution. Feedback may lead to clarification, revised INT/REQ/SOL or development rework; routing is external.

Retain the original decision/report and link the correction through durable records. Assess which downstream evidence or decisions may be stale. Do not silently replace historical approvals or treat earlier evidence as a check on a new candidate.

VERBAL/gists is not recovery context or evidence; a dedicated task gists field is only an optional reference annotation. A Feature must remain understandable and valid after all disposable attachments and their index are removed. Retain necessary analysis conclusions and reports in design/tasks before making decisions.

## End or hand off

Leave the actual task state, candidate/output points, saved recovery point and unsaved scope, checks and limitations, unresolved decisions, next action and follow-up owner discoverable in durable records. Use the authorized persistence method in [checkpoints.md](checkpoints.md); transfer requests/receipts follow [handoffs.md](handoffs.md).

Have the maintainer reconcile the changed details/previews and refresh only the affected overall STATUS context. State what was verified and what remains unavailable; do not describe an unvalidated, unsaved or unresolved result as complete.
