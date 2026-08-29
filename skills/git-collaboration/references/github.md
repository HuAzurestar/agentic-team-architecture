# GitHub CI/CD implementation

Use this reference only for repositories hosted on GitHub. Inspect existing `.github/workflows`, repository visibility/plan, default branch, Rulesets, Pages, Environments, package registry, and release conventions before writing workflows. Recheck preview, plan, and edition assumptions in [platform-capabilities.md](platform-capabilities.md) before implementation.

## Shared GitHub baseline

Create the minimum workflows needed:

```text
.github/workflows/ci.yml       # pull_request + push to main: deterministic required checks
.github/workflows/release.yml  # version tags or workflow_dispatch: immutable release artifacts
.github/workflows/pages.yml    # push to main/manual: only when continuously publishing a site/PDF
```

Splitting the language jobs into separate files is acceptable when ownership, triggers, or runtimes differ materially. Give jobs stable UI names such as `policy`, `python / test (3.13)`, `lean / build`, or `tex / build`; Rulesets require those exact status checks.

For PR CI:

- trigger on `pull_request` and on pushes to `main`; add `workflow_dispatch` for diagnosis;
- use `concurrency` keyed by workflow and PR/ref with cancellation of superseded CI runs;
- default to `permissions: contents: read`; grant additional permissions only to the job that needs them;
- run fork code with `pull_request`, not secret-bearing `pull_request_target` checkout patterns;
- pin trusted actions according to repository policy, preferably immutable SHAs for higher-risk repositories, and automate updates;
- cache only reproducible dependencies/intermediates with OS, toolchain, and lockfile hashes in the key; never cache credentials;
- upload logs, coverage, binaries, or preview PDFs as short-retention workflow artifacts, not caches.

Configure a Ruleset for `main`: require a PR, approvals, resolved conversations, the stable CI job names, and block force-push/deletion. Add `CODEOWNERS` when specialist review is required. Enable merge queue only if repository traffic warrants it, and ensure required workflows support the merge-group event.

Add the contribution files selected in [issues-and-templates.md](issues-and-templates.md). Prefer Issue Forms under `.github/ISSUE_TEMPLATE/*.yml`, configure the chooser with `.github/ISSUE_TEMPLATE/config.yml`, and place the PR template at `.github/pull_request_template.md` unless multiple templates are genuinely needed.

Create a separate GitHub Issue Form for each enabled primary type (`bug.yml`, `feature.yml`, `docs.yml`, `proof.yml`, `paper.yml`, and so on), using the form's `type` field when organization Issue Types are available and a canonical type label otherwise. GitHub organization Issue Types default to task, bug, and feature and may be customized; labels remain useful where that organization capability is unavailable.

For an Issue-backed branch, prefer creating it from the Issue's Development section so GitHub records the relationship, then check it against `<prefix>/<issue>-<summary>`. This branch-link capability is preview-dependent, so the policy job must still parse the branch and query the Issue. Reject a missing/closed or wrong-repository Issue, absent/conflicting primary type, prefix/type mismatch, commit/PR type mismatch, or PR that does not link the primary Issue.

For the issue-first commit policy, configure Ruleset commit-message metadata restrictions where the repository plan supports them. A baseline RE2 first-line pattern generated from `policy-model.json` is shown below. Regenerate it with `python scripts/validate_policy.py . --print-ruleset-regex` after changing the taxonomy.

```regex
^#[1-9][0-9]* (feat|fix|docs|refactor|perf|test|build|ci|chore|proof|paper|revert)(\([a-z0-9][a-z0-9-]*\))?!?: [^\r\n]+
```

Test it in Ruleset `Evaluate` mode before making it active. Define explicit bypass actors only for justified bots/release automation and ensure their generated messages follow a separately documented pattern. Ruleset metadata restrictions can reject a push before Actions runs, but use CI to enforce the 72-character policy, allowed scopes, required body and `Refs:` footer, valid/open Issue lookup, PR title/body, and any exemptions. Take care that GitHub-created squash/merge commits also comply; prefer squash merge with the validated PR title as the commit subject.

