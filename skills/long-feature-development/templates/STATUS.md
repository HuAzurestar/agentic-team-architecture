---
title: <feature> Status
---

# <feature> Status

| Item | Current value | Note |
| --- | --- | --- |
| Phase | Requirement | Display only |
| Next transition | Solution | Read transition rules only when changing |
| Current task | REQ | Resolve from local task summary |
| Blocker | None | Include the release condition when blocked |

## Local repositories

| Repository | Local path | Branch | HEAD SHA | Purpose |
| --- | --- | --- | --- | --- |
| `<project-manage-repo>` | `<path>` | `<branch>` | `SELF` | Repository containing this file; resolve live HEAD |
| `<implementation-repo>` | `<path>` | `<branch>` | `<sha>` | Feature integration branch |

## PR/MR objects

| Object | Repository | Source branch@SHA | Target branch@SHA | Note |
| --- | --- | --- | --- | --- |
| Not created | `<repo>` | `<feature-branch>@<sha>` | `<stable-branch>@<sha>` | Final target branch |

## Remote project-management objects

| Object | Binding | Purpose |
| --- | --- | --- |
| Requirement | `<remote-or-none>` | Approved intent |
| Solution | `<remote-or-none>` | Current implementation proposal |
