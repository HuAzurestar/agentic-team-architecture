# 质量 Task 合同

只在质量、验收或 gate task 中读取。所有 task 仍使用 `transitions.md` 的统一生命周期；下列字段写在 `tasks/<task-id>.md` 的 `## Type contract` 表中。

## TEST

必需字段：`Target SHA`、`Environment`、`Planned checks`、`Executed`、`Passed`、`Failed`、`Skipped`、`Unknown`、`Result gist`。

- 报告绑定一个字面 tested SHA；实现 SHA 改变后必须建立新 attempt 或 task。
- 合同只放数量和短检查名；命令、日志、截图、失败原因和覆盖详情放入 `gists/TEST-*.md`。
- 执行、通过、失败、跳过、未知分别记录，不得把部分执行写成“全部通过”。
- 项目已有受支持 Docker 环境时优先使用，不为满足规则而引入 Docker。
- 确定性 mock 仅在项目已有约定位置且无敏感信息时提交，否则放在 gist 或临时测试环境。

## REVIEW

必需字段：`Target SHA`、`Blocking findings`、`Deferred findings`、`Result gist`。具体评论和长推理写入 `gists/REVIEW-*.md`。阻断发现建立依赖的 `REWORK-*`，不得改写已完成开发 task。

review/v1 引用设计短 Review scope 的来源/版本；详情可保存相同 `- Review scope:` 快照及账本路径。保留旧字段，区分强制阻断与可选计分发现。P0 必须关闭；保留 P1/P2/P3 可扣分而不自动 REWORK，不免除必需检查和人工接受。

加载旧 findings 前使用 blind 恢复。原始包和本轮报告/快照在 Gists 声明，原始包标记 `- Evidence type: original`。保存含 Review phase、Review task、Target SHA、Review scope 行的盲审快照后，才以其声明路径进入 reconcile。根 REVIEW.md 是共享状态索引，不替代 Result gist 或不可变逐轮报告。有发现的报告可以完成，分数与接受分开，完整合约/ref 校验不变。

## REWORK

必需字段：`Source findings`、`Target SHA`、`Output SHA`、`Result gist`。它依赖发现问题的 review；复测使用新的依赖 `TEST-*`，保持 tested SHA 明确。

## ACCEPT

新建 task 的必需字段：`Target SHA`、`Acceptance scope`、`Decision`、`Decided by`、`Acceptance brief`。brief 是从 `templates/ACCEPTANCE.md` 创建并在 `Gists` 声明的 `gists/` 路径；缺少该字段的历史完成 task 仍可读取。Agent 提出范围、准备并主动展示自然语言 brief，但最终决定只能由 developer 提供。WIP 期间保持 `WAITING`；进入 RECORDING 后持久化 developer 的 `CONFIRMED`、`REJECTED` 或 `REWORK`，再完成 refs。

## GATE

必需字段：`From phase`、`To phase`、`Required tasks`、`Decision ref`。必需 task 必须与 gate 直接依赖一致；`Decision ref` 是记录流转的项目管理 commit，记录前为 `-`。
