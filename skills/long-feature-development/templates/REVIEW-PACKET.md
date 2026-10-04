# Review packet

Copy into a task-declared gist, replace every placeholder, and declare all source
gists on that review task. Hash original bytes, not normalized Markdown. This is
an intentionally incomplete template, not permission to dispatch or a report.
Read [review instructions](../references/review.md) before using it.

```review-packet-v1
{
  "schema": "review-packet-v1",
  "packet_id": "REPLACE-unique-packet-id",
  "attempt_id": "REPLACE-unique-attempt-id",
  "reviewer_assignment": "REPLACE-unique-dispatch-id",
  "feature": "REPLACE-feature",
  "review_task": "REVIEW-01",
  "mode": "review",
  "target_refs": {"app": "REPLACE-full-candidate-SHA"},
  "repositories": {
    "app": {
      "identity": "REPLACE-stable-repository-identity",
      "source_refs": [{"path": "gists/source.md", "sha256": "REPLACE-original-byte-digest"}]
    }
  },
  "scope": {
    "requirement_ids": ["REQ-001"],
    "solution_ids": ["SOL-001"],
    "requirement_ref": {"path": "REQUIREMENT.md", "sha256": "REPLACE-original-byte-digest"},
    "solution_ref": {"path": "SOLUTION.md", "sha256": "REPLACE-original-byte-digest"},
    "acceptance_scope": "REPLACE-exact-scope",
    "exclusions": []
  },
  "checklist_ref": {"path": "gists/checklist.md", "sha256": "REPLACE-original-byte-digest"},
  "checklist_reason": "REPLACE-why-this-checklist-covers-current-scope",
  "required_check_ids": ["CHECK-001"],
  "evidence_refs": [
    {"path": "gists/test.md", "sha256": "REPLACE-original-byte-digest", "kind": "test"},
    {"path": "gists/contract.md", "sha256": "REPLACE-original-byte-digest", "kind": "contract"}
  ],
  "authority": {
    "source_ref": "REPLACE-real-host-authorization-reference",
    "read_only": true,
    "allowed_tools": ["read", "diff"]
  },
  "limits": {"max_files": 1000, "max_bytes": 67108864, "max_file_bytes": 4194304, "max_checks": 10000},
  "prior_report_refs": [],
  "expected_output": {
    "schema": "report-v1",
    "path": "review-output/REPLACE-new-report.md",
    "coordinator": "REPLACE-coordinator",
    "missing_policy": "UNKNOWN/NOT-RUN"
  }
}
```

For recheck set mode to `recheck` and list immutable `{path, sha256}` prior report
refs separately. Exclusions use `{scope, reason, decision_ref: {path, sha256}}`;
the host verifies the actual human decision and its current applicability.
