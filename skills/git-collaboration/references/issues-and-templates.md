# Issues, pull requests, and contribution templates

## Traceability lifecycle

1. Create or triage an actionable Issue before ordinary implementation work.
2. Branch from the correct base and include the Issue number in the branch when the naming policy permits it.
3. Reference that Issue in every normal commit using [commits-and-prs.md](commits-and-prs.md).
4. Open a focused PR whose title carries the primary Issue and whose body links or closes all affected Issues.
5. Merge only when acceptance criteria, review, and required checks pass; let the default-branch merge close the Issue.

An Issue describes a problem or outcome, not a preselected patch. Its title is concise and searchable. Its body provides context, observed/current behavior, expected outcome, scope/non-goals, acceptance criteria, reproduction or mathematical statement as applicable, environment/version, risks, and dependencies. Do not combine several independently deliverable requests in one Issue.

Use the primary types from [policy-model.json](policy-model.json) for type labels; repositories may disable optional types such as `proof` or `paper`. Use separate labels for status (`triage`, `blocked`) and area/scope. Avoid labels that duplicate assignee or milestone information. Security vulnerabilities follow `SECURITY.md`, not a public Issue form.

## GitHub community files

Materialize only the files useful to the repository:

```text
CONTRIBUTING.md
SECURITY.md                         # public/security-relevant projects
SUPPORT.md                          # when support channels exist
CODE_OF_CONDUCT.md                  # community projects
GOVERNANCE.md                       # when roles/decision rights need definition
.github/CODEOWNERS
.github/ISSUE_TEMPLATE/config.yml
.github/ISSUE_TEMPLATE/bug.yml
.github/ISSUE_TEMPLATE/feature.yml
.github/ISSUE_TEMPLATE/proof.yml    # Lean repositories
.github/ISSUE_TEMPLATE/paper.yml    # TeX/paper repositories
.github/pull_request_template.md
```

Keep canonical process rules in `CONTRIBUTING.md`; templates collect task-specific data and link back rather than duplicating the full policy. Organization-wide defaults may live in a public special `.github` repository, but a repository's local templates override the corresponding defaults.

## Issue Forms

Use a distinct template/form for each enabled primary Issue type; do not send bugs, features, proof tasks, and paper defects through one generic questionnaire. Each template assigns or requests exactly one primary type/label that maps to the branch and commit policy in [branches.md](branches.md).

Prefer YAML Issue Forms when the forge supports structured required fields. A bug form asks for reproduction, observed/expected behavior, minimal example, environment/toolchain, logs, regression range, and confirmation that secrets were removed. A feature form asks for user problem, proposed outcome, alternatives, scope/non-goals, compatibility, and acceptance criteria. Documentation, refactor, performance, test, CI, and maintenance forms collect their own relevant current state, target outcome, validation, risks, and acceptance criteria; combine rarely used types only when their required information is truly the same.

A Lean proof form additionally asks for the exact theorem statement, imports/toolchain, allowed axioms, whether `sorry` is present, informal source/citation, and what has already been tried. A TeX paper form asks for root document, engine, minimal failing excerpt, log, affected output/page, bibliography backend, and expected rendering.

Set `blank_issues_enabled: false` only when the available forms and contact links cover legitimate requests. Route questions to Discussions/support and vulnerabilities to `SECURITY.md` or a private reporting channel.

Triage rejects or reclassifies Issues whose selected template/type disagrees with their content. Before implementation, ensure the primary type/label is present; priority, area, status, milestone, and language labels are secondary metadata and must not replace it.

## Pull request template

Require the author to fill in:

- `Closes #N` or `Refs #N`;
- problem/outcome and concise change summary;
- change type and affected scope;
- validation commands with actual results;
- acceptance-criteria checklist;
- compatibility, breaking change, migration, security, deployment, proof-trust, or PDF-output impact as applicable;
- screenshots/PDF preview/theorem names when relevant;
- checklist confirming focused change, documentation, generated artifacts, and no secrets.

Templates guide authors but do not enforce completeness. Add a deterministic PR policy check for title format, Issue reference, required sections, and prohibited placeholder text. Avoid brittle checks that reject legitimate Markdown formatting without improving review quality.
