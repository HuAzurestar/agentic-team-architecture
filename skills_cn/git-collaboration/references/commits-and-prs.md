# 提交与 Pull Request

## Commit Message

普通项目变更使用 Issue-first 的 Conventional Commits 扩展格式：

```text
#<issue> <type>[(<scope>)][!]: <imperative summary>

<body: context, what changed, and why>

Refs: #<issue>
[Closes: #<issue>]
[BREAKING CHANGE: migration and impact]
[Co-authored-by: Name <email>]
```

普通 feature、fix、文档、重构、测试和 CI 工作必须携带 `#<issue>`。只有仓库初始化、自动依赖更新、release/version commit 或无法合理提前创建 Issue 的紧急管理操作，才可定义少量且有文档记录的例外；绝不能用 `#0` 等虚假编号。如果所有变更都必须由 Issue 驱动，就先创建 Issue。

基准类型来自 [policy-model.json](policy-model.json)：`feat`、`fix`、`docs`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`；启用对应 Issue 类型时增加 `proof` 和 `paper`。`revert` 是 `bug` 或 `maintenance` Issue 的显式动作 override，body 必须说明被回退 commit 及原因。仓库可以缩小模型，并定义稳定的小写 kebab-case scope。type 必须符合 Issue/分支映射或已声明 override。第一行保持简洁（目标不超过 72 字符），不加句号，使用祈使式摘要，只描述一个逻辑变更。使用 `!` 和 `BREAKING CHANGE:` footer 表示不兼容变更。

Issue-first 前缀属于仓库扩展，并非默认 Conventional Commits 语法。必须为 commitlint/release 工具配置自定义 header parser，或解析前规范化消息；不能声称它与未经配置的 Conventional Commit 工具直接兼容。修改 taxonomy 后，通过 `python scripts/validate_policy.py . --print-ruleset-regex` 从 policy model 生成 GitHub Ruleset 基准正则，不得手工维护另一份 type 列表。

示例：

```text
#142 feat(parser): support nested Lean comments

Accept nested block comments during tokenization and preserve source spans.
This prevents the parser from truncating generated proof files.

Refs: #142
Closes: #142

#87 fix(tex): preserve labels during appendix split

Refs: #87

#203 ci(python): test supported interpreter versions

Refs: #203
```

非平凡变更必须包含 body，解释动机、行为、限制和重要实现选择，不能重复 subject。正文统一换行宽度，72 字符是实用默认值。footer 使用 Git trailer 或项目定义 token。始终包含 `Refs: #N`；只有合并进默认分支确实应关闭 Issue 时才使用 `Closes: #N`/`Fixes: #N`。跨仓库引用使用 `owner/repo#N`。

没有实际运行测试时，不得声称测试通过。不得包含密钥、凭证、个人数据或生成式 AI 的过程性说明。只有一个提交确实原子地跨越多个 Issue 时才允许引用多个，并在 footer 中写出完整引用。

## Pull Request

PR 标题遵循相同的 Issue-first header，使用 squash merge 时尤其如此：

```text
#142 feat(parser): support nested Lean comments
```

描述应说明：

- 问题与预期结果；
- 实现方式和重要权衡；
- 验证命令及结果；
- 用户可见影响、兼容性、迁移、安全或部署影响；
- 使用 `Closes #142`/`Refs #142` 链接 Issue，以及需要时的截图或日志摘录。

保持 PR 聚焦。将无关重构与行为变更分开。审查者检查正确性、测试、可维护性、兼容性、安全性、文档，以及生成文件是否与源文件一致。作者应回应审查意见，不得通过静默覆盖来隐藏未解决的问题。

## 执行方式

分层执行：

1. 提供 `CONTRIBUTING.md`、Commit Message 示例/模板，以及用于快速反馈的可选本地 `commit-msg` hook；
2. CI 验证 PR 标题和 Issue 链接；
3. 保留独立提交时，验证 PR 范围内每个 commit，包括 body/footer；
4. GitHub 套餐支持时，使用 Ruleset commit metadata 限制，拒绝第一行不符合 Issue-first 规则的 push；
5. 配置 squash merge 从已经验证的 PR 标题/body 生成消息，保证 GitHub 创建的 commit 仍然合法。

本地 hook 不能作为唯一门禁，因为 Git 不会自动克隆 hook。GitHub Ruleset regex 是较早的结构门禁，但有效 Issue 是否存在/开放、允许 scope、body/footer 内容和例外仍需由 CI 检查。
