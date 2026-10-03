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
6. 最终报告记录真实 reviewer/context 来源。允许交接不会增加已执行检查数。中断保留已执行行；`remaining_checks` 对尚未触及的必查 ID 补 NOT-RUN、原因和下一动作，已经尝试但缺证据的项用 UNKNOWN。此 helper 不验证报告结果或授权 PASS；解释数量与质量资格前仍须完整报告校验。

`packet.build` 日志仅含 attempt ID、来源/检查数、字节数、耗时和错误码。CLI 不输出包/来源正文或授权文本；拒绝时也不能记录完整输入。

旧最小 `review-packet-v1` 恢复记录仍由 `review_resume.py` 读取，不是完整交接包。不能静默升级或补造独立性证据。修改此边界时运行 `test_review_packet.py` 和原有 review/context 回归；模拟宿主 fixture 只验证拒绝逻辑，不证明 F04-T01 的真实空白审查结果。
