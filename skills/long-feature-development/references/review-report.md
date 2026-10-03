# Complete report and finding ledger

Use `review_report.py` after collecting a report, not instead of an independent
review. The pure `compute_report(raw, related_reports=(), verified=None)` validates
the complete report and computes its counts. `raw` is a JSON-compatible object,
a JSON string, or one top-level `report-v1` Markdown fence. It never reads files,
contacts a provider, mutates the input, dispatches a reviewer or changes a task.

## Identity and original sources

`report_ref` is the stable logical ID assigned to one immutable report (for
example a UUID-based ID). It is not the hash of the report that contains it.
The complete finding key is `{feature, report_ref, attempt_id, finding_id}`.
All four fields are mandatory in `duplicate_of`. Check IDs are report-local.
Report identities must be unique in a supplied set; same-named findings from
different reports/attempts remain distinct unless explicitly linked with proof.

Actual source refs `{path, sha256}` bind original bytes separately. The read-only
CLI `python scripts/review_report.py <feature-directory> gists/report.md
[--related gists/old-report.md]` checks the current review task's Gists declaration,
loads only explicit related reports, refuses aliases/unsafe paths and rechecks
its read set before output. Output includes the actual report source hashes.
Never overwrite an old report or retarget its SHA. Preserve its original summary,
findings and provenance even when a new report records a recheck.

The pure calculator validates evidence reference syntax, not the existence,
truth or independent provenance of referenced material. Its output explicitly
has `source_evidence_verified=false` and `quality_assessed=false`. The CLI verifies
the report files but does not fetch their evidence. A quality consumer must load
and verify every required source, actual target/attempt/checklist, required scope
and host facts before using this schema result. A green schema result, ratio or
REVIEW DONE is never release permission.

## Full schema

Use the REVIEW-REPORT template. Top-level fields include report/packet/attempt
identity, feature/task, literal target refs, checklist, reviewer and context,
evidence refs, checks, findings, diagnostics and summary. Missing full-schema
fields return `LEGACY_EVIDENCE_INCOMPLETE`; old minimal recovery reports remain
readable through `review_resume.py` and are never silently upgraded.

The report also records `result` (SUCCESS/FAILED/BLOCKED) and its nonempty `reason`.
These are report conclusions, not new task states; a delivered FAILED report may
still make its REVIEW task DONE. SUCCESS is inconsistent with an empty applicable
set, a known open blocker, required FAIL/UNKNOWN/NOT-RUN, or unresolved current blocking
diagnostics and is rejected. Group/core-scenario impact belongs to the reviewer's
evidence-backed reason, not a guessed numeric P1/P2 threshold. A reported SUCCESS
still needs actual host/source/quality validation; it is never self-authorization.

Each check has `id`, `outcome`, `required` (Boolean), `scope_ids`, `evidence_refs`,
`reason`, `next_action`, and `finding_ids`. Only PASS/FAIL/UNKNOWN/NOT-RUN/N/A are
allowed. PASS/FAIL need evidence; FAIL needs linked findings. N/A needs an
applicability reason; UNKNOWN/NOT-RUN need both a reason and next action. Supply
`scope_exception_ref` when a human scope decision is needed. A quality consumer
must compare `required`/scope/N/A against the actual packet and approved intent;
the report cannot remove required work by declaring it optional.

Check reuse optionally adds `reuse` with `prior_check_ref` (full feature/report/
attempt/check key), nonempty `diff_refs`, `dependency_refs`, and `reviewer_basis`.
These are required evidence references, not automatic permission to reuse an old
PASS. A current-target quality check must verify actual diff, unchanged scope and
dependencies and the reviewer's basis. Whole-report ancestry alone is insufficient.

Each finding has id, P0/P1/P2 severity, Boolean blocking, open/addressed/closed
status, description, evidence, affected checks, resolution/verification fields,
nonblocking rationale, requirement-violation flag and severity history. Check ↔
finding links must agree in both directions. Identical repetitions of one finding
ID count once; conflicting repetitions fail. Duplicate check IDs always fail.
`duplicate_of` also needs `duplicate_reason` and `duplicate_evidence_refs`; title
similarity is never deduplication proof. Missing targets and cycles fail closed.

P0 must be blocking. P1/P2 affecting required failed checks or confirmed intent
cannot be marked nonblocking without a current verified scope exception. Other
nonblocking suggestions still need a reason.
Every finding has `follow_up`; nonblocking findings need a concrete nonempty
follow-up arrangement as well as their no-impact rationale. Addressed requires
a resolution ref; closed additionally requires a different verifier from the implementation author,
a verification ref and exact verified target refs. Those claims alone do not
close anything: absent trusted host evidence the ledger keeps it open and emits
`CLOSURE_UNVERIFIED`. Old closed claims do not transfer to a new candidate.

## Trusted facts and counting

`VerifiedReportEvidence` is an in-process host boundary, not a Markdown schema.
Never deserialize it from a report, JSON assertion or author self-attestation.
The host checks actual independent closure, human scope exceptions and reviewed
severity changes before constructing it. Each key is bound to the exact canonical
`report_digest(raw)`, including target and content. A changed report invalidates
those host facts. The CLI deliberately provides no import switch for them.

Severity history entries contain from/to, reason, independent verified_by,
verified_ref and target_refs. The chain must be continuous and end at the claimed
current severity. Without current host verification the most severe historical
level remains effective; a P2 duplicate cannot hide a P0 root. Actual approved
changes preserve history. Closure of a duplicate group needs verified current
closure for every member appearing in the current report. Historical-only roots
remain visible; without a current member, closure needs verified closed claims
for all supplied members on the exact current target. Other historical roots
remain open until current evidence accounts for them. An actual
current human exception may remove blocking, but never claims the issue fixed.

ALL = PASS + FAIL + UNKNOWN + NOT-RUN; total = ALL + N/A. ALL=0 yields ratio=null.
The current report supplies check counts; the explicit complete ledger supplies
deduplicated severity/open counts. `discovered_current`, `inherited_current` and
`historical_only` distinguish provenance. Original report diagnostics are retained
as source-tagged codes, without leaking their prose into telemetry.

Reported diagnostics have code/reason and optional Boolean blocking (default
true). Explicit informational diagnostics may be nonblocking; known missing
scope/evidence, source change, unverified independence and resource exhaustion
cannot be disguised as informational. Native closure/severity diagnostics keep
their finding group's effective blocking status instead of inventing a blocker
for an otherwise explicitly nonblocking issue.

`summary: {}` requests a fresh derivation; a supplied current summary must exactly
match the computed `{valid, counts, ratio}`. Related historical summaries are
never trusted for arithmetic or copied into the new report. On validation or
budget failure, summary.valid=false, counts=null and ratio=null; no partial 100%.

## Limits and tests

Limits apply across the entire explicit report set: 10000 checks, 10000 finding
observations, 30000 links, 64 MiB and two seconds of computation. Evidence, scope,
check/finding, duplicate and history references all consume link budget. Hash maps
and an iterative three-colour traversal avoid pairwise text comparison and Python
recursion for duplicate chains. No background work or SQL state is introduced.

`report.validate` / `report.summarize` events contain counts, target refs and error
codes, never finding text, evidence content or authorization prose. Use
`test_review_report.py` and the bundled `scripts/fixtures/review-report.json` for
F04-T07/T08/T09 and refusal paths. These fixtures are explicitly synthetic; they
do not prove actual independent review, accepted scope or source availability.
