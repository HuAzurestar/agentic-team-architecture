---
name: long-feature-development
description: Resume and advance persistent Feature tasks through the configured Project-Manage CLI, with own-author results, document editing and explicit offline YAML tools. Organization and authorization are supplied externally.
---

# Long Feature Development

Use the assigned Feature/task and current Project-Manage CLI. The primary client needs logical keys and a local CLI configuration, never the service's PM directory, SSH or a mounted share. Read the assignment's exact versions, allowed writes and authority before acting. This skill does not approve designs, gates, another author's results, publication or deployment.

## Management route and compatibility

For authorized ordinary management, choose direct current documents or the existing CLI/API for the same object, according to the runtime and role contract. Direct document work requires explicit access to the actual management root and the record/index checks; it is not required for remote CLI clients. A failed or rejected API operation must not automatically fall back to files. For an unknown submission, read back the actual object and effects before any deliberate retry.

The twelve target-only legacy files are preserved for existing users. Their REQUIREMENT/SOLUTION, task_context/task_state and automatic NO-FEAT conventions do not apply to the current YAML/CLI workflow. Do not select those entrypoints or their tests as current-protocol validation. Current records use STATUS/DESIGN/TASKS and focused YAML details.

## Start or resume through CLI

Read [CLI workflow](references/cli-workflow.md) for configuration, commands, own-author payloads, document roundtrips and outcome handling. Use `scripts/pm_cli.py` with an explicit current `client/cli/project_manage.py` and caller boundary. That CLI stays in its repository with its operation catalog and `task_workflow.py`; do not copy it out as a standalone client.

1. Verify the configured service/target, assignment and current readiness. `service-context` describes the configured service/repository; `context` reads the assigned task's current selected fields and report. Context and provenance strings do not authenticate the writer.
2. Work only within the granted scope. Each execution, independent quality or verified decision author uploads their own facts. Orchestration owns organization/dependencies/routing. It does not synthesize other authors' primary outcomes.
3. Use `update` for allowed own task fields, `report-save` for the own original report and `report-get` to recover its exact current body. A report save replaces the task body: download it first and retain current required content in the authored report when necessary.
4. Use `document-get` to extract Envelope.body.raw into a local working file, edit that file and use `document-put` to upload through the existing CLI. Exact document write paths must be granted. The service validates syntax/identity/graph and maintains supported indexes. Do not manually assemble STATUS/TASKS business summaries to compensate for missing server derivation.
5. Return the full candidate, actual commands/outcomes, source evidence, limitations and pending operations. A matching current readback does not prove request authorship, atomic compare-and-save, durable receipt or external hook completion. Do not automatically replay a failed or ambiguous write.

Before official writes, verify the real connection/target, authorized object and role scope, readiness and service-side coordination through the supplied runtime contract. When unavailable, preserve the own report/candidate locally and report the exact pending upload and engineering owner. No filesystem fallback, borrowed credentials or invented API/identity/CAS route.

New work maintains current content only: no new history files, full prior-version snapshots or cumulative history fields. Preserve existing formal evidence and Git history. The retained offline profile `configure` now replaces only its current profile without creating archives; it is not the online client's configuration route.

## Record contracts and offline tools

The [protocol](references/protocol.md), templates and topical references describe the YAML record vocabulary. Machine PM paths and old mandatory filesystem maintenance in these references apply only to explicitly assigned local/offline administration, never as prerequisites for CLI clients. See the complete [IO inventory and migration](references/cli-migration.md) before invoking a retained helper.

| Purpose | Reference |
| --- | --- |
| Task scope and IO | [Capability IO](references/capability-io.md), [task workflow](references/task-workflow.md) |
| Record schema and initialization | [Protocol](references/protocol.md), [initialization](references/initialization.md) |
| Design and decisions | [Detailed design](references/decisions.md), [confirmation](references/confirmation.md) |
| Dependencies and state | [Planning](references/task-planning.md), [transitions](references/transitions.md) |
| Quality and handoff | [Quality records](references/task-contracts.md), [handoffs](references/handoffs.md) |
| Acceptance and gates | [Acceptance](references/acceptance.md), [gates](references/gates.md) |
| Repository and continuation | [Repository context](references/repository-context.md), [continuity](references/continuity.md), [checkpoints](references/checkpoints.md) |
| Explicit offline index administration | [Generated indexes](references/generated-indexes.md) |
| Separate legacy notification access | [Runtime persistence](references/runtime-persistence.md), [notification hooks](references/notification-hooks.md) |

Retained `contract_check.py`, `feature_indexes.py` and `project_refs.py` operate on explicit disposable exports or separately authorized local administration. They are not transport implementations. Never point them at a guessed server root; the server owns online validation/index transactions. `runtime_state.py` and `workflow_events.py` are legacy offline runtime/notification auxiliaries; they do not provide the CLI's connection or authentication. The checker can read pre-existing history for reference compatibility, but no helper creates full prior-record snapshots and templates do not request them.

## Source and version

This package establishes a managed Skill source at `skills/long-feature-development` in the registered AOPC repository (`https://github.com/HuAzurestar/agentic-team-architecture.git`), seeded from the pinned installed YAML Skill (SKILL.md SHA256 `c5a3abfc86a63bcfdfaebc8b24fb8b46c715ee6f552ae073a65fd6626931e226`). The installed directory was not a Git repository. Package version is `cli-source-3`; repository commit identifies the actual candidate. Installation and deployment are separate actions. Read [migration](references/cli-migration.md) for source mapping, compatibility and pending upstream integration.
