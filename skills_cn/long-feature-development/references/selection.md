# Next-action selection

Read this when choosing the next task after strict recovery. A suggestion is
neither execution permission nor a second task-state writer.

## Implementation boundary

The pure API is in [task_next.py](../scripts/task_next.py). Its read-only CLI uses
[selection_context.py](../scripts/selection_context.py) to run the complete
task_context validator and project its validated records, without changing the
old reader's default output. Arbitrary JSON cannot replace validated context.
Task quality types follow the strict reader's ID-prefix contract rules; changing
an ACCEPT row's display type cannot remove its acceptance checks.

The adapter hashes raw control documents and the tasks/gists trees before and
after validation, together with real local repository identity, HEAD, branch,
refs, config and scoped worktree status. Added/removed sources and refs invalidate
the binding. Symlinks/junctions are rejected; inputs are bounded to 11,004 files
and 64 MiB, with a bounded directory traversal. These optimistic observations are
not a cross-repository transaction: use the single coordinator, and revalidate
immediately before any authorized writer. Full loader separation is independent
work, not a claim made by this consistency envelope.

Git observations disable optional locks to avoid index refresh writes. The
selector's two-second budget covers graph selection, not full filesystem/Git
recovery. Adapter snapshot Git calls each have a ten-second timeout. Errors emit
bounded codes, not raw repository config, document text or command diagnostics.

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

## Read-only command

First run without host inputs. The output includes source_ref and a NextAction
(normally wait-human/AUTHORITY_MISSING); no authority is inferred from documents.

~~~text
python scripts/task_next.py /path/to/feature --repo app=/path/to/app --repo pm=/path/to/pm
~~~

For selection with authority, the host explicitly invokes the same command with
--host-input and --authority-source-ref naming the actual current instruction.
It supplies a UTF-8 JSON envelope on stdin, limited to 1 MiB. No feature-local
permission file is loaded. The reference is traceability, not authentication of
a human acceptance; the host remains responsible for actual authority/provenance.
Unknown fields/task IDs/capabilities, duplicate keys and wrong boolean types fail.

~~~json
{
  "source_ref": "selection-sha256:copy-the-current-returned-binding",
  "grants": {
    "DEV-02": {"operation": "work", "capabilities": ["execute"]}
  },
  "evidence": {
    "DEV-02": {"verdict": "ready", "evidence_refs": ["actual-observation-reference"]}
  }
}
~~~

Only supply ready after checking the facts described above. Optional grant field
outside_scope defaults false. Optional evidence fields are target_sha,
acceptance_task, release_condition and release_satisfied (default false). Omitted
evidence does not pass. Each invocation re-runs real recovery and compares the
envelope's binding, so a stale saved envelope cannot select on changed inputs.

Stdout contains only source_ref and next_action; stderr contains one
selector.result JSON event with action, reason_code, candidate_count and
elapsed_ms. The count describes structurally eligible candidates, not permissions.
Exit 0 means a valid selection/diagnostic, including wait-human/wait-external or
stop-scope; exit 2 means repair-plan, invalid input or failed recovery. There is
no apply mode. A coordinator must inspect action, not just the process exit code.

## Regression

Run [test_task_next.py](../scripts/test_task_next.py) and the real Git/CLI tests
in [test_selection_context.py](../scripts/test_selection_context.py):

~~~text
python scripts/test_task_next.py
python scripts/test_selection_context.py
~~~

Behavioral cases cover deterministic repetition, authority and scope, exact
release proof, rejected acceptance, failed tests, old/missing targets, malformed
graphs, deadlines, a 10,000-node chain and no-I/O/input preservation. They are
author tests, not independent review or human acceptance. Adapter tests compare
all fixture worktree/Git bytes (including indexes, refs and reflogs), preserve old
reader output, verify stale/mid-read changes, rejected acceptance and host waits,
and ensure document bodies are absent from command output/events.
