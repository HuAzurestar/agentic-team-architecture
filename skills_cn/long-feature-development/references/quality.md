# 质量证据与放行边界

共享严格恢复入口在信任 clean status 前拒绝 `assume-unchanged` / `skip-worktree` 索引项，返回 HIDDEN_INDEX_STATE。管理仓库只检查当前 Feature，实现/支持仓库检查全仓库；其他管理 Feature 不扩大纳入。读取有界 NUL 分隔索引标记，不刷新索引、不自动清标记。隐藏编辑不能因为普通 Git status 不显示就成为已确认意图；恢复前应明确核对标记和内容，读取器不会覆盖这些工作。

## 实际宿主组合

### 只读命令行诊断

执行 `python scripts/quality_host.py <feature-directory> --config <bindings.json> --repo app=<actual-path> --format json`，省略 `--format` 则输出文本。文本显示 eligible、原因码、缺失检查、阻塞项、过期/证据引用及下一核对，明确 NOT_APPLIED 且不授予 merge；JSON 为同一判断。退出码 0 表示 eligible，1 表示原件读取完成但策略拒绝，2 表示配置/上下文/来源无效。stderr 仅输出 `quality.evaluate` 的 phase、allowed、原因码、目标向量和毫秒耗时，不记录原件正文或凭据。

显式配置限 4 MiB，schema 为 `quality-host-config-v1`，仅有 `schema, roles, documents, repositories`。roles 包含 `request, report, tests, checklist, related_reports`（数组）和 `result_tests`（路径或 null）。每个 document 仅含 `logical_path, repository`（登记名）、`relative_path`；仓库物理路径和 HEAD 由严格读取器实时解析，不接受 JSON 自报。每个 repository binding 含 `repository_ref, remote, expected_remote, source_branch, source_sha, source_tree, target_branch, target_before`，候选/冻结 refs 应独立保留并与实际 Git 核对。这些只是来源选择，不是范围授权或身份凭证。重复 key、未知字段（包括 allowed/provenance/module）、链接、超限及观察期间配置变化均拒绝，保留外部修改。

独立 CLI 没有真实 reviewer/真人 transport，不会把完整原件升级为已核实独立性或接受，而是报告缺失来源。实际 Python 宿主可嵌入 `main(argv, read_provenance=其真实认证读回器)`；没有命令行信任开关或可执行模块导入。两种方式都执行相同原件/策略核验。准备中状态写入适配、实际平台读回器部署、逐点决定提交和 UI 仍须分别完成。

`quality_host.evaluate(root, documents=..., roles=..., repositories=..., read_provenance=..., repo_overrides=...)` 实际调用严格本地 Feature 恢复，再读取已提交 Git 原件及实时交付状态。完整 quality-request-v1 原件内的报告、关联报告、测试和结果测试，必须分别等于独立读取的原件，并对应任务声明的 Result gist；登记源仓库 HEAD 和声明的实际物理路径须一致。真实摘要不能搭配另一份 PASS 对象，也不能用其他路径的相同副本代替声明源。结构化清单为仅含 `schema, required_checks` 的 `quality-checklist-v1`，完整映射和清单路径/摘要须一致；不把既有散文自动升级为已验证清单。

SourceRoles、仓库及文档绑定由宿主独立配置，不从项目文件反序列化权限。真实认证的 `read_provenance` 回调取得不可变完整请求/原件字节和版本，摘要绑定 Feature 与实际交付观察。宿主须独立核实 reviewer 身份/上下文、当前审查链、关闭/降级证据、排除/复用及真人决定与候选适用性，才返回对应摘要的 HostProvenance。类型和摘要本身不是认证；不接受 JSON allowed 标记或动态插件。没有回调时，原件可读也仍因独立性未核实而拒绝。回调错误脱敏。

组合入口重算策略，并重读来源权限、全部原件、严格 Feature 和交付事实后返回 Assessment。`Assessment.for_task(current_source_ref, task_id)` 提供已有 selector/state guard 消费的 QualityInputs；消费者再次比较完整计划并重算策略，不跨操作边界缓存。不 merge/publish/改任务或持久化第二份 Gate。该入口只接干净已提交元数据；准备中的状态写入须专门核对，不提供忽略 dirty 的开关。真实平台认证配置、准备中写入组合、生产工作流/UI 调用及逐点决定提交仍是未完成集成。真实 Git 测试只证明来源和组合行为，身份回调明确为合成夹具。

## 状态写入接入

`task_state.update(root, args, evidence_reader=host_reader)` 已在新 Acceptance WIP 前检查 pre_accept，在最终 DONE Gate 的 WIP/RECORDING/DONE 前检查 post_merge。Acceptance 带真实决定进入 RECORDING 或 DONE 走独立的 decision_host.inspect_decision 路径；适用的 CONFIRMED、REJECTED、REWORK 均可记录。REVIEW 完成和 WAITING 的 Acceptance RECORDING 不要求零 blocker；旧来源不足会拒绝新写入，不改历史状态。普通 CLI 不提供证据导入参数，因此受保护写入需要配置 Python 宿主读取器。

