# Markdown Multi-Remote Sync 回归测试计划

本文档用于验证 `scripts/md-sync` 的本地 Markdown 与 GitHub、YouTrack 之间的下载、上传和双向同步功能。

## 测试环境

- GitHub 仓库：`HuAzurestar/test-repo`
- Gitee 仓库：`liangyu-hu/test-repo`
- YouTrack 地址：本地 YouTrack 实例
- 本地配置：`config/sync.yaml`
- 编码要求：所有 Markdown、YAML、日志均使用 UTF-8
- Token：只允许保存在本地 `config/sync.yaml`，禁止提交到 Git

## 命令约定

```powershell
cd scripts/md-sync
$env:PYTHONPATH='.'
python -m src.controller.main status
python -m src.controller.main download <file.md> --remote <provider>:<id>
python -m src.controller.main upload <file.md> --target <provider>/<type>/<project>
python -m src.controller.main sync-to-remote <file.md>
python -m src.controller.main sync-to-remote <file.md> --joint
python -m src.controller.main sync-from-remote <file.md>
```

## 测试文档清单

| 编号 | 测试文档/对象 | 操作 | 预期结果 |
|---|---|---|---|
| T01 | GitHub Issue #1 | download | 创建 UTF-8 Markdown，包含 YAML、标题、正文和基本 Issue 字段 |
| T02 | GitHub Issue #3 | download + upload | 删除平台 ID 后上传创建新 Issue；父 Issue 关系被设置；PR 关系只警告并保留本地 |
| T03 | GitHub Issue #4 | download | 获取 parent issue、sub issues；子 Issue 只下载，不自动上传或移动 |
| T04 | GitHub PR #6 | download | 获取标题、正文、分支、提交、reviewer、CI check、deployment 等 development 信息 |
| T05 | GitHub PR 新分支 | upload | 使用 `base_branch` 和 `head_branch` 创建新 PR；本地 YAML 回写新 PR ID |
| T06 | YouTrack Issue DEMO-9 | download | 获取项目、优先级、类型、状态、指派人、版本、估算、关系等存在的字段 |
| T07 | YouTrack Issue DEMO-37 | download + 修改 | 修改标题和正文后执行 sync-to-remote；默认只更新标题和正文 |
| T08 | YouTrack Article DEMO-A-2 | download | 获取标题、项目、父 Article、子 Article，并保持正确父子方向 |
| T09 | YouTrack Article 子文章 | download + upload | 只绑定当前文章的父 Article，不把当前文章错误移动到其它父文章下面 |
| T10 | 多端 Markdown | download + sync-to-remote | `id` 中存在多个平台 ID 时，按第一个平台 ID 作为主端 |
| T11 | 两份本地副本 | 一份修改后 sync-to-remote，另一份 sync-from-remote | 未修改的副本从远端重新获取后，与远端内容一致 |
| T12 | `--joint` 模式 | 修改 YAML 扩展字段后执行 sync-to-remote | 明确允许时才尝试同步额外字段；失败必须记录，不得静默成功 |
| T13 | Gitee Issue | download 已创建的 Gitee Issue | 获取标题、正文、仓库和状态，并正确写入 `gitee_issue` |
| T14 | GitHub Issue → Gitee Issue | GitHub download 后 upload 到 Gitee | 创建 Gitee Issue，并回写 Gitee ID；API 失败时保留原文件且明确报错 |
| T15 | Gitee Issue → GitHub Issue | Gitee download 后 upload 到 GitHub | 创建 GitHub Issue，并回写 GitHub ID |
| T16 | Gitee PR | 使用存在的 base/head 分支 upload、download、sync | 获取和更新标题、正文、分支、状态；无分支时明确拒绝 |
| T17 | Gitee 对称性 | 对照 GitHub Issue/PR 字段逐项检查 | 双方共有字段使用统一 YAML 名称；平台独有字段放在各自平台节点 |

## 拒绝与错误回归

| 编号 | 测试对象 | 操作 | 预期结果 |
|---|---|---|---|
| E01 | 无 YAML 的 Markdown | sync-to-remote | 拒绝，提示必须存在 YAML front matter 和 `doc_type: markdown` |
| E02 | 无平台 ID 的 YAML | sync-to-remote | 拒绝，不调用远端 API |
| E03 | GitHub `HuAzurestar/test-repo#100` | download | API 返回 404，拒绝，不创建本地文件 |
| E04 | YouTrack `DEMO-100` | download | API 返回 404，拒绝，不创建本地文件 |
| E05 | YouTrack Article `DEMO-A-100` | download | API 返回 404，拒绝，不创建本地文件 |
| E06 | 远端正文为空 | download | 拒绝写入本地文件，避免生成无效备份 |
| E07 | upload 已存在 ID | upload | 拒绝创建重复远端对象，并提示使用 sync-to-remote |
| E08 | PR 缺少分支 | upload PR | 拒绝，提示必须提供 `base_branch` 和 `head_branch` |
| E09 | GitHub PR 关联 | upload | 输出警告：公共 API 无法创建 Development 关联；不能伪装成成功 |
| E10 | 不同仓库父子 Issue | upload | 拒绝设置父子关系，避免跨仓库错误绑定 |

