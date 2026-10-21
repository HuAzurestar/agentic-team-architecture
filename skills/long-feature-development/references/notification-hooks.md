# Workflow-aware notification hooks

workflow_events.py implements an offline persistent event/attempt/acknowledgement/reply ledger. It sends no network traffic and starts no worker; actual runtime tools remain responsible for dispatch. Runtime adapter state is defined in [runtime persistence](runtime-persistence.md). Confirm the event mapping and receiver/adapter contract before implementation.

## Offline helper IO

Use `workflow_events.py --state-root <absolute-state-directory> --runtime-id <runtime-id>` followed by `record`, `attempt`, `ack`, or `reply --input <json-file>`. Replies also require `--current-object-revision <actual-workflow-revision>`. Use `inspect [--event-id <id>]` to resume from persisted state. The notification profile must be configured first; its delivery state directory holds the runtime-bound ledger.

- `record`: event id/type, phase, purpose, priority, feature, task, object revision, occurred at, actor and correlation id are strings; decision required is boolean; payload is JSON data. Decision requests also name decider, requested scope and allowed consequences. Event identity with identical data is idempotent; conflicting data is rejected.
- `attempt`: event id, attempt id, occurred at, adapter tool reference and route. Adapter and route must match the explicit current profile. Save this before the host calls a real tool. The helper does not perform that call.
- `ack`: event id, attempt id, occurred at and status (`accepted`, `failed`, `unknown`), plus optional receipt. Preserve immutable acknowledgements; retries use distinct attempts and retain the original event id.
- `reply`: event id, reply id, correlation id, object revision, declared decider, original wording, source and occurred at. Structural matching against both the original request and the explicit current workflow revision rejects stale replies. Identity authentication is not performed and workflow authorization is not evaluated; the host verifies identity and an authorized role records actual decisions in PM.

The helper does not filter by receiver subscriptions, invoke adapters, modify formal approvals or interpret arbitrary decision payload as permission. A failed/unknown acknowledgement remains durable after restart. No automatic retry or background queue exists.

## Event IO

Input: a real workflow occurrence plus Feature/task, exact object revision, the applicable policy/mandate reference supplied by the caller, actual actor, timestamp, question or outcome, evidence/known limits and correlation context. Output: a durable event and an honest dispatch result (`not_attempted`, `accepted`, `failed` or `unknown`) with available acknowledgement. Emit factual occurrences even when presentation is terse; the user's receiver chooses subscriptions, prioritization, display and muting. Acknowledge missing information explicitly.

An event envelope contains `event id`, `event type`, `phase`, `purpose`, `priority`, Feature/task/object revision, occurrence time/actor, `correlation id`, decision-required/decider, requested scope/allowed consequences and payload/evidence references. Retain event identity on a retry; distinguish attempts. Stable identity is scoped to the actual occurrence and revision, not only its title.

Suggested event families (adapter bindings remain data):

| Event | Meaning |
| --- | --- |
| intent.recorded / intake.routed | Source received, associated and routed without inventing approval |
| design.confirmation.requested | Exact REQ/SOL revisions need a decision |
| decision.recorded | Human or valid delegated decision, with actual decider and mandate |
| gate.evaluated / gate.authorization.requested | Evaluated conditions or a pending authorization request |
| task.planned | Intention: what will be done, why, scope and expected result; not proof it started |
| task.started / task.blocked / task.result.recorded | Actual work progression, blockers and results |
| review.finding.recorded / test.result.recorded | Version-bound findings and checks |
| feedback.recorded / acceptance.requested | Feedback or a request to accept a specific candidate |
| release.action.planned / release.action.result | Authorized merge/deployment, document update, external notice or announcement activity and actual result |

`purpose` separates information, intended action and requested decision. `priority` expresses importance; neither field grants permission or determines blocking. A workflow occurrence may reference several related records; deduplicate the occurrence/recipient without silently dropping distinct REQ/SOL/GATE decisions. Proposed labels and mappings remain reviewable, not a mandatory company state machine.

## Dispatch and response

1. The workflow records the real occurrence/subject in PM and forms an event. The runtime adapter persists its dispatch state and uses configured tools/routes; the receiver decides how it is presented. A planned-work notice precedes the described action and must state any pending authorization.
2. Retain correlation, attempts and actual acknowledgements. A tool success/HTTP acceptance does not prove human receipt or approval. Failure/unknown returns a concrete limitation, retains pending state and permits only configured retry/recovery. No silent drop, unbounded retry, unapproved fallback channel or background process is implied.
3. Response processing verifies the actual decider, request and object revision, records original wording/source/time, and returns a versioned decision to the orchestrator. Ambiguous/stale replies stay unresolved. A change of receiver subscription must not change workflow authorization.

Only applicable policy makes a decision block dependent actions. A required GATE/REQ/SOL decision remains pending without a valid answer even if notifications are muted. Informational delivery failure does not automatically block unrelated authorized work; report it according to configured handling. Notification hooks never auto-merge, deploy or approve.

## Suggested acceptance experiments

Use a fixture adapter without real external sending: migrate runtime A/B with unchanged instruction; replay one event without duplicate decision execution; mute a display subscription without granting approval; fail dispatch while retaining the event; reject a reply for the previous object revision. Real network callbacks, delivery guarantees and retry scheduling need separately agreed implementation and tests.

## Policy and integration boundary

The helper validates the documented base fields and request/reply correlation, preserves extra JSON data, and does not verify a mandate or receipt's authenticity. The workflow caller supplies and checks applicable policy/mandate/evidence references. Omitted policy metadata is not interpreted as permission. The helpers do not install automatic hooks into the index generator, platform events or state transitions; the authorized workflow calls them at its actual transition points.
