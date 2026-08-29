# 时变平台能力

实施前重新验证这些声明。`official` 表示提供商记录了此能力；`custom` 表示这是必须通过仓库特定 smoke test 的推断。本表没有列出某项能力，不代表它存在或不可用。

核验日期：**2026-08-29**

| 能力 | 支持级别 | 条件与 fallback | Primary source |
| --- | --- | --- | --- |
| GitHub YAML Issue Forms 与顶层 `type` | official，public preview | Organization Issue Types 可选；不可用时使用一个权威 label。保留 Markdown/template fallback，因为 preview schema 可能变化。 | [GitHub Issue Form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) |
| 从 Issue Development 区创建/链接分支 | official，public preview | 需要仓库 write 权限。UI 链接不是 policy 事实来源，仍须解析分支并查询 Issue。 | [Creating a branch for an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-a-branch-for-an-issue) |
| GitHub Ruleset Commit metadata regex | official，依赖套餐 | 使用 RE2。可用时先在 Evaluate 模式测试；更丰富的 Issue/body/footer 规则继续由 CI 验证。 | [Creating rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository) |
| SonarQube 原生 DevOps binding | GitHub、GitLab、Bitbucket、Azure DevOps 为 official | Gitee 不在原生 binding 列表中。其他 forge 可能能运行 scanner，但 PR decoration/status 需要另行保护的自定义 adapter。 | [SonarQube DevOps integrations](https://docs.sonarsource.com/sonarqube-server/2025.1/devops-platform-integration) |
| Alibaba OpenCodeReview branch range 与 JSON output | official CLI behavior | 固定经过审查的版本，并验证 provider、数据、telemetry、fork 和凭证行为。 | [OpenCodeReview repository](https://github.com/alibaba/open-code-review) |
| OpenCodeReview on Gitee Go | custom/inferred | 具有完整 Git 历史的通用 runner 可能执行 CLI，但没有有文档支持的原生 Gitee integration。要求无密钥 smoke test，并通过显式保护的 adapter 发布 feedback。 | [OpenCodeReview CI/CD documentation entry](https://open-codereview.ai/docs/cicd) |

套餐、edition、preview 或第三方版本无法验证时，按有文档记录的低能力 fallback 设计，并把不可用设置列给维护者。不得把推断能力静默升级为必需合并门禁。