## Optional Open-Code-Review

Recommend Alibaba `open-code-review` when the repository can safely supply an approved LLM endpoint/credential, code processing satisfies privacy and residency policy, CI budget/runner capacity is available, and maintainers accept the pinned tool/version. Run it on the PR base/head range with machine-readable JSON output. Keep it advisory: findings become review comments/report artifacts and do not provide approval or a required status by default.

OCR supplements human review, CODEOWNERS, tests, static/security analysis, and language-specific gates. It cannot replace Lean kernel/no-sorry/axiom checks or TeX PDF build/visual review. Never expose secrets to fork PR code, allow the review job to push fixes, or publish unsanitized prompts/reports. A team may later promote a stable severity policy to a blocking check through a separate decision, but this Skill does not do so automatically.

## Optional SonarQube

When [sonarqube.md](sonarqube.md) prerequisites are satisfied, add Sonar analysis after the relevant build/test/coverage steps. Use the supported GitHub integration for PR decoration and Quality Gate status; after a report-only rollout, the stable `SonarQube Code Analysis` status may become a Ruleset required check. SonarQube remains optional and does not replace language jobs.

## Python on GitHub Actions

PR/push `ci.yml` should:

1. check out the code and install only declared supported Python versions; use a small matrix, with one canonical version running lint/format/type checks and all supported versions running tests;
2. install dependencies through the repository's lock/package manager and its supported cache integration;
3. run `compileall`, Ruff, the configured type checker, pytest, and import/CLI smoke tests as selected in [python.md](python.md);
4. for a distributable package, build wheel/sdist once, run metadata checks, install the wheel in a clean job/environment, and smoke-test the installed package;
5. upload coverage/test reports or built distributions only when reviewers or downstream jobs need them.

For CD, do nothing for an internal script. For a released library/application, select one release artifact profile from [ci-cd.md](ci-cd.md): either build/test once on the protected release ref, or promote an already attested candidate without rebuilding. Verify tag/source/package-version agreement, publish with GitHub trusted publishing/OIDC where supported, and attach the same verified wheel/sdist or platform bundles to the GitHub Release. Use GitHub Environments for approval and secrets when publishing to PyPI or deploying an application.

## C/C++, Java, and Shell on GitHub Actions

- C/C++: use supported compiler/OS matrix jobs, run the repository configure/build/test presets, static analysis in a canonical job, and sanitizer jobs on supported runners. Tag workflows publish only tested platform-specific packages with checksums/provenance.
- Java: use the committed Maven/Gradle wrapper, a supported JDK matrix, style/static analysis, unit/integration tests, then package and smoke-test the JAR/WAR/distribution. Tag workflows publish the same verified artifact to the selected package registry/Release through a protected Environment.
- Shell: discover scripts by shebang as well as extension, run declared-shell syntax, ShellCheck, shfmt, and Bats/smoke tests. Usually no CD is needed; when scripts ship in an installer/archive/container, test and publish that exact artifact with executable modes preserved.

## Lean on GitHub Actions

PR/push `ci.yml` should:

1. install the exact `lean-toolchain`, restore Lake/Mathlib caches keyed by runner OS plus hashes of `lean-toolchain` and `lake-manifest.json`, then fetch dependencies without updating the manifest;
2. run `lake build` for all project targets;
3. run the project no-`sorryAx` check and the allowed-axiom audit for every claimed/public main theorem;
4. verify the theorem modules are reachable from built targets; run project linters or `lake test` when defined;
5. upload diagnostic logs only on failure when they add value.

Keep these deterministic jobs as required Ruleset checks. Optionally request GitHub Copilot code review or add an agentic workflow for lemma search, statement/proof review, changed-axiom detection, or proof-maintenance suggestions. Agentic workflows and third-party agents depend on current GitHub plan/preview availability, billing, permissions, and organizational policy. Keep them advisory by default and never treat an agent comment as kernel verification or mathematical approval.

