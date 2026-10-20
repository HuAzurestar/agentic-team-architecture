# Review attempt report

Reviewer: copy to a new attempt file and replace every `{{...}}`. Strong and weak modes share this report. Save and freeze the blind report before reading history; reconciliation/final reporting uses a different file and references the frozen report, never edits it.

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

Long feature: copy the exact `Review refs` JSON from blind recovery, declare this gist, and use only the frozen blind file as `--review-report`. Standalone: remove the long-feature-only Review task/Review refs lines and bind all repositories below. For a separate final report, change Review phase to reconcile and record the frozen report path/digest. Missing evidence never becomes verified through a template.

## Version and scope binding

| Repository / identity | Branch | Base SHA | Head SHA | Evidence applicability |
| --- | --- | --- | --- | --- |
| {{repository_identity}} | {{branch}} | {{base_sha}} | {{head_sha}} | {{applicability}} |

## Topic coverage

| Topic | CHECKED / PARTIAL / UNKNOWN / N/A / EXCLUDED | Paths and evidence | Gap / reason |
| --- | --- | --- | --- |
| {{topic}} | {{coverage}} | {{scanned_paths_and_evidence}} | {{gap_or_reason}} |

One row per selected topic, plus explicit exclusions/N/A. Strong mode records hypotheses and actual exploration; weak mode additionally references checked content-point IDs. This is not a per-question score.

## Counterexamples and sibling paths

| Promise / hypothesis | Input and failure trigger | Expected | Observed / command / evidence | Sibling paths / result |
| --- | --- | --- | --- | --- |
| {{hypothesis}} | {{counterexample}} | {{expected}} | {{observed_or_not_run}} | {{sibling_surfaces_and_result}} |

## Findings

Copy the block for each independent issue; remove it if no issue was established and explicitly state that zero findings alone do not prove completeness. Priority is p0=severe / p1=risk / p2=warning / p3=suggestion. One defect can have several locations; one content point can yield several defects.

{{topic}}-{{finding_id}} ({{priority}}): {{module}} {{summary}}
- location: {{file_and_line_locations}}
- problem: {{trigger_observed_behavior_impact_and_priority_basis}}
- suggest: {{smallest_reasonable_remediation}}
- status: OPEN
- resolution: {{outstanding_or_versioned_independent_recheck_or_design_rejection}}
- evidence: {{code_test_runtime_refs_and_target_applicability}}

## Result and handoff

| Field | Value |
| --- | --- |
| Report completion | INCOMPLETE |
| Scope completeness | INCOMPLETE |
| Applicable unique OPEN/DEFERRED P0 / P1 / P2 / P3 | {{known_counts}} |
| Score | null |
| Result | INCOMPLETE |
| Mandatory P0 rework / valid rejection | {{mandatory_action}} |
| Optional retained findings | {{retained_findings_and_impact}} |
| Human acceptance / merge / release | Not granted by this report |
| Next action / evidence owner / release condition | {{next_action_owner_and_boundary}} |

Use the deterministic scoring helper only after assessing completeness; retain null/INCOMPLETE for missing critical evidence or interruption. A completed report may contain findings; score, mandatory rework and human acceptance are separate.

## History reconciliation — final report only

Before freeze: NOT READ. Remove the following row from a blind report; populate only in a separate post-freeze report. Keep the blind snapshot unchanged.

| Frozen blind report / digest | Attempt ID → ledger ID | Historical disposition and applicable recheck evidence |
| --- | --- | --- |
| {{frozen_path_and_digest}} | {{id_mapping}} | {{status_transition_with_target_and_evidence}} |
