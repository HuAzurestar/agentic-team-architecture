# 审查包与只读交接

准备审查或复核时读本文件。先用 `task_context.py` 恢复真实 Feature；审查包校验不能代替任务、Git 或质量校验。将 [REVIEW-PACKET.md](../templates/REVIEW-PACKET.md) 放入任务声明的 gist。新候选、清单或派发必须使用新的 packet、attempt 和 reviewer-assignment ID；保留全部旧包和报告。

## 构建与检查

`python scripts/review_packet.py <feature-directory> gists/<packet>.md` 只读验证明确声明的原始字节及摘要，输出目标 refs、点 ID、必查数量和缺口，不完整时返回 2。退出码 0 只表示**材料完整**，不是独立审查或质量通过。CLI 不派发，也不认证宿主，始终返回 `handoff_allowed=false`、`INDEPENDENCE_UNVERIFIED`、`independent_executed=0`。

API `build_packet(inputs, documents=..., host=..., previous_packets=...)` 接收不可变原始字节，不以开发者摘要替代原文。`documents` 将精确的 Feature 相对路径映射为 `bytes`，没有隐式文件读取或外链展开。`target_refs` 保持 F03 的 repo 名称/完整 SHA 映射；`repositories` 补充稳定身份与声明的固定候选源文件/diff 快照。宿主必须将快照与实际可访问 Git 对象核对，文件 hash 相符不能单独证明这种关系。交付完整 REQ/SOL 原文，不能只给实现者记得选择的点；审查者据原文检查拟定范围和清单有无遗漏。

每个来源用 `{path, sha256}` 绑定原始字节（含 BOM/换行）。Evidence 增加 `kind`：`test`、`contract`、`fixture` 或 `dependency`；至少含真实测试记录及一个契约/fixture/依赖记录。helper 校验结构及字节，不认证正文事实或充分性。排除项含 scope、reason 和原始 decision_ref；引用本身不产生范围例外权限。必查项使用唯一的本地 ID。

资源上限只能降低：1000 文件、总计 64 MiB、单文件 4 MiB、10000 检查。CLI 的文件/字节预算包含 packet 和 task detail。包及证据不能存凭据、聊天记录。来源限 REQ/SOL 原文或任务明确声明的 gist；大小写别名、越界、链接/junction、读取期间变动及重复声明会被拒绝。

## 宿主边界及手动空白会话

1. 协调者核验冻结 repo 身份/SHA 和来源快照，取得真实的当前 reviewer 启动权限，并核对工具、预算、只读保护。不得从 Markdown 或预选项推导授权；packet 的 authority 只是实际来源引用。
2. 使用获授权宿主启动真正空白的 reviewer 会话，或请用户手动打开。只交付包及原始材料，不带开发聊天。实现文件、REQ/SOL、STATUS/TASKS 和已有证据均只读。仅允许写入新的精确 `review-output/...` 路径，不得覆盖已有输出或选择来源；协调者随后将不可变报告导入声明 gist。本 Python helper 不负责强制文件系统 ACL。
3. 受信任宿主适配器只能依据实际 API 返回/对话和已强制实施的权限构造 `HandoffEvidence`，其 digest 必须匹配本包、授权、assignment 和输出。不能从 packet 正文、JSON 断言文件或 reviewer 自证反序列化。宿主能力不足时记录 `INDEPENDENCE_UNVERIFIED` / `NOT-RUN`，不能把作者自检或新 Python 进程当独立审查。
4. 用 `previous_packets` 提供宿主拥有的派发历史。同一包可重入校验，但不能再次授权派发；每次真实新派发均追加历史。本模块没有持久派发服务，不做后台任务。
5. Reviewer 先读原始资料并记录初步覆盖，此后宿主才可展开 `prior_report_refs` 做复核/对照。准备阶段不读旧报告；之后读取时仍须核验可用性和摘要，不能从包准备成功推导。
6. 最终报告记录真实 reviewer/context 来源。允许交接不会增加已执行检查数。中断保留已执行行；`remaining_checks` 对尚未触及的必查 ID 补 NOT-RUN、原因和下一动作，已经尝试但缺证据的项用 UNKNOWN。此 helper 不验证报告结果或授权 PASS；解释数量前运行[完整报告计算器](review-report.md)，schema/数量有效仍不授予质量放行资格。

