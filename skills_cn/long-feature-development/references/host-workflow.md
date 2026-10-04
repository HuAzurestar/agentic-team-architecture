# 前台宿主与接受尝试接续

`feature_host.FeatureHost` 是 Skill-only 调用方入口，组合现有点决定、审查、接受、
返工和质量 API；不引入服务、Web UI、调度器或插件导入器。

宿主代码配置 REQ／SOL session、接受 session、审查来源、独立认证的操作授权读取器
和质量来源读取器。缺能力时保持不可用，不能从 Markdown、人名或 CLI 参数生成权限。
原生消息／权限服务为可选路线，既有已认证会话适配器可提供相同的每次重新读取的
read_reply／interpret／read_grant。本包不部署服务，也不因构造 session 而认证账号。

## 调用入口

组合的业务入口为 [point_workflow.py](../scripts/point_workflow.py)、
[decision_workflow.py](../scripts/decision_workflow.py)、
[review_workflow.py](../scripts/review_workflow.py) 和
[acceptance_workflow.py](../scripts/acceptance_workflow.py)。认证点流程的集中检查见
[scripts/test_decision_workflow.py](../scripts/test_decision_workflow.py)；服务身份为合成夹具，
不作为生产账号验证证据。

```text
python scripts/feature_host.py FEATURE context --format json
python scripts/feature_host.py FEATURE review --purpose development
python scripts/feature_host.py FEATURE acceptance ACCEPT-01
python scripts/feature_host.py FEATURE quality --config /path/to/source-bindings.json
```

独立命令只读诊断。无真人 session 的独立点应用会拒绝；已配置宿主可通过
`feature_host.main(argv, host=host)` 显式调用既有点 CLI 的 apply。仓库 override
由宿主持有，不能通过第二组 CLI override 替换。无隐式推送、合并或新增权限。
程序入口为 `point(id)`、`review()`、`acceptance()`、`rework()` 及
`assess_quality(config_bytes)`。

## 在途接受的完整处置与接续

F04-T06 要求的是保留旧尝试并取得真实处置，不是任意改写已启动任务。
没有实际决定时保留旧 target／brief／历史及 WIP／BLOCKED；不能用未启动 Gate
隐藏在途接受。“继续实施”的指令不等于接受 REWORK／REJECTED。

1. 通过 `host.acceptance().prepare/record` 记录实际旧决定，另作管理检查点并恢复。
   本接续路线仅接受已完成 REWORK／REJECTED 的旧接受尝试。
2. 用现有任务规划器为修复候选建立新审查尝试，保留旧报告 target 和 finding，
   新审查使用相同的明确 REQ／SOL selectors。
3. 调用 `host.rework().preview_successor(old_acceptance, new_review,
   decision_path=declared_original_path, candidate_repository=registered_name,
   exact_scope=scope_tuple)`。它独立读取已提交的实际决定／brief，核对旧 target、
   scope、actor 与当前真人来源／权限，并验证新审查的候选绑定。内部 ID 自动分配。
4. 显式调用 `create_successor(plan, **binding)`，宿主操作权限绑定完整计划并重新读取。
   新接受为 PENDING、Decision=WAITING、Decided by='-'，不继承 brief 或完成 refs；
   旧任务／brief／回复保持原样。APPLIED_PENDING_CHECKPOINT 要求先作管理检查点。
   已存在的同一后继只读观察，不重复创建。
5. 对仍 PENDING 的下游调用 `rewire_pending(old, successor, downstream,
   expected_index_digest=actual_digest, operation_gist=declared_gist, **binding)`。
   重新核验实际旧处置、后继范围／新审查及精确宿主权限，复用有日志的依赖写入器。
   已启动下游拒绝；部分／未知效果按原 UUID 走 F03 对账，不重复发起或自动回滚。
6. 再作检查点并恢复。新接受等待新审查及当前质量证据，随后提供新 brief 和真人决定。
   旧拒绝或 DONE 行不放行合并／Gate。

`AcceptanceWorkflow.verify_disposition` 可验证已经前进的产品仓库中的旧负面决定，
因为它只处置冻结的旧接受，不把接受迁移到新产品版本。

创建复用前台协调锁下的既有 task_create，不承诺跨文件事务。中断或结果未知时先检查
实际任务文件并恢复，再写入；不自动重试创建、提交、发布或合并。

后继 writer 使用统一的最终 before_write guard：核对捕获的文件集，回读当前操作权限，
回读结束后重核实际仓库读集（身份、HEAD、分支、注册 refs、本地配置及产品工作区状态）
和完整文件集，然后才允许 task_create 写准备内容。管理运行锁不算版本变化，管理字节
单独核对。这是写入目标绑定，不是规定每次 SHA 变化都使适用测试证据作废。
回读期间的其他编辑或产品提交返回 SUCCESSOR_SOURCE_CHANGED，并保留原样；
不新增后继、不执行补偿回滚／reset。正常检查点／
恢复后，依据保留的新内容重新制定计划，不用 reset 抹掉编辑。这是乐观本地核对，
不是跨 ACL／文件的原子事务，也不锁住最后比较之后的任意外部 writer。

## 保留边界与验证

本流程不改写已启动任务的历史依赖，不增加 snapshot-task schema。点重开仍有已启动
消费者时，保持 DEPENDENCY_COORDINATION_REQUIRED；通用历史点迁移需要额外明确策略，
不能以放宽图校验悄悄实现。

`test_rework_workflow.py` 集中检查真实 Git 的负面决定、无权限拒绝、内部后继分配、
检查点分隔接续、重入、未启动 Gate 改接及旧记录原字节保留。身份 transport 为合成夹具；
生产账号和独立审查证据继续分开记录。
