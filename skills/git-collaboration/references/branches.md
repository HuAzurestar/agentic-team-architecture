# Branch conventions

## Default: trunk-based collaboration

Use `main` as the protected, always-green branch. Create short-lived topic branches from current `main`, open a PR early, merge after review and required checks, then delete the branch.

Branch names use lowercase ASCII kebab-case:

```text
feature/<issue>-<summary>
fix/<issue>-<summary>
docs/<issue>-<summary>
refactor/<issue>-<summary>
perf/<issue>-<summary>
test/<issue>-<summary>
build/<issue>-<summary>
ci/<issue>-<summary>
chore/<issue>-<summary>
proof/<issue>-<summary>
paper/<issue>-<summary>
revert/<issue>-<summary>
release/<version>
hotfix/<issue>-<summary>
```

For ordinary tracked work the Issue segment is mandatory. Examples: `feature/142-lean-parser`, `fix/87-tex-crossrefs`, `ci/203-python-matrix`. When a repository has no tracker, adopt an explicitly documented alternative rather than silently omitting traceability.

## Issue-type binding

Use one canonical mapping and enforce it across Issue metadata, branch, commit, and PR:

| Issue type/label | Branch prefix | Commit/PR type | Purpose |
| --- | --- | --- | --- |
| `feature` | `feature/<issue>-...` | `feat` | new user-visible capability |
| `bug` | `fix/<issue>-...` | `fix` | defect correction |
| `documentation` | `docs/<issue>-...` | `docs` | documentation-only change |
| `refactor` | `refactor/<issue>-...` | `refactor` | behavior-preserving restructuring |
| `performance` | `perf/<issue>-...` | `perf` | measured performance work |
| `test` | `test/<issue>-...` | `test` | test-only change |
| `build` | `build/<issue>-...` | `build` | build system, packaging, or dependency graph change |
| `ci` | `ci/<issue>-...` | `ci` | pipeline/workflow change |
| `maintenance` | `chore/<issue>-...` | `chore` | repository maintenance |
| `proof` | `proof/<issue>-...` | `proof` | Lean theorem/proof work |
| `paper` | `paper/<issue>-...` | `paper` | TeX/paper content or production |

The canonical machine-readable mapping is [policy-model.json](policy-model.json). `hotfix/<issue>-...` is a release-path override for a `bug` Issue and keeps commit/PR type `fix`. `revert/<issue>-...` is an action override for a `bug` or `maintenance` Issue; its commit/PR type is `revert`, and the PR identifies the reverted commit and reason. `release/<version>` is a release override backed by a `maintenance` Issue unless the repository documents a narrow release-automation exemption.

Before creating or accepting a branch, verify that the referenced Issue exists, is open/actionable, belongs to the intended repository, and carries exactly one primary workflow type. The branch prefix and commit/PR type must match that primary type or a declared override in `policy-model.json`. Every ordinary commit and the PR title carry the same primary Issue. If work changes category, re-triage the Issue or create/split the correct Issue before renaming/replacing the branch; do not relabel merely to bypass policy.

Platform linkage is additional evidence, not a substitute for naming and CI validation. On platforms that support it, create/link the branch from the Issue UI so the Issue shows active development. CI should query the forge API to validate Issue existence, state, type/label, branch prefix, commit type, and PR linkage.

Prefer squash merge when the branch's intermediate commits are not independently valuable. Prefer rebase merge when each commit is deliberately curated. Permit merge commits only when preserving branch topology is an explicit project choice. Never rewrite a shared protected branch.

## Add long-lived branches only when justified

Add `develop` only when the team truly needs an integration state distinct from the next deployable state. Add `release/<version>` only for a stabilization window with parallel ongoing development. A production hotfix starts from the deployed stable ref and is merged/cherry-picked back into every still-supported line.

Document the base and destination for each long-lived branch. Avoid environment branches such as `staging` or `production`; promote immutable artifacts between environments instead.

## Protection baseline

- Require PRs, successful named checks, resolved conversations, and at least one approval.
- Dismiss stale approvals when security-sensitive or high-risk code changes after approval.
- Block force-push and deletion on protected branches.
- Require linear history only if the chosen merge strategy supports it.
- Use `CODEOWNERS` for areas needing specialist review, not as a substitute for general review.
