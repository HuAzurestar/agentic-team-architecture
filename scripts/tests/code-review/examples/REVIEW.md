# 账本示例：仅在 blind-01.md 保存后建立

这是合成模板效果示例，不是 PIRC-39 的真实审查账本。输入为 review-input.md，冻结报告为 blind-01.md；账本保存持续状态，报告保存当时观察。

## 当前轮次

| 字段 | 值 |
| --- | --- |
| Attempt | template-demo-01 |
| Review scope | review/v1 mode=strong topics=data exclude=ui |
| 候选版本 | 9da5125751785e248db5edc101975bd15136936d 的合成现金函数 |
| 原始输入 | review-input.md / demo/v1 |
| 冻结报告 | blind-01.md，不覆盖 |
| 独立性 | 非独立模型审查；作者演示已知夹具 |
| 当前适用 P0 / P1 / P2 / P3 | 1 / 0 / 0 / 0 |
| Score / Result | 0 / FAIL，仅对合成 DATA-01 范围 |
| 人工接受 | 未发生 |

## 问题索引

| 账本 ID | 本轮 ID/报告 | 状态/评级 | 当前适用目标 | 修复/复核证据 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| data-001 | data-001 / blind-01.md | OPEN / p0=severe | 上述候选的 DATA-01 | 未修复、未独立复核 | 真实交付时需技术修复及独立复核；本例保留夹具 |

问题完整描述及原始实验仍在冻结报告，不通过本账本预加载到下一轮输入。

## 变更与轮次历史

本轮仅建立 OPEN 记录，没有 FIXED/REJECTED 的证据。未来修复只能先记提交；独立复核有效后才转 FIXED，并引用新报告。第一轮 blind-01.md 的 0 分及反例不会被改成通过。
