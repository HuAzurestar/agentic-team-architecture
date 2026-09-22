# User-facing acceptance

Read this reference when creating, starting, or presenting an acceptance task.

Create a version-controlled brief under `gists/` from `templates/ACCEPTANCE.md`, declare it in the task's `Gists` field, and record it as `Acceptance brief` in the type contract. Fill every section with bounded, plain-language content. Internal task IDs, point IDs, and raw logs may remain in trace records but are not prerequisites for a user decision.

Before asking for a decision, run:

```text
python scripts/task_context.py <feature-directory> --task <acceptance-task> --format acceptance
```

Present that short output proactively. The user may answer in natural language: accept, request changes, or postpone while asking for a specific check. The Agent maps that answer to the internal decision and records the exact human source; it never asks the user to edit the contract or understand `ACCEPT-*`.

An acceptance task remains `WAITING` while PENDING, WIP, or BLOCKED. Once the human decides, move it to RECORDING, persist the decision, then complete its refs. A gate may proceed only after the acceptance task is DONE.
