# Decision evidence and applicability

`scripts/decision_evidence.py` is a pure applicability checker. It does not read sources, write decisions, update task states, or assess quality. Source adapters and policy integration are still required.

The `decision-evidence-v1` record retains `decision_id`, `feature`, `human_source_ref`, `actor`, timezone-aware `received_at`, `decision_kind`, `target_ref`, `exact_scope`, `outcome`, `original_reply`, and `approved_body`. A target identifies its source and either a full Git SHA or an actual provider-native conditional version. Never fabricate a Git SHA for a provider object.

- `point` binds exactly one REQ/SOL ID. Its outcomes are CONFIRMED, REJECTED, OUT-OF-SCOPE, INFEASIBLE, and REOPENED. Split enumerated multi-point replies into individually bound records and commits.
- `acceptance` permits CONFIRMED, REJECTED, or REWORK. A negative decision can be recorded without granting merge authority.
- `scope-exception` permits APPROVED or REJECTED for the exact enumerated scope; it is not point approval or general acceptance.

Supply current material from an independently verified source read, not by copying the decision's claimed target. Feature, kind, scope, and source must match. A changed version or body produces `DECISION_STALE`; changed bodies produce a bounded linear changed-span diff. Preserve the original reply and approved material. Applicability never implies that a write occurred or that review, testing, or merge conditions are satisfied.

`VerifiedDecisionSource` is host-only evidence, not authentication by Python type. Construct it only after actual conversation/platform readback verifies the human's identity, authority, interpretation, reply, and approved material. It binds the whole record's digest and the readback reference. Never create it from a Markdown/JSON claim that the source is human. Synthetic test instances are not real decisions. No importer or source-verification adapter is provided by this pure module.

The combined record/current-material budget is 4 MiB, scope is limited to 1,000 explicit IDs, and the CPU budget is 2 seconds. Diffs retain at most 4,096 characters per side and report truncation. Budget or schema failures deny applicability. The event contains only decision ID, applicability, and reason codes, never reply, body, actor, or diff text.