## 默认同步模式

默认执行 `sync-to-remote` 时，只同步：

- 标题
- Markdown 正文

默认跳过：

- 项目
- 状态、优先级、类型
- 指派人、标签、版本
- 父子关系和其它远端管理字段

只有显式添加 `--joint` 时，才允许进入扩展字段同步流程。被发送和被跳过的字段都必须写入本次日志。

## 日志验收标准

每次 CLI 执行都应生成独立日志：

```text
md-sync.yyyymmdd.hhmmss.msms.log
```

日志首行必须包含完整 CLI 参数，例如：

```text
CLI ARGS: python ...\\src\\controller\\main.py sync-to-remote example.md --joint
```

关键节点至少包括：

- CLI 参数
- 解析到的本地文件和平台 ID
- 选择的主平台
- 请求的 API 方法和路径
- 实际发送的字段
- 跳过的字段及原因
- API 响应状态码
- 错误状态码和响应摘要
- 本地文件是否写入

## 通过标准

1. 所有成功测试的 YAML 和正文均保持 UTF-8。
2. 所有失败测试均明确报错，不得伪装成成功。
3. 远端不存在时不得创建本地空文件。
4. 默认模式不得修改非正文属性。
5. `--joint` 才能触发扩展字段同步。
6. Token、完整 Authorization 头和敏感配置不得出现在日志或 Git 提交中。
7. GitHub Issue/PR、YouTrack Issue/Article 的 ID 必须正确回写到本地 YAML。
8. Gitee Issue/PR 的 ID、标题、正文、状态、分支和可用关系字段遵循同样的回归标准。

## 已执行结果（2026-08-30）

| 测试 | 实际结果 |
|---|---|
| GitHub PR #13 download | 成功，生成 `github-pr13-to-gitee.md`，包含标题、正文、base/head 和 commit 信息 |
| GitHub PR #13 → Gitee Issue | 成功，创建 `liangyu-hu/test-repo#IKC1GX`，并回写本地 `gitee_issue` |
| Gitee Issue `IKC1GX` download | 成功，标题、正文、状态和仓库信息可读取 |
| Gitee Issue 字段检查 | 成功读取状态、类型、作者、指派人、标签、里程碑字段；本次 Issue 的里程碑、标签为空，按规则省略 |
| Gitee Issue 关系检查 | 已调用关联 PR 接口；本次没有关联 PR；父子字段为空，未伪造关系 |
| Gitee Issue 初次 upload | 首次失败，原因是错误使用 GitHub 风格创建路径；修正为 Gitee `/repos/{owner}/issues?repo={repo}` 后成功 |
| Gitee Issue/PR 列表 | Issue 存在 `IKC1GX`；PR 列表为空 |
| Gitee 仓库分支 | 分支列表为空，无法进行真实 Gitee PR 创建回归 |
| Gitee PR upload | 已用 `base_branch: main`、`head_branch: test-gitee-pr` 实测；API 返回 400“目标库为空”，正确拒绝且未创建 PR |
| Gitee PR 基线创建 | 创建 `master` 基线和 `test/md-sync-pr` 分支，并提交 `pr-fixture.md` 作为差异 |
| Gitee PR upload（重测） | 使用 `master` → `test/md-sync-pr` 创建成功，得到 `liangyu-hu/test-repo#1` |
| Gitee PR #1 download | 成功获取标题、正文、base/head 分支和 commit 信息 |
| GitHub Issue #1/#3/#12 download | 按“远端正文为空即拒绝”规则失败，不生成本地空备份 |
| 不存在对象 `#100`/`DEMO-100`/`DEMO-A-100` | 均返回 404 并记录 API 错误详情 |
| 跨平台 sync-to-remote | 已修正为按 `id` 中所有平台 ID 更新，而不是只更新主平台 |

## Gitee 与 GitHub 对称性检查

Gitee Provider 已使用与 GitHub 相同的抽象入口：`fetch`、`create`、`update`。当前已对称支持：

- Issue/PR 的标题和正文下载、创建、更新；
- Issue/PR 的平台 ID 写回 YAML；
- Issue/PR 的状态、作者、标签等基础字段保留在平台 YAML 节点；
- PR 的 base/head 分支和 commit 信息下载；
- Issue 关联 PR 信息下载；
- UTF-8 JSON/Markdown、API 状态码和错误摘要日志；
- 默认安全同步与 `--joint` 参数入口。

仍需在拥有有效分支和 PR 的 Gitee 仓库中补测：PR 创建、PR 更新、reviewer、CI 检查、deployment、分支关联以及 Issue-PR Development 关系。Gitee 测试仓库当前为空仓库，因此这些项目暂记为 BLOCKED，不视为通过。
