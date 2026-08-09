# 工作流 03：架构迭代与云↔本地同步

> 架构文档以**云端 GitHub 仓库为主源**，本地工作目录作为工作副本；任何一次迭代都要同时落在两边。

## 目的

保证架构文档云↔本地始终同步、版本有记录，可追溯。

## 触发

- 每次架构迭代（[docs/05-iteration.md](../docs/05-iteration.md) 四步循环）的评审 / 复盘产出变更。
- 每次 agent run（每个迭代）开始与结束。

## 步骤

1. **动手前先同步**：修改前 `git pull`，确保基于最新 commit。
2. **本地完成修改**：编辑、`git add`、`git commit`（提交信息说明改动，带 docs: 前缀）。
3. **推送云端**：`git push` 到云端主源。
4. **同步回本地**：push 后再 `git pull`（或确认已一致）。
5. **本地材料隔离**：`Skill 下载与审查/`、`新建文件夹/` 等本地材料由 `.gitignore` 排除，不纳入提交。
6. **冲突处理**：若 pull 冲突，以云端主源为准解决。

## 出口物

- 云端 origin/main 与本地工作副本同一 commit。
- 变更记录（[docs/05-iteration.md](../docs/05-iteration.md) §5）更新。

## 负责角色

- **CKO**：管理本架构仓库，负责文档 / 版本 / 工作流更新（[docs/02-boundaries.md](../docs/02-boundaries.md) §1.6）。
- **各中心**：提交本中心相关文档变更。

## 引用

- [README](../README.md)「云端 ↔ 本地同步与迭代规则」
- [docs/05-iteration.md](../docs/05-iteration.md)（可自我迭代）
