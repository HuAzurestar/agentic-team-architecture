# Original review input

Coordinator: copy to a fresh per-attempt input file and replace every `{{...}}` before use. Include only current normative intent, real authorization and original evidence, not old findings, scores, fix hints or author conclusions. This declaration routes input; it does not certify completeness or cleanliness.

- Evidence type: original
- Input ID: {{input_id}}
- Review scope: {{review_scope}}
- Scope source/version: {{scope_source_version}}
- Requirement/design version: {{intent_version}}
- Skill version: {{skill_version}}
- Environment: {{environment}}
- Authorization source/version: {{authorization_source_version}}
- Action boundary: {{permitted_and_prohibited_actions}}
- Release condition: {{evidence_or_human_decision_required_to_release_wait}}

Use the authoritative design scope in a long feature; this packet cannot override it. If no wait exists, explicitly say so without inventing authorization. Missing or inseparable boundaries remain an input limitation.

## Candidate versions

| Repository / identity | Role | Branch | Base SHA | Head SHA | Verification |
| --- | --- | --- | --- | --- | --- |
| {{repository_identity}} | {{role}} | {{branch}} | {{base_sha}} | {{head_sha}} | {{observed_or_unverified}} |

One row per relevant repository; do not substitute a moving branch alias for a SHA. Long-feature recovery verifies its registered refs separately.

## Normative requirements and design

| Point | Current promise / acceptance condition | Source and version |
| --- | --- | --- |
| {{point_id}} | {{normative_excerpt}} | {{source_version}} |

Describe the delta as reuse/adaptation/new work and state applicable user tasks and invariants. Preserve approved meaning; do not include previous review outcomes.

## Original evidence and permitted reproduction

| Artifact / location | Observed version | What it demonstrates / how to reproduce | Limits |
| --- | --- | --- | --- |
| {{original_artifact}} | {{artifact_version}} | {{original_observation_or_safe_command}} | {{evidence_limits}} |

## Missing inputs and owner

| Missing evidence / scope limitation | Effect on review | Owner / release condition |
| --- | --- | --- |
| {{missing_input_or_explicit_none}} | {{impact}} | {{owner_and_next_action}} |

Do not resolve a missing fact by copying a historical report into this packet. Give the reviewer code, raw observations and normative intent, not the intended answer.
