# 分支规范

## 默认方案：主干开发

使用 `main` 作为受保护且始终保持绿色的分支。从最新 `main` 创建短生命周期主题分支，尽早打开 PR，通过审查和必需检查后合并，随后删除主题分支。

分支名使用小写 ASCII kebab-case：

```text
feature/<issue>-<summary>
fix/<issue>-<summary>
docs/<issue>-<summary>
refactor/<issue>-<summary>
perf/<issue>-<summary>
test/<issue>-<summary>
build/<issue>-<summary>
ci/<issue>-<summary>
chore/<issue>-<summary>
proof/<issue>-<summary>
paper/<issue>-<summary>
revert/<issue>-<summary>
release/<version>
hotfix/<issue>-<summary>
```

普通受跟踪工作必须包含 Issue 段。例如：`feature/142-lean-parser`、`fix/87-tex-crossrefs`、`ci/203-python-matrix`。仓库没有问题跟踪器时，应采用明确记录的替代标识，不能静默取消可追溯性。

## Issue 类型绑定

使用一套权威映射，并在 Issue 元数据、分支、Commit 和 PR 之间强制执行：

| Issue 类型/标签 | 分支前缀 | Commit/PR type | 用途 |
| --- | --- | --- | --- |
| `feature` | `feature/<issue>-...` | `feat` | 新增用户可见能力 |
| `bug` | `fix/<issue>-...` | `fix` | 缺陷修复 |
| `documentation` | `docs/<issue>-...` | `docs` | 纯文档变更 |
| `refactor` | `refactor/<issue>-...` | `refactor` | 不改变行为的重构 |
| `performance` | `perf/<issue>-...` | `perf` | 有度量依据的性能工作 |
| `test` | `test/<issue>-...` | `test` | 纯测试变更 |
| `build` | `build/<issue>-...` | `build` | 构建系统、打包或依赖图变更 |
| `ci` | `ci/<issue>-...` | `ci` | 流水线/工作流变更 |
| `maintenance` | `chore/<issue>-...` | `chore` | 仓库维护 |
| `proof` | `proof/<issue>-...` | `proof` | Lean 定理/证明工作 |
| `paper` | `paper/<issue>-...` | `paper` | TeX/论文内容或制作 |

权威机器可读映射位于 [policy-model.json](policy-model.json)。`hotfix/<issue>-...` 是 `bug` Issue 的发布路径覆盖，Commit/PR type 仍为 `fix`。`revert/<issue>-...` 是 `bug` 或 `maintenance` Issue 的动作覆盖，Commit/PR type 为 `revert`，PR 必须说明被回退 commit 及原因。`release/<version>` 是 release 覆盖，通常由 `maintenance` Issue 支持；只有仓库记录了狭窄的发布自动化例外时才可免 Issue。

创建或接受分支前，验证引用 Issue 存在、处于开放/可执行状态、属于预期仓库，并且恰好有一个主工作流类型。分支前缀与 Commit/PR type 必须匹配主类型或 `policy-model.json` 中声明的 override。每个普通 commit 和 PR 标题必须携带相同主 Issue。如果工作类别发生变化，应重新分类 Issue，或创建/拆分正确 Issue 后重命名/替换分支；不得为了绕过政策而改 label。

平台原生链接属于附加证据，不能替代命名和 CI 验证。平台支持时，从 Issue UI 创建/链接分支，让 Issue 显示正在开发。CI 通过平台 API 验证 Issue 存在性、状态、类型/label、分支前缀、Commit type 和 PR 链接。

当分支中的中间提交没有独立保留价值时，优先使用 squash merge；每个提交都经过认真整理时，优先使用 rebase merge。只有项目明确希望保留分支拓扑时才允许 merge commit。绝不改写共享的受保护分支。

## 只有充分理由时才增加长期分支

只有团队确实需要一个区别于“下一个可部署状态”的集成状态时，才增加 `develop`。只有存在稳定化窗口且主开发仍需并行进行时，才增加 `release/<version>`。生产热修复从当前已部署的稳定引用开始，并合并或 cherry-pick 回所有仍受支持的开发线。

记录每个长期分支的来源和合入目标。避免使用 `staging`、`production` 等环境分支；应在不同环境之间晋级不可变制品。

## 分支保护基线

- 必须通过 PR、具名检查、解决全部对话，并至少获得一次批准。
- 安全敏感或高风险代码在批准后发生变化时，撤销旧批准。
- 禁止受保护分支的强制推送和删除。
- 只有选定合并策略支持时才要求线性历史。
- 使用 `CODEOWNERS` 指定需要专家审查的区域，但不能以此替代常规审查。
