# Feature records, previews and Project references

The caller supplies the management root, authorization and state interface, plus any specific orchestration requirements. Without specific orchestration, use the [default task loop](task-workflow.md). Templates define shared records, not company policy.

## Feature and Project

Feature content lives in `<Project-Manage>/feature/<feature-key>/` and covers a set of Projects and requirements. A Project lives in `<Project-Manage>/project/<project-key>/project.yaml` and identifies one Repository's stable remote/local mapping and basic rules. Feature content need not be a Git repository.

Keep DESIGN/design, TASKS/tasks, disposable VERBAL/gists and STATUS. Do not add separate top-level intent, decision, feedback, acceptance or evidence modules.

feature-key comes only from the user, platform or external upstream. Orchestrators and other agents do not allocate, guess or generate temporary keys. Do not create a Feature directory without an externally supplied key; replace the template's example-feature with the externally assigned identity. Internal point/task IDs are distinct from Feature keys.

Agents author concrete INT/REQ/SOL, task bodies and judgments from templates; scripts only synchronize derived views of existing facts, check structure or resolve locations. Each operation follows the required maintenance in [SKILL.md](../SKILL.md). Ordinary communication methods belong to the external orchestrator; only a GATE requiring the user's decision binds a request/response contract.

## Integrated STATUS

STATUS.md brings together repository, Feature and development state: repository bindings and synchronization/integration status, Feature progress, development overview, current focus, cross-task blockers and next actions. It is the integrated management entry, not only a resumption summary.

Keep overall status and necessary links here: design/ owns design content and decision metadata, previewed by DESIGN.md; tasks/ owns task state, dependencies, commit points and reports, previewed by TASKS.md; VERBAL.md/gists/ holds the disposable attachment index and content. STATUS does not copy those indexes, details or attachment lists, or become a second design/task ledger. Report and reconcile conflicts with details rather than overriding them through the summary.

Project YAML remains stable repository configuration; current repository-level status belongs in the Feature's STATUS. The maintainer, write method and synchronization remain external, and overview items adapt to the work rather than prescribing a company workflow.

## Design metadata and preview

`DESIGN.md` previews `design/<id>.md`. Each detail is Markdown with YAML frontmatter. Stable IDs such as REQ-001, SOL-001 and INT-001 are independent of the descriptive type values requirement, solution and intent.

Common fields are `id`, `title`, `type`, `state`, `decided by`, `decided at` and `decided with`. The title summarizes the actual point; an INT title is a concrete intent summary, not a generic label such as “original intent record”. A record's title and matching rendered H1 are descriptive text: naming a disposable path as the work's subject does not make it an evidence dependency. Formal references and the remaining body retain their evidence restrictions. Interpret the attribution fields by type:

- INT: once expressed and retained it is RECORDED. decided by is required and identifies the original proposer, not the recorder or an approver. Preserve the supplied identity as free text: a person, colleague, client, agent, platform or combination; no email/account format is imposed. decided at may retain a known expression time and decided with a known reason; either may remain null independently. Do not apply the approval-tuple rule or introduce an approval wait for provenance.
- REQ/SOL and other approval-bearing points: the three fields are null before a decision; an actual decision fills the confirmer, time and mandatory reason together. A designated agent may confirm under an applicable AGENTS.md mandate, following [role mandates and reopening](confirmation.md); the mandate does not waive the reason.

Keep verbatim INT wording in the template's `## Original external wording` section (`## 外部原始说明` in the Chinese template). The checker treats that section, including retained historical versions, as literal source text until the next heading of the same or higher level, including empty ATX headings and Setext headings underlined with = or -. Headings inside fenced examples do not end it. Mentioning a disposable path there does not make the attachment an input or evidence. Formal reference metadata and the remaining body still cannot depend on disposable material; other record types receive no original-wording exemption.

For example, decided by may be myname@mycompany.com, mycollabo@collabo.company.com, codex sol 6.1 high or codex luna 6 xhigh & multica. These are examples, not an identity enum; do not invent an unknown proposer. source retains the source location or delivery context without requiring a duplicated author field.

Other YAML fields are specialized metadata, summarized in detail spec. Examples:

- requirement: `intent related to`.
- solution: `requirement related to`, and optionally `intent related to`.
- intent: original `source` and needed provenance; `intent type` and `initial opinion` classification/advisory metadata are optional and supplied by external intake when applicable.
- Any point: optional revision, domain-specific notes or relations.

