# GATE tasks

A GATE is a task type. Its caller supplies subject, policy, criteria, evidence requirements, deciding authority and consequences. This skill does not define company phases, a release sequence or who must act.

Use the common task YAML and body. The gate mapping holds subject, policy ref, criteria, evaluation, authorization, decision ref and allowed actions. Durable evidence belongs in result.evidence and the task report. References identify actual revisions.

An unconfigured template can remain evaluation=unknown with no subject/policy and no allowed actions. Before reporting satisfied or unsatisfied, identify the subject, policy and criteria. Missing or unsupported checks remain unresolved, not passes.

Evaluation and authorization are separate. A satisfied check can still await approval; granted authorization references the relevant DECISION task or external versioned decision. not_required is an assertion supported by the supplied policy, not a way around an unknown authorization boundary. Positive checks do not execute actions.

## Communication when the user's decision is required

GATE is the only generic record type that may make user communication a blocking prerequisite. The external gate policy must explicitly require that decision; not every GATE becomes human approval, and existing delegated authority remains valid.

When required, the maintainer must prepare and submit an explicit request identifying subject/version, decision question, criteria/evidence, remaining risks, proposed consequences and designated decider. Retain the request and its source/time in this task or a linked durable record. Channels, tools, phrasing and proactive follow-up belong to the external orchestrator/host; this skill binds no UI or messaging tool.

Without an actual response, keep authorization pending and record who is awaited, follow-up ownership and continuation conditions. Do not take actions dependent on that authorization. Successful script synchronization, positive technical checks, silence or agent inference do not substitute for the user's answer.

On response, retain the actual decider, original answer/source, time, subject version and allowed scope; reference the relevant DECISION or external versioned decision. Natural language can be valid, but ambiguous, stale or other-candidate answers do not establish current authorization. Reassess or request again under the policy when the subject changes. Ordinary clarification, progress conversation and nonblocking acceptance material do not become a skill-defined communication workflow.

## Check the actual candidate and prerequisites

Before concluding, identify the current subject and the prerequisites required by the supplied policy. Inspect the relevant dependency results, development outputs, tested/reviewed/accepted candidate points and any applicable integration or PR endpoints. A task being DONE does not prove its result passed or its evidence covers this subject.

Compare the versions, not just task IDs or completion counts. If evidence targets a different candidate, determine and record its applicability under the policy; do not silently claim that the current candidate was checked. Missing checks, unexplained mismatches and unhandled required findings remain unresolved. Deferred work needs an explicit disposition, not disappearance.

## Persist the conclusion without executing it

Record the subject/policy versions, evidence, evaluated criteria, unresolved items, actual decision and permitted consequences in the task. If the policy permits a Feature transition, have the assigned maintainer update the affected STATUS overview and next action, without duplicating the task report.

A failed evaluation can complete a gate-evaluation assignment, but cannot be represented as a satisfied gate or a successful Feature transition. Neither task DONE nor an agent summary proves release readiness. A recorded allowed action is not evidence that it was executed; track any authorized execution and its receipt separately.

The helper checks structural consistency: satisfied evaluations include durable evidence; allowed actions require satisfied evaluation plus granted/not_required authorization. It does not evaluate conditions, verify permissions or contact decision makers. Keep all necessary results and basis in durable task/design records rather than transient attachments.

### Workflow notification IO

Use [notification hooks](notification-hooks.md) for a real evaluation or authorization request, with the exact gate subject/version and designated decider. Receiver subscription and tool acceptance do not alter pending authorization or allowed actions.
