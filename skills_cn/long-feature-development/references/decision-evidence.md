# 决策证据与适用性

`scripts/decision_evidence.py` 是纯适用性校验器，不读取来源、不写入决定、不更新任务状态，也不评估质量。实际来源适配器和策略集成仍需实现。

`decision-evidence-v1` 记录保留 `decision_id`、`feature`、`human_source_ref`、`actor`、带时区的 `received_at`、`decision_kind`、`target_ref`、`exact_scope`、`outcome`、`original_reply` 和 `approved_body`。目标标识来源及完整 Git SHA 或实际平台原生条件版本；不得为平台对象伪造 Git SHA。

- `point` 仅绑定一个 REQ/SOL ID，结果为 CONFIRMED、REJECTED、OUT-OF-SCOPE、INFEASIBLE 或 REOPENED。逐项枚举的多点回复须拆分成单独绑定的记录与提交。
- `acceptance` 允许 CONFIRMED、REJECTED 或 REWORK。负面决定可记录，但不授予合并权限。
- `scope-exception` 对明确枚举的范围允许 APPROVED 或 REJECTED，不等同于点确认或整体验收。

当前材料须来自独立核验的来源读取，不能复制决定自称的目标。Feature、类型、范围和来源必须一致。版本或正文变化返回 `DECISION_STALE`；正文变化提供有界线性变更区间差异。保留原回复与原批准材料。适用性不表示已写入，也不表示审查、测试或合并条件成立。

`VerifiedDecisionSource` 是宿主专用事实，不凭 Python 类型完成认证。仅在实际会话或平台回读核实人类身份、权限、解释、回复及批准材料后构造；它绑定整条记录摘要与回读引用。不得从 Markdown/JSON 中自称人类来源的字段构造。测试中的合成实例不是真实决定。本纯模块不提供导入器或来源认证适配器。

记录与当前材料合计限制 4 MiB，范围最多 1,000 个明确 ID，CPU 预算 2 秒。差异每侧最多保留 4,096 字符并标记截断。预算或 schema 失败拒绝适用性。事件仅含决定 ID、适用性与原因码，不含回复、正文、身份或差异文本。
