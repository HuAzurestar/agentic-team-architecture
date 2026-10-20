---
id: "GATE-001"
type: "gate"
title: "Evaluate an externally defined gate"
state: "PENDING"
owner: null
depends on: []
started at: null
completed at: null
head sha: []
revision: "v1"
inputs: []
result:
  execution: "not_started"
  outcome: null
  summary: null
  evidence: []
  remaining: []
resume action: "Obtain the assignment, applicable inputs and authorized return location."
gate:
  subject: null
  policy ref: null
  criteria: []
  evaluation: "unknown"
  authorization: "pending"
  decision ref: null
  allowed actions: []
completion criteria:
  - "Evaluate the assigned conditions and record the applicable authorization or unresolved items."
---

# GATE-001 — Evaluate an externally defined gate

## 外部提供的 GATE 定义

由调用方提供对象、策略、条件、证据要求与判定权限。声明检查结果前填写 gate；本模板不定义公司阶段或发布顺序。

## 检查与权限

分别记录 evaluation 和 authorization，版本化持久证据写入 result.evidence。检查满足不等于后续动作获准；granted 需要对应决定，pending、denied 或未知检查不能允许动作。

## 用户决定请求与答复（策略要求时）

由 agent 准备对象/版本、决定问题、证据/限制、拟允许后果及指定确认者，保存请求来源/时间。实际答复到达前保持 authorization=pending，不放行依赖动作；保存答复原文/来源、实际确认者、时间和允许范围，并关联决定记录。渠道、具体提问和跟进方式由外部 orchestrator 决定；不要求每个 GATE 都联系用户。
