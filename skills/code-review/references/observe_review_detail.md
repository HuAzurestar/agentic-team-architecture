# Weak review: observability

Ask whether a real failure report could be localized with available evidence.

## Content points

- Are key success, failure and partial-success stages distinguishable?
- Do logs carry useful request/job/entity/correlation context via the project's logger?
- Can retry and recovery be connected to the original operation and distinguished from first execution?
- Are exceptions logged once at the useful boundary with appropriate stack/context and levels?
- Are failures swallowed, printed without context or repeated so heavily that the cause is hidden?
- Are secrets, credentials, private payloads and restricted data absent from logs and metrics?
- Can a long flow's current/stuck stage and relevant business events be identified without logging unnecessary content?

## Scan and challenge

Trace logging around the same IO/state transitions checked in recovery. Inspect actual output from an isolated failure and a retry. From a user report of “failed,” attempt to identify the operation and failure stage. Search print/logger/error/warn and sensitive field names across sibling entry points. Propose metrics only for an actual diagnostic need and project convention, not to satisfy a generic telemetry quota.
