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

## Externally supplied gate definition

The caller supplies the subject, policy, criteria, evidence requirements and deciding authority. Populate gate before claiming an evaluated result; this template defines no company phases or release sequence.

## Checks and permission

Record evaluation separately from authorization. Cite versioned durable evidence in result.evidence. Positive checks do not grant later actions. A granted authorization names its decision; pending, denied or unknown checks cannot enable actions.

## User decision request and response (when required by policy)

Have the agent prepare subject/version, decision question, evidence/limits, proposed consequences and designated decider; retain request source/time. Keep authorization=pending and dependent actions blocked until the actual answer arrives. Preserve its wording/source, actual decider, time and scope and link the decision record. Channels, phrasing and follow-up belong to the external orchestrator; not every GATE requires contacting the user.
