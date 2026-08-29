# Gitee collaboration and CI/CD

Use this reference for Gitee-hosted repositories. First identify Community, Enterprise/Professional, Gitee Go, private deployment, or external CI: Issue, protection, pipeline, artifact, approval, and API capabilities vary by product and plan. Do not assume GitHub files/settings work on Gitee. Recheck current claims through [platform-capabilities.md](platform-capabilities.md).

## Traceability and templates

Apply [branches.md](branches.md): every ordinary branch is `<prefix>/<issue>-<summary>`; the Gitee Issue exists, is actionable, and has the mapped primary type label; commit and PR title use the same Issue and mapped type; the PR body references or closes it.

Gitee's documented community template convention is locale-oriented:

```text
.gitee/ISSUE_TEMPLATE.zh-CN.md
.gitee/ISSUE_TEMPLATE.en.md
.gitee/ISSUE_TEMPLATE.zh-TW.md
.gitee/PULL_REQUEST_TEMPLATE.zh-CN.md
.gitee/PULL_REQUEST_TEMPLATE.en.md
```

Do not claim these provide GitHub-style multiple YAML Issue Forms. If the actual Gitee product supports multiple work-item templates/types, configure one per primary type. Otherwise put a type chooser in each locale template, require `[Bug]`, `[Feature]`, `[Proof]`, `[Paper]`, and other canonical title prefixes, apply exactly one primary type label during triage, and link to type-specific guidance. Pipeline/API policy checks enforce type ↔ branch ↔ commit ↔ PR consistency.

Protect `main` and other stable branches with Gitee protected/read-only branch rules: restrict push/merge actors, require PR review and available pipeline/quality gates, and document behavior that the selected product cannot enforce automatically.

## Gitee Go or external CI/CD

Use Gitee Go when available and suitable; it supports YAML/visual orchestration, manual/automatic/scheduled triggers, serial/parallel stages, quality/manual gates, build, and deployment plugins. Otherwise connect approved external CI through Gitee webhooks/status API. Run exactly the same language commands defined by this Skill.

```text
policy -> language jobs -> integration -> required aggregate
                                      -> package/release/deploy (trusted refs)
```

`policy` queries Gitee for Issue state/type and validates branch, commits, PR linkage/template. Run Python, C/C++, Java, Shell, Lean, and TeX jobs independently when detected. TeX always publishes a short-retention PDF artifact or commit-keyed object; version tags publish immutable PDF/source/checksums through available release/artifact storage. Packages, binaries, and containers are built and tested once, stored in the available Gitee/external registry, and promoted unchanged.

## Optional Open-Code-Review and SonarQube

Consider Alibaba `open-code-review` under the privacy/credential/cost conditions in [github.md](github.md). Its CLI supports a base/head range and JSON output, so it may run on a Gitee Go or external runner with complete Git history; this is a custom integration, not documented native Gitee support. Prove it first in a secret-free smoke test and do not promise native PR feedback. Keep it advisory; publish a sanitized summary/report through a separately permissioned step and never expose credentials to untrusted fork code.

SonarQube does not list Gitee among its native DevOps platform bindings. It may still scan code from Gitee Go/external CI and fail that job by waiting for the Quality Gate; pass PR key/base/branch parameters explicitly when doing PR analysis. Do not promise native Gitee PR decoration. Publish a sanitized link/summary or status through Gitee API only if the deployment implements and secures that adapter. See [sonarqube.md](sonarqube.md).

## Mirrors

If GitHub and Gitee mirror one repository, designate one authority for Issues, PRs, tags, releases, and deployments. Do not create competing Issue numbers or independently build two artifacts under one version. Mirror verification may rerun deterministic checks, but mirrored releases record the authoritative URL and source SHA.
