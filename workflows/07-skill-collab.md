# 工作流 07：skill 需求 → 导入评测 → 挂载 协同

> 各中心提出 skill 需求后，跨角色完成「检索导入 → 评测 → 挂载」的标准流程（v2.39 RC skill 落地首次走通）。流程 = 步骤与责任，写在 workflows；skill 本体不落本仓库（[README](../README.md)）。

## 目的

把 skill 的**需求、导入、评测、挂载**四步标准化，责任到角色，避免重复检索、绕过评测、越权配置。

## 触发

- 各中心负责人（如 CRO / CTO / CPO）提出新 skill 需求。
- 现有 skill 需要改描述、升级或停用。

## 步骤

1. **需求确认**：需求方（C..O / 中心负责人）确认要什么能力、给谁用、解决什么问题。**创建前查重**：先检索同父 issue / 已有 skill 是否已存在同任务，避免并行重复创建（NEX-55/57 重复创建教训，2026-08-12）。
2. **检索导入**：**CKO** 检索可用 skill 并导入，优先复用已有 / 官方 / 社区成熟 skill。
3. **评测**：CKO 对导入 skill 做评测（是否满足需求、质量如何）；按 CEO 指示批量导入的，**以后续实际结果评判**，不预先卡审。
4. **挂载**：**HR** 将 skill 挂载到目标 Agent / 配置（配置变更属 HR，[docs/02-boundaries.md](../docs/02-boundaries.md) §1.4）。
5. **回填**：CKO 把本轮 skill 清单变化记入知识库（[工作流 01](01-knowledge-routine.md)），与 HR 对齐。

## 出口物

- 新 skill 挂载到目标 Agent，可用。
- skill 清单变化记录。

## 负责角色

- **需求方**：C..O / 中心负责人（确认需求）。
- **CKO**：检索导入 + 评测（[docs/02-boundaries.md](../docs/02-boundaries.md) §1.6）。
- **HR**：挂载配置（§1.4，配置变更须 CEO 批准）。

## 引用

- [docs/02-boundaries.md](../docs/02-boundaries.md) §1.4（HR 配置权）、§1.6（CKO skill 职责）
- [docs/05-iteration.md](../docs/05-iteration.md)（skill / 工作流优化归 CKO 整理）
