# 质量证据与放行边界

## 下一动作接入

`task_next.GateEvidence.quality_inputs` 接收宿主专用 `QualityInputs(source_ref, task_id, feature, request, observations, report_evidence, decision_sources)`。选择器在建议请求接受（pre_accept）、合并/发布（pre_merge）或最终 DONE Gate（post_merge）前实际重算 assess_quality，核对精确选择读集/任务、完整规范任务图/契约及阶段。ready 摘要、序列化 allowed 标记、别的计划或旧观察不能替代策略；历史明细缺失返回 LEGACY_EVIDENCE_INCOMPLETE，不改旧 DONE。CLI 的 host JSON 刻意不能导入 QualityInputs；已认证宿主应通过 Python API 组合，不从 stdin 制造核实事实。

操作权限及既有直接矛盾检查仍有效；质量成功不授予合并/发布权限。正常合并后的对应判断绑定已接受 source vector 和实际 result，不仅因普通 merge SHA 不同就重收决定。普通工作、返工/重测/复核及非最终 Gate 不添加零阻塞限制。此接入只建议动作，尚不完成 REVIEW/ACCEPT、写决定或守护 task_state 修改。详见[组合测试](../scripts/test_quality_selection.py)；其宿主来源为合成夹具，不代表真实独立审查。

## 实际本地来源快照

`quality_source.read_git_documents(tuple_of_GitDocument)` 从实际 Git 对象、索引和工作文件读取配置的原材料。宿主传入逻辑证据路径、已登记仓库/路径及独立观察的 HEAD，不得从上传声明反序列化绑定。核对仓库根、当前 HEAD、普通已提交 blob、精确索引项、有界 UTF-8 正文和安全无链接工作文件，再复核整个已读集合。只容许 CRLF 检出差异；source refs 摘要绑定实际工作字节，HEAD/blob 版本单独保留。重复路径/物理身份、缺失来源、暂存变化及并发变化均拒绝。上限为 1,000 文档、合计 64 MiB，每个 Git 子进程 I/O 超时 50 秒；不写 refs、索引或来源。

不可变快照的 `object(path, schema)` 解析完整 JSON 或唯一明确 schema 标记的 Markdown 围栏，拒绝重复 JSON 键和歧义围栏。`require_object(path, schema, expected)` 将完整策略输入与实际原件比较，防止真实摘要搭配伪造 PASS 明细；每次返回新的解析对象。消费者必须从实际读取导出报告/测试/checklist，并在操作边界重读；快照不锁文件。读取器不证明远端新鲜性、审查独立性、关闭权限或真人决定；完整可信宿主适配和任务/UI 接线仍需完成。

## 三阶段纯判断

`quality_policy.assess_quality(validated_feature, request, observed=..., report_evidence=..., decision_sources=...)` 只读。feature 必须是既有 `task_context.ValidatedFeature`，不能用 JSON 替代。宿主专用 QualityObservations 绑定完整请求摘要及 feature 读集/仓库摘要；字段表示实际核实的来源 `(path,sha256)`、审查独立性、当前审查链、完整仓库范围、checklist 与必查项对应、当前人类排除、逐项复用、Git 集成事实、权威远端目标和精确接受-候选绑定。类型或摘要不是认证；这些值必须来自真实宿主读回，本纯模块不提供该适配器，也不从文档导入可信事实。合成测试不证明独立审查、真人接受或真实平台权限。

quality-request-v1 精确字段为 schema、feature、phase、target_refs、attempt_id、checklist_ref、required_checks、report、related_reports、tests、result_tests、frozen、acceptance。报告须为原始 report-v1，不接受计数摘要；必查项为 `{id,scope_ids}`，对应关系须与独立读取的 checklist 一致。完整已确认 ACTIVE REQ/SOL 范围取自已验证 feature 原文，不让报告自选范围。当前 Review 及 Test 任务须实际 DONE，但 DONE 不替代明细成功。test-results-v1 字段为 schema、test_task、target_refs、attempt_id、checks；每项含 id、required、outcome、scope_ids、evidence_refs、reason。必需失败/未知/未跑、漏项/漏范围、缺来源或未核实关闭都会阻止放行。没有宿主核实的精确当前人类排除，N/A 不能删除必需范围。

