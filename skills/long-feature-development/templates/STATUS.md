# example-feature — STATUS

Integrated status-management entry for repository, Feature and development state. Keep overall status here and link to detailed records rather than duplicating DESIGN, TASKS or VERBAL content. The overview items below are examples, not a required workflow.

| Item | Current value |
| --- | --- |
| Feature key | example-feature |
| Project keys | example-project |
| Feature state | PLANNING |
| Development overview | Not started; no implementation candidate recorded |
| Integration / release overview | Not started |
| Current focus | Process external intent and begin detailed design |
| Focused work / record | - |
| State maintainer / access | Supplied by the caller |
| Authority source / access | Supplied by the caller |
| Next action | Obtain the INT source and assign detailed design |
| Blocker / release condition | - |

## Entry points

- [Design index](DESIGN.md)
- [Task index](TASKS.md)

## Repository status and Project bindings

| Project key | Stable configuration | Repository / sync / integration status | Related work |
| --- | --- | --- | --- |
| example-project | ../../project/example-project/project.yaml | Unverified; no repository observation recorded | - |

## Management boundaries

Keep current repository-level status here, leaving stable remote/local mappings and basic rules in Project YAML. Summarize overall development and cross-task blockers without maintaining a second task ledger. Design decisions, task states/dependencies, commit points and execution reports remain in their respective details and previews; disposable attachment lists remain in VERBAL. If an overview conflicts with its source, report and reconcile it rather than overriding the detail.

Do not embed this document's own Git HEAD. State maintenance and synchronization are supplied externally; the Feature directory need not be a Git repository.
