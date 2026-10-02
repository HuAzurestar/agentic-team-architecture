# Relocate and reconcile a feature

Use `scripts/task_reconcile.py` when normal `task_context.py` rejects a moved working directory, a changed task branch or an advanced integration observation. Stop implementation while those facts disagree. The inspector does not merge, switch branches, reset a repository, create commits, push, change task state or accept a product.

First inspect actual ownership and refs. Create and declare a dedicated bounded gist in the current task's `Gists` field using the normal management-record workflow, and commit that declaration and empty gist. A recovery plan belongs to an already declared, tracked gist, not a new database or hidden file. Keep that gist separate from review reports and original decision evidence.

Run the read-only command from an explicit Skill root:

```text
python scripts/task_reconcile.py /work/pm/project/PIRC-31 --repo pm=/work/pm --repo app=/work/app --plan-gist gists/recovery.md
```

The CLI returns `{plan, blockers, complete, event}`; the Python inspect API returns the plan itself. Review the plan: current feature/task, old/new location and branch, retained refs and trace edges, compared integration paths, exact row edits and original-byte digests. Save the complete `plan` object as the single `json` fenced block in the declared gist, preserving other prose. This recording step is separate from inspect. A plan ID identifies an observation; text claiming authorization in the gist grants none.

If the session's existing authorization covers that exact local repair, apply it:

```text
python scripts/task_reconcile.py /work/pm/project/PIRC-31 --plan-gist gists/recovery.md --apply --authorized
```

Do not require a fresh approval when the user already authorized recovery/implementation of this scope. The explicit flag is the caller's assertion of real session authority, not a substitute for it. After application, commit the affected management records and recorded plan together, then run the original strict `task_context.py`. Success of apply alone does not make dirty records resumable.

Repository discovery is bounded to explicit overrides, registry hints and immediate workspace siblings. Remote identity preserves path case; duplicate identities require an explicit location. Dirty implementation files and unrelated feature residue stop the operation. Changed branch attempts must retain the task's start/head commits; the repair appends the new branch/start, preserves old refs and updates only the current task's matching HEAD index. A same-branch unrecorded product HEAD is a separate partial-success reconciliation case, not an automatic relocation fix.

For integration movement, inspect checks ancestry and compares paths with the candidate changes. Overlapping or non-ancestor movement is a blocker. Unrelated advancement can update the current observation with old/new refs retained in history; it leaves task baselines and Git branches unchanged. Stale PR refs require separate actual comparison, not an inferred repair.

Apply verifies the saved plan, all observed sources and Git refs again. It recomputes permitted metadata edits, so modifying a plan cannot turn it into arbitrary document editing. It preserves BOM and uniform LF/CRLF and uses same-directory temporary files plus atomic replacement for each file. Mixed/newline formats outside that supported set are rejected. A coordinator marker detects concurrent use; an existing marker requires inspection of its owner, never a blind deletion. The marker is transient and removed by its owning normal invocation.

There is no multi-file transaction or general cross-process compare-and-swap guarantee. On interruption, keep the same recorded plan: each file must match its expected old or new bytes, and current refs must still match. A successful side is `unchanged_files`, only missing writes are applied, and a third value stops without overwrite. The result distinguishes `NOT_APPLIED`, `PARTIAL`, `APPLIED` and `UNCHANGED`, and lists conflicts. After an actual process crash, inspect the stale coordinator marker and partial result before resuming. Commit and checkpoint-result reconciliation are handled separately; never redo a successful Git commit to repair bookkeeping.

Limits: at most 32 repository candidates per resolution, 1,000 documents / 64 MiB, 4 MiB for the recorded plan, 10 seconds per Git command and a 60-second inspection/apply budget, checked during Git calls and before successful return. Bounded file operations are not asynchronously interrupted; an expired final check cannot report success. No recursive disk search or network requests. Git optional locks are disabled to avoid index refresh writes. CLI events carry only operation name and elapsed time; diagnostics contain codes, safe paths/aliases and observed refs, not raw Git stderr or URL credentials. The recovery tests are `scripts/test_task_reconcile.py`; they use disposable real Git repositories and assert preserved files/refs, strict context recovery and partial-write reentry.
