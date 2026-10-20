---
name: long-feature-development
description: Maintain persistent Feature design points and tasks across sessions or agents, with YAML details, Markdown previews and stable Project repository mappings. Organization, orchestration, authorization and the management-root location are supplied externally.
---

# Long Feature Development

Use the Feature's records to continue work. This skill defines records and a default single-task loop, not intent recognition, company roles or company orchestration. The caller supplies assignment, authority, state maintenance and environment; a supplied workflow takes precedence over the fallback loop.

## Feature and Project

The caller resolves `<Project-Manage>`. A Feature is persistent work across Projects and requirements. A Project identifies one Repository and its stable local/remote mapping and basic rules:

```text
<Project-Manage>/
├── feature/<feature-key>/
│   ├── STATUS.md
│   ├── DESIGN.md
│   ├── TASKS.md
│   ├── VERBAL.md
│   ├── design/<point-id>.md
│   ├── tasks/<task-id>.md
│   └── gists/<attachment>.*
└── project/<project-key>/
    └── project.yaml
```

The management directory need not be a Git repository. Resolve its actual location, state/authority access and the assignment externally. Report missing or conflicting facts without inventing ownership.

## Records and previews

- DESIGN unifies numbered requirement, solution and intent points. INT preserves the external wording, uses decided by for the proposer and title for the concrete intent summary; RECORDED does not approve derived REQ/SOL. Deriving REQ/SOL is detailed design. Detail YAML is the state source; DESIGN.md previews common columns and compresses specialized fields into detail spec.
- TASKS contains all task types, including development, review, docs, decision, feedback, test and gate. Owner may identify a Human, Agent or Platform. Task-specific repository, review, result and other fields are YAML additions, previewed in detail spec.
- VERBAL/gists holds disposable drafts, exports and logs. Tasks may list them only in the dedicated reference-only gists field, never as inputs, decision reasons, evidence or completion prerequisites. Deleting them must not break validation or resumption.

STATUS.md is the Feature's integrated status-management entry for repository, Feature and development state, current focus, blockers and next actions, not merely a resume summary. Use concise status and links without duplicating the other modules.

## Initialize a feature

For a new Feature, follow the [initialization checklist](references/initialization.md), using the record templates rather than a content-writing script. It defines the minimum records, sample cleanup, initial states and completion checks.

- Caller: "Initialize Feature FEAT-42 at the supplied management root; preserve Lin's request to report invalid entries." Prepare the Feature skeleton and an INT with Lin as originator; do not invent approved REQ/SOL or copy unrelated sample tasks.
- Caller: "Start a feature for this request," without a key. Retain the request context and obtain the external identity before creating a directory; do not generate a temporary key.

## Feature identity

Only the user, platform or upstream caller supplies feature-key. No agent, including an orchestrator, may allocate, guess or generate a temporary Feature key. Without an explicit key/location mapping, retain available context and obtain that identity externally rather than creating a Feature directory. The template's example-feature is not an assigned key. Feature identity is distinct from agent-allocated internal point/task IDs.

## Start or resume

Follow [continuity](references/continuity.md): resolve identity and assignment, read STATUS and focused details, check recorded inputs and actual repository context, then validate before affected work. Resume existing records instead of copying templates over them.

## Work on one task

Read the supplied orchestration instructions when present. If no specific orchestration is supplied, use the [default task loop](references/task-workflow.md): establish scope/readiness → record WIP → work and verify → RECORDING → persist and validate → DONE and return the result. It preserves blocking, interruption and reopening without prescribing company phases or additional roles. Both paths follow the common state/record contracts and the maintenance below.

## Required maintenance for each operation

In commands, `<skill-root>` is the absolute directory containing this loaded SKILL.md, not the working repository or Feature directory. `<feature-directory>` resolves to `<Project-Manage>/feature/<feature-key>` and `<project-directory>` to `<Project-Manage>/project`. Substitute actual absolute paths and quote paths containing spaces. Commands then work from any current directory without changing repositories.

- Before operating, reread current source versions and write ownership; run the read-only record checker for an initialized Feature. Queries/resumption do not write files. For first initialization with no records to check, obtain the external key and have the assigned agent prepare records from templates, then perform the same closing checks below.
- Content work belongs to the assigned agent: author INT/REQ/SOL, task bodies, judgments and state using templates and the supplied state interface. Scripts do not compose SOL, invent requirements/owners/decisions or choose the next state. Template use does not require another fixed role.
- After each creation, edit, state transition, feedback/decision record or handoff update, run both commands before claiming that maintenance operation is complete:

```text
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --write
python "<skill-root>/scripts/contract_check.py" "<feature-directory>" --format json
```

- For a stable Project-only edit, check project.yaml; supply --project-root to Feature checks when repository mappings are involved. If sync/check fails, a script is unavailable or concurrent edits are found, retain and report the evidence and stop dependent mutations, handoffs or releases rather than silently skipping checks. Unrelated read-only diagnosis may continue. Repair derived-only drift through the generator only when the source is understood; do not rewrite business facts as a repair.

