# Initialize a Feature

Read when creating a Feature's first records. For an existing or partially written Feature, use [continuity](continuity.md) and [recovery](checkpoints.md); do not overwrite records with examples.

## Inputs and identity

### First-use configuration

Resolve the runtime-supplied skill-state locator and initialize/read the two persistent profiles in [runtime persistence](runtime-persistence.md). Keep PM paths and notification nodes/tools out of agent instructions. Runtime installation and locator access are actual prerequisites, not supplied by this draft. Use the selected PM/Project mapping; keep organization/authority policy a separate versioned input. Reuse known environment configuration.

A supplied Feature key may be an opaque label without a reachable issue URL. Preserve actual wording/provenance. Report missing proposer/business-owner/decision-maker/executor as decision points; do not infer them.

Obtain the external feature-key, management-root mapping, authorized scope, state maintainer/write interface and authority source. Apply the Feature identity rule in [SKILL.md](../SKILL.md#feature-identity). A missing key is not permission to invent NO-FEAT or use example-feature. Missing access/authority remains unresolved; do not claim initialized state is ready for execution.

## Prepare the records

1. Confirm the supplied Feature location is new and coordinate writes through the supplied interface. Read the [record specification](protocol.md) for schema and [generated-region rules](generated-indexes.md) for index layout.
2. Prepare STATUS.md, DESIGN.md and TASKS.md from their [templates](protocol.md#templates), with design/ and tasks/ directories even when empty. Include the VERBAL.md template for the disposable attachment index; create gists/ only when attachments are needed. VERBAL/gists may later be removed without invalidating authoritative records. Keep PROJECT.yaml out of the Feature directory.
3. Replace example-feature in titles/STATUS with the supplied key. Fill actual focus, next action, state/authority access and relevant Project bindings; remove unneeded sample rows, tasks, design points and their relations. Do not leave sample identities, repository locators, requests or completion conditions as real facts. Preserve headings and marker pairs; let the generator replace sample preview contents.
4. Create only records needed by the actual request. For an external request, preserve its exact wording/source and supplied originator in an INT using [detailed-design rules](decisions.md). INT is RECORDED; newly proposed REQ/SOL are PROPOSED with null decision fields until decided. Initialization does not require inventing REQ/SOL or one task per design point.
5. If initial tasks are needed, use [task planning](task-planning.md) and the common task template. Allocate non-conflicting internal IDs; record scope, versioned inputs, completion conditions and dependencies. New unassigned tasks remain PENDING with null owner/timestamps and no fabricated commit point. Do not copy sample DECISION/FEEDBACK/GATE work merely to populate the index.
6. Reuse existing stable Project definitions. If an authorized new Project mapping is needed, prepare project/<project-key>/project.yaml separately from [PROJECT.yaml](../templates/PROJECT.yaml), replace sample locators and validate it. Missing mappings stay explicit and block dependent repository work, not unrelated record preparation. Never clone, move or synchronize repositories as a consequence of initialization.

## Complete initialization

Run the index generator and record checker using the absolute-path commands in [SKILL.md](../SKILL.md#required-maintenance-for-each-operation). There is no pre-check for an entirely new Feature: prepare its initial record set as one coordinated operation, then perform these closing checks. After successful initialization, ordinary before/after maintenance applies. Pass the actual project registry with --project-root when Project mappings are involved. Repair source/layout errors before claiming success; scripts do not fill missing business facts.

Initialization is complete when identity/access are resolved, authoritative records contain only actual scoped facts, local relations/dependencies resolve, previews match their sources, and checks pass. Persist through the authorized state interface and leave STATUS pointing to the current work and next action. Report unavailable repository/remote facts as unverified; structural success is neither design approval nor execution/release permission. The next task uses the supplied workflow or the [default task loop](task-workflow.md).
