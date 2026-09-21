# <task-id> — <task-name>

- Goal:
- Inputs:
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
