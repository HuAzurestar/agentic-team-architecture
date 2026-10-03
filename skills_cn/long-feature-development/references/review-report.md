# 完整报告与 finding 账本

收集报告后使用 `review_report.py`，不能用它代替独立审查。纯函数 `compute_report(raw, related_reports=(), verified=None)` 验证完整报告并计算数量；raw 可为 JSON 兼容对象、JSON 字符串或单个顶层 report-v1 Markdown fence。不读文件、不联系 provider、不修改输入、不派发 reviewer、不改任务状态。

## 身份与原始来源

`report_ref` 是分配给一份不可变报告的稳定逻辑 ID（例如基于 UUID 的 ID），不是该报告自身的内容 hash。finding 完整主键为 `{feature, report_ref, attempt_id, finding_id}`，duplicate_of 四字段缺一不可；check ID 只在报告内唯一。输入集合内报告身份不可重复；不同报告/attempt 的同名 finding 不自动合并，必须有显式关联与证据。

实际来源引用 `{path, sha256}` 另行绑定原始字节。只读 CLI：`python scripts/review_report.py <feature-directory> gists/report.md [--related gists/old-report.md]`，核验当前 review task 的 Gists 声明，只读取明确指定的历史报告，拒绝别名/不安全路径，输出前复核 read set；输出包含实际报告原字节摘要。不得覆盖旧报告或替换其目标 SHA；新报告记录复核时，旧 summary、finding 与 provenance 均保留。

纯计算器只校验证据引用结构，不认证资料存在、内容真实或来源独立；明确输出 `source_evidence_verified=false` 和 `quality_assessed=false`。CLI 验证报告文件，但不获取被引用证据。质量消费者必须读取并核实所有必需来源、实际 target/attempt/checklist、必需范围及宿主事实，才能消费结构结果。schema 通过、比例高或 REVIEW DONE 都不是放行权限。

## 完整 schema

使用 REVIEW-REPORT 模板。顶层包括 report/packet/attempt 身份、feature/task、literal target refs、checklist、reviewer/context、evidence_refs、checks、findings、diagnostics、summary。缺完整字段返回 LEGACY_EVIDENCE_INCOMPLETE；旧最小恢复报告继续由 review_resume.py 读取，不静默升级。

每个 check 有 id、outcome、required（布尔）、scope_ids、evidence_refs、reason、next_action、finding_ids。只允许 PASS/FAIL/UNKNOWN/NOT-RUN/N/A。PASS/FAIL 需要证据，FAIL 需要关联 finding；N/A 需要适用理由；UNKNOWN/NOT-RUN 需要原因和下一动作。需要人类范围决定时提供 scope_exception_ref。质量消费者须把 required/scope/N/A 与真实 packet 和已确认意图比对，报告不能自称 optional 来删除必需工作。

复用可增加 reuse，含完整 feature/report/attempt/check 主键 prior_check_ref、非空 diff_refs、dependency_refs、reviewer_basis。这些是待核验资料，不自动允许沿用旧 PASS。当前版本质量检查仍须验证实际 diff、范围/依赖未变及 reviewer 依据，仅同属祖先链不能沿用整份报告。

finding 包含 id、P0/P1/P2 severity、布尔 blocking、open/addressed/closed status、description、evidence_refs、affected_check_ids、resolution/verification 字段、非阻塞理由、需求违背标记及 severity_history。check 与 finding 双向关联必须一致。同一 finding ID 的相同重复记录只计一次；内容冲突则失败。重复 check ID 一律失败。duplicate_of 还须 duplicate_reason 和 duplicate_evidence_refs；不以标题相似度去重，目标缺失或链成环拒绝。

P0 必须 blocking=true。影响必需失败检查或确认意图的 P1/P2，没有当前版本已核实范围例外不能标 nonblocking；其他非阻塞建议也必须有理由。addressed 需要 resolution_ref；closed 还需要不同于实现作者的 verifier、verified_ref 及精确 verified_target_refs。仅有这些正文声称仍不能关闭：没有真实宿主核验时继续计为未关闭，诊断 CLOSURE_UNVERIFIED；旧 closed 不自动沿用新候选。

## 受信任事实与计数

VerifiedReportEvidence 是进程内宿主边界，不是 Markdown schema。不能从报告、JSON 断言或作者自证反序列化。宿主必须实际验证独立关闭、人类范围例外及严重性变更，再构造它。每个 key 都绑定完整当前报告的 canonical report_digest(raw)，含 target 与正文；报告改变即失效。CLI 故意不提供导入此类声称的开关。

severity_history 每项含 from/to、reason、独立 verified_by、verified_ref、target_refs；链须连续并以声明的当前 severity 结束。缺当前宿主核验时按历史最严重级别生效，P2 duplicate 不能隐藏 P0 根问题。真实确认的变更仍保留历史。重复组关闭须当前报告内每个成员均有独立核验关闭；没有当前成员时，须明确传入的同一当前 target 成员全部核实关闭。其他历史根问题仍可见并保持开放，等待当前证据处置。实际当前人类例外可以解除 blocking，但不声称问题已修好。

ALL = PASS + FAIL + UNKNOWN + NOT-RUN；total = ALL + N/A；ALL=0 时 ratio=null。check 计数来自当前报告，严重性及未关闭计数来自显式完整账本去重；discovered_current、inherited_current、historical_only 分开来源。原报告诊断保留来源标记与 code，不把正文泄漏到 telemetry。

summary:{} 请求重新推导；已提供的当前 summary 必须精确匹配计算后的 {valid, counts, ratio}。历史 summary 不参与算术，也不复制为新报告结果。校验或预算失败时 summary.valid=false、counts=null、ratio=null，不输出部分 100%。

## 资源与测试

整个显式报告集合共用上限：10000 checks、10000 finding 观察、30000 links、64 MiB、2 秒计算时间。证据、scope、check/finding、duplicate、history 引用都消耗 link 预算。哈希表和迭代三色遍历避免逐对文本比较及深链 Python 递归，不引入后台或 SQL 状态。

report.validate / report.summarize 事件只记数量、target refs 和错误码，不含 finding 正文、证据内容、授权文本。运行 test_review_report.py 及随包 scripts/fixtures/review-report.json 的 F04-T07/T08/T09 与拒绝路径。fixtures 明确是模拟，不证明真实独立审查、已接受范围或来源可用。
