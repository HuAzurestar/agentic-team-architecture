# Code review contract

Use this contract for read-only assessments and pull-request/code-review work. Deterministic compilers, kernels, linters, tests, and security scanners remain separate merge evidence; a human or AI review does not replace them.

## Establish scope and coverage

Record the base/head refs, changed files, generated/vendor exclusions, detected languages, deliverables, and cross-component boundaries before reviewing. Review every in-scope changed file or list it as skipped with a reason. Follow relevant call sites, tests, schemas, manifests, generated sources, and public interfaces when a diff cannot be judged locally.

For a multi-language change, apply the common review below, then every detected language reference routed from `SKILL.md`. Review boundaries explicitly: FFI/ABI, RPC/API schemas, serialization, shared databases, generated code, package metadata, command-line contracts, version strings, proof-to-paper links, and artifact assembly.

## Review dimensions

- correctness and edge cases, including failure and concurrency behavior;
- security, privacy, authorization, secrets, and untrusted input;
- compatibility, migrations, public API/ABI/schema and supported-version impact;
- tests and observability that would detect the claimed behavior;
- maintainability, ownership, documentation, and generated-source consistency;
- build, packaging, release, deployment, and rollback consequences.

Use severity according to consequence, not style preference:

| Severity | Meaning |
| --- | --- |
| `blocking` | Unsafe, incorrect, data-losing, security-sensitive, or release-breaking behavior that must be resolved before merge. |
| `high` | A common path can fail or a promised compatibility/reliability property is not met. |
| `medium` | A bounded maintainability, test, or operational gap with a concrete future cost. |
| `advisory` | Optional improvement or question; never present it as a merge blocker. |

Each finding includes path/line, observable evidence, consequence, severity, and a focused remediation or verification step. Separate facts from inferences and do not claim a test passed unless it ran. If no actionable findings remain, state the reviewed and skipped scope rather than manufacturing comments.

## Review output

Return, in order:

1. blocking/high findings;
2. medium findings and advisory notes;
3. coverage: reviewed files/components/languages and skipped scope;
4. validation evidence: commands/results already observed and checks still needed;
5. cross-language or release risks that require owner confirmation.

AI-assisted review stays advisory by default. Pin and permission it like any third-party CI dependency, keep secrets away from untrusted changes, define timeout/outage behavior, and never use model output as the sole required gate for deterministic correctness.
