---
name: git-collaboration
description: 建立、评估或应用仓库的 Git 协作规范，包括提交信息、分支、Pull Request、CI/CD 门禁以及代码或质量评审。适用于仓库治理和贡献流程；不适用于不会影响团队规范的一次性普通 Git 命令。
---

# Git 协作

建立一套足够精简、团队愿意遵守，同时足够严格、能够验证的协作规范。提出工具方案前先检查仓库：阅读贡献说明、项目清单、锁文件、CI 工作流、受保护分支要求、发布流程，并在可用时检查 Git 历史。保留兼容的本地约定，并解释迁移。

## 选择一个模式

- **Assess（评估）** 是只读模式。盘点现有控制，引用仓库证据，对缺口和风险分类，区分已经验证与不可用的证据，并给出有顺序的修复计划。不得编辑文件或外部设置。
- **Design（设计）** 产出建议规范、文件布局、准确本地命令、必需检查名称、托管平台设置、采用顺序及迁移/回滚说明。除非用户同时要求实施，否则不落地建议。
- **Implement（实施）** 只修改用户授权范围内的文件和设置。验证本地产物，并报告仍未验证的外部设置或检查。即使在此模式，修改仓库设置、远程分支、推送、发布和部署仍需明确授权。

用户要求“审查并修复”时，先评估，再把同一份证据带入实施。缺失的仓库决策会改变分支拓扑、发布制品、部署或外部权限时，停止并请求决定，不得猜测。

## 工作流程

1. 确定仓库结构、语言、交付物、包管理/构建工具、支持版本、托管平台、发布方式，以及是否存在部署。不得虚构命令、服务、制品或密钥。
2. 阅读 [policy-model.json](references/policy-model.json) 中的权威 taxonomy。选择与实际发布拓扑相匹配的最轻量分支模型，再阅读 [branches.md](references/branches.md)。
3. 使用 [commits-and-prs.md](references/commits-and-prs.md) 定义 Issue → branch → commit → PR 可追溯链路。需要贡献文件和表单时，还要阅读 [issues-and-templates.md](references/issues-and-templates.md)。
4. 使用 [workflow-and-recovery.md](references/workflow-and-recovery.md) 定义日常开发、同步、merge/rebase、Hotfix、Release、冲突恢复、标签和忽略文件流程。所有适用命令和示例必须遵守 taxonomy 与 Issue 绑定。
5. 对评估或代码审查请求，阅读 [code-review.md](references/code-review.md)。应用下列每种已检测语言的 overlay，并审查跨语言边界；确定性门禁必须与人工或 AI 评审分开。
6. 只为仓库中检测到的语言选择检查：
   - Python：阅读 [python.md](references/python.md)。
   - C/C++：阅读 [cpp.md](references/cpp.md)。
   - Java：阅读 [java.md](references/java.md)。
   - Bash/POSIX Shell：阅读 [shell.md](references/shell.md)。
   - Lean：阅读 [lean.md](references/lean.md)。
   - TeX/LaTeX：阅读 [tex.md](references/tex.md)。
   - 对其他语言，从仓库 manifest、锁文件、贡献文档和现有 CI 推导命令。复用仓库权威命令；明确标记不支持或未验证的检查，不得虚构工具链。
7. 使用 [ci-cd.md](references/ci-cd.md) 设计 CI；只有发布或部署属于任务范围且方式已知时才设计 CD。GitHub 阅读 [github.md](references/github.md)，Gitee 阅读 [gitee.md](references/gitee.md)。其他托管平台保持命令与厂商无关，只使用已经验证的平台能力，并列出所需外部设置，不得虚构平台特定文件。SonarQube 已可用或正在评估时阅读 [sonarqube.md](references/sonarqube.md)。通过 [platform-capabilities.md](references/platform-capabilities.md) 重新核实时变声明。
8. 在 Implement 模式中，将规范写入仓库既有的约定位置。每项门禁优先提供一个权威命令，并确保本地与 CI 使用相同命令。
9. 运行可用检查。明确区分已经验证的结果，以及因工具、依赖、密钥、外部服务、套餐或权限不可用而跳过的检查。
10. 修改此 skill 包后，运行 `python scripts/validate_policy.py .` 和 `python scripts/test_validate_policy.py`；同时存在两个 locale 包时，还要向 validator 传入 `--counterpart <other-skill-root>`。

## 必须达到的结果

- 禁止直接推送稳定分支；变更必须通过经过审查且满足确定性 CI 要求的 PR 合入。
- 保持变更易于审查、提交原子化，并确保生成物和锁文件的变更是有意为之。
- 确保 taxonomy、分支名、commit/PR header、表单和 policy check 与 `policy-model.json` 一致。
- 按风险固定 CI Action/工具链版本；只有缓存键包含相关锁文件时才缓存依赖。
- 为每项必需检查提供适合分支保护的稳定、清晰名称。
- 将快速 PR 门禁与较慢的定时、发布或部署任务分开。
- 赋予 CI 任务最小权限；不得向不受信任的 Fork 代码暴露密钥。
- 按选定 release profile 只构建并验证一次发布制品，随后发布或晋级完全相同的比特。
- 除非用户已经授权，否则不得提交、推送、改写历史、创建远程分支、修改仓库设置、发布或部署。

## 交付形式

- **Assess：**仓库事实、现有控制、证据支持的 findings、已审查/跳过范围及按优先级排列的修复计划。
- **Design：**简明规范、选定 taxonomy/拓扑/release profile、文件布局、准确命令、稳定检查名称、平台设置和采用顺序。
- **Implement：**变更文件/设置、验证命令及实际结果、跳过检查、剩余外部配置及迁移/回滚说明。

每个再分发包都必须保留 [third-party-notices.md](references/third-party-notices.md)；只有检查来源或许可证义务时才加载它。
