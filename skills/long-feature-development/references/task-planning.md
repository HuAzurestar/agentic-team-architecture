# Agent-owned task planning

Read this reference when new work must be added to an existing feature.

## User and Agent boundary

The user supplies the business outcome, constraints, priority, and any required authorization. The Agent owns internal task IDs, task types, dependencies, and requirement/solution selectors. Never ask the user to invent or understand an internal ID merely to start or continue work.

Ask the user only when a product choice, authorization boundary, destructive action, or genuinely ambiguous scope cannot be derived safely. Show the plan in business language; keep internal labels as optional trace information.

## Controlled creation

Use `scripts/task_create.py` for normal task creation. It allocates the next non-conflicting ID for the selected task type, validates dependencies and point selectors, creates `tasks/<id>.md`, inserts the `TASKS.md` row, and regenerates Mermaid. The Agent supplies repository baselines from observed refs.

Example for Agent use:

```text
python scripts/task_create.py <feature-directory> --type Development --name "Add import validation" --depends-on SOL-004 --requirement-points REQ-004 --solution-points SOL-004 --goal "Reject invalid imports" --work "Implement validation and tests" --completion-condition "Invalid rows are rejected with tests" --resume-action "Implement the parser boundary" --repo-ref "app|feature-x|main@<observed-sha>"
```

Do not expose this command as a required user prompt. A failed creation leaves the old index intact and removes the new detail file.
