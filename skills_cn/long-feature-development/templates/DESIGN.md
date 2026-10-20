# example-feature — DESIGN

design/ 中的 YAML 是状态来源，此表是预览。通用字段固定展示，关系和其他专用字段汇总到 detail spec；点击 ID 查看完整详情。

## preview-table

<!-- design-preview-table:start -->
| id | title | type | state | decided by | decided at | decided with | detail spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [INT-001](design/INT-001.md) | 校验输入数据并说明无效原因 | intent | RECORDED | requester@example.invalid | - | - | revision: v1<br>intent type: requirement-intent<br>source: {location: external:message/example-001} |
| [REQ-001](design/REQ-001.md) | Report invalid entries with a reason | requirement | PROPOSED | - | - | - | revision: v1<br>relate to intent: INT-001@v1 |
| [SOL-001](design/SOL-001.md) | Validate entries before accepting them | solution | PROPOSED | - | - | - | revision: v1<br>relate to requirement: REQ-001@v1 |
<!-- design-preview-table:end -->

## complementary

按日期追加补充说明（YYYY-MM-DD — 内容）。只维护本节和介绍文字，不手改生成区。