Lean libraries normally have no deployment. On a version tag, CD may create a GitHub Release containing source archives, generated documentation, or explicitly supported binaries. Publish packages to the project's actual registry only when one exists; do not invent a deployment target.

## TeX/LaTeX on GitHub Actions

PR/push `ci.yml` should:

1. use a pinned TeX distribution/container compatible with the document;
2. run ChkTeX or the configured static checker;
3. build the root document with `latexmk` and fail on compiler errors plus unresolved citations/references under the project policy;
4. upload the PDF as a short-retention artifact named with the PR/run and commit SHA so reviewers can inspect layout.

For versioned CD, `release.yml` triggers on protected `v*` or `paper-v*` tags, builds the document once in the pinned environment, packages PDF plus the required source/bibliography/license files, generates checksums, and attaches them to an immutable GitHub Release. Ensure the document version and tag agree.

For a continuously updated `latest` PDF, `pages.yml` builds on `main`, uploads a Pages artifact, then deploys it with a separate job using `pages: write`, `id-token: write`, and the protected `github-pages` Environment. Display the source commit and keep this moving publication distinct from immutable releases. Do not deploy PR artifacts to public Pages.

Thus a GitHub TeX repository has at least `ci.yml` producing a downloadable PDF on every successful relevant run. Add `release.yml` when versioned PDFs are published; add `pages.yml` only when a moving latest edition is useful. Configure a short `retention-days` value for preview artifacts, because GitHub Release assets—not workflow artifacts—are the long-term version record.

For multilingual TeX, use a matrix or explicit jobs keyed by document/locale. Each entry runs its own static check/build/log validation and uploads a distinct PDF artifact. The release job downloads all language artifacts, verifies the expected set and checksums, then publishes them together; Pages may provide an index linking each current language edition.

## Compiled programs and services

For C/C++/Rust/Java or other compiled deliverables, PR CI configures and compiles the supported build variants, runs unit tests against the build tree, and runs integration/smoke tests against the actual binary. Use a matrix only for supported OS/compiler/architecture combinations. Upload binaries only when they are useful; ordinary debug outputs are not releases.

For tag releases, build each supported platform artifact in isolated jobs, test it, collect artifacts in a release job, generate checksums and provenance/attestations where appropriate, then attach immutable assets to the GitHub Release. Never combine untrusted PR builds with a secret-bearing release job.

For services, build the actual container once, scan/test it, push it to GitHub Container Registry or the selected registry with immutable digest/version tags, then deploy that digest through a protected GitHub Environment. Prefer OIDC/short-lived credentials, require production approval when appropriate, serialize deployments, record the deployment URL, and define rollback to the preceding digest.

## Multi-language GitHub workflows

When a repository contains more than one implementation/document language, create one job or reusable workflow per applicable language policy rather than choosing one. A typical dependency graph is:

```text
policy ─┬─ python ─┐
        ├─ lean ───┼─ integration ── ci / required
        └─ tex ────┘
```

Not every repository needs all four jobs; include every detected and supported component. If TeX consumes generated Python output or Lean theorem data, the integration job regenerates those inputs from the same commit and verifies the PDF against them. If components are independent, `ci / required` can depend directly on their jobs without an integration job.

Use reusable workflows only when they remove real duplication while keeping job/check names stable. If path-based selection is used, add a classifier job and ensure each expected language check reports a conclusive result; GitHub required checks must not remain pending because an entire workflow was skipped. Release workflows collect the already validated wheel/binary/proof documentation/PDF artifacts, verify a release manifest, and fail closed when any expected component or language edition is absent.

## When CD is intentionally absent

Do not add `release.yml` or `pages.yml` when the repository has no published artifact or deployment. A complete GitHub setup may consist solely of `ci.yml` plus Ruleset configuration. Document required GitHub UI/API settings separately because workflow files cannot fully configure Rulesets, Environment reviewers, repository secrets, or Pages source selection.
