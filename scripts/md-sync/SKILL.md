---
name: md-sync
description: Use the scripts/md-sync controller to synchronize UTF-8 Markdown documents with GitHub, Gitee, and YouTrack Issues, Pull Requests, and Articles.
metadata:
  short-description: Sync Markdown across GitHub, Gitee, and YouTrack
---

# Markdown Multi-Remote Sync

Use this skill when a user asks to download, upload, or synchronize a Markdown document with GitHub, Gitee, or YouTrack through `scripts/md-sync`.

## Entry point

Run commands from `scripts/md-sync` with `PYTHONPATH=.`:

```powershell
python -m src.controller.main status
python -m src.controller.main download <file.md> --remote <provider>:<id>
python -m src.controller.main upload <file.md> --target <provider>/<type>/<project>
python -m src.controller.main sync-from-remote <file.md>
python -m src.controller.main sync-to-remote <file.md>
python -m src.controller.main sync-to-remote <file.md> --joint
```

Supported ID keys are `github_issue`, `github_pull_request`, `gitee_issue`, `gitee_pull_request`, `youtrack_issue`, and `youtrack_article`.

## Required behavior

- Treat remote IDs in YAML as authoritative; local Markdown is a backup and synchronization payload.
- Use the first platform ID under `id` as the primary platform when resolving conflicts.
- `download` creates or refreshes a local Markdown file from a remote object.
- `upload` creates a new remote object and writes its returned ID into the local YAML.
- `sync-from-remote` refreshes local content from existing remote IDs.
- `sync-to-remote` updates every existing remote ID in YAML, in ID order; it must not update only the primary platform.
- Reject synchronization when YAML front matter, `doc_type: markdown`, or a platform ID is missing.
- Reject remote 404s and empty remote content; never write an empty backup as success.

## Safe synchronization

Default `sync-to-remote` is conservative: update the title and Markdown body only. Do not change project, state, priority, type, assignee, labels, versions, or relationships by default.

Use `--joint` only when the user explicitly requests extended-field synchronization. Log which fields were sent and which were skipped. Platform API limitations, such as GitHub Development PR links that cannot be created through the public API, must be reported as warnings rather than success.

## YAML and encoding

Keep all Markdown and YAML UTF-8. Use platform-specific fields under `platform.<platform_id>` and keep cross-platform IDs under `id`. Omit unavailable values instead of writing `''`, `[]`, or fabricated relationships.

Examples:

```yaml
---
doc_type: markdown
id:
  youtrack_issue: DEMO-37
  github_issue: HuAzurestar/test-repo#12
platform:
  youtrack_issue:
    title: Example
  github_issue:
    title: Example
---
Document body.
```

For new GitHub or Gitee Pull Requests, the platform section must provide `base_branch` and `head_branch`. For new objects, the command must include an explicit target such as `gitee/issue/owner/repo` or `youtrack/article/DEMO`.

## Credentials and logs

Read provider URLs and tokens from local `config/sync.yaml` or its configured environment variable. Never print, commit, or copy tokens into Markdown or logs. Keep `config/sync.yaml` and generated `logs/` untracked.

Each invocation creates `md-sync.yyyymmdd.hhmmss.msms.log`. The log must include the complete CLI arguments, selected platform, API method/path, response status, sent fields, skipped fields, local write result, and error details without authorization headers.

## Verification

After a mutating operation, verify the returned remote ID and, when practical, run `download` or a provider read-back to compare title and body. Use the regression checklist in [docs/regression-test-plan.md](docs/regression-test-plan.md) for cross-platform or provider changes.