frozen 按候选仓库映射 source_tree、target_before、result，合并前 result 为 null。每仓库均须匹配独立核实的 Git 对应关系和远端目标；当前 feature HEAD 在合并前匹配候选，合并后匹配结果。逐项复用需要 prior check、显式差异/依赖/reviewer 依据及宿主核实；目标变化不能沿用旧 attempt ID。原始缺陷账本及独立核实的关闭/降级证据仍为依据，比例和作者自标 closed 均不能覆盖 blocker。

pre_accept 不要求尚未产生的接受。pre_merge 还要求来源核实、当前适用的 CONFIRMED 接受，且完整候选绑定须独立核实。acceptance 包含 decision_evidence 的 record/current，decision_sources 提供真人读回事实；REJECTED/REWORK 可以是真实已记录决定，但不允许 merge。post_merge 另需实际 source/result 祖先和整树对应、当前结果目标以及精确 result/attempt/scope 的 result_tests；普通 merge 产生新 SHA 不会单独触发重收接受。

输出 eligible/allowed、reason_codes、missing_checks、open_blockers、stale_refs、required_next_actions、evidence_refs，始终 NOT_APPLIED、merge_authorized=false。不改变 REVIEW/ACCEPT 完成状态，也不持久化另一份 Gate 状态。上限为累计 10,000 检查/发现/catalog 条目、30,000 遍历关联、64 MiB 序列化请求和包含报告计算的 2 CPU 秒。日志把未知自定义诊断正文归为固定代码；历史明细缺失返回 LEGACY_EVIDENCE_INCOMPLETE，不改历史。真实宿主适配、持久化决定写入及 task_state/task_next/UI 消费仍未完成。

任务完成不等于质量成功。审查可以带 blocker 完成；真实 REJECTED/REWORK 接受可以结束任务，却不允许集成。完整质量策略须分别在 pre_accept、pre_merge、post_merge 阶段核对当前审查/测试明细、完整 REQ/SOL 范围、独立缺陷关闭与适用的人类证据；不能把不完整历史记录自动升级。下述读取器不等于该聚合策略及任务/宿主接线已完成。

## 实际 Git 集成对应关系

`quality_git.observe_integration(IntegrationBinding(...), phase, result_sha=...)` 读取实际本地 Git 对象和 refs。宿主独立提供已登记仓库身份、source 分支/SHA/tree、target 分支及冻结的 target-before SHA。校验分支名、仓库根与配置 remote 身份，并在观察前后核对两分支和身份。共享 Git runner 禁用 replace objects，读取器拒绝本地 graft 文件；不 fetch、改 refs、刷新 index、merge 或 push。

接受/合并前，source ref 必须仍为冻结的候选，local target 必须等于 target-before。target-before 必须是 source 的真实祖先，source 的实际整棵树须等于保留的候选树。对于已同步目标的 source，这些事实确定正常 merge 的预期树，但不授权 merge。

合并后，target 必须等于精确 result SHA，source 仍为冻结候选，result 必须以 source 为祖先，且实际整棵结果树等于保留候选树。普通 no-fast-forward merge 因而可以具有新 SHA，不自动使已接受内容失效；fast-forward 同样可满足该对应关系。目标移动、source 未同步目标、结果改树，或 squash/rebase 缺少所需祖先关系时即停止。仅 diff 相似不能转移批准。

返回的 valid 仅表示本地对应关系，并附 source/tree/target-before/result 事实；始终明确 quality_assessed=false、merge_authorized=false、remote_target_verified=false、worktree_verified=false。消费方仍须独立核对权威远端目标、干净应用工作区、当前测试、独立审查关闭、范围、真人决定及真实操作授权，不得把该只读结果标成质量通过。每条 Git 子进程使用共享 50 秒 I/O 预算，与后续纯策略的 2 CPU 秒聚合预算分开。最后一次观察不锁定 refs，实际操作边界仍需重核。
