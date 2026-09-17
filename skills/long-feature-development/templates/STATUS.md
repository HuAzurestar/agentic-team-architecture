---
title: <feature> Status
---

# <feature> Status

| Item | Current value | Note |
| --- | --- | --- |
| Phase | Requirement | Display only |
| Next transition | Solution | Read transition rules only when changing |
| Current task | REQ | Locate this row below, then read its TASKS section |
| Blocker | None | Include the release condition when blocked |

## Task state

| Task | Type | State | Pickup refs | Completion refs | Next action |
| --- | --- | --- | --- | --- | --- |
| REQ | Requirement | `TODO` | - | - | Confirm requirement |
| SOL | Solution | `TODO` | - | - | Baseline solution |

## Working branches

| Repository | Local path | Working branch | Working HEAD SHA | Current task |
| --- | --- | --- | --- | --- |
| `<project-manage-repo>` | `<path>` | `<branch>` | `SELF` | `<task>` |
| `<implementation-repo>` | `<path>` | `<task-branch>` | `<sha>` | `<task>` |

## Integration opponents

| Repository | Integration branch | Integration SHA | Receives | Note |
| --- | --- | --- | --- | --- |
| `<project-manage-repo>` | `<stable-branch>` | `LIVE:<stable-branch>` | Project-management work branch | Resolve live ref |
| `<implementation-repo>` | `<feature-branch>` | `<sha>` | Task branches | Ongoing development merge target |

## PR/MR objects

| Object | Repository | Source branch | Source SHA | Target branch | Target SHA | Note |
| --- | --- | --- | --- | --- | --- | --- |
| Not created | `<repo>` | `<feature-branch>` | `<sha>` | `<stable-branch>` | `<sha>` | Final review and merge target |

## Remote project-management objects

| Object | Binding | Purpose |
| --- | --- | --- |
| Requirement | `<remote-or-none>` | Approved intent |
| Solution | `<remote-or-none>` | Current implementation proposal |
