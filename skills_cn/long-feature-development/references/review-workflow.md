# 前台审查工作流

`review_workflow.ReviewWorkflow` 为 Agent／Workbench 连接既有 Git 和原生审查
组件。宿主绑定一个 Git 来源或 NativeDocument，写入时另外绑定已声明的操作
gist 和当前授权读取器。`read(purpose, explicit_review=..., statuses=...,
rv_ids=...)` 仅在审查用途或明确请求时读取；来源未绑定为空态，已绑定而不可达
报错。读取结果保留 agent_consumed=false，显示意见不代表 Agent 已处理。

独立 CLI 只读，按 STATUS.md 注册的仓库路径和 remote 身份读取实际远端 master：

```text
python scripts/review_workflow.py FEATURE --repository app --review-path REVIEWS.md
python scripts/review_workflow.py FEATURE --repository app --status VERIFIED --rv-id RV-UUID
```

结果 JSON 保存选中的原评论和来源观察。原生调用方注入已配置的
`main(argv, workflow=configured_workflow)`，或直接调用 read；凭据由宿主配置。

## 样本核对与同步

`preflight(observation, expected_working_head=..., expected_branch=...,
samples=...)` 使用实际 GitSampleBinding。MASTER_SYNC_REQUIRED 表明需同步
精确 master 版本。`prepare_master_sync(observation)` 持久记录 F03 操作并返回
operation_id／intent_digest；宿主保留两者，获授权后调用
`synchronize_master(operation_id, intent_digest)`。既有同步器处理实现仓库与
管理仓库的差异、dispatch 和未知结果重入。同步后重新读取意见，以新实际 HEAD
和样本再次 preflight。冲突处置及最终集成仍走各自授权流程。

## 条件发布

`prepare_publication(draft, observation=..., supersedes=...)` 绑定完整来源、三种
意见状态、草稿摘要及明确替代的冲突，调用已有 Git lease／原生 If-Match
准备器，返回 operation_id／intent_digest。准备保留本地草稿，不立即发布。
`publish(operation_id, intent_digest)` 核对本来源的操作记录，再读取该操作的
当前授权；后端先保存 dispatch，再发送一次条件写。重入读回相同 RV UUID，
409 或未知结果保留草稿，沿用不自动重试规则。
`inspect_publication(operation_id)` 只读核对远端，不改 journal。UI 可显示实际
结果和保留草稿位置，但不能将其标为 Agent 已消费。

## 宿主授权

`authorize(request)` 是受信任的进程内读取器，不能从 CLI／JSON 导入。请求绑定
action、feature、root、独立配置的 source、operation gist 和精确版本／草稿或
operation／intent 范围。宿主核验当前实际权限后返回
`ReviewPermission(permission_digest(request), actual_authority_source_ref)`。
类型或摘要不证明权限；缺失或绑定不符在调用 writer 前拒绝。执行时重新读取
授权，不沿用准备阶段的旧许可；每次执行先核对 journal 确属当前来源。

provider、发布和同步底层已有回归。依用户最新安排，组合生产账号／provider
验证留待后续审查；新增入口本身不执行远端发布或 master 同步。
