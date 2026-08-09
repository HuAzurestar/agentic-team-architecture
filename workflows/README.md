# 工作流库

> 可复用的**流程**（workflow）整理，由 **CKO** 维护（见 [docs/02-boundaries.md](../docs/02-boundaries.md) §1.6）。流程与 skill 的分界：**流程 = 步骤与责任**，写在这里；**skill = 可执行的具体能力**，不落本仓库（本仓库只定义架构，见 [README](../README.md)）。

## 工作流清单

| 编号 | 工作流 | 用途 | 主要角色 |
| --- | --- | --- | --- |
| 01 | [例行知识管理](01-knowledge-routine.md) | CKO 例行轮次：红线核对 / 工作流整理 / skill 维护 / 快讯 / 仓库同步 | CKO |
| 02 | [红线扫描与处置](02-redline-scan.md) | S0/S1/S2 的扫描节奏、处置与通知 | Assistant AS / AS / CKO |
| 03 | [架构迭代与云↔本地同步](03-iteration-sync.md) | 架构文档迭代四步 + 云端 push / 本地 pull | CKO / 各中心 |
| 04 | [升级三问与红线认定](04-escalation-triage.md) | 越权疑点的升级复核与级别认定 | 直属上级 / AS / CKO |
| 05 | [核心价值流](05-core-value-flow.md) | PC 设计 → TC 实现 → OC 运营 的交接与驳回 | CPO / CTO / COO / AS |

## 约定

- 每个工作流给出：**目的 / 触发 / 步骤 / 出口物 / 负责角色**，并引用相关 docs。
- 流程可被 Autopilot、issue、手动操作引用；**触发时机由 CEO 确认创建、AS 跟进**（[docs/08-bootstrap.md](../docs/08-bootstrap.md) §5）。
- 变更流程须同步更新本目录与相关 docs，按 [云↔本地同步规则](../README.md) 提交。
