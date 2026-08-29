# Git workflow and recovery

This policy adapts practical workflow ideas from [Galaxy-Dawn/claude-scholar's git-workflow](https://github.com/Galaxy-Dawn/claude-scholar/tree/main/skills/git-workflow) while preserving this skill's stricter Issue binding and trunk-based default. See [third-party-notices.md](third-party-notices.md) for the checked upstream revision and license notice.

## Choose the topology first

Default to protected `main` plus short-lived Issue branches. Add `develop` only when the repository documents a distinct integration line. The same procedures apply to either topology by substituting the documented integration branch for `<base>`.

Record each branch class, source, merge destination, merge method, and deletion rule. Do not copy a `master + develop` Git Flow into a repository that releases directly from `main`.

## Daily Issue-backed development

```bash
git switch <base>
git pull --ff-only origin <base>
git switch -c feature/142-lean-parser

# Make one logical change, stage deliberately, and run the canonical checks.
git add <paths>
git diff --cached
git commit
git push -u origin feature/142-lean-parser
```

Open a draft PR early. Require the Issue type, branch prefix, commit type, PR title, and closing/reference footer to agree. Merge only through the protected destination after required checks and review, then delete the topic branch.

Use `git pull --ff-only` on protected or shared branches so a pull cannot create an accidental merge commit. To refresh a private topic branch, fetch first and then rebase or merge according to repository policy:

```bash
git fetch origin
git rebase origin/<base>       # private topic branch only
# or: git merge origin/<base>  # shared topic branch or topology-preserving policy
```

Never rebase a protected branch or commits already consumed by others. If rewriting an explicitly private remote branch is necessary, use `git push --force-with-lease`, never plain `--force`.

## Merge policy

- Prefer squash merge when intermediate topic commits are disposable; validate the PR title/body because they become the landing commit.
- Prefer rebase merge when every commit is intentionally curated and separately valid.
- Allow `--no-ff` merge commits only when branch topology or a release train is meaningful.
- Keep the protected branch green and do not perform manual local merges that bypass PR gates.

The repository must select one default, configure the forge accordingly, and make its commit-validation strategy compatible with that choice.

## Hotfix workflow

Create the bug Issue first and label it `bug` plus the repository's urgent/severity metadata. Start `hotfix/<issue>-<summary>` from the deployed stable tag or supported release branch—not blindly from the newest development branch.

```bash
git fetch origin --tags
git switch --detach <deployed-tag>
git switch -c hotfix/317-auth-bypass
# Fix, test, commit as: #317 fix(auth): ...
git push -u origin hotfix/317-auth-bypass
```

Land the fix through an expedited but reviewed PR. Tag the repaired release after all release gates pass. Forward-port the same fix into every supported development/release line using a PR or a traceable cherry-pick; never leave `main`, `develop`, and supported release branches inconsistent.

## Release workflow and tags

Use Semantic Versioning where it fits the project:

```text
vMAJOR.MINOR.PATCH[-PRERELEASE]
```

Create `release/<version>` only when a real stabilization window must run alongside new development. Otherwise release directly from a verified commit on `main`. A release branch may contain only release-approved fixes, version metadata, changelog, and generated release artifacts.

Create annotated, preferably signed tags from the exact verified commit:

```bash
git tag -s v1.4.0 -m "release: v1.4.0"   # use -a when signing is unavailable
git push origin v1.4.0
```

Do not retag a published version. Correct it with a new version. Build once from the tag, attach checksums/provenance where supported, and promote the same immutable artifact between environments.

## Conflict handling

Before editing, identify the operation and conflicted paths:

```bash
git status
git diff --name-only --diff-filter=U
```

Resolve content deliberately, remove conflict markers, run syntax/format/tests for affected languages, stage only resolved paths, then continue:

```bash
git add <resolved-paths>
git merge --continue       # merge
git rebase --continue      # rebase
git cherry-pick --continue # cherry-pick
```

Abort when the intended result is uncertain:

```bash
git merge --abort
git rebase --abort
git cherry-pick --abort
```

Do not choose `--ours` or `--theirs` without checking operation semantics; their meaning can be surprising during rebase. Never resolve generated files independently when they can be regenerated from reviewed sources.

## Safe correction and recovery

- Amend or interactively rebase only unpublished private commits.
- Revert a published commit with `git revert <commit>` so history remains auditable.
- Use `git reflog` to locate accidentally lost local refs before changing more state.
- Stash only short-lived context and name it: `git stash push -u -m "issue-142 parser WIP"`; inspect before `pop`/`apply`.
- Inspect outgoing commits with `git log --oneline origin/<base>..HEAD` and staged content with `git diff --cached`.
- Treat `reset --hard`, `clean -fdx`, history filtering, tag deletion, and remote force-push as destructive operations requiring explicit target verification and authorization.

## `.gitignore` and generated artifacts

Build `.gitignore` from detected tools rather than copying a universal list. Ignore reproducible caches, local environments, editor state, secrets, logs, and disposable build output. Do not ignore required lockfiles, source assets, checked-in fixtures, or release inputs merely because a broad template does.

Use these diagnostics before changing ignore rules:

```bash
git check-ignore -v <path>
git status --ignored
```

Ignoring a path does not remove an already tracked file. Review `git rm --cached` separately and never apply it recursively without verifying the exact targets. Store personal exclusions in `.git/info/exclude` or the user's global excludes file, not in the shared project policy.
