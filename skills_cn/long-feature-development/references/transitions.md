# 状态流转

仅在 task 状态或 feature 下一流转变化时读取。它不是第二套全局状态机。

## Task 流转

`PENDING` 是唯一未接取状态。直接依赖全部 `DONE` 时派生 `READY`，否则派生 `WAITING`；两者不写入 State 列。`BLOCKED` 只用于已接取 task 的具体障碍，并要求 blocker、impact 和 release condition；未完成依赖不会把未接取 task 变成 BLOCKED。

| 从 | 到 | 必需更新 |
| --- | --- | --- |
| `PENDING` | `WIP` | 核对依赖均为 `DONE`；记录负责人、开始时间、baseline history、start refs、HEAD。 |
| `WIP` | `BLOCKED` | 记录 blocker、影响和解除条件。 |
| `BLOCKED` | `WIP` | 记录解除原因；新 attempt 或新基线时追加 start refs。 |
| `WIP` | `RECORDING` | 完成条件满足；冻结候选输出，登记最终 commit 和 refs。 |
| `RECORDING` | `DONE` | 记录完成时间和每个受影响仓库唯一 completion SHA；同步索引与拓扑。 |
| `RECORDING` | `WIP` | 候选不完整；记录失败检查和 resume action，不伪造 completion refs。 |
| `DONE` | `WIP` | 记录 `REOPENED` commit 或其他明确重开理由，清除完成时间并追加 start refs。 |

不得根据总结推断 `DONE`。只有详情文件的完成条件满足后，owner 才修改 `TASKS.md`。`FAILURE` 与 `REOPEN` 是事件，不是持久状态：保留失败 attempt，再回到 `WIP` 或显式重开。

正常流转使用 `scripts/task_state.py`。它拒绝非法流转和非 READY 接取，校验 task 合同，并原子替换 task 行与派生 Mermaid。直接编辑并运行 `task_context.py --sync-topology` 只用于明确修复或旧数据导入；正常恢复只读，陈旧拓扑必须失败。

需求/方案点决定读取 [confirmation.md](confirmation.md)。点状态与 task 状态相互独立。

## Feature 流转

`STATUS.md` 保存 phase、condition、当前 task/gate 和下一流转。`GATE-*` 是普通 task 节点，其完成授权一次 feature 流转。流转时：

1. 核对 `TASKS.md` 中 gate 依赖和 Git/PR/MR refs；
2. 更新 phase；
3. 替换下一流转；
4. 单独提交项目管理变更。
