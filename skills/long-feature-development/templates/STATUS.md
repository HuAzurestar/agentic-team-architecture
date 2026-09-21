---
title: <feature-key> Status
---

# <feature-key> Status

| Item | Current value | Note |
| --- | --- | --- |
| Feature ID | `NO-FEAT-<6-char-random>` | Developer assigns the official ID when appropriate |
| Previous IDs | - | Append aliases after an ID change |
| Phase | `PLANNING` | Feature phase; only a completed gate changes it |
| Condition | `ACTIVE` | `ACTIVE`, `BLOCKED`, `WAITING_HUMAN`, `WAITING_EXTERNAL`, or terminal `COMPLETE` |
| Next transition | `GATE-START` | Gate task that may perform the next feature transition |
| Current task | REQ-001 | Locate this row in TASKS.md, then read tasks/REQ-001.md |
| Current gate | GATE-START | A task ID, not a second state machine |
| Blocker | None | Include the release condition when blocked |

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
