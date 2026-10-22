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

## Decision question

State the precise question for the subject revision and the designated deciding authority.

## Decision and comment

Record the actual decider, scope, authority, conclusion and explanation in decision. An authorized agent can decide within its mandate. On the affected design point, decided with summarizes the reasoning and can name this task; it is not a substitute for authority ref.

For an AGENTS.md role mandate, authority ref identifies the actual rule location and revision; comment must explain the concrete reason and how the stated conditions were met. In delegated mode, record the actual agent as decider and the delegating party in on behalf of. The skill supplies no role, simplicity threshold or business approval rule. Confirming and reopening require their respective effective authority.

## Result

A rejected proposal can still mean the decision task is DONE. Preserve the conclusion rather than turning every completed task into a pass.
