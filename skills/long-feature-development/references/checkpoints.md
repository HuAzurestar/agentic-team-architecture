# Durable checkpoints and recovery

Read this reference when starting, resuming, checkpointing, or handing off implementation work.

## Automatic timing

The Agent creates a local checkpoint without waiting for a user reminder:

- after one coherent, testable work unit;
- before a long-running or high-risk operation;
- before a normal handoff or end of run.

Use `scripts/task_checkpoint.py` with an explicit list of owned files. It refuses directories, sensitive-looking paths, pre-staged work, unchanged includes, and any changed path outside the declared scope. It creates a local commit only, never pushes, then updates the task HEAD, resume action, and checkpoint note. Commit the resulting project-management record separately.

## Recovery behavior

`task_context.py` checks resolved repositories before returning resumable context. Any staged, unstaged, or untracked implementation change is a recovery-required hard stop. In the project-management repository, only residue inside the selected feature directory blocks that feature; unrelated feature files remain untouched.

When recovery stops:

1. identify whether each residual path belongs to the interrupted task;
2. inspect and test it before staging;
3. either create a scoped checkpoint or ask the user about genuinely unowned work;
4. rerun recovery before making new changes.

The guarantee is recovery to the most recent successful local checkpoint. Zero loss at an arbitrary power-cut instant requires host, editor, filesystem, or daemon support and must not be promised by this Skill.

For relocation, branch identity and integration-observation mismatches, use the read-only plan and scoped apply described in [reconciliation](reconciliation.md). Commit the resulting management records before rerunning strict recovery. A partial apply is not permission to overwrite a third version or repeat a successful external operation.
