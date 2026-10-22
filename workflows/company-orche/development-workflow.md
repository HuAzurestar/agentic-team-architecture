# `dev-orchestrator` 动态编排约束

说明版本：`feature-delivery/2026-10-22-v7`

正常：`INT` → 已确认的 `REQ`、`SOL` → `GATE-START-0` → `DEV` → `TEST`、`REVIEW` → `GATE-COMPLETION` → 获准的发布任务。

反馈：`TEST`／`REVIEW` 发现 → 新 `INT` → 受影响 `REQ`／`SOL` 更新和确认 → `GATE-START-X` → 新 `DEV`／返工 → `TEST`、`REVIEW` ＋必要回归 → 汇入同一个 `GATE-COMPLETION`。

- 图可动态增减与调整；必要依赖不可绕过。每轮 `INT` 记录及适用 `REQ`／`SOL` 确认在该轮 `START` 前，该轮 `DEV` 在有效 `START` 授权后，必要验证在最终 `COMPLETION` 前。
- `START` 按轮次保留准确对象与授权历史，不借用旧轮批准；仅两类 `GATE`，不新增“发布关口”等第三类。`DONE`、evaluation 与 authorization 分开表达。
- 发布文档及部署方案可按委托提前准备；受控合并、部署、公告等副作用须核对有效完成决定及对应动作授权。最终完成确认不等于已部署。
- 派发以 `(feature-key, task-key)` 为入口；一次委托一个 `task-key`、一种工作类型，涉及的 `project-key` 由任务解析。跨仓库执行工作拆分明确子任务与集成依赖，不要求用户重复提供仓库配置。
- 同一执行者同一时段只承担一种工作类型，同一候选不边改边审。独立、只读的 `TEST`／`REVIEW` 可针对冻结候选并行；共享环境有副作用时仍需独占或串行。候选变化重新判断受影响验证有效性。
- 派发前核对运行中任务、执行者占用、输入版本、候选及写入范围，保留任务认领及派发映射。缺可靠的跨会话排他机制时串行化，不把口头约定当锁，不靠重复派发解决无回执。
- 已正式转交的 `Feature` 由 `orchestrator` 管理内部新增 `INT`／`REQ`／`SOL`、任务与关口；`socket` 转交后续用户输入及决定，不并发改同一正式索引。内容可委托起草，正式写入须有明确归属。
