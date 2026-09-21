---
title: <feature-key> 状态
---

# <feature-key> 状态

| 项目 | 当前值 | 备注 |
| --- | --- | --- |
| Feature ID | `NO-FEAT-<6-char-random>` | 开发者在合适时分配正式 ID |
| Previous IDs | - | ID 改变后追加旧别名 |
| 阶段 | `PLANNING` | 只有已完成 gate 能改变 phase |
| 条件 | `ACTIVE` | `ACTIVE`、`BLOCKED`、`WAITING_HUMAN`、`WAITING_EXTERNAL` 或终态 `COMPLETE` |
| 下一流转 | `GATE-START` | 可执行下一次 feature 流转的 gate task |
| 当前任务 | REQ-001 | 从 TASKS.md 定位，再读取 tasks/REQ-001.md |
| 当前 gate | GATE-START | 它是 task ID，不是第二套状态机 |
| 阻塞 | 无 | 阻塞时同时写解除条件 |

## 工作分支

| 仓库 | 本地路径 | 工作分支 | 工作 HEAD SHA | 当前 task |
| --- | --- | --- | --- | --- |
| `<project-manage-repo>` | `<path>` | `<branch>` | `DERIVED:HEAD` | `<task>` |
| `<implementation-repo>` | `<path>` | `<task-branch>` | `<sha>` | `<task>` |

## 日常汇入对手分支

| 仓库 | Integration branch | Integration SHA | 接收对象 | 备注 |
| --- | --- | --- | --- | --- |
| `<project-manage-repo>` | `<stable-branch>` | `<observed-sha>` | 项目管理工作分支 | 上次验证的 merge target |
| `<implementation-repo>` | `<feature-branch>` | `<observed-sha>` | Task branches | 上次验证的 merge target |

## PR/MR 对象

| 对象 | 仓库 | Source branch | Source SHA | Target branch | Target SHA | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 待创建 | `<repo>` | `<feature-branch>` | `<observed-sha>` | `<stable-branch>` | `<observed-sha>` | 最终评审与合入对象 |

## 远端项目管理对象

| 对象 | 绑定 | 用途 |
| --- | --- | --- |
| Requirement | `<remote-or-none>` | 已批准意图 |
| Solution | `<remote-or-none>` | 当前实施提案 |
