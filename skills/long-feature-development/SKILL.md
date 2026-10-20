---
name: long-feature-development
description: Maintain persistent Feature design points and tasks across sessions or agents, with YAML details, Markdown previews and stable Project repository mappings. Organization, orchestration, authorization and the management-root location are supplied externally.
---

# Long Feature Development

Use the Feature's records to continue work. This skill defines content and reference meaning; it does not identify intent, choose company roles, orchestrate work, choose a state maintainer or configure machines and synchronization.

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

## Required maintenance for each operation

Only the user, platform or upstream caller supplies feature-key. No agent, including an orchestrator, may allocate, guess or generate a temporary Feature key. Without an explicit key/location mapping, retain available context and obtain that identity externally rather than creating a Feature directory. The template's example-feature is not an assigned key. Feature identity is distinct from agent-allocated internal point/task IDs.

- Before operating, reread current source versions and write ownership; run the read-only record checker for an initialized Feature. Queries/resumption do not write files. For first initialization with no records to check, obtain the external key and have the assigned agent prepare records from templates, then perform the same closing checks below.
- Content work belongs to the assigned agent: author INT/REQ/SOL, task bodies, judgments and state using templates and the supplied state interface. Scripts do not compose SOL, invent requirements/owners/decisions or choose the next state. Template use does not require another fixed role.
- After each creation, edit, state transition, feedback/decision record or handoff update, run both commands before claiming that maintenance operation is complete:

```text
python scripts/feature_indexes.py path/to/feature --write
python scripts/contract_check.py path/to/feature --format json
```

- For a stable Project-only edit, check project.yaml; supply --project-root to Feature checks when repository mappings are involved. If sync/check fails, a script is unavailable or concurrent edits are found, retain and report the evidence and stop dependent mutations, handoffs or releases rather than silently skipping checks. Unrelated read-only diagnosis may continue. Repair derived-only drift through the generator only when the source is understood; do not rewrite business facts as a repair.

These commands are record-maintenance discipline, not a company workflow. Scripts perform mechanical derived synchronization, structural checks and location resolution, not Git/remote synchronization or release authorization, and do not replace external write coordination.

Ordinary clarification, proactive conversation, channels and questioning methods belong to the external orchestrator; this skill binds no communication tool. Only a [GATE that requires the user's decision](references/gates.md) defines a mandatory request/response and no-response/no-release contract.

## Read references for the current action

Use the matching reference, not the entire references directory. Read the record specification when creating/editing records or resolving schema questions; an ordinary task need not preload every schema, report type or repository document. A reference supplies record requirements, not a mandatory phase or a new grant of authority.

| When doing this | Read this |
| --- | --- |
| Initialize records; edit YAML, previews, STATUS or Project configuration | [Record specification](references/protocol.md) |
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

A valid delegated decision does not require a fixed second human confirmation. Work completion, outcome and later permission remain separate. The organization supplies ownership, sequencing, policy, state-write methods and environment.

## Project-qualified references

A commit point is `<project-key>@<head-sha>`. A moving branch area is `<project-key>@<branch>`. Full point spelling `<project-key>@<branch>@<head-sha>` is supported, but its canonical identity remains project+SHA. Do not substitute a branch area for a recorded commit point. Prefer a full observed SHA; abbreviations require uniqueness verification in the corresponding Repository.

Project YAML stays stable during work. Current HEAD, working/integration branches, review targets and PR endpoints belong to tasks, not the Project definition.

## Mechanical maintenance commands

With Python and PyYAML, the read-only [record checker](scripts/contract_check.py) checks details, previews/topology and local references. The [index generator](scripts/feature_indexes.py) generates and updates only marked table, dependency-graph and attachment-list regions; do not maintain their contents by hand. Read [generated-region rules](references/generated-indexes.md) before updating, preserving titles, introductions and complementary notes. The [Project resolver](scripts/project_refs.py) returns repository mappings without fetching or verifying commits.

```text
python scripts/contract_check.py path/to/feature --project-root path/to/project --format json
python scripts/contract_check.py path/to/feature --render design
python scripts/contract_check.py path/to/feature --render tasks
python scripts/feature_indexes.py path/to/feature --check
python scripts/feature_indexes.py path/to/feature --write
python scripts/contract_check.py path/to/project/project-key/project.yaml
python scripts/project_refs.py path/to/project project-key@0123456789abcdef0123456789abcdef01234567
python scripts/project_refs.py path/to/project project-key@main --kind area
```

--write permits synchronizing existing facts into generated index regions, not creating or rewriting SOL/task bodies; default --check is read-only. --format json/text selects the check report's machine-readable/text representation, not content authoring; --render only prints derived content. Missing registry verification remains unverified; helpers do not authenticate authority or judge business correctness. After script changes run [record tests](scripts/test_contract_check.py), [generation tests](scripts/test_feature_indexes.py) and [reference tests](scripts/test_project_refs.py).
