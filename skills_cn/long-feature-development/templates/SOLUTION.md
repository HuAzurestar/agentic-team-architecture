---
title: <feature-key> 方案
---

# <feature-key> 方案

## 派生文档状态

| 项目 | 值 |
| --- | --- |
| 状态 | `DRAFT` |
| 派生规则 | 每个活动 `SOL-*` 点均已单独 `CONFIRMED`；不存在活动的 `PROPOSED` 或 `REOPENED` 点 |
| 对应需求 | `<requirement-reference>` |

该状态由点状态派生，不通过全局批准设置。已确认方案点在人员明确重开前不可修改。动态分支和 SHA 保存在 `STATUS.md`，不写在这里。

## 审查范围

- Review scope: review/v1

仅保存短选择；默认 strong 和全部适用主题。排除 UI 用 exclude=ui，可选 topics/focus 指定范围及重点。弱审 detail 留在 `code-review` skill，任务快照必须匹配此权威行。

## SOL-001 — <point-title>

| 项目 | 值 |
| --- | --- |
| 类别 | `ACTIVE` |
| 状态 | `PROPOSED` |
| 需求点 | `REQ-001` |
| 决定人 | - |
| 决定时间 | - |

### 做法

一个原子的方案表述。

### 受影响接口

- API：
- 数据库：
- 其他仓库或消费者：

### 验证

说明会检查什么，以及明确不检查什么。

### 决定历史

- 无。

## 处置记录

把已拒绝、范围外和不可行的点移动到这里，不得删除其做法、理由或决定历史。将 `类别` 设置为 `DISPOSITION`。

## 修订记录

- 无。
