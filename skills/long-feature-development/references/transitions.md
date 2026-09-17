# State transitions

Read this file only when a task changes state or the feature's next transition changes. It is not a second global state machine.

## Task transitions

| From | To | Required update |
| --- | --- | --- |
| `TODO` | `WIP` | Record every relevant pickup `repo@branch@SHA`. |
| `WIP` | `BLOCKED` | Record the blocker, its effect, and the release condition. |
| `BLOCKED` | `WIP` | Record the new pickup refs and why the blocker is released. |
| `WIP` | `DONE` | Record every completion ref and the next task or action. |
| `DONE` | `WIP` | Reopen only with an explicit reason and new pickup refs. |

Do not infer `DONE` from a summary statement. The task owner changes the row after its stated completion condition is satisfied.

## Feature transition note

`STATUS.md` stores only the current phase and the next intended transition. When the transition happens:

1. verify the relevant task rows and Git/PR/MR refs;
2. update the current phase;
3. replace the next-transition note;
4. commit the project-management change separately.

