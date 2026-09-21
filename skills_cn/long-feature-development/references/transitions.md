# 状态流转

仅在 task 状态或 feature 下一流转发生变化时读取本文件。它不是第二套全局状态机。

## Task 流转

| 从 | 到 | 必需更新 |
| --- | --- | --- |
| `TODO` | `WIP` | 记录所有相关接取 `repo@branch@SHA`。 |
| `WIP` | `BLOCKED` | 记录阻塞、影响和解除条件。 |
| `BLOCKED` | `WIP` | 记录新的接取 refs 和阻塞解除原因。 |
| `WIP` | `DONE` | 记录所有完成 refs 和下一 task 或动作。 |
| `DONE` | `WIP` | 记录点的 `REOPENED` commit 或其他明确理由，以及新的接取 refs。 |

不得根据总结性表述推断 `DONE`。匹配的 `TASKS.md` 完成条件满足后，由 task owner 修改 `STATUS.md` 行。

需求点和方案点的决定读取 [confirmation.md](confirmation.md)。点状态与 task 状态相互独立，其中的 Mermaid 图是两者关系的权威规则。

## Feature 流转备注

`STATUS.md` 只保存当前阶段和下一次计划流转。流转发生时：

1. 核对相关 task 行和 Git/PR/MR refs；
2. 更新当前阶段；
3. 替换下一流转备注；
4. 单独提交项目管理变更。
