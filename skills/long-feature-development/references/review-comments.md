# Editable review comments

`review_comments.py` provides a bounded in-memory Markdown codec, selection and conversion preview. It does not read remote authority, publish comments, change point decisions, update tasks, assess quality, or prove verification merely because a record says VERIFIED. Those workflow integrations remain required.

New records have `rv_id=RV-<UUID>`, `Target={feature,ref,selector?}`, `Basis={source_key,source_text,git_basis?,line_start?,line_end?}`, `Status`, `Comment`, and optional `Resolution`/`Verification`. Status is PENDING, ADDRESSED or VERIFIED. A record's identity is `(feature,reviews_ref,rv_id)`; the review document reference is supplied independently from its commented target. New UUIDs are allocated once by `new_review`; an uncertain publication must search that same UUID before creating another.

## Safe Markdown format

The document begins with `# Reviews`. Each `## RV-<UUID>` block contains `- Status: PENDING` and dotted Target/Basis scalar fields. Every scalar is a JSON string, including decimal line numbers, for example `- Target.feature: "PIRC-31"` and `- Basis.line_start: "1"`. Git basis, when present, is a full actual SHA, not the REVIEWS document version. Source text is not stored in a scalar: it appears under `### Source`. Comment, Resolution and Verification use equally named level-three headings. Every text line, including empty lines and apparent Markdown headings, is prefixed with `> `. Newline semantics are LF; CRLF document input is accepted and its original is retained. Unknown/unquoted content, duplicate fields/IDs, invalid versions or cross-feature content fail closed, rather than being silently discarded.

`parse(text, feature=..., reviews_ref=...)` returns records, linear identity/target indexes, original source and its digest. `select(parsed)` defaults to PENDING; explicit status filters read the requested states. Explicit RV IDs without a status filter read any state, and unknown requested IDs are errors.

## Legacy and conversion

Known old `OPEN/open`, lowercase statuses and `closed` are mapped only in memory. A `- Basis: <free text>` field is retained in legacy metadata; its provenance is unresolved, never guessed. Parsed legacy records carry `_legacy` and cannot be directly rendered. Preserve the original source. Explicitly resolve the Basis, remove the legacy marker in the proposed copy, and call `preview_conversion(original, proposed, ...)` before editing. The preview retains the original digest, requires unchanged identities, supplies the complete proposed document and a bounded before/after changed span, and always returns NOT_APPLIED. A truncated diff is not full review; display the complete affected material before any later authorized conditional write. Removing the marker is not authorization or proof that a user saw the preview.

Each operation accepts at most 1,000 comments/4 MiB; parsing/rendering has a 2 CPU-second limit. The codec performs no I/O or logging. It deliberately does not implement platform authority, conditional writes, draft recovery, stale-basis checks, or agent consumption acknowledgments yet.
