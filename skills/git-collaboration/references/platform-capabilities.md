# Time-varying platform capabilities

Verify these claims again before implementation. `official` means the provider documents the capability; `custom` means the workflow is an inference that requires a repository-specific smoke test. Absence from this table is not evidence that a capability exists or is unavailable.

Verified on: **2026-08-29**

| Capability | Support level | Conditions and fallback | Primary source |
| --- | --- | --- | --- |
| GitHub YAML Issue Forms and top-level `type` | official, public preview | Organization Issue Types are optional; use one canonical label when unavailable. Keep a Markdown/template fallback because preview schemas may change. | [GitHub Issue Form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) |
| Create/link a branch from an Issue Development section | official, public preview | Requires repository write permission. Continue parsing the branch and querying the Issue because UI linkage is not the policy source of truth. | [Creating a branch for an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-a-branch-for-an-issue) |
| GitHub Ruleset commit metadata regex | official, plan-dependent | Uses RE2. Test in Evaluate mode where available; retain CI validation for richer Issue/body/footer rules. | [Creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository) |
| SonarQube native DevOps binding | official for GitHub, GitLab, Bitbucket, Azure DevOps | Gitee is not listed as a native binding. On other forges, scanner execution may work but PR decoration/status requires a separately secured custom adapter. | [SonarQube DevOps integrations](https://docs.sonarsource.com/sonarqube-server/2025.1/devops-platform-integration) |
| Alibaba OpenCodeReview branch range and JSON output | official CLI behavior | Pin a reviewed version and verify provider, data, telemetry, fork and credential behavior. | [OpenCodeReview repository](https://github.com/alibaba/open-code-review) |
| OpenCodeReview on Gitee Go | custom/inferred | A generic runner with complete Git history may execute the CLI, but native Gitee integration is not documented. Require a secret-free smoke test and publish feedback through an explicitly secured adapter. | [OpenCodeReview CI/CD documentation entry](https://open-codereview.ai/docs/cicd) |

When a plan, edition, preview, or third-party version cannot be verified, design with the documented lower-capability fallback and list the unavailable setting for a maintainer. Do not silently upgrade an inferred capability to a required merge gate.
