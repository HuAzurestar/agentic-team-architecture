# Long feature document authority

Choose one editing authority for each document before saving or publishing it. A Git commit is a snapshot; a remote copy is a replica unless the table explicitly makes that remote object the source. Record a repository by its identity and full commit SHA, since a local path alone does not identify the source.

## Authority register

Use one row per document, even when the project uses a hybrid strategy.

| Field | Meaning |
| --- | --- |
| `environment/project` | The named project and environment; never infer it from a directory name. |
| `document` | Stable document ID and exact repository path or platform object ID. |
| `source` | The single editable authority, including repo identity or provider and object ID. |
| `provider_condition` | Optional observed native revision or other verified conditional write value. Absence does not authorize an unconditional remote update. |
| `original_evidence` | Source content hash or exact object revision observed before editing. |
| `replicas` | Named exports, platform copies, or published locations, with their last known result. |
| `maintainer` | Who may authorize source edits and a change of authority. |
| `rule_ref` | The strategy and task decision that selected the source. |

Git first: edit the repository Markdown. A commit fixes a reviewable snapshot; publishing a platform copy is a separate operation. Provider first: edit the exact provider object through a verified native conditional operation or an explicit human procedure; exported Markdown is a replica. If the provider cannot enforce the needed condition, keep programmatic access read only. Hybrid: select Git first for some documents and provider first for others, while retaining one source per document.

Before switching a document's source, stop writes to the old source, compare unpublished changes, record the last observed source ref and the intended new source, obtain the maintainer's decision, then update this register. A newer timestamp never chooses the winner. Do not run an implicit two way sync or overwrite either side to make them match. The same fictional Beacon project is routed under all three strategies in [the worked example](../../examples/long-feature/authority-routing.md).

## Cross repository refs

Write `repository identity@full SHA:path#task-id`, for example `https://github.com/example/beacon-api.git@0123456789abcdef0123456789abcdef01234567:project/OPS-7/TASKS.md#OPS-7`. If another repository also has `OPS-7`, it must have its own repository identity and SHA. A bare `OPS-7`, SHA, or local path cannot establish which record was reviewed. Check that a real repository and commit exist before treating a ref as evidence; the Beacon refs are deliberately illustrative.

## Partial success record

Keep one bounded row per target in the current task's declared gist. Use `operation`, `target_identity`, `expected_source` or `provider_condition`, `observed_result` (`success`, `failure`, or `unknown`), `receipt/ref`, and `next_check`. A save, local commit, push, and provider publish are separate targets. A read back of expected content can show that state exists; without an operation receipt it does not prove which attempt caused it. Follow [the recovery walkthrough](../../examples/long-feature/recovery.md) before retrying any uncertain target.
