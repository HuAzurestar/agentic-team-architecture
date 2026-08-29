# GitHub CI/CD 实施规范

本文件只用于托管在 GitHub 上的仓库。编写工作流前，先检查现有 `.github/workflows`、仓库可见性和套餐、默认分支、Rulesets、Pages、Environments、包注册表及 Release 约定。实施前通过 [platform-capabilities.md](platform-capabilities.md) 重新核对 preview、套餐和 edition 假设。

## GitHub 通用基线

只创建实际需要的最少工作流：

```text
.github/workflows/ci.yml       # pull_request + push main：确定性的必需检查
.github/workflows/release.yml  # 版本 tag 或 workflow_dispatch：不可变发布制品
.github/workflows/pages.yml    # push main/手动：仅用于持续发布网站或 PDF
```

当所有权、触发条件或运行环境有实质差异时，可以把不同语言 job 拆到独立文件。为 job 使用稳定的 UI 名称，例如 `policy`、`python / test (3.13)`、`lean / build`、`tex / build`；Ruleset 要求的是这些准确的状态检查名称。

PR CI 应当：

- 在 `pull_request` 和推送 `main` 时触发，另加 `workflow_dispatch` 便于诊断；
- 使用按 workflow 和 PR/ref 分组的 `concurrency`，取消被后续提交取代的 CI；
- 默认使用 `permissions: contents: read`，仅向确实需要的 job 增加权限；
- 用 `pull_request` 运行 Fork 代码，避免通过带密钥的 `pull_request_target` 检出不受信任代码；
- 按仓库策略固定可信 Action，高风险仓库优先固定不可变 SHA，并自动更新；
- 只缓存可复现依赖/中间产物，缓存键包含 OS、工具链和锁文件哈希；绝不缓存凭证；
- 日志、覆盖率、二进制或预览 PDF 使用短期 workflow artifact，而不是 cache。

为 `main` 配置 Ruleset：要求 PR、批准、解决全部对话、稳定 CI job 名称，并禁止强制推送和删除。需要专家审查时增加 `CODEOWNERS`。只有仓库流量确有必要时才启用 merge queue，并确保必需工作流支持 merge-group 事件。

按 [issues-and-templates.md](issues-and-templates.md) 选择并添加贡献文件。优先使用 `.github/ISSUE_TEMPLATE/*.yml` Issue Forms，通过 `.github/ISSUE_TEMPLATE/config.yml` 配置选择器；除非确实需要多个模板，否则 PR 模板放在 `.github/pull_request_template.md`。

为每个启用的主类型创建独立 GitHub Issue Form（`bug.yml`、`feature.yml`、`docs.yml`、`proof.yml`、`paper.yml` 等）。组织 Issue Types 可用时使用 Form 的 `type` 字段，否则使用权威 type label。GitHub Organization 默认 Issue Type 为 task、bug、feature，且可自定义；没有该组织能力时继续使用 label。

Issue 驱动分支优先从 Issue 的 Development 区创建，让 GitHub 记录关联，然后按 `<prefix>/<issue>-<summary>` 检查。该分支链接能力依赖 preview，因此 policy job 仍解析分支并查询 Issue。缺失/已关闭/错误仓库 Issue、缺少或冲突的主类型、prefix/type 不匹配、Commit/PR type 不匹配，或 PR 未链接主 Issue 时都拒绝。

对 Issue-first Commit Policy，在仓库套餐支持时配置 Ruleset commit-message metadata 限制。下面的基准 RE2 第一行正则由 `policy-model.json` 生成；修改 taxonomy 后通过 `python scripts/validate_policy.py . --print-ruleset-regex` 重新生成。

```regex
^#[1-9][0-9]* (feat|fix|docs|refactor|perf|test|build|ci|chore|proof|paper|revert)(\([a-z0-9][a-z0-9-]*\))?!?: [^\r\n]+
```

先在 Ruleset `Evaluate` 模式中测试，再切换 Active。只有确有理由的 bot/release automation 才配置显式 bypass actor，并为它生成的消息规定单独格式。Ruleset metadata 限制可以在 Actions 运行前拒绝 push，但 72 字符限制、允许 scope、必需 body 和 `Refs:` footer、Issue 是否存在/开放、PR 标题/正文及例外仍由 CI 执行。注意 GitHub 创建的 squash/merge commit 也必须合法；优先使用 squash merge，并把已验证 PR 标题作为 commit subject。

## 可选 Open-Code-Review