These commands are record-maintenance discipline, not a company workflow. Scripts perform mechanical derived synchronization, structural checks and location resolution, not Git/remote synchronization or release authorization, and do not replace external write coordination.

Ordinary clarification, proactive conversation, channels and questioning methods belong to the external orchestrator; this skill binds no communication tool. Only a [GATE that requires the user's decision](references/gates.md) defines a mandatory request/response and no-response/no-release contract.

## Read references for the current action

Use the matching reference, not the entire references directory. Read the record specification when creating/editing records or resolving schema questions; an ordinary task need not preload every schema, report type or repository document. A reference supplies record requirements, not a mandatory phase or a new grant of authority.

| When doing this | Read this |
| --- | --- |
| Initialize a new Feature | [Initialization checklist](references/initialization.md) |
| Execute one task; resolve supplied versus fallback orchestration | [Task workflow](references/task-workflow.md) |
| Edit YAML, previews, STATUS or Project configuration | [Record specification](references/protocol.md) |
| Preserve external intent; derive and relate INT/REQ/SOL | [Detailed design](references/decisions.md) |
| Decide, partially accept, revise or reopen a design point | [Point decisions and revisions](references/confirmation.md) |
| Add/split work or change dependencies | [Task planning](references/task-planning.md) |
| Generate or refresh DESIGN/TASKS/VERBAL indexes and task topology | [Generated regions and scoped updates](references/generated-indexes.md) |
| Assign, block, complete or reopen a task | [Task state machine and records](references/transitions.md) |
| Receive work, delegate it or return a result/receipt | [Handoff records](references/handoffs.md) |
| Plan/report tests, reviews or rework | [Quality task records](references/task-contracts.md) |
| Prepare/present acceptance or record its response | [User-facing acceptance](references/acceptance.md) |
| Evaluate a GATE or record a policy-dependent Feature transition | [GATE checks and permission](references/gates.md) |
| Resolve checkouts, compare code points or prepare integration/PR handoff | [Repository context](references/repository-context.md) |
| Start/resume/end work; process feedback | [Continuity](references/continuity.md) |
| Save recovery context, inspect interrupted work or prepare risky work/handoff | [Checkpoints and recovery](references/checkpoints.md) |

Keep the spaced YAML keys and preview markers from the templates. Unknown specialized metadata belongs directly in YAML and is summarized automatically; it does not need a new table column. Preserve original intent, revisions and decision history.

A role mandate in applicable AGENTS.md may permit agent confirmation of REQ/SOL under explicit conditions, with mandatory recorded reasoning; follow [point decisions](references/confirmation.md). A valid delegated decision does not require a fixed second human confirmation. Work completion, outcome and later permission remain separate. The organization supplies ownership, sequencing, policy, state-write methods and environment.

## Project-qualified references

A commit point is `<project-key>@<head-sha>`. A moving branch area is `<project-key>@<branch>`. Full point spelling `<project-key>@<branch>@<head-sha>` is supported, but its canonical identity remains project+SHA. Do not substitute a branch area for a recorded commit point. Prefer a full observed SHA; abbreviations require uniqueness verification in the corresponding Repository.

Project YAML stays stable during work. Current HEAD, working/integration branches, review targets and PR endpoints belong to tasks, not the Project definition.

## Mechanical maintenance commands

With Python and PyYAML, the read-only [record checker](scripts/contract_check.py) checks details, previews/topology and local references. The [index generator](scripts/feature_indexes.py) generates and updates only marked table, dependency-graph and attachment-list regions; do not maintain their contents by hand. Read [generated-region rules](references/generated-indexes.md) before updating, preserving titles, introductions and complementary notes. The [Project resolver](scripts/project_refs.py) returns repository mappings without fetching or verifying commits.

```text
python "<skill-root>/scripts/contract_check.py" "<feature-directory>" --project-root "<project-directory>" --format json
python "<skill-root>/scripts/contract_check.py" "<feature-directory>" --render design
python "<skill-root>/scripts/contract_check.py" "<feature-directory>" --render tasks
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --check
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --write
python "<skill-root>/scripts/contract_check.py" "<project-directory>/<project-key>/project.yaml"
python "<skill-root>/scripts/project_refs.py" "<project-directory>" "project-key@0123456789abcdef0123456789abcdef01234567"
python "<skill-root>/scripts/project_refs.py" "<project-directory>" "project-key@main" --kind area
```

--write permits synchronizing existing facts into generated index regions, not creating or rewriting SOL/task bodies; default --check is read-only. --format json/text selects the check report's machine-readable/text representation, not content authoring; --render only prints derived content. Missing registry verification remains unverified; helpers do not authenticate authority or judge business correctness. After script changes run [record tests](scripts/test_contract_check.py), [generation tests](scripts/test_feature_indexes.py) and [reference tests](scripts/test_project_refs.py).
