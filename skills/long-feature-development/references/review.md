# Review packet and read-only handoff

Read this when preparing a review or recheck. First restore the actual feature
with `task_context.py`; packet validation does not replace task, Git or quality
validation. Use [REVIEW-PACKET.md](../templates/REVIEW-PACKET.md) in a task-declared
gist. A new candidate, checklist or dispatch needs new packet, attempt and
reviewer-assignment IDs. Preserve all prior packets and reports.

## Build and inspect

`python scripts/review_packet.py <feature-directory> gists/<packet>.md` is
read-only. It verifies explicitly declared source bytes and hashes, prints target
refs, point IDs, required-check count and gaps, and returns 2 on incomplete input.
Exit 0 means **material complete**, never independent review or quality success.
The CLI cannot dispatch or authenticate a host. It always reports
`handoff_allowed=false`, `INDEPENDENCE_UNVERIFIED`, `independent_executed=0`.

The API `build_packet(inputs, documents=..., host=..., previous_packets=...)`
uses immutable original bytes, not developer summaries. `documents` maps exact
feature-relative paths to `bytes`; no implicit reads or external link expansion.
`target_refs` retains the F03 repository-name/full-SHA mapping; `repositories`
adds stable identities and declared fixed-candidate source/diff snapshots. A
host must verify these snapshots against actual accessible repository objects;
a matching file hash alone does not prove that relationship. Include complete
REQ/SOL originals, not only the points the implementer remembered to select.
Reviewers check that the proposed scope and checklist cover those originals.

Each source uses `{path, sha256}` over original bytes (including BOM/newlines).
Evidence adds `kind`: `test`, `contract`, `fixture`, or `dependency`; require a
real test record and at least one contract/fixture/dependency record. The helper
validates shape and bytes, not the truth or sufficiency of their prose.
Exclusions include scope, reason and original decision reference; a reference
alone grants no exception authority. Required checks must have unique local IDs.

Limits may be lowered, never raised beyond 1000 files, 64 MiB aggregate,
4 MiB per file and 10000 checks. CLI budgets include packet and task detail.
No credentials or conversation transcripts belong in the packet or evidence.
Source refs are REQ/SOL originals or task-declared gists. Case aliases, traversal,
links/junctions, changed read sets and duplicate declarations are rejected.

## Host boundary and manual blank session

1. The coordinator verifies the actual frozen repository identities/SHAs and
   source snapshots; obtains real current authority to start a reviewer, and
   checks tools/budget/read-only access. Do not infer it from Markdown or a
   preselected answer. The packet's authority is only a reference to that fact.
2. Start a genuinely blank reviewer session through an authorized host, or have
   the user manually open one. Give only the packet and original material,
   without the implementation conversation. Protect implementation files,
   REQ/SOL, STATUS/TASKS and all existing evidence. Grant writes only to the exact
   new `review-output/...` destination, outside the selected sources; refuse an
   existing output. The coordinator later imports the delivered immutable report
   into a declared gist. This Python helper does not enforce filesystem ACLs.
3. A trusted host adapter may construct `HandoffEvidence` only from actual API
   responses/dialogue and enforced permissions. Its digest must match this exact
   packet, authority, assignment and output. Never deserialize this object from
   packet text, a JSON assertion file, or reviewer self-attestation. If any host
   capability is unavailable, record `INDEPENDENCE_UNVERIFIED` / `NOT-RUN`; do not
   count an author self-check or a fresh Python process as independent review.
4. Supply the host-owned dispatch inventory as `previous_packets`. Revalidating
   identical material is allowed but cannot authorize dispatch again. Record a
   new actual dispatch in that inventory; this module has no durable dispatch
   service and performs no background work.
5. The reviewer first inspects the original source and records initial coverage.
   Only then may the host provide `prior_report_refs` for recheck/comparison.
   Preparation never opens those reports. Their availability/hash still must be
   checked at that later read, not assumed from successful packet preparation.