仓库能够安全提供获批 LLM endpoint/credential、代码处理符合隐私和数据驻留政策、CI 预算/runner 容量足够，且维护者接受固定工具/版本时，建议使用阿里 `open-code-review`。针对 PR base/head 范围运行并输出机器可读 JSON。默认只作建议：finding 进入 review comment/report artifact，不提供批准，也不成为 required status。

OCR 只能补充人工审查、CODEOWNERS、测试、静态/安全分析和语言门禁。它不能替代 Lean kernel/无 sorry/公理检查，也不能替代 TeX PDF 构建/视觉审查。绝不向 Fork PR 代码暴露密钥，不允许 review job 推送修复，也不发布未脱敏 prompt/report。团队以后可以另行决定把稳定的严重级策略升级为阻断检查，但本 Skill 不会自动这样做。

## 可选 SonarQube

满足 [sonarqube.md](sonarqube.md) 前置条件时，在相关 build/test/coverage 步骤后增加 Sonar 分析。使用受支持 GitHub integration 提供 PR decoration 和 Quality Gate status；经过只报告试运行后，可以把稳定的 `SonarQube Code Analysis` 状态设为 Ruleset required check。SonarQube 始终是可选项，不能替代各语言 job。

## GitHub Actions 中的 Python

PR/push 的 `ci.yml` 应当：

1. 检出代码并仅安装项目声明支持的 Python 版本；使用小型矩阵，一个标准版本运行 lint/format/type，全部支持版本运行测试；
2. 使用仓库已有锁文件/包管理器安装依赖，并使用它支持的缓存集成；
3. 按 [python.md](python.md) 运行 `compileall`、Ruff、选定类型检查器、pytest 和导入/CLI smoke test；
4. 对可分发包，只构建一次 wheel/sdist，执行元数据检查，在干净 job/环境中安装 wheel 并 smoke-test 已安装包；
5. 只有审查者或下游 job 需要时，才上传覆盖率/测试报告或构建分发包。

CD 方面，内部脚本什么也不发布。需要发布的库/应用从 [ci-cd.md](ci-cd.md) 选择一种 release artifact profile：要么在受保护 release ref 上只构建测试一次，要么原样晋级已证明的候选制品而不重建。验证 tag/source/package version 一致；支持时通过 GitHub trusted publishing/OIDC 发布；把同一个已验证 wheel/sdist 或平台 bundle 附加到 GitHub Release。发布 PyPI 或部署应用时，使用 GitHub Environments 做审批和密钥隔离。

## GitHub Actions 中的 C/C++、Java 与 Shell

- C/C++：使用受支持 compiler/OS matrix，运行仓库 configure/build/test preset；标准 job 运行静态分析，受支持 runner 运行 sanitizer。Tag workflow 只发布经过测试的平台特定包，并附校验和/provenance。
- Java：使用已提交 Maven/Gradle wrapper、受支持 JDK matrix、风格/静态分析、单元/集成测试，再打包并 smoke-test JAR/WAR/distribution。Tag workflow 通过受保护 Environment 把同一个已验证制品发布到选定 package registry/Release。
- Shell：通过 shebang 和后缀发现脚本，运行声明 shell 语法、ShellCheck、shfmt 和 Bats/smoke test。通常不需要 CD；脚本随安装器/归档/容器交付时，测试并发布该准确制品且保留 executable mode。

## GitHub Actions 中的 Lean

PR/push 的 `ci.yml` 应当：

1. 安装 `lean-toolchain` 指定的准确版本；恢复以 runner OS、`lean-toolchain` 和 `lake-manifest.json` 哈希为键的 Lake/Mathlib 缓存；获取依赖但不更新 manifest；
2. 对所有项目目标运行 `lake build`；
3. 运行项目的无 `sorryAx` 检查，并对每个公开/宣称的主要定理执行允许公理审计；
4. 验证定理模块可从构建目标到达；定义了项目 linter 或 `lake test` 时运行它们；
5. 只有失败诊断确有价值时才上传日志。

这些确定性 job 应作为 Ruleset 必需检查。可以选择请求 GitHub Copilot Code Review，或添加 Agentic Workflow，用于引理搜索、陈述/证明审查、新增公理检测和证明维护建议。Agentic Workflows 和第三方 Agent 取决于当时的 GitHub 套餐/预览开放状态、计费、权限及组织策略。默认只作建议，绝不能把 Agent 评论当成 kernel 验证或数学批准。

