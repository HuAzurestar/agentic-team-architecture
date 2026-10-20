---
id: "DECISION-001"
type: "decision"
title: "Decide the specified requirement revision"
state: "PENDING"
owner: null
depends on: []
started at: null
completed at: null
head sha: []
revision: "v1"
inputs:
  -
    id: "REQ-001"
    revision: "v1"
    location: "design/REQ-001.md"
result:
  execution: "not_started"
  outcome: null
  summary: null
  evidence: []
  remaining: []
resume action: "Obtain the assignment, applicable inputs and authorized return location."
decision:
  subject:
    id: "REQ-001"
    revision: "v1"
    location: "design/REQ-001.md"
  conclusion: null
  decider: null
  mode: null
  authority ref: null
  on behalf of: null
  comment: null
completion criteria:
  - "Record an authorized decision and update the target point's decision metadata."
---

# DECISION-001 — Decide the specified requirement revision

## 待决问题

说明针对哪个对象版本、需要决定什么，以及指定的判定权限。

## 决定与评论

在 decision 中记录实际决定者、范围、授权、结论和说明。获授权 agent 可在委托内决定。同步设计点时，decided with 概括判定说明并可标明本任务；它不替代 authority ref。

## 处理结果

提案被拒绝时，决定任务仍可 DONE。保留实际结论，不把所有已完成任务都当作通过。
