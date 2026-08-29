# Commits and pull requests

## Commit messages

Use an issue-first extension of Conventional Commits for ordinary project changes:

```text
#<issue> <type>[(<scope>)][!]: <imperative summary>

<body: context, what changed, and why>

Refs: #<issue>
[Closes: #<issue>]
[BREAKING CHANGE: migration and impact]
[Co-authored-by: Name <email>]
```

`#<issue>` is mandatory for normal feature, fix, documentation, refactor, test, and CI work. Define narrow documented exemptions for repository bootstrap, automated dependency updates, release/version commits, or emergency administration only when they cannot reasonably have an issue; never use fake identifiers such as `#0`. If every change must be issue-backed, create the issue first.

Allowed baseline types come from [policy-model.json](policy-model.json): `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, plus `proof` and `paper` when those Issue types are enabled. `revert` is an explicit action override for a `bug` or `maintenance` Issue and must identify the reverted commit and reason in the body. Repositories may narrow the model and define stable lowercase kebab-case scopes. The type must match the Issue/branch mapping or a declared override. Keep the first line concise (target at most 72 characters), omit the final period, use an imperative summary, and describe one logical change. Use `!` and a `BREAKING CHANGE:` footer for incompatible changes.

The issue-first prefix is a repository convention, not the default Conventional Commits grammar. Configure commitlint/release tooling with a custom header parser or normalize the message before parsing; do not claim compatibility with unmodified Conventional Commit tooling. Generate the baseline GitHub Ruleset pattern from the policy model with `python scripts/validate_policy.py . --print-ruleset-regex` rather than maintaining another type list by hand.

Examples:

```text
#142 feat(parser): support nested Lean comments

Accept nested block comments during tokenization and preserve source spans.
This prevents the parser from truncating generated proof files.

Refs: #142
Closes: #142

#87 fix(tex): preserve labels during appendix split

Refs: #87

#203 ci(python): test supported interpreter versions

Refs: #203
```

The body is required for non-trivial changes and explains motivation, behavior, constraints, and noteworthy implementation choices; do not merely repeat the subject. Wrap prose consistently (72 characters is a useful default). The footer uses Git trailers or project-defined tokens. Always include `Refs: #N`; use `Closes: #N`/`Fixes: #N` only when landing on the default branch should close the issue. Cross-repository references use `owner/repo#N`.

Do not claim tests passed unless they ran. Do not include secrets, credentials, personal data, or generated AI commentary. One commit may reference multiple issues only when it is genuinely atomic across them; repeat complete references in the footer.

## Pull requests

PR title follows the same issue-first header, especially when squash-merging:

```text
#142 feat(parser): support nested Lean comments
```

The description states:

- problem and intended outcome;
- approach and noteworthy tradeoffs;
- validation commands and results;
- user-visible, compatibility, migration, security, or deployment impact;
- linked issue using `Closes #142`/`Refs #142`, and screenshots/log excerpts when relevant.

Keep a PR focused. Split unrelated refactors from behavioral changes. Reviewers check correctness, tests, maintainability, compatibility, security, documentation, and whether generated files match their sources. Authors respond to review without silently overwriting unresolved concerns.

## Enforcement

Enforce at several layers:

1. provide `CONTRIBUTING.md`, a commit message example/template, and an optional local `commit-msg` hook for fast feedback;
2. validate the PR title and issue linkage in CI;
3. when preserving individual commits, validate every commit in the PR range, including body/footer requirements;
4. on GitHub plans that support it, use Ruleset commit-metadata restrictions to reject pushes whose first line does not match the issue-first pattern;
5. configure the squash-merge message from the validated PR title/body so the commit created by GitHub remains valid.

A local hook cannot be the sole enforcement point because hooks are not cloned automatically. A GitHub Ruleset regex is an early structural gate, but CI is still needed for richer rules such as valid issue existence/state, allowed scopes, body/footer content, and exemptions.
