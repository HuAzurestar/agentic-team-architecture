---
title: <feature-key> Status
---

# <feature-key> Status

| Item | Current value | Note |
| --- | --- | --- |
| Feature ID | `NO-FEAT-<6-char-random>` | Developer assigns the official ID when appropriate |
| Previous IDs | - | Append aliases after an ID change |
| Phase | Requirement | Display only |
| Next transition | Solution | Read transition rules only when changing |
| Current task | REQ-001 | Locate this row below, then read its TASKS section |
| Blocker | None | Include the release condition when blocked |

## Task state

| Task | Type | State | Pickup refs | Completion refs | Next action |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | Requirement | `TODO` | - | - | Decide `REQ-001` |
| SOL-001 | Solution | `TODO` | - | - | Decide `SOL-001` after its requirement points are confirmed |

## Working branches

| Repository | Local path | Working branch | Working HEAD SHA | Current task |
| --- | --- | --- | --- | --- |
| `<project-manage-repo>` | `<path>` | `<branch>` | `DERIVED:HEAD` | `<task>` |
| `<implementation-repo>` | `<path>` | `<task-branch>` | `<sha>` | `<task>` |

## Integration opponents

| Repository | Integration branch | Integration SHA | Receives | Note |
| --- | --- | --- | --- | --- |
| `<project-manage-repo>` | `<stable-branch>` | `<observed-sha>` | Project-management work branch | Last verified merge target |
| `<implementation-repo>` | `<feature-branch>` | `<observed-sha>` | Task branches | Last verified merge target |

## PR/MR objects

| Object | Repository | Source branch | Source SHA | Target branch | Target SHA | Note |
| --- | --- | --- | --- | --- | --- | --- |
| Not created | `<repo>` | `<feature-branch>` | `<observed-sha>` | `<stable-branch>` | `<observed-sha>` | Final review and merge target |

## Remote project-management objects

| Object | Binding | Purpose |
| --- | --- | --- |
| Requirement | `<remote-or-none>` | Approved intent |
| Solution | `<remote-or-none>` | Current implementation proposal |