`packet.build` 日志仅含 attempt ID、来源/检查数、字节数、耗时和错误码。CLI 不输出包/来源正文或授权文本；拒绝时也不能记录完整输入。

旧最小 `review-packet-v1` 恢复记录仍由 `review_resume.py` 读取，不是完整交接包。不能静默升级或补造独立性证据。修改此边界时运行[审查包测试](../scripts/test_review_packet.py)和原有 review/context 回归；模拟宿主 fixture 只验证拒绝逻辑，不证明 F04-T01 的真实空白审查结果。

## 受控依赖替换

纯函数[依赖规划器](../scripts/task_dependencies.py)提供
`plan_dependencies(index_bytes, detail_bytes, task_id, expected_index_digest, dependency_ids)`。
生成新索引/拓扑与 Gate Required tasks 前，核验原始字节摘要、全图、尚未分配且无 start refs 的 PENDING 目标和原有类型契约；依赖 ID 按输入顺序去重。
上限为 10000 节点、30000 边、输入合计 4 MiB、2 秒 CPU；超限整体拒绝预览，保留 BOM/换行。

纯函数结果含原始/候选字节，不得作为事件元数据记录；CLI 只输出 ID、数量、摘要、变更路径和错误。
修改时运行[依赖回归测试](../scripts/test_task_dependencies.py)。
READY 只代表依赖任务状态，不代表审查成功、人工接受或允许合并。
已启动接受或 Gate 必须保留实际 attempt，不能用新任务隐藏，也不能伪填人类拒绝来代替尚未收到的决定。

先执行 `python scripts/task_dependencies.py FEATURE TASK --depends-on REVIEW-02` 预览，核对旧/新依赖并保留精确的 `expected_index_digest`。
只有实际会话授权后才重复命令并加 `--apply --authorized --expected-index-digest DIGEST --operation-gist gists/DECLARED.md --authority-source-ref SESSION-REF`；
必要时显式传 `--repo NAME=PATH`。这些参数声明真实调用者决定，Markdown 不授予权限。

API `replace_dependencies(feature, task_id, expected_index_digest, dependency_ids, ...)` 核验当前 feature、已跟踪记录及 Git refs，
先在当前任务已声明且存在的 gist 持久化有限 `dependency-rewire` 意图，再修改 TASKS.md 的索引/派生图及 Gate 的 Required tasks。
每个文件原子替换，不是全事务；F03 来源读取和意图大小上限同样适用，超限拒绝写入。
链接/别名、非所属或已暂存改动、过期来源和移动 refs 均拒绝；不改变任务状态、接受决定、Git 提交或远端。

中断后用 `task_reconcile.py FEATURE --plan-gist GIST --operation-id UUID` 只读检查实际字节；
只有新的真实授权 `--apply --authorized` 才补齐缺失一侧。依赖 CLI 也接受 operation ID，gist 参数为 `--operation-gist`。
第三种文件值一律冲突，不回滚、不覆盖；已经完成的重试不重复写文件。随后单独提交一致的管理记录并运行 task_context.py。
协议假设单一协作 writer，不能承诺对编辑器在最终读取/替换间竞争的全文件系统事务。

完整交付的 REVIEW 可以带 blocker 而 DONE；只有真实 finding 才建立 REWORK → TEST → REVIEW，每个结果绑定自己的目标，旧报告不改写。
尚未启动的接受前置可指向最新完整复核链；若接受或 Gate 已在途，保留停止 attempt 和候选失效事实，先取得真实人类处置再建新 attempt，
不能伪填 REJECTED/REWORK 令旧任务完成。替换还会拒绝从目标依赖祖先中移除在途接受/Gate。
finding 独立关闭和最终质量资格另行检查，不能从依赖修改推导。
