# Recover a partially completed checkpoint

Use the optional operation mode when a checkpoint must be recoverable across a Git commit and separate management writes. The original checkpoint CLI remains compatible; it does not retroactively acquire an intent record. Commit bookkeeping and bounded remote readback are supported below. An unknown remote result must never be retried as a create/upload.

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

## Read back a remote result without repeating the write

The actual host records a remote-write operation in the same declared gist. Required fields remain operation_version, operation_id, kind, feature, task, authority_source_ref, target_identity, expected_source, owned_paths, intent_ref, observed_result and recorded_fields. Use kind remote-write, empty owned_paths, and target_identity containing only a provider_key chosen by the host. expected_source contains an exact version string, a content_digest, or both. content_digest is SHA-256 of UTF-8 canonical JSON with sorted keys, compact separators and the exact title/body strings; an explicit null body from the provider is treated as an empty body. Use the helper's content_digest function to compute it. observed_result carries the actual previously returned object_id when available, not a guessed match by title.

The GET-only JSON adapter is `scripts/remote_lookup.py`. Construct ObjectReader from the host's actual authorized URL template and credentials; operation text supplies no URL or credentials. The template must contain one {id} slot in its HTTPS path and no query, fragment or userinfo. Field names for ID, title, body and version are host-configurable; unsupported response shapes are rejected instead of guessed. A host can use this port without SMMD or another service. The CLI exposes the same port:

```text
python scripts/task_reconcile.py /work/pm/project/PIRC-31 --repo pm=/work/pm --repo app=/work/app --plan-gist gists/remote-operation.md --operation-id 00000000-0000-4000-8000-000000000001 --lookup-provider approved-provider --lookup-url https://approved.example/objects/{id}
```

Supply real endpoint/ID values under existing read authority; this example is not a live provider assertion. An optional host-selected bearer token environment variable is named by --lookup-token-env; token values never enter the gist or result. Non-default response fields use --lookup-id-field, --lookup-title-field, --lookup-body-field and --lookup-version-field. Plain HTTP is restricted to explicit loopback tests with --lookup-allow-loopback-http. No redirects, proxy inference, create/upload/update methods or write retries exist in this reader.

An absent unique ID returns REMOTE_OUTCOME_UNKNOWN without a query. With an ID, query only that object and compare its actual ID and intended content/version. A mismatch returns a conflict, not success. Network failure, read timeout, invalid/oversized response or unresolvable outcome remains unknown; at most one transient read retry is allowed. Default connect/read/total budgets are 3/10/15 seconds, including a 0.5-second reserve for worker cleanup. A short-lived spawned worker makes DNS/connect and stalled reads cancellable; it is joined/terminated and not a persistent service. Query bodies are capped at 1 MiB and returned evidence at 8 KiB; output contains only safe IDs, version/digest, counts and diagnostics, never response text, raw exception messages or credentials.

After valid readback, --apply --authorized permits only recording the reference in the declared gist. Sources and Git observations are checked again before that atomic local write. The original observed_result is retained as initial_observed_result. Evidence is explicitly current-readback-not-call-receipt: it proves the current object matches the intended state, not general exactly-once execution or a reconstructed receipt of the earlier call. Repeating completed record-only recovery may query again but performs no duplicate local write when evidence is unchanged. Commit management evidence and run strict recovery afterward.

`scripts/test_remote_lookup.py` exercises real loopback HTTP transport, remote outcome cases, read-only CLI/application, deadline worker cleanup and injected connection stalls. This is not a live forge/provider or independent acceptance test. Standalone save/record kinds still require their own covered reconciliation path; their mere presence in the record vocabulary does not make that path implemented.
