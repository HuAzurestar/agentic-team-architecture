# 工作流库

> 可复用的**流程**（workflow）整理，由 **CKO** 维护（见 [docs/02-boundaries.md](../docs/02-boundaries.md) §1.6）。流程与 skill 的分界：**流程 = 步骤、责任与组织安排**，写在这里；**skill = 通用能力与产物协议**，见 [skills](../skills/)。工作流使用 skill，通用 skill 不依赖公司的组织配置。

## 工作流清单

| 编号 | 工作流 | 用途 | 主要角色 |
| --- | --- | --- | --- |
| 01 | [例行知识管理](01-knowledge-routine.md) | CKO 例行轮次：红线核对 / 工作流整理 / skill 维护 / 快讯 / 仓库同步 | CKO |
| 02 | [红线扫描与处置](02-redline-scan.md) | S0/S1/S2 的扫描节奏、处置与通知 | Assistant AS / AS / CKO |
| 03 | [架构迭代与云↔本地同步](03-iteration-sync.md) | 架构文档迭代四步 + 云端 push / 本地 pull | CKO / 各中心 |
| 04 | [升级三问与红线认定](04-escalation-triage.md) | 越权疑点的升级复核与级别认定 | 直属上级 / AS / CKO |
| 05 | [核心价值流](05-core-value-flow.md) | PC 设计 → TC 实现 → OC 运营 的交接与驳回 | CPO / CTO / COO / AS |
| 06 | [失败备案归档与统一索引](06-failure-filing.md) | RC 失败备案镜像进 CKO 归档与统一索引（源真，NEX 锚点） | RC / CKO |
| 07 | [skill 需求→导入评测→挂载 协同](07-skill-collab.md) | 新 skill 从需求到挂载的四步流程（检索导入 / 评测 / HR 挂载） | 需求方 / CKO / HR |
| 08 | [研究交付物审核与升级](08-research-review-escalation.md) | RC 交付物审核口 + 1 次不通过升级 Senior（2026-08-13 CEO 指令） | 作者 / 审核专员 / CRO / Senior |
| 09 | [长任务执行协议](09-long-task-execution.md) | 小时级长任务：冒烟 → 备份+实验号 → 报路径 → CEO 一键运行 → 回传（CEO `0d4909c2`） | 发起方 / CEO / CRO |

## 公司四角色配置

`company-orche/` 是公司流程与角色配置，文件作为角色指令由宿主显式加载，不依赖自动发现 `AGENTS.md`：

- [orchestrator](company-orche/orchestrator_agent.md)：Task/GATE 编排、状态管理与跨角色/人员交接。
- [out-socket](company-orche/out_socket_agent.md)：intent 识别、难易判断、授权范围内的 REQ/SOL 代审及能力改进。
- [dev-processor](company-orche/dev_processor_agent.md)：开发与内部测试。
- [release-check](company-orche/release_check_agent.md)：必要审核、测试与 REQ/SOL 回归。

公司 SQL、PaaS、运维、管理者审批和开发环境的安排属于此工作流；具体联系人、状态位置与授权由项目提供，不是通用 skill 的默认配置。

## 约定

- 每个工作流给出：**目的 / 触发 / 步骤 / 出口物 / 负责角色**，并引用相关 docs。
- 流程可被 Autopilot、issue、手动操作引用；**触发时机由 CEO 确认创建、AS 跟进**（[docs/08-bootstrap.md](../docs/08-bootstrap.md) §5）。
- 变更流程须同步更新本目录与相关 docs，按 [云↔本地同步规则](../README.md) 提交。
- **创建前查重**：新建 issue / 工作流 / skill 前先检索同父 issue 或已有清单，避免并行重复创建（NEX-55/57、NEX-56/58 教训，2026-08-12）；已发现的重复 issue 由 AS 收口置 cancelled，须在评论说明并以主 issue 为准。
