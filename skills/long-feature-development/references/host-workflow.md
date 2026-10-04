# Foreground host and acceptance continuation

`feature_host.FeatureHost` is the Skill-only caller entry. It composes the
existing point, review, acceptance, rework and quality APIs in one foreground
host; it does not introduce a service, Web UI, scheduler or plugin importer.

Host code binds REQ/SOL sessions, an acceptance session, review source/options,
the independently authenticated operation authorizer and quality provenance
reader. Missing capabilities remain unavailable. Never build a permission from
Markdown, an uploaded actor label or a CLI flag. A native message/policy service
is optional: an existing authenticated conversation adapter can provide the same
fresh read_reply/interpret/read_grant methods. This package does not deploy such
a service or certify a production account merely by constructing a session.

## Caller routes

```text
python scripts/feature_host.py FEATURE context --format json
python scripts/feature_host.py FEATURE review --purpose development
python scripts/feature_host.py FEATURE acceptance ACCEPT-01
python scripts/feature_host.py FEATURE quality --config /path/to/source-bindings.json
```

These standalone routes read and diagnose. A standalone point application has
no human session and refuses. The configured host can embed
`feature_host.main(argv, host=host)` and explicitly request a point apply through
the existing point CLI. Repository overrides are owned by that host; a second
CLI override cannot replace them. No implicit push, merge or new authorization
is performed. Programmatic host routes are `point(id)`, `review()`,
`acceptance()`, `rework()` and `assess_quality(config_bytes)`.

## Complete the in-flight acceptance disposition flow

The required F04-T06 flow is not an unrestricted rewrite of an assigned task.
Keep the old attempt and its frozen target, brief and history. If it has no real
decision, retain WIP/BLOCKED; the existing dependency writer refuses to replace
its dependencies or hide it behind an unstarted Gate. A user request to continue
implementation is not a REWORK/REJECTED acceptance decision.

1. Record the real old decision through `host.acceptance().prepare/record`,
   checkpoint the exact management changes, and recover. Only a completed
   REWORK/REJECTED disposition can enter this continuation route.
2. Establish a new review attempt for the repaired candidate through the
   existing task planner. Do not change the old report's target or inherit its
   finding closures. The review has the same explicit REQ/SOL selectors.
3. Call `host.rework().preview_successor(old_acceptance, new_review,
   decision_path=declared_original_path, candidate_repository=registered_name,
   exact_scope=scope_tuple)`. It independently reads the committed original
   decision and brief, checks the exact old target/scope/actor and fresh human
   source/grant, and verifies that the review is new and belongs to the current
   candidate. It allocates the internal successor ID; users need not choose it.
4. Explicitly call `create_successor(plan, **binding)`. Fresh host operation
   permission is required and bound to the complete plan. The successor is
   PENDING, Decision=WAITING, Decided by='-', with no inherited acceptance brief
   or completion refs. The old task/brief/reply remain unchanged. The result
   APPLIED_PENDING_CHECKPOINT requires a management checkpoint before continuing.
   An existing matching successor is observed, not created again.
5. For each still-PENDING downstream task call `rewire_pending(old, successor,
   downstream, expected_index_digest=actual_digest, operation_gist=declared_gist,
   **binding)`. It rereads the actual old disposition, verifies successor scope
   and new-review binding, obtains an exact host operation permission and uses
   the existing journaled dependency writer. A started downstream is refused.
   Partial/unknown writes retain their UUID and use existing F03 reconciliation,
   not another dispatch or an automatic rollback by this workflow.
6. Checkpoint and recover. The new acceptance waits for the new review and
   eligible current quality evidence, then receives a new brief and human
   decision. No negative old decision or DONE row authorizes merge/Gate.

`AcceptanceWorkflow.verify_disposition` permits the actual product to have
advanced, because it only verifies a negative decision for the old frozen
attempt. It never transfers an acceptance to that new product version.

Creation reuses the existing task_create writer under the foreground coordinator;
it is not a cross-file transaction. If creation is interrupted or its result is
unknown, inspect/recover the actual task files before another write. This API
does not automatically retry creation, commit, publish or merge.

## Preserved boundary and verification

This continuation does not change assigned historical dependencies or add a new
snapshot-task schema. Point reopen with assigned consumers continues to return
DEPENDENCY_COORDINATION_REQUIRED. General historical-point rebasing needs an
explicit policy beyond this acceptance continuation and must not be silently
implemented by weakening graph validation.

`test_rework_workflow.py` is a concentrated real-Git check of the completed
negative decision, denied operation authority, internal successor allocation,
checkpoint-separated continuation, reentry, pending Gate rewire and byte-exact
preservation of the old attempt/originals. Its identity transport is synthetic;
production-account and independent-review evidence remain separate.
