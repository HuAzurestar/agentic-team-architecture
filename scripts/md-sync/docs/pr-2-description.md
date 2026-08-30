## Summary

Add a UTF-8 Markdown + YAML multi-remote synchronization controller under `scripts/md-sync/`.

- Support GitHub Issues and Pull Requests.
- Support YouTrack Issues and Articles.
- Support Gitee Issues and Pull Requests.
- Define a standard Markdown + YAML Front Matter format.
- Add a central controller and replaceable provider adapters.
- Use platform IDs in YAML to synchronize one document across multiple remotes.
- Keep remote-authoritative mode and local backup directories explicit.

## Commands

- `download`: create a local Markdown backup from a remote object.
- `upload`: create a new remote Issue, Article, or Pull Request and write its ID back to YAML.
- `sync-from-remote`: refresh the local Markdown from remote IDs.
- `sync-to-remote`: update all existing configured remote IDs in YAML.
- `--joint`: explicitly enable the extended-field synchronization flow.

The default sync mode is safe: it updates only the title and Markdown body. Project, status, priority, assignee, labels, versions, and relations are skipped unless extended synchronization is explicitly requested.

## Relations and metadata

- Preserve parent/child and related platform IDs where the remote API supports them.
- Download GitHub Development information such as pull requests, commits, checks, and deployments when available.
- Download Gitee Issue relationships, including associated Pull Requests, when available.
- Reject missing YAML, missing platform IDs, missing remote objects, and empty remote content.

## Validation

- `python -m compileall -q scripts/md-sync/src`
- GitHub Issue and Pull Request regression tests.
- YouTrack Issue and Article regression tests.
- Gitee Issue `IKC1GX` created and downloaded successfully.
- Gitee Pull Request `#1` created and downloaded successfully using `master` -> `test/md-sync-pr`.
- Cross-platform tests: GitHub Pull Request -> Gitee Issue, and YouTrack Article -> GitHub Issue.
- Update and read-back tests for Gitee Issue and Pull Request.
- Full test plan: [`docs/regression-test-plan.md`](regression-test-plan.md)

## Logging and security

- Generate one log per CLI invocation as `md-sync.yyyymmdd.hhmmss.msms.log`.
- Record complete CLI arguments, selected platform, API requests, response status, sent fields, skipped fields, and errors.
- Keep tokens in local `config/sync.yaml` only.
- Do not commit local configuration or generated logs.

## Notes

The GitHub, YouTrack, and Gitee provider adapters are now implemented for their supported Issue, Article, and Pull Request operations. Platform-specific API limitations are reported as explicit warnings or errors instead of being reported as successful synchronization.