Lean 库通常没有部署。版本 tag 上的 CD 可以创建包含源码归档、生成文档或明确支持的二进制文件的 GitHub Release。只有项目确实存在包注册表时才发布，不能虚构部署目标。

## GitHub Actions 中的 TeX/LaTeX

PR/push 的 `ci.yml` 应当：

1. 使用与文档兼容且版本固定的 TeX 发行版/容器；
2. 运行 ChkTeX 或项目配置的静态检查器；
3. 使用 `latexmk` 构建根文档，并按项目策略对编译错误、未解决 citation/reference 失败；
4. 将 PDF 作为短期 artifact 上传，用 PR/run 和 commit SHA 命名，供审查者检查版面。

版本化 CD 的 `release.yml` 由受保护的 `v*` 或 `paper-v*` tag 触发，在固定环境中只构建一次文档，将 PDF 与必要源码、参考文献和许可证打包，生成校验和，并附加到不可变 GitHub Release。确保文档版本与 tag 一致。

持续更新 `latest` PDF 时，`pages.yml` 在 `main` 上构建，上传 Pages artifact，然后由独立 job 使用 `pages: write`、`id-token: write` 和受保护的 `github-pages` Environment 部署。页面显示源 commit，并与不可变 Release 明确区分。不得把 PR artifact 部署到公开 Pages。

因此，GitHub TeX 仓库至少要有 `ci.yml`，并在每次相关构建成功后产生可下载 PDF。需要发布版本化 PDF 时增加 `release.yml`；只有需要持续更新 latest 版本时才增加 `pages.yml`。预览 artifact 设置较短 `retention-days`，因为长期版本记录应当是 GitHub Release asset，而不是 workflow artifact。

多语言 TeX 使用按 document/locale 划分的 matrix 或显式 job。每一项分别运行静态检查、构建和日志验证，并上传独立 PDF artifact。Release job 下载所有语言 artifact，验证预期集合与校验和后一起发布；Pages 可以提供链接到每个当前语言版本的索引页。

## 编译型程序与服务

对 C/C++/Rust/Java 等编译型交付物，PR CI 配置并编译受支持构建变体，针对构建树运行单元测试，再对实际二进制运行集成/smoke test。只有支持承诺确实覆盖的 OS、编译器、架构才进入 matrix。只有确有用途时才上传二进制；普通调试输出不是 Release。

tag 发布时，在隔离 job 中构建各受支持平台制品并测试，由 release job 汇总 artifact，按需生成校验和及 provenance/attestation，再把不可变 asset 附加到 GitHub Release。绝不能把不受信任 PR 构建与带密钥的发布 job 混合。

对服务，只构建一次真实容器，完成扫描/测试后，以不可变 digest/版本 tag 推送 GitHub Container Registry 或选定注册表，再通过受保护 GitHub Environment 部署该 digest。优先使用 OIDC/短期凭证，按需要求生产批准，串行执行部署，记录部署 URL，并定义回滚到前一 digest 的方法。

## 多语言 GitHub 工作流

仓库包含一种以上实现/文档语言时，为每种适用语言政策创建独立 job 或 reusable workflow，不能只选一种。典型依赖图为：

```text
policy ─┬─ python ─┐
        ├─ lean ───┼─ integration ── ci / required
        └─ tex ────┘
```

并非所有仓库都需要四个 job；应包含每个检测到且受支持的组件。如果 TeX 使用 Python 生成输出或 Lean 定理数据，integration job 从同一 commit 重新生成输入，并验证 PDF 与之匹配。如果组件相互独立，`ci / required` 可以直接依赖各语言 job，不需要 integration。

只有确实减少重复且保持 job/check 名称稳定时才使用 reusable workflow。如果使用路径选择，增加 classifier job，并确保每个预期语言检查都报告确定结果；不能因为整个 workflow 被跳过而让 GitHub required check 永久 pending。Release workflow 收集已经验证的 wheel、binary、proof documentation、PDF artifact，验证 release manifest，任何预期组件或语言版本缺失时都必须失败关闭。

## 明确不配置 CD 的情况

仓库没有发布制品或部署目标时，不增加 `release.yml` 或 `pages.yml`。完整 GitHub 配置可以只有 `ci.yml` 和 Ruleset。工作流文件无法完整配置 Ruleset、Environment 审批者、仓库密钥或 Pages 发布源，因此要单独记录必须通过 GitHub UI/API 完成的设置。
