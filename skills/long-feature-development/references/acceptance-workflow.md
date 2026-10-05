# Acceptance workflow entry

Use `acceptance_workflow.AcceptanceWorkflow(feature_directory, session=session,
repo_overrides=...)` in the agent/workbench host. The session has the same
feature, source_key and fresh read_reply/interpret/read_grant methods as the
decision entry; a native session or an authenticated platform adapter works.
No callback or permission is loaded from a decision record or CLI option.

`inspect(task_id)` reads the actual retained acceptance state, dependencies,
candidate, scope, brief and decision without contacting a human service or
performing a write. The standalone CLI only performs this inspection:

```text
python scripts/acceptance_workflow.py FEATURE ACCEPT-01 --repo product=/path/to/repo
```

## Record one real decision

1. Retain the actual decision-evidence-v1 record and six-section brief as
   declared, committed originals. Their target is the actual product candidate,
   not the commit containing the management records. Read the original human
   reply through the configured session; a coordination request is not acceptance.
2. Build task_state arguments for WIP to RECORDING or RECORDING to DONE and
   exact detail/STATUS byte changes. Call `workflow.prepare(args, changes)` while
   the full baseline is still clean. Prepare only those exact metadata changes
   through the caller's existing file-edit mechanism.
3. Call `workflow.record(preparation, decision_document=git_document,
   candidate_repository=registered_name, exact_scope=scope_tuple)`. This connects
   AcceptanceReader directly to the guarded task_state writer. It checks the
   retained scope/brief/candidate, current human source and independent grant,
   then atomically replaces only TASKS.md and its derived topology.
4. APPLIED_PENDING_CHECKPOINT requires the ordinary separate management
   checkpoint and strict recovery before another operation. For a second state
   transition, capture a new clean preparation after that checkpoint. Dry-run
   returns NOT_APPLIED. On an exception or interrupted/unknown effect inspect the
   actual files and recover first; do not automatically repeat the call.

The entry does not prepare arbitrary files, commit, push, merge, assign new
attempts, or change dependencies. Cross-file preparation remains deliberately
separate from the atomic index write; do not promise an atomic multi-file commit.

## In-flight attempt disposition

An actual REJECTED/REWORK decision can complete its frozen acceptance attempt
without declaring quality success or permitting merge. Preserve that attempt's
target, brief and human record. New review/candidate work gets a new attempt;
only still-PENDING downstream tasks can be rewired through task_dependencies.
Without an applicable actual decision keep the old attempt WIP, or record its
concrete blocker through the existing WIP to BLOCKED transition. A changed
product HEAD cannot silently substitute for the old candidate.

This acceptance entry does not remove a historical dependency on a reopened
REQ/SOL point. PointWorkflow still returns DEPENDENCY_COORDINATION_REQUIRED
when any assigned consumer would make the graph invalid. Disposition of an
acceptance attempt alone does not solve that graph conflict; never reset started
tasks or weaken the graph validator to force a point reopen through it.

Broad cross-platform and provider verification is deferred to the combined
review. The host entry is not evidence that a production identity service has
been deployed or a human has accepted the current feature.
