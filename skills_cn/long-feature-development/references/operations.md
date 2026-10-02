# Recover a partially completed checkpoint

Use the optional operation mode when a checkpoint must be recoverable across a Git commit and separate management writes. The original checkpoint CLI remains compatible; it does not retroactively acquire an intent record. This local implementation handles commit bookkeeping only. Remote-write query/reconciliation is not implemented here yet; an unknown remote result must never be retried as a create/upload.

First declare a dedicated, tracked gist in the current task and commit that declaration and source records through the ordinary management workflow. Do not mix relocation plans, unrelated reports or secrets into this gist. An empty heading/prose is sufficient; no operation database or mandatory feature initialization file is added.

```text
python scripts/task_checkpoint.py /work/pm/project/PIRC-31 DEV-01 app --repo pm=/work/pm --repo app=/work/app --include src/owned.py --summary "save parser work" --resume-action "Run focused verification" --operation-gist gists/checkpoint-operation.md --authority-source-ref session:actual-user-request
```

The authority reference identifies actual caller authorization; a string in Markdown is not permission. Existing session authority must cover the exact commit and owned paths. This command does not push, merge, or publish. The implementation in `scripts/task_operation.py` records operation-v1 intent before committing, including an operation UUID, actual repository/branch identity, prior HEAD, owned file blobs, intended tree and source evidence. The commit carries an Operation-Id trailer. Observed result and recorded fields describe side effects; they are not new task states.

Source snapshots are bounded byte evidence in the declared gist, not a replacement authority. Recovery verifies their text against the retained management commit and checks source digests, retained start ancestry, actual commit parent/tree/paths/blobs, current HEAD, repository identity and management residue. Do not place secrets in source management records; credential-bearing registered URLs are rejected. The record has a 4 MiB cap and at most 1,000 operation entries. Lookup examines only the recorded start..HEAD range, capped at 1,000 commits; it never guesses from a similar subject.

If interrupted, inspect the exact operation UUID from that gist:

```text
python scripts/task_reconcile.py /work/pm/project/PIRC-31 --repo pm=/work/pm --repo app=/work/app --plan-gist gists/checkpoint-operation.md --operation-id 00000000-0000-4000-8000-000000000001
```

When the implementation commit exists, this is read-only confirmation, not a new commit. Under actual authorization to repair those records, repeat with `--apply --authorized`. It records the observed commit and repairs only missing task detail, TASKS index/topology and STATUS working-HEAD fields. Successful files must match the expected result; missing files must match original bytes. Any third content value stops without overwrite. Repeated completed recovery performs no atomic writes or Git commits.

When the original HEAD remains and no matching commit was observed, inspect reports `resume-authorized-checkpoint`. Only then may the original checkpoint invocation be resumed with its exact `--operation-id` and original scope/summary/resume values. It verifies owned working bytes and staged tree before committing; unexplained staged work or extra paths are never silently absorbed. Changed HEAD, commit content or source requires investigation, not automatic reset/rebase.

One coordinator owns the transient .operation.lock marker. An existing marker is a conflict: inspect its owner and partial effects before any cleanup, never blindly delete it. Individual file writes are atomic, not a multi-file transaction or cross-process CAS. A commit timeout can mean unknown outcome; inspect the durable UUID and actual Git evidence before retrying. After recovery, commit the management records and gist together and rerun strict task_context. No power-loss guarantee extends past the last successfully persisted checkpoint.

The real-Git regression suite is `scripts/test_task_operation.py`. It injects interruptions before commit, after commit/before detail, after detail/before index, and after index/before final recording. It also covers unowned residues, tampered intent, third-party content, missing checkpoint structure, moved refs, bounded lookup, CLI inspection/application and zero-write repeated recovery. These are author tests, not independent review or a live remote-provider test.
