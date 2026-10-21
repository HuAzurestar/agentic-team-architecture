# Standard capability IO

Design proposal, draft-1. Skill capabilities define how scoped input becomes a verifiable result; agent instructions choose responsibility, delegation and decision authority. Runtime bindings supply physical access. No role's capability implies permission.

Common input: request/source identity, Feature/task association, exact inputs/revisions, scope/constraints, applicable authority, runtime profile and return contract. Common output: actual operations, versioned artifacts, checks/limits, outcome, pending items and persisted-record status. Keep facts, inference, recommendation and actual decisions distinguishable.

| Capability | Input -> output | Reference |
| --- | --- | --- |
| PM bootstrap | Explicit runtime setup -> verified profile or concrete missing input | [runtime persistence](runtime-persistence.md) |
| Intake association/routing | Source and known Feature context -> retained INT, duplicate/association result, clarifications and target work | [design](decisions.md) |
| Requirement/solution analysis | INT/context/constraints -> versioned REQ/SOL proposals and options | [design](decisions.md) |
| Human/delegated decision | Exact proposal and valid mandate/actual reply -> attributed scoped decision and downstream effect | [confirmation](confirmation.md) |
| Planning/assignment | Approved scope and readiness -> tasks, dependencies and explicit handoff | [planning](task-planning.md), [handoff](handoffs.md) |
| Execution | Assigned candidate/scope/authority -> actual artifacts and bounded checks | [task workflow](task-workflow.md) |
| Review/test/rework | Exact target/criteria/findings -> report, revised target and applicable revalidation | [quality](task-contracts.md) |
| Acceptance/GATE | Candidate/criteria/policy/evidence -> actual answer, evaluation and authorization kept separate | [acceptance](acceptance.md), [gates](gates.md) |
| Notification | Real workflow occurrence -> durable event/dispatch acknowledgement or correlated reply | [hooks](notification-hooks.md) |
| Release work | Explicit action, audience, candidate and authority -> merge/deployment, docs, announcement or external handoff result | [handoff](handoffs.md) |
| Recovery | Actual records/versions and unfinished attempt -> reconciled next step | [continuity](continuity.md) |

Design, execution and release are useful work groupings, not mandatory stages. Release can include documentation, stakeholder messages and announcements; instantiate only in-scope work. Role missingness is an explicit decision point. The company supplies who may approve, START round policy and final-completion authority.
