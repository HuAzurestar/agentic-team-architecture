# CI/CD conventions

For GitHub repositories, apply the concrete workflow and platform mapping in [github.md](github.md) after selecting the relevant language gates below.

## CI topology

Use stable, descriptive job/check names. A practical split is:

- `policy`: PR title, forbidden files, generated-file consistency, or repository-specific policy;
- `python`: lint/format, typing, tests, package build as applicable;
- `cpp`: format, compilation/static analysis, tests/sanitizers, package as applicable;
- `java`: compile/style/static analysis, tests, package smoke test;
- `shell`: syntax/static/format checks and script tests;
- `lean`: pinned-toolchain build and project linters/tests;
- `tex`: static checks and document build;
- `integration`: only when cross-component behavior exists.

Run relevant gates on pull requests and pushes to the stable branch. Use path filters only when skipped jobs do not become ambiguous required checks; a change to shared CI/build configuration must trigger affected jobs. Cancel superseded runs on the same PR. Keep required gates deterministic and reasonably fast.

Validate workflow syntax with the platform's supported tooling when available. Pin third-party actions to trusted immutable revisions where the threat model requires it, and use automated update tooling to keep pins current. Set explicit job timeouts and least-privilege permissions.

Select build and packaging gates from the deliverable, not merely the implementation language:

- interpreted scripts may require syntax, import, lint, and tests but no package artifact;
- libraries should build and validate the package consumers install;
- compiled applications should compile/link in CI and test the produced binary;
- deployable services should build the actual container or bundle once and test that artifact;
- proofs should build all claimed theorem modules and audit incompleteness/trust assumptions;
- papers should build the PDF and inspect references, with preview or release packaging when useful.

Unit tests are the baseline for behavioral logic. Add integration, end-to-end, or platform matrix jobs only where they cover a real boundary or support promise. A successful build does not replace tests, and tests that never build/import the shipped artifact are insufficient.

## Multi-language repositories

Detect every language and deliverable in the repository; do not select only the dominant language. Give each applicable language an independent required job so failures are attributable (`python`, `cpp`, `java`, `shell`, `lean`, `tex`, and so on), then add an `integration` job when outputs cross language boundaries—for example Python generates Lean/TeX sources, Lean results are included in a paper, Java invokes a native library, Shell packages artifacts, or a C/C++ extension is imported by Python.

Use a final stable aggregate job such as `ci / required` that depends on all mandatory language and integration jobs and fails if any required dependency failed or was unexpectedly skipped. Configure branch protection against this stable aggregate when individual matrix names or project composition may change. Path filters may avoid expensive work only if a lightweight change classifier still produces an explicit success/failure result and shared manifests, generators, workflows, schemas, and lockfiles trigger every affected language.

When a detected language has no dedicated reference in this skill, derive its gate from repository-owned manifests, lockfiles, contributor documentation, and existing CI. Record the component, canonical commands, artifact, and support status in the design. If evidence is insufficient, mark the gate unsupported or unverified; do not silently omit the component or introduce a fashionable toolchain by default.

For multi-language CD, define one release manifest containing source commit/tag, toolchain versions, checksums, and every expected artifact. Build each artifact in its owning validated job, pass immutable artifacts to a collection/release job, verify the complete manifest, and publish them under one coherent version. Do not silently publish a partial release when one language edition, binary, proof bundle, package, or PDF failed.

## Agent-assisted checks

Some Git platforms provide AI code review or agent workflows; capabilities, licensing, trust boundaries, and fork behavior vary. Use agents for advisory review, theorem/lemma search, test-gap suggestions, or maintenance tasks. Keep deterministic compiler, kernel, linter, test, and security checks as the required merge gates. Do not give an agent write permissions or secrets merely to review an untrusted PR. If an agent check becomes required, pin its configuration/model where possible, define timeout and failure semantics, control cost, and document how maintainers proceed during provider outages.

## Release artifact profiles

Select exactly one profile for each published deliverable and document it in the policy:

1. **Build on release ref once:** a protected tag or explicit release workflow checks out the verified source ref, builds and tests the release artifact once, then publishes or promotes that same artifact.
2. **Promote an attested candidate:** CI builds and tests a candidate once, records its digest, source SHA, toolchain, checks and provenance, then the release workflow verifies tag/source agreement and promotes those same bits without rebuilding.

Both profiles preserve the invariant that no untested artifact is substituted between validation and publication. Packaging metadata or signing added later must not change payload bits without a new validation step. Require environment approval for production when appropriate, serialize production deployments, and record artifact version, digest, source commit, actor, and result.

Define rollback before enabling automatic production deployment. Keep credentials in the forge/environment secret store, prefer short-lived federated identity, and never print secrets. Do not run secret-bearing deployment jobs for untrusted pull requests.

If this is a library, paper, or proof repository with no runtime environment, "CD" may correctly mean publishing a package, attaching a PDF, or creating a release—or may be omitted entirely. Do not fabricate a deployment stage merely to complete an acronym.

## Adoption sequence

Introduce formatting and lint gates after formatting the baseline or scoping checks to changed files. Add type checking incrementally when legacy errors exist. Make branch protection require checks only after their names and trigger behavior are stable. Document any hosting-platform settings that cannot live in version control.
