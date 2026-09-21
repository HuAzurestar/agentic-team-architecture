# <task-id> — <task-name>

- Goal:
- Inputs:
- Requirement points: none
- Solution points: none
- Work:
- Completion condition:
- Resume action:
- Blocker: none
- Gists: none

## Repository refs

Use literal observed SHAs. Separate multiple start refs with semicolons; preserve baseline advancement as an ordered `branch@sha <= branch@sha` chain. Use `-` only before the task is assigned.

| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |
| --- | --- | --- | --- | --- | --- |
| `<repo>` | `<branch>` | `<stable-branch>@<sha>` | `<branch>@<sha>` | `<sha>` | - |

## Attempt notes

Keep only short facts needed to resume. Put verbose logs, review comments, and test output in declared gists.

## Type contract

Development tasks may remove this section. For `TEST-*`, `REVIEW-*`, `REWORK-*`, `ACCEPT-*`, and `GATE-*`, replace the rows with the exact fields required by `references/task-contracts.md`.

| Field | Value |
| --- | --- |
| Contract | `<task-type>` |
| Target SHA | - |
| Result gist | none |
