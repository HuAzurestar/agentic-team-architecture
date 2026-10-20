---
title: <feature-key> Solution
---

# <feature-key> Solution

## Derived document state

| Item | Value |
| --- | --- |
| Status | `DRAFT` |
| Derivation | Every active `SOL-*` point is individually `CONFIRMED`; no active point is `PROPOSED` or `REOPENED` |
| Requirement | `<requirement-reference>` |

This status is derived, not globally approved. Confirmed solution points are immutable until a human explicitly reopens them. Keep dynamic branches and SHAs in `STATUS.md`, not here.

## Solution points

### Review scope

- Review scope: review/v1

Keep only this short selection; `mode=strong` and all applicable topics are defaults. Use `exclude=ui` when UI is excluded, and optional `topics`/`focus` for scope and emphasis. Weak detail stays in the `code-review` skill. A task snapshot must match this authoritative line.

## SOL-001 — <point-title>

| Item | Value |
| --- | --- |
| Class | `ACTIVE` |
| State | `PROPOSED` |
| Requirement points | `REQ-001` |
| Decided by | - |
| Decided at | - |

### Approach

One atomic solution statement.

### Affected interfaces

- API:
- Database:
- Other repositories or consumers:

### Validation

What will be checked, and what will intentionally not be checked.

### Decision history

- None.

## Disposition records

Move rejected, out-of-scope, and infeasible points here without deleting their approach, reason, or decision history. Set `Class` to `DISPOSITION`.

## Revisions

- None.
