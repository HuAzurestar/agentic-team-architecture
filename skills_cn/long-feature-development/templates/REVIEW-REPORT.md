# 审查报告

替换全部占位符，保留原固定目标；新候选使用新的逻辑 report_ref 和 attempt。
列出每项必查检查，保留 UNKNOWN 与 NOT-RUN，不从分母移除。
本模板故意不完整，不证明独立性，也不授予接受权限。

```report-v1
{
  "schema": "report-v1",
  "result": "BLOCKED",
  "reason": "REPLACE-actual-conclusion-and-basis",
  "report_ref": "REPLACE-unique-report-id",
  "feature": "REPLACE-feature",
  "review_task": "REVIEW-01",
  "packet_id": "REPLACE-packet-id",
  "attempt_id": "REPLACE-attempt-id",
  "target_refs": {"app": "REPLACE-full-candidate-SHA"},
  "checklist_ref": {"path": "gists/checklist.md", "sha256": "REPLACE-original-byte-digest"},
  "reviewer": "REPLACE-actual-reviewer",
  "context": {
    "source_ref": "REPLACE-actual-host-context-source",
    "authority_ref": "REPLACE-actual-authorization-source",
    "implementation_author": "REPLACE-author"
  },
  "evidence_refs": [{"path": "gists/evidence.md", "sha256": "REPLACE-original-byte-digest"}],
  "checks": [{
    "id": "CHECK-001",
    "outcome": "NOT-RUN",
    "required": true,
    "scope_ids": ["REQ-001"],
    "evidence_refs": [],
    "reason": "REPLACE-missing-material-or-interruption",
    "next_action": "REPLACE-concrete-next-step",
    "finding_ids": []
  }],
  "findings": [],
  "diagnostics": [],
  "summary": {}
}
```

实际发现问题时使用以下字段（不要为填模板而编造 finding）：

```json
{
  "id": "FINDING-001",
  "severity": "P1",
  "blocking": true,
  "status": "open",
  "description": "REPLACE-observed-failure",
  "evidence_refs": [{"path": "gists/evidence.md", "sha256": "REPLACE-original-byte-digest"}],
  "affected_check_ids": ["CHECK-001"],
  "resolution_ref": null,
  "verified_by": null,
  "verified_ref": null,
  "verified_target_refs": null,
  "nonblocking_reason": "",
  "follow_up": "REPLACE-rework-or-explicit-follow-up-plan",
  "violates_requirement": true,
  "severity_history": []
}
```

在受影响 checks 中回链实际 finding。重复来源使用四字段完整主键、明确根因依据及证据。
作者修复记 addressed，不是 independently closed。精确关闭、严重性变更、例外和复用字段
见 references/review-report.md；普通报告正文不能认证这些决定。
