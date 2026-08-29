# Issue、Pull Request 与贡献模板

## 可追溯生命周期

1. 普通实现工作开始前，先创建或分类一个可执行的 Issue。
2. 从正确基线创建分支；分支命名策略允许时包含 Issue 编号。
3. 按 [commits-and-prs.md](commits-and-prs.md) 在每个普通 commit 中引用该 Issue。
4. 创建聚焦的 PR；标题携带主 Issue，正文链接或关闭所有受影响 Issue。
5. 验收标准、审查和必需检查通过后才合并；由合入默认分支的动作关闭 Issue。

Issue 描述问题或预期结果，而不是预先指定补丁。标题简洁且便于搜索。正文包含背景、当前/观察行为、预期结果、范围/非目标、验收标准、适用时的复现步骤或数学陈述、环境/版本、风险和依赖。多个可独立交付的请求不能合并在一个 Issue 中。

类型 label 使用 [policy-model.json](policy-model.json) 中的主类型；仓库可以禁用 `proof`、`paper` 等可选类型。状态（`triage`、`blocked`）及 area/scope 使用独立 label。避免用 label 重复 assignee 或 milestone 信息。安全漏洞按照 `SECURITY.md` 报告，不能使用公开 Issue Form。

## GitHub Community 文件

只创建对仓库确实有用的文件：

```text
CONTRIBUTING.md
SECURITY.md                         # 公开或安全相关项目
SUPPORT.md                          # 确有支持渠道时
CODE_OF_CONDUCT.md                  # 社区项目
GOVERNANCE.md                       # 需要说明角色/决策权时
.github/CODEOWNERS
.github/ISSUE_TEMPLATE/config.yml
.github/ISSUE_TEMPLATE/bug.yml
.github/ISSUE_TEMPLATE/feature.yml
.github/ISSUE_TEMPLATE/proof.yml    # Lean 仓库
.github/ISSUE_TEMPLATE/paper.yml    # TeX/论文仓库
.github/pull_request_template.md
```

权威流程规则写在 `CONTRIBUTING.md`；模板只收集任务特定信息并链接回规范，不重复整套政策。组织级默认文件可以放在公开的特殊 `.github` 仓库，但仓库本地模板会覆盖相应默认值。

## Issue Forms

为每个启用的主 Issue 类型使用不同模板/Form；Bug、Feature、Proof 和 Paper 不能共用一套泛化问题。每个模板分配或要求恰好一个主类型/label，并映射到 [branches.md](branches.md) 的分支和 Commit 政策。

平台支持结构化必填字段时，优先使用 YAML Issue Forms。Bug Form 收集复现方式、观察/预期行为、最小示例、环境/工具链、日志、回归范围，以及确认已经移除密钥。Feature Form 收集用户问题、预期结果、替代方案、范围/非目标、兼容性和验收标准。Documentation、Refactor、Performance、Test、CI 和 Maintenance 分别收集与自身相关的当前状态、目标结果、验证、风险和验收标准；只有少用类型的必需信息确实相同时才合并模板。

Lean proof form 还应收集准确 theorem statement、imports/toolchain、允许公理、是否含 `sorry`、非形式化来源/引用及已经尝试的方法。TeX paper form 应收集根文档、引擎、最小失败片段、日志、受影响输出/页码、参考文献后端和预期渲染。

只有现有表单和 contact link 能覆盖合法请求时，才设置 `blank_issues_enabled: false`。问题咨询转到 Discussions/support，漏洞转到 `SECURITY.md` 或私密报告渠道。

Triage 应拒绝或重新分类所选模板/type 与内容不一致的 Issue。实施前必须确保存在主 type/label；priority、area、status、milestone 和 language label 是次级元数据，不能替代主类型。

## Pull Request 模板

要求作者填写：

- `Closes #N` 或 `Refs #N`；
- 问题/结果和简洁变更摘要；
- 变更类型与影响 scope；
- 验证命令及实际结果；
- 验收标准 checklist；
- 适用时的兼容性、breaking change、迁移、安全、部署、证明信任或 PDF 输出影响；
- 适用时的截图、PDF preview 或 theorem 名称；
- 确认变更聚焦、文档/生成制品同步且不含密钥的 checklist。

模板只能引导作者，不能保证完整。增加确定性 PR policy check，验证标题格式、Issue 引用、必需章节和禁止的占位文本。避免不能提升审查质量、只会误拒绝合法 Markdown 的脆弱检查。
