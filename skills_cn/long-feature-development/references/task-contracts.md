# 质量 Task 合同

只在质量、验收或 gate task 中读取。所有 task 仍使用 `transitions.md` 的统一生命周期；下列字段写在 `tasks/<task-id>.md` 的 `## Type contract` 表中。

## TEST

必需字段：`Target SHA`、`Environment`、`Planned checks`、`Executed`、`Passed`、`Failed`、`Skipped`、`Unknown`、`Result gist`。

- 报告绑定实际被测的字面 SHA，不改标为当前候选或记账 HEAD。影响被测功能及依赖闭包的语义变化才要求新测试 attempt/task；整树未变或宿主新鲜核验完整输入闭包未变时，可以在当前质量 attempt 中复用原结果，不改写旧任务/报告目标。详见[质量适用性](quality.md)。
- 合同只放数量和短检查名；命令、日志、截图、失败原因和覆盖详情放入 `gists/TEST-*.md`。
- 执行、通过、失败、跳过、未知分别记录，不得把部分执行写成“全部通过”。
- 项目已有受支持 Docker 环境时优先使用，不为满足规则而引入 Docker。
- 确定性 mock 仅在项目已有约定位置且无敏感信息时提交，否则放在 gist 或临时测试环境。

## REVIEW

必需字段：`Target SHA`、`Blocking findings`、`Deferred findings`、`Result gist`。具体评论和长推理写入 `gists/REVIEW-*.md`。阻断发现建立依赖的 `REWORK-*`，不得改写已完成开发 task。

## REWORK

必需字段：`Source findings`、`Target SHA`、`Output SHA`、`Result gist`。它依赖发现问题的 review；复测使用新的依赖 `TEST-*`，保持 tested SHA 明确。

## ACCEPT

新建 task 的必需字段：`Target SHA`、`Acceptance scope`、`Decision`、`Decided by`、`Acceptance brief`。brief 是从 `templates/ACCEPTANCE.md` 创建并在 `Gists` 声明的 `gists/` 路径；缺少该字段的历史完成 task 仍可读取。Agent 提出范围、准备并主动展示自然语言 brief，但最终决定只能由 developer 提供。WIP 期间保持 `WAITING`；进入 RECORDING 后持久化 developer 的 `CONFIRMED`、`REJECTED` 或 `REWORK`，再完成 refs。

## GATE

必需字段：`From phase`、`To phase`、`Required tasks`、`Decision ref`。必需 task 必须与 gate 直接依赖一致；`Decision ref` 是记录流转的项目管理 commit，记录前为 `-`。

未启动 PENDING Gate 只按[审查流程](review.md)通过受控依赖 helper 改前置，它同步 Required tasks 并记录部分效果。
在途接受/Gate 不可就地换依赖，也不能被新任务隐藏。REVIEW DONE 表示报告已交付而非无 blocker；真实 finding 建立新的 REWORK → TEST → REVIEW 链。
