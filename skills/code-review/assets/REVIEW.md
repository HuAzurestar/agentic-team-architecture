# Review ledger

Read this ledger only after saving the current blind attempt. Fill the current metadata and keep old attempt references and status transitions.

This is the evolving index, not raw input or an immutable report. Use the [input template](REVIEW_INPUT.md) before scanning and the [report template](REVIEW_REPORT.md) for each attempt. Never preload this populated ledger through an input packet.

## Current attempt

| Field | Value |
| --- | --- |
| Attempt | Not recorded |
| Review scope | review/v1 mode=strong |
| Scope source and version | Not recorded |
| Skill version | Not recorded |
| Requirement/design version | Not recorded |
| Repository base/head refs | Not recorded |
| Environment | Not recorded |
| Independent context / blind contamination | Not verified |
| Original input path/version | Not recorded |
| Blind snapshot | Not recorded |
| Blind snapshot digest / Review refs binding | Not recorded |
| Final attempt report | Not recorded |
| Completeness | INCOMPLETE |
| P0 / P1 / P2 / P3 | 0 / 0 / 0 / 0 known findings |
| Score | Not calculated |
| Result | INCOMPLETE |
| Excluded / N/A / unknown scope | Not assessed |
| Mandatory rework | Not assessed |
| Human acceptance | Not requested |
| Next action / evidence owner | Complete the clean-input review |

## Findings

No findings recorded. This does not mean the review passed. Copy confirmed blocks from the per-attempt report with location, problem, suggest, status, resolution and evidence; map attempt IDs to stable ledger IDs. An author fix commit is not independent closure.

| Ledger ID | Attempt ID / report | Status / priority | Current applicable target | Fix/decision version and recheck evidence | Next action / owner |
| --- | --- | --- | --- | --- | --- |

## Finding transitions

| Ledger ID | Old → new status/priority | Target / decision version | Independent reviewer / evidence / rationale |
| --- | --- | --- | --- |

FIXED requires an applicable independent recheck; REJECTED requires evidence of false positive/non-applicability. A real issue retained is DEFERRED and still counts. Preserve historical transitions instead of overwriting the evidence that supported an old closure.

## Attempt history

Reference immutable reports and their target versions; never rewrite an earlier score because a later version fixes an issue. Keep unmatched, unchecked or out-of-scope historical findings visible with their applicability and next action.

| Attempt | Input path/version | Frozen blind report/digest | Final report | Target refs / scope | Completeness / counts / score / result |
| --- | --- | --- | --- | --- | --- |
