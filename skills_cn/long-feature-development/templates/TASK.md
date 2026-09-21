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

使用实际观察到的字面 SHA。多个 start ref 用分号分隔；稳定基线前进按 `branch@sha <= branch@sha` 保留有序历史。仅在 task 尚未接取时使用 `-`。

| Repository | Branch | Baseline history | Start refs | HEAD SHA | Completion SHA |
| --- | --- | --- | --- | --- | --- |
| `<repo>` | `<branch>` | `<stable-branch>@<sha>` | `<branch>@<sha>` | `<sha>` | - |

## Attempt notes

只保留恢复所需短事实。详细日志、评审意见和测试输出写入显式 gist。

## Type contract

开发 task 可删除本节。`TEST-*`、`REVIEW-*`、`REWORK-*`、`ACCEPT-*`、`GATE-*` 必须按 `references/task-contracts.md` 替换成对应字段。

| Field | Value |
| --- | --- |
| Contract | `<task-type>` |
| Target SHA | - |
| Result gist | none |
