---
title: <feature-key> 状态
---

# <feature-key> 状态

| 项目 | 当前值 | 备注 |
| --- | --- | --- |
| Feature ID | `NO-FEAT-<6-char-random>` | 开发者在合适时分配正式 ID |
| Previous IDs | - | ID 改变后追加旧别名 |
| 阶段 | 需求 | 仅用于展示 |
| 下一流转 | 方案 | 只在实际流转时读取规则 |
| 当前任务 | REQ-001 | 从下表定位，再读取对应 TASKS 章节 |
| 阻塞 | 无 | 阻塞时同时写明解除条件 |

## Task 状态

| Task | 类型 | 状态 | 接取 refs | 完成 refs | 下一步 |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | 需求 | `TODO` | - | - | 决定 `REQ-001` |
| SOL-001 | 方案 | `TODO` | - | - | 对应需求点确认后决定 `SOL-001` |

## 工作分支

| 仓库 | 本地路径 | 工作分支 | 工作 HEAD SHA | 当前 task |
| --- | --- | --- | --- | --- |
| `<project-manage-repo>` | `<path>` | `<branch>` | `DERIVED:HEAD` | `<task>` |
| `<implementation-repo>` | `<path>` | `<task-branch>` | `<sha>` | `<task>` |

## Integration 对手

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
