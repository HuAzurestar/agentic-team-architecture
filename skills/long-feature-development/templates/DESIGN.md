# example-feature — DESIGN

YAML in design/ is the state source. This table previews common fields and summarizes relationships and all other specialized metadata in detail spec; follow the ID link for the full detail.

## preview-table

<!-- design-preview-table:start -->
| id | title | type | state | decided by | decided at | decided with | detail spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [INT-001](design/INT-001.md) | Validate incoming data and explain invalid entries | intent | RECORDED | requester@example.invalid | - | - | revision: v1<br>intent type: requirement-intent<br>source: {location: external:message/example-001} |
| [REQ-001](design/REQ-001.md) | Report invalid entries with a reason | requirement | PROPOSED | - | - | - | revision: v1<br>relate to intent: INT-001@v1 |
| [SOL-001](design/SOL-001.md) | Validate entries before accepting them | solution | PROPOSED | - | - | - | revision: v1<br>relate to requirement: REQ-001@v1 |
<!-- design-preview-table:end -->

## complementary

Append dated notes here (YYYY-MM-DD — note). Maintain this section and the introduction, not generated regions.
