# Weak review: failure and recovery

Construct a short failure table: failure point, current behavior, recovery, risk and evidence. Do not turn speculative concerns into findings without a trigger.

## Content points

- What happens when each database, file, network or external service operation fails?
- Is a half-written file or interrupted transaction safe and detectable?
- If remote success is followed by local failure, or the reverse, is partial success explicit and recoverable?
- Can a timeout distinguish failure from unknown remote success before retrying?
- Are retries bounded and safe, with side effects deduplicated or reconciled?
- Can restart/resume recover the necessary state without re-executing completed work?
- Do users retain sufficient input/state and receive a concrete recovery action?
- Are exceptions swallowed, overly broad, mistranslated or stripped of useful context?
- Are compensation, cleanup and failure during recovery itself handled consistently across entry points?

## Scan and challenge

Trace IO boundaries, commit/rollback, retry/resume/restart/status and equivalent state transitions. Inject a failure between meaningful steps, then retry or restart. Compare observable durable state and side effects with the promised outcome. Inspect preview/submit/restore and batch/single paths together. Use supported fault injection or isolated fixtures; do not manufacture a destructive production failure to test the hypothesis.
