# Review report

Replace all placeholders, keep the original fixed target and use a new logical
report_ref and attempt for a new candidate. Include every required check; retain
UNKNOWN and NOT-RUN instead of removing them. This intentionally incomplete
template does not certify independence or grant acceptance.

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

For an actual finding use these fields (not a fabricated mandatory finding):

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

Link the actual finding back from the affected checks. Duplicate origins use all
four key fields, explicit root-cause reason and evidence. Author fixes are
addressed, not independently closed. Read references/review-report.md for exact
closure, severity-change, exception and reuse fields; plain report text cannot
authenticate those decisions.
