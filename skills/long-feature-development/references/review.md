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
   This helper does not validate report outcomes or authorize PASS; use complete
   report validation before interpreting counts or quality eligibility.

The event `packet.build` contains only attempt ID, source/check counts, byte
count, elapsed time and error codes. CLI output omits packet/source prose and
authority text. Don't log the full input on rejection.

Legacy minimal `review-packet-v1` recovery records remain readable by
`review_resume.py`; they are not complete handoff packets. Do not silently upgrade
them or invent missing independence evidence. Run [packet tests](../scripts/test_review_packet.py) plus
the existing review/context regressions when changing this boundary. Synthetic
host fixtures verify rejection logic, not F04-T01's real blank-review outcome.
