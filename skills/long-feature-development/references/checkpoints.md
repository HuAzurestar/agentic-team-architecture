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

## Optional review breakpoint

The [read-only review recovery helper](../scripts/review_resume.py) is called by full context validation; its [real Git/process tests](../scripts/test_review_resume.py) exercise version mismatch and source preservation. It restores references and remaining findings, not report quality, independent-review authority, finding closure or acceptance. Features without a review declaration need no new file or service.

An active task may declare one top-level `- Review recovery: gists/resume.md`. Declare that file and every referenced packet, report, checklist and original evidence in the same task's `- Gists:`. References are objects with `path` (feature-relative, already loaded) and `sha256` (digest of exact raw bytes, including newline encoding). No URL is fetched. Missing declared evidence fails with EVIDENCE_MISSING; changed digests, targets or attempts fail with STALE_REVIEW. Preserve old reports and create new attempts for new candidates; never edit an old target to transfer its PASS.

The recovery gist contains a whole JSON object, or one explicitly tagged `review-resume-v1` fenced block, with `schema`, `feature`, `review_task`, `attempt_id`, `target_refs`, `packet_ref`, `report_ref`, and `checklist_ref`. `target_refs` maps registered repository names to full 40-character commit SHAs. Each must exist in the actual repository and equal its observed working HEAD. Packet/report documents use whole JSON or explicit `review-packet-v1` / `report-v1` fences and the matching `schema` value. Their feature, review task, attempt, target refs, checklist ref and packet ID must agree. This validates only the recovery fields of these documents, not the full F04 report schema.

The report also carries nonempty `evidence_refs`, `findings` and a `summary` object. Findings have report-scoped `id` and `status` (`open`, `addressed`, `closed`). Identical repeated IDs within the same report are deduplicated; contradictory repeats fail. Addressed remains open. If summary or recovery gist includes `open_finding_ids`, it must equal the derived set or recovery fails with REVIEW_SUMMARY_MISMATCH. Other quality counts, severity policy and independent closure evidence remain the report assessor's responsibility.

Successful focused output includes `review_recovery`: report/checklist refs, attempt, actual candidate refs, report-scoped open finding references and `next_review_action`. Open findings yield `resume-rework`; otherwise `needs-independent-recheck`, never acceptance or merge permission. `quality_assessed` is always false. Default Markdown includes the candidate and next action; JSON includes the same projection. CLI stderr emits a metadata-only `review.resume` event with digest/count/error and elapsed time, not report prose. A fresh subprocess verifies persistence but is not evidence of an independent Agent review session.

Use the optional [operation recovery](operations.md) mode when a local commit and separate bookkeeping need resumable intent. Preserve old CLI behavior for existing callers; do not claim that a legacy checkpoint has operation evidence it never recorded.

For relocation, branch identity and integration-observation mismatches, use the read-only plan and scoped apply described in [reconciliation](reconciliation.md). Commit the resulting management records before rerunning strict recovery. A partial apply is not permission to overwrite a third version or repeat a successful external operation.
