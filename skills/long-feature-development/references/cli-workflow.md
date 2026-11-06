# Configured CLI workflow

Python 3.10+ is sufficient. All business IO is delegated to the actual Project-Manage Python CLI. There is no HTTP library or server filesystem access in `pm_cli.py`. Local inputs/outputs are caller working files; no persistent client history or automatic loader is installed.

The CLI reads `api.json` beside its code, or the explicit `--config` chosen by the local caller boundary. Current code contract: `{"base_url":"http://127.0.0.1:3000","host":"windows","operation_timeout_seconds":null}`. Paths in a boundary's `config` are resolved relative to that boundary. Connection/host/timeout belong to this existing CLI configuration; host is repository/hook context, not identity. Current CLI has no authentication field. Use an actual runtime-supported access route when required; do not add token fields and claim support. Do not include secrets in reports.

Example caller boundary (a local scope guard, not server authorization):

```json
{
  "feature_key": "F", "task_id": "DEV-1", "config": "api.json",
  "writer": "actual execution author", "authority_reference": "exact assignment/source",
  "allowed_fields": ["state", "result", "head sha", "resume action"],
  "allow_task_update": true, "allow_report_save": true,
  "writable_documents": ["feature/F/tasks/DEV-1.md"]
}
```

Use only actual assigned values. For read-only work omit write flags. Allowed top-level fields are the existing task-workflow whitelist: state, result, owner, depends on, resume action, head sha, completed at, started at. Do not grant unrelated ownership/dependency changes merely because they are supported. Do not add history/raw to task patches.

```text
python <aopc>/skills/long-feature-development/scripts/pm_cli.py --cli <pm>/client/cli/project_manage.py --boundary scope.json service-context --project-key P
python <aopc>/skills/long-feature-development/scripts/pm_cli.py --cli <pm>/client/cli/project_manage.py --boundary scope.json context
python <aopc>/skills/long-feature-development/scripts/pm_cli.py --cli <pm>/client/cli/project_manage.py --boundary scope.json update --data-file result.json
python <aopc>/skills/long-feature-development/scripts/pm_cli.py --cli <pm>/client/cli/project_manage.py --boundary scope.json report-save --body-file own-report.md
python <aopc>/skills/long-feature-development/scripts/pm_cli.py --cli <pm>/client/cli/project_manage.py --boundary scope.json report-get --output current-report.md
python <aopc>/skills/long-feature-development/scripts/pm_cli.py --cli <pm>/client/cli/project_manage.py --boundary scope.json document-get --path feature/F/tasks/DEV-1.md --output working.md
python <aopc>/skills/long-feature-development/scripts/pm_cli.py --cli <pm>/client/cli/project_manage.py --boundary scope.json document-put --path feature/F/tasks/DEV-1.md --raw-file working.md
```

Own-author `result.json` uses the actual CLI patch format, with current facts rather than embedded prior reports:

```json
{"metadata_patch":[{"op":"set","path":["result"],"value":{"author":"actual author","role":"DEV","candidate":"full observed SHA","outcome":"pass","summary":"actual scope and limitations","evidence":"exact original report/source"}}]}
```

These result members are free YAML metadata, not a newly enforced identity or permission schema. Report command/scope, baseline, PASS/FAIL/SKIP/UNKNOWN, original author, candidate, evidence and unfinished work in the own report. Independent TEST/REVIEW and socket-verified decisions retain their own authors and exact sources. No default orchestration proxy or manual aggregate summary is supplied.

Document download extracts the complete raw string from the CLI envelope and writes UTF-8 bytes, preserving BOM/newlines within that string. Edit the working file and upload using existing `--raw-file`; body-only work uses the existing CLI's `--body-file` through `report-save`. The service applies identity/graph/index rules. Raw save may overwrite a change made since download: there is no CAS, and an extra preflight GET would not eliminate the race. Coordinate writes externally and assess current contents before any deliberate resubmission.

Exit meanings remain: 0 acknowledged/current readback match; 1 server non-success; 2 local/transport/protocol failure, unknown readback or mismatch; 3 saved with after-hook errors/unknown. `write_cli_exit` remains visible if readback fails. Inspect hook facts and CLI error details; a matching readback does not turn exit 3 into success. No write replay or lookup cache is used. On ambiguous outcome, inspect current object and external effects before deciding what to do next.

Measurements list each subprocess exit, elapsed time and stdout/stderr bytes. Those are not wire bytes. Total requests, transport bytes and backend IO remain UNKNOWN unless separately instrumented. No cloud performance/deployment claim follows from isolated localhost tests.


For split-candidate DEV fixtures, use the actual two clean checkouts, with Node 24 and PM locked dependencies available:

```powershell
$env:AOPC_CANDIDATE = (Resolve-Path '<aopc>').Path
$env:AOPC_CANDIDATE_SHA = '<full AOPC candidate SHA>'
# Run from the paired PM checkout at its full candidate SHA.
node --import tsx --test --test-timeout=120000 tests/skill-cli.test.ts tests/task-workflow.test.ts tests/document-workflow.test.ts
```

The integration test requires the explicit AOPC absolute path, full SHA, matching HEAD and clean Skill directory. Missing/wrong locators fail clearly. It never searches installed Skills, copies a Skill into PM or skips unavailable inputs. These are isolated fixture tests, not official target, independent quality or cloud proof. Use the existing CLI configuration for service selection; clients do not receive a server PM root.