Relations may be an ID, a list of IDs, or versioned references with id/revision/location. A bare ID expresses a current relationship, not a frozen content version. For example, SOL-001 may contain `requirement related to: [REQ-001]`; the preview shows `relate to requirement: REQ-001`. A versioned relation also shows its revision.

INT preserves original external instructions, including review-intent, test-intent, refactor-intent and requirement-intent. Processing these into core requirements and solutions is detailed design, not an automatic approval or implementation step.

The common state vocabulary remains PROPOSED, REOPENED, CONFIRMED, REJECTED, OUT-OF-SCOPE, INFEASIBLE and RECORDED where appropriate. No class column is required; any extra classification can be a specialized field.

The preview uses exactly these columns:

```text
## preview-table

<!-- design-preview-table:start -->
| id | title | type | state | decided by | decided at | decided with | detail spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
<!-- design-preview-table:end -->
```

IDs link to details. YAML is the state source; the table is a reviewable preview. Specialized fields are summarized automatically rather than requiring table-schema changes. Null/empty fields are omitted from detail spec and history lists only revision labels. Each complete detail spec cell has a shared limit of 50 text characters, including labels and any trailing ..., and at most 3 generated lines. Newlines and HTML br breaks count as line boundaries; Markdown/HTML escaping does not consume the text budget. When either limit is exceeded, truncate the preview and append ... within both limits. The full detail remains authoritative and is never shortened by preview generation.

## Task metadata and preview

`TASKS.md` previews `tasks/<id>.md`. Common fields are `id`, `type`, `title`, `state`, `owner`, `depends on`, `started at`, `completed at` and `head sha`. The start-time spelling is started at. Owner identifies the actual Human, Agent, Platform or other actor. depends on is a list of task IDs.

