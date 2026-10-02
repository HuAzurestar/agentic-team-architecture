# Next-action selection

Read this when choosing the next task after strict recovery. A suggestion is
neither execution permission nor a second task-state writer.

## Implementation boundary

The pure API in [task_next.py](../scripts/task_next.py) is implemented. The
strict-reader projection, CLI, read-set binding and selector.result event adapter
are not yet integrated. Do not construct a "validated" JSON file or replace
task_context with this core. Continue strict recovery and the existing writer.

## Inputs and trust

Call select_next(validated_context, authorization, observed_gate_evidence).
Frozen dataclasses hold normalized inputs; nested mappings must also be treated
as read-only. The function makes no filesystem, Git, network or writer calls.

ValidatedContext contains the complete TASKS row order, states, dependencies,
types, quality contracts, release conditions, current task and Gate. It must
come from full validation, not a focused excerpt. source_ref must bind the full
plan/read-set and observed repository refs; both other inputs require that exact
binding. An old binding returns STALE_INPUT.

Authorization grants come from actual host/current-user authority, never ordinary
Markdown saying approved. Each grant names the operation, capabilities and
authority_ref. The generic Development type cannot distinguish work from
merge/publish; the host must classify the actual authorized operation explicitly.
Every action needs execute; merge/publish also need their separate capability.
accept needs request-acceptance, permission to present a decision, never invent it.
Outside the Gate closure additionally needs outside_scope=true.

Observed GateEvidence supplies a verdict (ready, wait-human, wait-external or
repair-plan) and bounded evidence_refs. ready asserts actual checks of applicable
quality, target scope, budget and external contracts. Do not synthesize it from
READY, DONE, author summaries or missing evidence. A quality assessor (including
F04 when available) supplies observations; this core does not implement that
assessor or authenticate remote/human evidence. Transitive findings and complete
multi-repository target applicability remain that assessor's responsibility.

BLOCKED release needs the exact release_condition and release_satisfied=true with
evidence. merge/publish and a Gate whose To phase is DONE need an existing DONE
Acceptance task in the Gate closure, CONFIRMED and the same full target SHA.
Human-decision provenance must already be verified. Direct failed/incomplete
tests, blocking reviews, rejected acceptance and missing Gate decisions override
a positive summary. Rework/retest/rereview may consume failures, not deliver them.

## Selection and handoff

The entire graph, even outside the closure, is checked before selecting. Unknown
IDs, duplicate IDs/edges, cycles and missing current task/Gate fail closed.
Iterative queues enforce O(V+E) traversal, 10,000 tasks, 30,000 edges and two
seconds. Overruns reject the whole selection, not merely the uninspected tail.

Unfinished current WIP/RECORDING work takes precedence; BLOCKED needs release
proof. Another assigned task inconsistent with the current pointer requires plan
repair. Otherwise consider structurally ready PENDING tasks, explicit
rework/retest/rereview first, then original TASKS row order. One candidate's
diagnostic need not prevent another legal candidate. No candidates means a
human/external/plan/scope diagnostic, not automatic feature completion.

NextAction contains action, task_id, reason_code, evidence_refs and
required_authority. SCOPE_EXHAUSTED only describes this graph closure, never
feature acceptance. Before acting, the coordinator must revalidate the same
read-set, task row and repository refs. If changed, discard and recompute. Then
record owner/start refs and invoke the existing authorized task_state writer.
Selection cannot assign, release BLOCKED, commit, merge or push itself.

## Regression

Run [test_task_next.py](../scripts/test_task_next.py):

~~~text
python scripts/test_task_next.py
~~~

Behavioral cases cover deterministic repetition, authority and scope, exact
release proof, rejected acceptance, failed tests, old/missing targets, malformed
graphs, deadlines, a 10,000-node chain and no-I/O/input preservation. They are
author tests, not independent review or human acceptance.