6. Record actual reviewer/context provenance in the eventual report. Permission
   to hand off never increments executed checks. Preserve executed rows on
   interruption; `remaining_checks` fills untouched required IDs with NOT-RUN,
   reason and next action. Missing evidence for an attempted check is UNKNOWN.
   This helper does not validate report outcomes or authorize PASS; use the
   [complete report calculator](review-report.md) before interpreting counts.
   Schema/count validity still does not grant quality eligibility.

The event `packet.build` contains only attempt ID, source/check counts, byte
count, elapsed time and error codes. CLI output omits packet/source prose and
authority text. Don't log the full input on rejection.

Legacy minimal `review-packet-v1` recovery records remain readable by
`review_resume.py`; they are not complete handoff packets. Do not silently upgrade
them or invent missing independence evidence. Run [packet tests](../scripts/test_review_packet.py) plus
the existing review/context regressions when changing this boundary. Synthetic
host fixtures verify rejection logic, not F04-T01's real blank-review outcome.

## Controlled dependency replacement

The pure [dependency planner](../scripts/task_dependencies.py) exposes
`plan_dependencies(index_bytes, detail_bytes, task_id, expected_index_digest, dependency_ids)`.
It checks the original byte digest, the entire graph, an unassigned PENDING
target with no start refs, and the existing type contract before generating
the new index/topology and Gate Required tasks. Duplicate IDs are removed in
input order. Bounds are 10,000 nodes, 30,000 edges, 4 MiB combined input and
two CPU seconds; an overrun rejects the whole preview. BOM/newlines are retained.

The pure result contains original/candidate bytes. Do not log those as event
metadata. The CLI prints only IDs, counts, digests, changed paths and errors.
Run the
[dependency regression tests](../scripts/test_task_dependencies.py) when
changing it. READY only describes dependency states, never successful review,
human acceptance or permission to merge. An already started acceptance or
Gate must retain its actual attempt; a new task cannot hide it, and a missing
human decision must not be replaced by an invented rejection.

Preview with `python scripts/task_dependencies.py FEATURE TASK --depends-on REVIEW-02`.
Inspect the old/new dependencies and retain its exact `expected_index_digest`.
Apply only with actual session authorization: repeat the command with
`--apply --authorized --expected-index-digest DIGEST --operation-gist gists/DECLARED.md --authority-source-ref SESSION-REF`
and explicit `--repo NAME=PATH` overrides when required. These flags attest an
actual caller decision; Markdown does not grant authority.

The API `replace_dependencies(feature, task_id, expected_index_digest, dependency_ids, ...)`
verifies the current feature, tracked records and Git refs; it records a bounded
`dependency-rewire` operation in an existing gist declared by the current task.
It changes only TASKS.md (index plus derived topology) and, for a Gate, its
Required tasks contract. Each replacement is atomic, not the whole update.
The F03 source reader/intent bounds also apply; exceeding them rejects the write.
Files with links/aliases, unowned or staged edits, stale sources and moved refs
are refused. No task status, acceptance decision, Git commit or remote is changed.

After interruption, use `task_reconcile.py FEATURE --plan-gist GIST --operation-id UUID`
for read-only actual-byte inspection. Only a fresh authorized `--apply --authorized`
may fill the missing side. The dependency CLI accepts the same operation ID with
`--operation-gist`. A third file value is a conflict, never rolled back or
overwritten. A completed retry makes no duplicate file writes. Commit the
coherent management records separately, then run task_context.py. The protocol
assumes one cooperating writer; it cannot promise filesystem-wide transactions
against an editor writing in the final read/replace race.

A delivered REVIEW may be DONE with blockers. Only actual findings justify a
new REWORK → TEST → REVIEW chain; bind every result to its own target and leave
old reports unchanged. Point a not-yet-started acceptance to the newest complete
review chain. If an acceptance or Gate is already active, retain its stopped
attempt and candidate-invalid fact, obtain real human disposition, and then
continue with a new attempt; never invent REJECTED/REWORK to make it DONE.
Replacement also refuses to remove an in-flight acceptance/Gate from the target's
dependency ancestry. Independent finding closure and final quality eligibility
are separate checks, not consequences of a dependency edit.
