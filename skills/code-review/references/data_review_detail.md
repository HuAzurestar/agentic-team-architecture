# Weak review: data

Derive invariants from requirements before inspecting author assertions or declaration fields.

## Content points

- Do amounts, counts, ownership and derived totals preserve the promised business invariants?
- Are duplicate links, cycles, missing prerequisites and inconsistent states handled without losing or double-counting contributions?
- Does validation verify real conditions rather than trust qualified/closed/same_source-style declarations?
- Is the transaction boundary the complete business operation, with network work and partial commits handled appropriately?
- Can read-modify-write or check-then-act race, lose updates, double-create or double-charge?
- Are locks effective across the actual process/deployment boundary, with sound lock order and transaction behavior?
- Are requests, queue redelivery, retry, restart and restore idempotent where promised?
- Do stale versions, out-of-order messages and conflicting writers have a defined outcome?
- Are preview, validation, submission, import and historical re-enable paths evaluating the same rules?

## Experiments and scan

Trace calculations, state mutations, commit/rollback/save/flush and unique constraints. Try empty/null/zero/negative/extreme inputs, unordered and duplicate relations, a relation cycle, missing condition and partially completed state. For writes, attempt sequential duplicate requests, parallel duplicates, stale-version writes and restart between steps. State expected invariant and observed result; only run on permitted isolated data. Inspect siblings sharing the same root cause.
