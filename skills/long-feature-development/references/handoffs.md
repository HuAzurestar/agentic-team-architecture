# Task records and handoff

Read when receiving or returning work.

The assignment supplies scope, versioned inputs, owner, expected result, completion conditions and the return interface. Record this in tasks/<id>.md using YAML state and a reviewable Markdown body. REVIEW, DEVELOPMENT, DOCS, DESIGN, TEST, DECISION, FEEDBACK, ACCEPTANCE and GATE are task types, not separate modules.

For work decomposition read [task-planning.md](task-planning.md); for assignment, blocking, completion and reopening read [transitions.md](transitions.md). These tasks share one lifecycle; the caller controls scheduling and transition authority.

The task result separates execution from outcome and evidence. A completed test can fail; a completed decision can reject the proposal. Record checks actually executed, their limits, candidate/input versions and the substantive verification summary directly in a durable task report. External evidence must be version-identifiable.

For test/review/rework report content read [task-contracts.md](task-contracts.md); for an acceptance decision read [acceptance.md](acceptance.md). Before ending or transferring unfinished work, apply [checkpoints.md](checkpoints.md) using the authorized persistence method.

Put handoff requests and receipts in task sections or YAML. Identify recipient, request, input versions, expected answer, return location and follow-up owner. Receipt, acceptance, execution and effect verification establish different facts. A ticket number does not prove a requested action happened.

On return, state what actually happened, the output versions, checks and limits, outstanding items and who follows up. If no receipt arrives or a request is rejected, preserve its unresolved status; do not infer execution or retry/escalation permission. The orchestrator or supplied workflow owns routing and subsequent action.

Return unresolved work through the supplied state interface. Keep essential reasoning, verification and decision comments in design/tasks; official records cannot cite disposable drafts, exports or raw attachments.
