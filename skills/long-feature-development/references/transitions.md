# State transitions

Read this file only when a task changes state or the feature's next transition changes. It is not a second global state machine.

## Task transitions

| From | To | Required update |
| --- | --- | --- |
| `PENDING` | `WIP` | Verify all dependencies are `DONE`; record owner, start time, baseline history, start refs, and current HEAD. |
| `WIP` | `BLOCKED` | Record the blocker, its effect, and the release condition. |
| `BLOCKED` | `WIP` | Record why the blocker is released; append start refs if a new attempt or baseline is used. |
| `WIP` | `RECORDING` | Completion conditions are met; freeze candidate outputs while final commits and refs are recorded. |
| `RECORDING` | `DONE` | Record completion time and exactly one completion SHA per affected repository; make the index and topology consistent. |
| `RECORDING` | `WIP` | The candidate is incomplete; record the failed check and resume action without inventing completion refs. |
| `DONE` | `WIP` | Record the point's `REOPENED` commit or another explicit reopen reason, clear completion time, and append new start refs. |

Do not infer `DONE` from a summary statement. The task owner changes the `TASKS.md` row only after the matching detail file's completion condition is satisfied. `FAILURE` and `REOPEN` are events, not persistent states: record the failed attempt, then return to `WIP` or explicitly reopen a completed task.

For requirement and solution point decisions, read [confirmation.md](confirmation.md). Point state and task state are separate; the Mermaid diagrams there are authoritative for their relationship.

## Feature transition note

`STATUS.md` stores feature phase, condition, current task, current gate, and the next intended transition. A `GATE-*` task is an ordinary task node whose completion authorizes one feature transition. When the transition happens:

1. verify the gate dependencies in `TASKS.md` and the Git/PR/MR refs;
2. update the current phase;
3. replace the next-transition note;
4. commit the project-management change separately.
