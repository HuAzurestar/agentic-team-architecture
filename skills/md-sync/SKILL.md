---
name: md-sync
description: Upload, download, and synchronize UTF-8 Markdown data between GitHub, Gitee, and YouTrack through the project's md-sync controller.
metadata:
  short-description: Upload, download, and sync Markdown data
---

# Markdown Data Sync

Use this skill when the task is to upload, download, or synchronize Markdown data between supported remote platforms using `scripts/md-sync`.

## Commands

Run from `scripts/md-sync` with `PYTHONPATH=.`:

```powershell
python -m src.controller.main status
python -m src.controller.main download <file.md> --remote <provider>:<id>
python -m src.controller.main upload <file.md> --target <provider>/<type>/<project>
python -m src.controller.main sync-from-remote <file.md>
python -m src.controller.main sync-to-remote <file.md>
python -m src.controller.main sync-to-remote <file.md> --joint
```

Supported data IDs:

- `github_issue`
- `github_pull_request`
- `gitee_issue`
- `gitee_pull_request`
- `youtrack_issue`
- `youtrack_article`

## Data rules

- The local file must be UTF-8 Markdown with YAML front matter and `doc_type: markdown`.
- Platform IDs belong under `id`; the first platform ID is the primary source for ordering and conflict resolution.
- `download` creates or refreshes local data from a remote object.
- `upload` creates a new remote object and writes its returned ID into YAML.
- `sync-from-remote` refreshes local data from existing remote IDs.
- `sync-to-remote` updates every existing remote ID in YAML, in ID order.
- Reject missing YAML, missing IDs, missing remote objects, and empty remote content.
- Omit unavailable values; do not invent empty or fabricated relationships.

## Safe mode

Default `sync-to-remote` updates only title and Markdown body. It skips project, state, priority, type, assignee, labels, versions, and relationships.

Use `--joint` only when extended-field synchronization is explicitly requested. Record sent and skipped fields in the log. Report unsupported platform operations as warnings or errors.

## Platform fields

Put platform-specific values under `platform.<platform_id>`. New GitHub/Gitee Pull Requests require `base_branch` and `head_branch`.

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
Markdown body.
```

## Credentials and verification

Read provider addresses and tokens from local `scripts/md-sync/config/sync.yaml` or configured environment variables. Never print or commit tokens. Do not commit `config/sync.yaml` or generated logs.

After upload or synchronization, verify the returned ID and, when practical, download the remote object again to compare title and body. Use [the regression plan](../../scripts/md-sync/docs/regression-test-plan.md) for provider or cross-platform changes.
