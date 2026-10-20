# 单轮审查报告

Reviewer：复制为新的逐轮文件，替换所有 `{{...}}`。强弱审共用此报告。读历史前先保存并冻结盲审报告；历史核对/最终报告另存文件并引用盲审，不改写它。

- Review phase: blind
- Review task: {{review_task}}
- Target SHA: {{target_sha}}
- Review scope: {{review_scope}}
- Review refs: {{review_refs_json}}
- Attempt: {{attempt_id}}
- Input packet: {{input_path_and_version}}
- Scope source/version: {{scope_source_version}}
- Requirement/design version: {{intent_version}}
- Skill version: {{skill_version}}
- Environment: {{environment}}
- Reviewer / independence / contamination: {{reviewer_and_context_limits}}

长程任务原样复制 blind 的 Review refs JSON，声明本 gist，仅将冻结的盲审文件传给 `--review-report`。独立使用删除长程专用 Review task/Review refs 行，用下表绑定所有仓库。另存最终报告时将 Review phase 改为 reconcile，记录冻结报告路径/digest。模板不能把缺失证据变成已验证。

## 版本与范围绑定

| 仓库/身份 | 分支 | Base SHA | Head SHA | 证据适用性 |
| --- | --- | --- | --- | --- |
| {{repository_identity}} | {{branch}} | {{base_sha}} | {{head_sha}} | {{applicability}} |

## 主题覆盖

| 主题 | CHECKED / PARTIAL / UNKNOWN / N/A / EXCLUDED | 路径及证据 | 缺口/理由 |
| --- | --- | --- | --- |
| {{topic}} | {{coverage}} | {{scanned_paths_and_evidence}} | {{gap_or_reason}} |

每个选中主题一行，并明确排除/N/A。强审记录假设和实际探索，弱审额外引用已查内容点 ID；不对逐问题答案计分。

## 反例及相邻入口

| 承诺/假设 | 输入与失败触发 | 预期 | 实际/命令/证据 | 相邻路径/结果 |
| --- | --- | --- | --- | --- |
| {{hypothesis}} | {{counterexample}} | {{expected}} | {{observed_or_not_run}} | {{sibling_surfaces_and_result}} |

## 发现

每个独立问题复制以下块；未确认问题时删除并说明零发现不能证明完整。评级为 p0=severe / p1=risk / p2=warning / p3=suggestion。一个缺陷可有多位置，一个内容点可发现多个独立缺陷。

{{topic}}-{{finding_id}} ({{priority}}): {{module}} {{summary}}
- location: {{file_and_line_locations}}
- problem: {{trigger_observed_behavior_impact_and_priority_basis}}
- suggest: {{smallest_reasonable_remediation}}
- status: OPEN
- resolution: {{outstanding_or_versioned_independent_recheck_or_design_rejection}}
- evidence: {{code_test_runtime_refs_and_target_applicability}}

## 结果与交接

| 字段 | 值 |
| --- | --- |
| 报告完成情况 | INCOMPLETE |
| 范围完整性 | INCOMPLETE |
| 当前适用唯一 OPEN/DEFERRED P0 / P1 / P2 / P3 | {{known_counts}} |
| Score | null |
| Result | INCOMPLETE |
| 必须处理的 P0 / 有效误报证明 | {{mandatory_action}} |
| 可选保留问题 | {{retained_findings_and_impact}} |
| 人工接受/合并/发布 | 本报告不授予 |
| 下一步/补证据责任/解除条件 | {{next_action_owner_and_boundary}} |

判断完整性后才用确定性计分 helper；缺关键证据或中断保留 null/INCOMPLETE。有 findings 的报告可以完成，评分、强制返工和人工接受分别记录。

## 历史核对 — 仅最终报告

冻结前：NOT READ。盲审报告删除下列数据行；仅在另存的盲审后报告填写，不改写盲审快照。

| 冻结报告/digest | 本轮 ID → 账本 ID | 历史处置及适用复核证据 |
| --- | --- | --- |
| {{frozen_path_and_digest}} | {{id_mapping}} | {{status_transition_with_target_and_evidence}} |