读取器收到不可变 TransitionRequest，绑定实际根目录、任务、原/目标状态、完整修改前后索引摘要及有界实际 feature 文件读集。宿主必须独立核对准备中的元数据，并新读实际仓库/远端、审查和真人事实，返回绑定 request.digest 的 TransitionEvidence。QualityInputs 使用同一绑定和精确任务；writer 核对任务图、实际 REQ/SOL 摘要并重算阶段策略。回调是可信宿主配置，不能从项目文件加载；类型和摘要不等于认证，完整平台适配仍需完成。

HumanDecisionInputs 提供原决定及已配置的当前对象/回复/解释读取器与 grant。writer 要求已声明的实际六章节 brief 等于获准/当前正文，唯一顶层 Target version/目标版本等于任务 Target SHA，actor/feature/kind/outcome 一致，再由既有人类网关重读来源。writer 调用宿主两次，包括替换前，并复核来源成员/摘要；变化时保留外部修改、停止替换，晚期失败只清理本 writer 临时文件。这是既有单协调者下的乐观检查，不是 OS 权限边界或跨文件/远端原子事务。合并/发布执行和逐点决定提交仍是独立操作。

## 下一动作接入

`task_next.GateEvidence.quality_inputs` 接收宿主专用 `QualityInputs(source_ref, task_id, feature, request, observations, report_evidence, decision_sources)`。选择器在建议请求接受（pre_accept）、合并/发布（pre_merge）或最终 DONE Gate（post_merge）前实际重算 assess_quality，核对精确选择读集/任务、完整规范任务图/契约及阶段。ready 摘要、序列化 allowed 标记、别的计划或旧观察不能替代策略；历史明细缺失返回 LEGACY_EVIDENCE_INCOMPLETE，不改旧 DONE。CLI 的 host JSON 刻意不能导入 QualityInputs；已认证宿主应通过 Python API 组合，不从 stdin 制造核实事实。

操作权限及既有直接矛盾检查仍有效；质量成功不授予合并/发布权限。正常合并后的对应判断绑定已接受 source vector 和实际 result，不仅因普通 merge SHA 不同就重收决定。普通工作、返工/重测/复核及非最终 Gate 不添加零阻塞限制。选择器只建议动作；上文独立状态写入接入核验受保护 task_state 流转。两者均不执行逐点决定提交或合并/发布。详见[组合测试](../scripts/test_quality_selection.py)；其宿主来源为合成夹具，不代表真实独立审查。

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

`quality_git.observe_delivery(binding, phase, result_sha=...)` 将下面的集成对应读取与实际远端目标、干净工作区读取组合。接受/合并前要求检出候选分支；合并后要求检出结果目标分支并已发布结果。使用实际 `ls-remote`，不信任旧 remote-tracking refs，并在本地核对前后重复观察。远端缺失/不可达/移动、分支错误或 detached、未跟踪/暂存/未暂存变更、assume-unchanged/skip-worktree 隐藏状态及未结束 Git 操作均拒绝。状态读取尊重 CRLF 等检出配置，不刷新索引，不 fetch/merge/push。成功仅增加实际 working branch/head/remote target 以及 `remote_target_verified=true`、`worktree_verified=true`，仍不授予质量成功或合并权限。这是乐观回读而非锁，也不证明独立 reviewer 或真人来源；完整质量宿主仍须消费这些事实并在操作边界重读。

`quality_git.observe_integration(IntegrationBinding(...), phase, result_sha=...)` 读取实际本地 Git 对象和 refs。宿主独立提供已登记仓库身份、source 分支/SHA/tree、target 分支及冻结的 target-before SHA。校验分支名、仓库根与配置 remote 身份，并在观察前后核对两分支和身份。共享 Git runner 禁用 replace objects，读取器拒绝本地 graft 文件；不 fetch、改 refs、刷新 index、merge 或 push。

接受/合并前，source ref 必须仍为冻结的候选，local target 必须等于 target-before。target-before 必须是 source 的真实祖先，source 的实际整棵树须等于保留的候选树。对于已同步目标的 source，这些事实确定正常 merge 的预期树，但不授权 merge。

合并后，target 必须等于精确 result SHA，source 仍为冻结候选，result 必须以 source 为祖先，且实际整棵结果树等于保留候选树。普通 no-fast-forward merge 因而可以具有新 SHA，不自动使已接受内容失效；fast-forward 同样可满足该对应关系。目标移动、source 未同步目标、结果改树，或 squash/rebase 缺少所需祖先关系时即停止。仅 diff 相似不能转移批准。

返回的 valid 仅表示本地对应关系，并附 source/tree/target-before/result 事实；始终明确 quality_assessed=false、merge_authorized=false、remote_target_verified=false、worktree_verified=false。消费方仍须独立核对权威远端目标、干净应用工作区、当前测试、独立审查关闭、范围、真人决定及真实操作授权，不得把该只读结果标成质量通过。每条 Git 子进程使用共享 50 秒 I/O 预算，与后续纯策略的 2 CPU 秒聚合预算分开。最后一次观察不锁定 refs，实际操作边界仍需重核。
