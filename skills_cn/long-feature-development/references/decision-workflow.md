# 决定工作流入口

宿主使用 `decision_workflow.PointWorkflow(feature_directory, session=host_session)`
处理明确指定的单个 REQ/SOL 决定。`inspect(point_id, record)` 读取实际原文和
真人来源，返回适用性和原文差异；`apply(point_id, record)` 应用决定提交，再用
独立状态提交登记准确 SHA。管理仓库从 Feature 注册表解析。完成后重入只读，
未知 dispatch 先读保留 refs，不重复发起写入。

可嵌入 CLI：`decision_workflow.main(argv, session=session)`。

```text
FEATURE SOL-001 --decision /path/to/decision.json --format text
FEATURE SOL-001 --decision /path/to/decision.json --apply --format json
```

默认只检查；`--apply` 明确请求应用。输入是 decision-evidence-v1 原件，不携带
权限。独立执行且未配置宿主 session 时返回 HUMAN_SOURCE_UNAVAILABLE。
Workbench/Agent 入口从自己的凭据库和预先绑定的消息／权限来源建立 session，
不得从决定文档或 CLI 导入插件、凭据或权限开关。

## 原生来源适配

`decision_native.NativeDecisionSession(feature=..., source_key=...,
message=..., authorization=...)` 接受两个现有 `review_native.NativeDocument`
实例，分别绑定原消息和当前权限服务。两者必须属于同一 Feature/provider，URL
和 source_ref 不同。HTTPS 服务以 UTF-8 text/plain 返回 JSON，使用 identity
编码和强 ETag。传输复用已有超时、体积、凭据和重定向约束；开发夹具才显式
开启本机 HTTP。

消息服务验证原作者身份并保存原回复／时间，返回完整 human-message-v1 对象：
`schema, source_ref, actor, actor_kind=human, received_at, text, interpretations`。
interpretations 是数组，每项为 `{decision_digest, basis_ref}`，绑定完整决定的
摘要与宿主已核实的解释出处。摘要不解释自然语言；未消除歧义的回复不得产生
适用解释，整体同意不得扩张成未逐项列举的点决定。适配器读取服务保存的解释，
不从上传决定自行制造解释。

独立权限服务返回 `{schema: human-authorization-v1, grants: [...]}`。每条 grant
包含 `actor, feature, decision_kind, source_key, exact_scope, outcomes`。点决定
outcomes 仅为 CONFIRMED/REJECTED/OUT-OF-SCOPE/INFEASIBLE/REOPENED；接受仅为
CONFIRMED/REJECTED/REWORK；范围例外仅为 APPROVED/REJECTED。空 outcomes 可撤销
该授权。缺项、重复、坏格式或账号／范围／来源不匹配均拒绝。

每次请求重读当前服务权限；gateway 再读实际消息和解释，修改后的消息必须更新
ETag。服务错误只返回原因码。JSON 结构本身不证明身份：信任来自独立配置的
认证传输及服务 ACL。具体平台账号映射和服务部署属于运行时接入配置。

已准备好的接受状态写入可使用
`session.acceptance_reader(preparation, decision_document=...,
candidate_repository=..., exact_scope=...)` 提供证据读回器。既有 AcceptanceReader
仍独立验证声明的 brief、实际产品 SHA 和准备的元数据；记录拒绝／返工不会
放行产品。

## 已被下游使用的点

重开遇到已分配的下游任务时返回 DEPENDENCY_COORDINATION_REQUIRED，逐项显示
任务 ID、状态和依赖。调用方先处置真实旧 attempt，通过受控依赖／返工流程形成
合法任务图，再继续应用。进行中的接受需要实际决定或明确 attempt 处置；不得
伪造完成。协调完成前保留原点不变。

本轮集中检查 `test_decision_workflow.py` 使用实际本机 HTTP 消息／权限服务和
临时 Git 仓库，检查撤销权限、两提交应用及完成后的 CLI 重入。服务身份为
明确标记的合成夹具，生产账号验证和全面跨平台检查留待审查。
