---
name: review
description: Review a software change or feature with topic-scoped strong or checklist-guided weak execution, evidence-backed findings, and a versioned REVIEW.md ledger. Use for requested development self-checks, independent software reviews, and finding rechecks; not for scientific proof review or organizational audits.
---

# Review

Paths such as `scripts/...` refer to the assembled skill root. For a repository checkout, first combine this locale's content with the same-named shared runtime directory; installed packages already include it. Development tests remain outside the skill.

Use one scope and one finding protocol for both modes. Strong review explores each topic freely; weak review scans the selected topic's concrete content points. A content point can yield zero, one, or several independent findings. Do not score checklist answers.

## Select scope

The compact contract is `review/v1`:

```text
review/v1 mode=strong exclude=ui focus=permission-inheritance,export-bypasses
review/v1 mode=weak topics=core,api,data,auth,regression exclude=ui
```

`mode` defaults to `strong`; `topics` defaults to `all`; `exclude` defaults to empty. Subtract exclusions from the selected topics. `focus` adds particular promises or design points to investigate; it never removes other selected checks. Record default choices. Reject unknown versions, fields, modes or topics and duplicate fields. An empty selection is INCOMPLETE, not a perfect score. Do not infer model capability from its name.

Without configuration, cover all applicable topics for the actual change and its affected paths. This does not authorize an audit of unrelated historical code. Record exclusions and justified N/A topics. Follow dependencies needed to assess an in-scope promise; disclose limitations caused by an exclusion instead of quietly changing scope.

| Topic | Strong-review objective | Weak-mode detail |
| --- | --- | --- |
| core | Map the delta to requirements; examine completeness, cohesion, reuse, dead code and necessary complexity. | [core](references/core_review_detail.md) |
| api | Trace interface meaning, input/output contracts, error conventions and consumers. | [api](references/api_review_detail.md) |
| ui | Perform real user tasks; assess information, bulk work, defaults, feedback and recovery. | [ui](references/ui_review_detail.md) |
| data | Challenge business invariants, transactions, ordering, concurrency and idempotency. | [data](references/data_review_detail.md) |
| auth | Trace inherited permissions, alternate entry points and sensitive-data exits. | [auth](references/auth_review_detail.md) |
| recovery | Examine IO failure, partial success, timeout, retries, restart and recovery side effects. | [recovery](references/recovery_review_detail.md) |
| regression | Check old semantics, historical data/configuration and direct/indirect consumers. | [regression](references/regression_review_detail.md) |
| observe | Determine whether logs/context locate failures without exposing sensitive information. | [observe](references/observe_review_detail.md) |
| perf | Assess critical-path scale, complexity, batching, unbounded resources and cleanup. | [perf](references/perf_review_detail.md) |

Strong mode does not load the weak detail references. For each selected topic, form hypotheses from the actual requirements, scan the implementation, look for bypasses, and try meaningful counterexamples. Give it room to discover issues beyond the listed topic objective.

Weak mode reads only the selected topics' detail references. Scan each applicable content point using its evidence and search directions; internal YES/NO/UNKNOWN/N/A notes are optional and are not the report or the score. Add an exploratory counterexample where useful. Random probes supplement mandatory checks and must be recorded.

## Establish clean inputs

Pin repository identity, base/head commits, requirement/design version, environment, scope and skill version. Distinguish author self-checks from an independent execution context; changing roles inside the same conversation is not independence. Do not create another task/session or delegate without existing authorization. If independence is unavailable, report that accurately and continue permitted self-checks.

Before this attempt's blind scan, do not read the existing REVIEW.md, older review reports, findings, scores or summaries. Do not get the same conclusions indirectly from dependency details or author handoff notes. Existing source, tests, normative design and original runtime evidence remain usable. Keep real authorization and safety boundaries. If inputs mix these boundaries with old findings and cannot be separated, mark the limitation; do not claim a clean blind review.

For a feature using `long-feature-development`, the **first** recovery call must use its blind view:

```text
python <long-feature-skill>/scripts/task_context.py <feature-directory> --review-phase blind --review-input gists/review-input.md
```

Do not first run its ordinary recovery output. The coordinator prepares a bounded, declared raw input containing the current normative requirement/design excerpts, authorization and original evidence, marked `- Evidence type: original`. That marker is a routing declaration, not proof of trustworthy content. The reviewer still detects contamination and missing evidence. The blind view exposes source references and IDs, not arbitrary full management prose. No raw packet means inputs incomplete, not PASS.

If the host already supplied old findings in this context, disclose contamination. A saved blind snapshot does not by itself prove an independent context.

## Scan the change

1. Read the actual diff; identify changed public interfaces, schemas, configuration, permissions, transactions, errors, logging and tests.
2. Trace important symbols through definitions, callers, callees, sibling implementations and tests.
3. Search the business concept and its alternative expressions, not just changed function names.
4. Inspect applicable UI/API/CLI/background/restart/import/export paths that can bypass the changed mechanism. A second occurrence of the same root cause warrants broader checks of that mechanism.
5. Try meaningful failure examples against promises such as amount conservation, inherited access, complete preview and safe recovery. Declaration fields alone are not evidence.

