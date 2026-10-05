# Foreground review workflow

`review_workflow.ReviewWorkflow` is the agent/workbench entry for the existing
Git and native review components. Bind one Git source or one NativeDocument,
plus a declared operation gist and the host's current authorization reader for
mutations. `read(purpose, explicit_review=..., statuses=..., rv_ids=...)` reads
only for review or an explicit request; ordinary development does not poll.
Unbound sources return an empty state, while a bound unavailable source fails.
Reads retain `agent_consumed=false`; displaying saved reviews alone does not
prove that an agent has acted on them.

Read a registered Git source from the standalone CLI:

```text
python scripts/review_workflow.py FEATURE --repository app --review-path REVIEWS.md
python scripts/review_workflow.py FEATURE --repository app --status VERIFIED --rv-id RV-UUID
```

The repository path and remote identity are resolved from STATUS.md, not from
review content. The source is the actual remote master. Native callers embed
`main(argv, workflow=configured_workflow)` or call `read()` directly with their
existing NativeDocument credential binding. Responses are JSON containing the
selected original comments and observed source version. CLI performs reads only.

## Apply a review and synchronize master

Call `preflight(observation, expected_working_head=..., expected_branch=...,
samples=...)` with actual configured GitSampleBinding targets. A passing result
means the observed samples and refs are current. MASTER_SYNC_REQUIRED identifies
the exact master observation to synchronize before applying changes.

`prepare_master_sync(observation)` writes the durable F03 operation and returns
its operation ID and immutable intent digest. Retain both in the host. Call
`synchronize_master(operation_id, intent_digest)` after authorization. It uses
the existing sync behavior for implementation and management repositories,
including journal-only management checkpoints. Reentry reads dispatched results;
it does not repeat an uncertain merge. After synchronization, read reviews and
run preflight again against the new actual working HEAD and samples. Conflict
resolution and final integration remain separate authorized actions.

## Publish a retained draft

`prepare_publication(draft, observation=..., supersedes=...)` binds the full
authoritative original, all review states, the draft digest and any explicitly
superseded conflict. It uses the existing Git lease or native If-Match publisher
and returns `{operation_id, intent_digest}`. Preparing may retain a local draft
and candidate but does not publish it remotely.

`publish(operation_id, intent_digest)` verifies that the journal belongs to this
configured source and obtains fresh permission for that exact operation. The
backend saves dispatch before sending a single conditional write. Reentry reads
the same RV UUIDs; conflict/unknown results retain the draft and the existing
no-retry behavior. `inspect_publication(operation_id)` reads the remote result
without altering the journal. UI can display that result and the preserved
draft reference, including 409 conflicts, without claiming agent consumption.

## Host authorization contract

`authorize(request)` is a trusted in-process reader, not loaded by CLI or JSON.
The immutable request content identifies action, feature, root, configured
source, operation gist and exact scope (version/draft or operation/intent).
The reader must verify actual current permission and return
`ReviewPermission(permission_digest(request), actual_authority_source_ref)`.
Constructing that type or hashing a request does not grant permission. Returning
no permit or a mismatched request binding stops before the writer is invoked.
Message/account/platform policy lookup is supplied by the actual host. The
workflow calls this reader again for execution instead of reusing preparation
permission, and checks the retained journal source before each execution.

The lower-level provider, publication and synchronization regressions remain
applicable; a combined production account/provider run is deferred to the
implementation's later review. No remote publication or master synchronization
is performed merely by adding this entry.
