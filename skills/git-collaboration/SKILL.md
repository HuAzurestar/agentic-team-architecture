---
name: git-collaboration
description: Establish, assess, or apply repository Git collaboration conventions, including commit messages, branches, pull requests, CI/CD gates, and code or quality review. Use for repository governance and contribution workflows; do not use for ordinary one-off Git commands that do not affect team conventions.
---

# Git Collaboration

Create a collaboration policy that is small enough to follow and strict enough to verify. Inspect the repository before proposing tools: read contributor instructions, manifests, lockfiles, CI workflows, protected-branch expectations, release process, and Git history when available. Preserve compatible local conventions and explain migrations.

## Select one mode

- **Assess** is read-only. Inventory the current controls, cite repository evidence, classify gaps and risks, distinguish verified from unavailable evidence, and recommend an ordered remediation plan. Do not edit files or external settings.
- **Design** produces a proposed policy, file map, exact local commands, required check names, forge settings, adoption sequence, and migration/rollback notes. Do not materialize the proposal unless the user also asks for implementation.
- **Implement** changes only files and settings within the user's authorized scope. Validate local artifacts and report external settings or checks that remain unverified. Repository settings, remote branches, pushes, releases, and deployments require explicit authorization even in this mode.

When the user asks to review and fix, assess first and carry the same evidence into implementation. Stop rather than guess when a missing repository decision would change the branch topology, published artifacts, deployment, or external permissions.

## Workflow

1. Determine the repository shape, languages, deliverables, package/build tools, supported versions, hosting platform, release method, and whether deployments exist. Never invent commands, services, artifacts, or secrets.
2. Read the canonical taxonomy in [policy-model.json](references/policy-model.json). Select the lightest branch model that matches the actual release topology, then read [branches.md](references/branches.md).
3. Define the Issue → branch → commit → PR traceability chain using [commits-and-prs.md](references/commits-and-prs.md). For contribution files and forms, also read [issues-and-templates.md](references/issues-and-templates.md).
4. Define daily development, synchronization, merge/rebase, hotfix, release, conflict-recovery, tag, and ignore-file procedures using [workflow-and-recovery.md](references/workflow-and-recovery.md). Keep the taxonomy and Issue binding in every applicable command and example.
5. For an assessment or code-review request, read [code-review.md](references/code-review.md). Apply every detected language overlay below and review cross-language boundaries; deterministic gates remain separate from human or AI review.
6. Select checks only for detected languages:
   - Python: read [python.md](references/python.md).
   - C/C++: read [cpp.md](references/cpp.md).
   - Java: read [java.md](references/java.md).
   - Bash/POSIX shell: read [shell.md](references/shell.md).
   - Lean: read [lean.md](references/lean.md).
   - TeX/LaTeX: read [tex.md](references/tex.md).
   - For any other language, derive commands from repository manifests, lockfiles, contributor docs, and existing CI. Reuse the repository's canonical commands; mark unsupported or unverified checks explicitly instead of inventing a toolchain.
7. Design CI and, only when publishing or deployment is in scope and known, CD using [ci-cd.md](references/ci-cd.md). For GitHub read [github.md](references/github.md); for Gitee read [gitee.md](references/gitee.md). For another forge, keep commands vendor-neutral, use only verified platform capabilities, and list required external settings without fabricating provider-specific files. When SonarQube is available or under consideration, read [sonarqube.md](references/sonarqube.md). Recheck time-varying claims through [platform-capabilities.md](references/platform-capabilities.md).
8. In Implement mode, materialize the policy in established repository locations. Prefer one canonical command per gate and make local and CI commands identical.
9. Run available checks. Distinguish verified results from checks skipped because a tool, dependency, secret, external service, plan, or permission is unavailable.
10. After changing this skill package, run `python scripts/validate_policy.py .` and `python scripts/test_validate_policy.py`; when both locale packages are present, also pass `--counterpart <other-skill-root>` to the validator.

## Required outcomes

- Protect stable branches from direct pushes; changes land through reviewed pull requests with required deterministic CI.
- Keep changes reviewable, commits atomic, and generated artifacts or lockfiles intentional.
- Keep taxonomy, branch names, commit/PR headers, forms, and policy checks consistent with `policy-model.json`.
- Pin CI actions/toolchains according to risk and cache dependencies only with keys that include relevant lockfiles.
- Give every required check a stable, clear name suitable for branch protection.
- Separate fast pull-request gates from slower scheduled, release, or deployment jobs.
- Grant CI jobs minimum permissions and do not expose secrets to untrusted fork code.
- Build and validate a release artifact once under the selected release profile, then publish or promote those same bits.
- Do not commit, push, rewrite history, create remote branches, alter repository settings, publish, or deploy unless the user authorized that mutation.

## Deliverables

- **Assess:** repository facts, current controls, evidence-backed findings, reviewed/skipped scope, and a prioritized remediation plan.
- **Design:** concise policy, selected taxonomy/topology/release profile, file map, exact commands, stable check names, forge settings, and adoption sequence.
- **Implement:** changed files/settings, validation commands and actual results, skipped checks, remaining external configuration, and migration/rollback notes.

Keep [third-party-notices.md](references/third-party-notices.md) in every redistributed package; load it only when checking provenance or license obligations.
