# 接受工作流入口

Agent／Workbench 宿主使用 `acceptance_workflow.AcceptanceWorkflow(feature_directory,
session=session, repo_overrides=...)`。session 与点决定入口一样，提供 feature、
source_key 及每次重新读取的 read_reply／interpret／read_grant；可接原生服务或
已认证的平台适配器。决定文件和 CLI 参数不加载回调或制造权限。

`inspect(task_id)` 只读实际保存的接受状态、依赖、候选、范围、brief 和决定，
不访问真人服务、不写文件。独立 CLI 只提供此检查：

```text
python scripts/acceptance_workflow.py FEATURE ACCEPT-01 --repo product=/path/to/repo
```

## 记录一个真实决定

1. 将实际 decision-evidence-v1 决定和六段 brief 保存为任务声明且已提交的原件。
   目标是实际产品候选，不是保存管理材料的提交。通过配置 session 读取真人原话；
   协调请求不能当作产品接受。
2. 构造 WIP → RECORDING 或 RECORDING → DONE 的 task_state 参数，以及详情／STATUS
   的精确候选字节。在完整基线仍干净时调用 `workflow.prepare(args, changes)`，
   再由调用方现有文件编辑机制仅准备这些精确修改。
3. 调用 `workflow.record(preparation, decision_document=git_document,
   candidate_repository=registered_name, exact_scope=scope_tuple)`。入口将
   AcceptanceReader 接到受保护 task_state 写入器，核验旧范围／brief／候选、
   当前真人来源及独立权限，仅原子替换 TASKS.md 和派生拓扑。
4. APPLIED_PENDING_CHECKPOINT 要求另作管理检查点并严格恢复后再执行下一操作。
   下一状态转换须在该检查点之后重新捕获干净准备；dry-run 返回 NOT_APPLIED。
   异常、中断或效果未知时先检查实际文件并恢复，不能自动重复调用。

入口不准备任意文件、不提交／推送／合并、不创建新 attempt、不改依赖。
跨文件准备仍与索引原子替换分开，不承诺跨文件事务。

## 在途 attempt 的处置

适用的真人 REJECTED／REWORK 决定可完成冻结接受 attempt，不提供质量成功或合并许可。
保留旧 target、brief 和真人记录；新审查／候选使用新 attempt，仅仍 PENDING 的
下游能通过 task_dependencies 改依赖。没有适用真人决定时保留旧 attempt WIP，
或按现有 WIP → BLOCKED 规则记录具体阻塞。不能用新产品 HEAD 偷换旧候选。

接受入口不移除重开 REQ／SOL 点的历史依赖。已启动消费者会导致无效任务图时，
PointWorkflow 仍返回 DEPENDENCY_COORDINATION_REQUIRED。接受 attempt 的处置不能
单独解决该图冲突；不得重置已启动任务或放宽图校验来强行重开。

跨平台及 provider 整链验证留待统一审查。入口实现不代表生产身份服务已部署，
也不代表当前 Feature 已获人类接受。