Use permitted environments and data. Record expected versus observed results; never claim an experiment ran when it did not. UI usability conclusions require real operation or interface evidence, and performance claims need a scale assumption. Evidence gaps are limitations, not low-severity invented findings.

## Freeze, reconcile, and report

Save the blind result as a separate attempt report before reading history. Bind it to the reviewed target and record:

```text
- Review phase: blind
- Review task: REVIEW-01
- Target SHA: the literal reviewed commit
- Review scope: review/v1 mode=strong
```

Record multi-repository base/head refs separately too. Preserve this snapshot when later reconciliation finds more issues. In a long feature, declare the snapshot gist in the task, then use:

```text
python <long-feature-skill>/scripts/task_context.py <feature-directory> --review-phase reconcile --review-report gists/blind-01.md
```

Only now read historical reports and REVIEW.md. Match independently observed issues to stable ledger IDs; inspect prior fixes and run their relevant regression examples. A prior issue absent from the blind findings is not automatically fixed. Changed targets invalidate affected evidence and old totals; unchanged evidence can be reused with an explicit applicability basis.

Use [the ledger template](assets/REVIEW.md) after the blind snapshot. In a long feature, the ledger lives at `<feature-directory>/REVIEW.md`, and immutable attempts remain in declared `gists/REVIEW-*.md`. Standalone use follows the requested or established report directory. Do not rewrite old attempt scores or copy unbounded logs into the ledger.

Every finding uses the same format in both modes:

```text
auth-001 (p0=severe): export Single-result export bypasses inherited access
- location: src/export.py 84; src/results.py 126
- problem: Trigger, observed behavior, impact, and evidence supporting the priority.
- suggest: The smallest reasonable remediation or verification.
- status: OPEN
- resolution: Outstanding; record fix/decision version and recheck when available.
- evidence: Code/diff/runtime/test refs and their applicability to the reviewed target.
```

The title contains topic-ID, priority, module and a concrete summary. Use `p0=severe`, `p1=risk`, `p2=warning`, `p3=suggestion` according to demonstrated consequence and triggerability, not code aesthetics. Give independent triggers/fixes separate IDs; give one defect's multiple locations one ID. Similar wording is not proof of duplication. IDs are stable within a ledger; use the ledger path plus ID across features. Reconciliation can map temporary attempt IDs to ledger IDs with an explicit mapping.

| Status | Meaning | Count in current applicable score? |
| --- | --- | --- |
| OPEN | Confirmed issue remains unresolved. | Yes |
| FIXED | Fix independently rechecked on the recorded target with valid evidence. | No |
| REJECTED | Evidence establishes false positive or non-applicability. | No |
| DEFERRED | Real issue intentionally retained or postponed. | Yes |

Authors may record a fix commit, but cannot close an independent finding themselves. Declining a suggestion is DEFERRED unless the problem itself is disproved. Preserve transition history, old priority and change rationale. Old closure evidence that does not apply to the new target is not a current closure. Unchecked/out-of-scope historical items stay visible separately; exclusions must not hide an unresolved delivery-blocking P0.

P0 must be fixed and rechecked, or disproved using an explicit project design point, design version and technical evidence. New documentation that changes intended behavior is a design change, not proof of a false positive. DEFERRED or quiet downgrading cannot bypass a P0. P1/P2/P3 fixes are optional; retention still deducts points and requires an honest impact/rationale. Optional remediation does not override agreed requirements or data/authorization boundaries.

## Score and continue

Count current, applicable, unique OPEN/DEFERRED findings:

```text
score = max(0, 100 - 100*P0 - 10*P1 - 2*P2 - P3)
result = PASS if P0 == 0 and score >= 60 else FAIL
```

Use the [deterministic helper](scripts/review_score.py), explicitly declaring completeness:

```text
python scripts/review_score.py --complete --p0 0 --p1 3 --p2 4 --p3 2
python scripts/review_score.py --incomplete --p0 1
```

Incomplete scope, missing critical evidence or interruption gives INCOMPLETE and a null score, retaining known counts. The helper does not read the ledger or decide evidence applicability. Zero discoveries alone do not establish completeness.

Report completion, score result, mandatory rework and human acceptance separately. An issue-bearing report can complete. P0 requires rework/valid rejection; P1/P2/P3 do not create endless automatic rework even below 60. PASS does not authorize acceptance, merge or release.

Within existing authority, continue technical reproduction, fixes, tests and rechecks. Product semantics/scope/budget/data-access changes and final acceptance/release retain their decision boundaries. Do not start unsupported independent execution automatically. Handoff states what changed against baseline, how to try it, limitations, exact next action, and actual human decisions needed. Record evidence blockers and who/what can release them; workflow column position is not quality evidence.