head sha is null, an empty list, one project-qualified commit point, or a list for work spanning Projects. A task with no code work need not invent a commit. Keep the existing PENDING, WIP, BLOCKED, RECORDING and DONE lifecycle and its [state machine](transitions.md#task-state-machine); scheduling and transition authority remain external.

The preview columns follow the same order, ending with detail spec, generated between `<!-- tasks-preview-table:start -->` and `<!-- tasks-preview-table:end -->` under ## preview-table. A second tasks-dependency-topology-mermaid region under ## dependency-topology generates the dependency graph. Both come from tasks/ and are not edited by hand. Type-specific fields belong directly in YAML. Typical development fields include project repository, working branch, integration branch, repository refs, review required, gists and result. Reviews, tests, documentation, gates, decisions and feedback use the same common model and add what their work needs.

Work completion, result and permission are distinct. A completed test can fail; a completed decision can reject. Durable reports, acceptance material, decision comments, evidence and handoff receipts belong to task YAML/body. Do not create separate top-level folders for them.

When present, result records execution, outcome, summary, evidence and remaining. execution is non-empty; DONE requires an actual outcome and summary. Put check names, commands, observations and limitations in the durable task body, not as string entries in evidence. result.evidence is a list of versioned reference mappings with id, revision and location; outcome=pass requires non-empty durable evidence. Local references must resolve to the actual retained revision. A report in the same task may be referenced by that task's ID/revision and body anchor, for example:

```yaml
result:
  execution: completed
  outcome: pass
  summary: Request summary written and checked against the retained INT.
  evidence:
    - {id: DOCS-001, revision: v1, location: "tasks/DOCS-001.md#verification"}
  remaining: []
```

Use that reference only when DOCS-001@v1 actually retains the substantive report under the named heading. An empty reference shell or a task state alone is not evidence that verification happened.

Feature checks resolve relative paths from the Feature root and normalize native absolute paths and `file:` URIs before checking local record IDs/revisions. Prefer Feature-relative paths for portability. Windows drive letters are paths, not URI schemes; `file://localhost/...` is local, and Windows file authorities use UNC paths. Ambiguous drive-relative paths, foreign Windows paths on a POSIX host and unsupported file authorities fail explicitly; resolve a foreign machine's locator through the supplied mapping first. External non-file URIs remain unverified.

A local reference with a fragment must resolve to an anchor in the referenced revision's body, including `history.body` for an old revision. The checker supports ATX/Setext heading slugs (lowercase, spaces to hyphens, formatting/punctuation removed, duplicate suffixes `-1`, `-2`, etc.) and explicit HTML `id`/`a name` anchors. See [section links and custom anchors](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links) for the basic naming rules. Fenced examples, inline-code HTML and comments cannot supply anchors. Anchor existence is structural evidence only, not proof of the report's correctness.

## Points and areas

A recorded commit point is `<project-key>@<head-sha>`. A moving branch area is `<project-key>@<branch-name>`. The full point spelling `<project-key>@<branch-name>@<head-sha>` carries extra branch context but normalizes to project+SHA.

A branch name is not a unique immutable point and may occur in multiple Projects. Qualifying it with project-key identifies its area. Use a full ref such as refs/heads/main when branch namespaces need distinction. Do not infer point/area meaning by whether a branch name looks hexadecimal; the field or explicit reference kind determines the meaning.

Use full observed SHAs for durable points when possible. Abbreviations are accepted by the syntax helper but need uniqueness verification in that Project's actual Repository. Changing a branch must not rewrite historical commit points.

## Stable Project YAML

Copy [PROJECT.yaml](../templates/PROJECT.yaml) to project/<project-key>/project.yaml. It contains project key, remote repository, local repository and optional basic rules. Local repository may be one locator or a mapping keyed by device/OS, so different systems can retain different checkout locations. The mapping is not an instruction to move or clone repositories.

Set up this definition once and leave it stable during normal work. Add Projects or explicitly change a remote, permanent local mapping or management rule when needed. Do not store current head sha, task branches, review state, integration opponents or PR source/target points in Project YAML. Those belong to the task's specialized fields; a transient worktree location can also be recorded there.

The Project resolver reads the configured locator and returns it. It neither contacts the remote nor checks local Git objects. A mapping resolution is not proof that a commit exists or that a local checkout is current.

## Versions, history and consistency

A revision is optional metadata; include it when freezing an input or report. Versioned references use id/revision/location. IDs are stable, unique in a Feature and match detail filenames.

Optional history entries retain metadata (complete previous YAML without nested history) and body (previous authoritative Markdown) in the same detail. Historical references remain valid when the referenced revision is fully retained. Existing reports must not be rewritten to claim they examined a new version.

The read-only checker validates retained references, relationships, dependencies and YAML/preview/topology agreement; --render design/tasks/topology only prints. To update indexes, use the [generator and fixed-region rules](generated-indexes.md), never hand-maintained generated content or standalone horizontal-rule wrappers. Keep titles, short introductions and dated ## complementary notes outside the generated regions. The assigned maintainer owns detail state; stale previews do not prevent reading one detail. External references and authority are not authenticated.

With --project-root, declared project repository keys, head points and working/integration areas are checked against the registered Project YAML. Without it, registry verification is explicitly unverified. This is a structural/locator check, not Git synchronization or business approval.

## VERBAL and optional gists annotations

VERBAL/gists holds disposable logs, exports and drafts. Its verbal-preview-table region under ## preview-table is generated by scanning gists/ for paths, sizes and UTC modification times, not by maintaining rows; see [generated-indexes.md](generated-indexes.md). As a reference-only exception, tasks may list paths in the dedicated top-level `gists` list; previews label them reference only. Their existence is not validated and deleting them does not invalidate the task.

Do not place those paths in inputs, relations, evidence, decision reasons or completion conditions. Keep required conclusions and sufficient verification summaries in design/tasks. Formal bodies and STATUS must not depend on transient attachments; a reference annotation is not evidence.

## Templates

These are coherent examples, not a mandatory workflow. For first setup, follow the [initialization checklist](initialization.md). Replace example IDs, keys, locators, relations and content; remove unused sample tasks and regenerate their preview.

- [Design preview](../templates/DESIGN.md), [task preview](../templates/TASKS.md), [status](../templates/STATUS.md), [reference attachments](../templates/VERBAL.md).
- [INT](../templates/design/INT-001.md), [REQ](../templates/design/REQ-001.md), [SOL](../templates/design/SOL-001.md).
- [Development/common task](../templates/tasks/DEV-001.md), [decision](../templates/tasks/DECISION-001.md), [feedback](../templates/tasks/FEEDBACK-001.md), [gate](../templates/tasks/GATE-001.md).
- [Project definition](../templates/PROJECT.yaml), copied to the separate Project directory rather than into a real Feature.

Reuse the common task for review, test, docs, design or acceptance. Loading a template does not migrate existing project-management records.
