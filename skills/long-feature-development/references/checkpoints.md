# Checkpoint and interruption recovery

Read before an interruption-prone operation, a handoff, or recovery of incomplete implementation/state writes. The host supplies the authorized checkpoint method; this skill does not require a Git-backed management folder or silently authorize commits.

## Record a recovery point

After a coherent work unit, before risky/long work and before handing off, use an available authorized persistence mechanism. Retain task identity, input versions, observed output points, checks and limits, dirty/residual work, exact resume action and known blockers. Keep the authoritative checkpoint note in the task; disposable logs cannot be its only context.

A code checkpoint may be an authorized scoped local commit; another host may provide an equivalent snapshot. State which material was actually saved and where. Do not claim persistence merely because a summary was written.

## Inspect residual work safely

On recovery, inspect relevant staged, unstaged and untracked implementation changes and partial Feature-state updates before further writes. Determine which paths and changes belong to the interrupted assignment. A dirty tree is evidence to reconcile, not blanket permission to delete, reset, stage or commit it, and not an automatic blocker for unrelated read-only work.

Preserve user changes and unrelated staged work. Review and, where appropriate, test owned residue before saving it. Continue only in an isolated, understood scope; if ownership, candidate identity or overlapping changes remain ambiguous, stop the affected mutation and obtain direction through the supplied interface.

When Git is the chosen checkpoint mechanism, name owned files explicitly, inspect staged content for unrelated changes/secrets and keep local checkpoint creation distinct from push/merge. Follow project authorization; no old checkpoint script or auto-commit policy is assumed.

## Reconcile and hand off

Compare observed repository points with recorded ones using [repository-context.md](repository-context.md). Reconcile task details, previews and the affected STATUS overview through the assigned maintainer. Partial writes are not complete checkpoints, and a structural checker does not verify Git ancestry or snapshot durability.

Leave the latest successful recovery point, unsaved residual scope, tests/results, exact next action, blockers and follow-up owner discoverable in durable records. Report missing persistence honestly. Recovery is bounded by the last successful save; arbitrary power-loss zero-loss guarantees require host/editor/filesystem support and are not supplied by this skill.
