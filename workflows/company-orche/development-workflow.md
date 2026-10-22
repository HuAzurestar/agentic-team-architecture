# `dev-orchestrator` 动态编排约束

说明版本：`feature-delivery/2026-10-22-v10`

正常：`INT` → 已确认的 `REQ`、`SOL` → `GATE-START-0` → `DEV`（含开发相关测试） → 独立 `TEST`、`REVIEW` → `GATE-COMPLETION` → 获准的发布任务。

反馈：`TEST`／`REVIEW` → `FEEDBACK` → 分类处置 → 需处理的 `ADVICE`／`BUG` → 本次 `SOL` 及确认 → `GATE-START-X` → `DEV-REFINE`／`DEV-BUG-FIX`／`DEV-REFACTOR` → 独立 `TEST`／`REVIEW` 及必要回归 → 汇入同一个 `GATE-COMPLETION`。建议不采纳或环境问题可分流，不强制代码返工。

- 图可动态增减与调整；必要依赖不可绕过。正常轮次INT、反馈轮次FEEDBACK及适用REQ／本次SOL确认在对应START前，该轮 `DEV` 在有效 `START` 授权后，必要验证在最终 `COMPLETION` 前。
- `START` 按轮次保留准确对象与授权历史，不借用旧轮批准；仅两类 `GATE`，不新增“发布关口”等第三类。`DONE`、evaluation 与 authorization 分开表达。
- 发布文档及部署方案可按委托提前准备；受控合并、部署、公告等副作用须核对有效完成决定及对应动作授权。最终完成确认不等于已部署。
- 派发以 `(feature-key, task-key)` 为入口；一次委托一个 `task-key`、一种工作类型，涉及的 `project-key` 由任务解析。跨仓库执行工作拆分明确子任务与集成依赖，不要求用户重复提供仓库配置。
- 上下文隔离按实际会话／进程判断，不按 Agent 名称判断。每个 `DEV`、`REVIEW`、`TEST`、`DOCS` 执行上下文只承担该类工作；同一个 `dev-agent` 可在不同干净上下文分别执行。禁止先在一个会话 DEV 再继续 REVIEW／TEST，DOCS 也不能复用开发／部署会话。任务与 run／session 建立映射，只有新任务ID不足以证明隔离。
- `INT`／`REQ`／`SOL` 设计允许一起处理，不必按设计点拆进程；确认与设计分离，另开干净确认上下文。socket 可以在此新上下文核验同一轮全部 REQ／SOL，不能携带起草会话历史或用新角色标签冒充隔离。
- START 默认交用户批准；只有公共规则的全部 socket 自确认、简单事项及本阶段输入收口条件同时满足时，socket 才可批准该轮 START。orchestrator 只安排、核验、登记和执行有效批准。COMPLETION始终交用户本人。
- 同一候选不边改边审。独立只读的 TEST／REVIEW 可在各自干净上下文针对冻结候选并行；共享环境有副作用仍需独占或串行。候选变化重新判断受影响验证有效性。
- 派发前核对运行中任务、执行者占用、输入版本、候选及写入范围，保留任务认领及派发映射。缺可靠的跨会话排他机制时串行化，不把口头约定当锁，不靠重复派发解决无回执。
- 已正式转交的 `Feature` 由 `orchestrator` 管理内部新增 `INT`／`REQ`／`SOL`、任务与关口；`socket` 转交后续用户输入及决定，不并发改同一正式索引。内容可委托起草，正式写入须有明确归属。

- DEV子类主类型保持DEV；YAML可用type: development和development kind: refine／bug-fix／refactor，对外都按DEV派发。子类名称是工作分类，不自动创建Git分支。反馈修复须有明确本次SOL，可引用未变REQ，不机械制造新REQ。
- DEV可以在自己的上下文写测试、做TDD、运行单元／局部集成和调试；这些属于开发，不是独立TEST。TEST的新干净上下文负责业务、回归和统一验证，可使用同样工具，但不能仅拿DEV自测结果冒充独立验证。
- REVIEW／TEST产出FEEDBACK并保留来源、候选和观察，orchestrator组织分类处置；不直接把它们改成INT。FEEDBACK可派生零到多个ADVICE／BUG；采纳／确认后安排SOL和对应DEV。环境问题可只做恢复与重测，用户另提业务意图才记录真实INT。
