# Task planning and decomposition

Read when adding, splitting or connecting work in an existing Feature. The caller owns workflow and assignment; this reference defines a usable planning artifact, not who must perform the planning.

## Inputs and output

Use the requested outcome, constraints, priority, applicable INT/REQ/SOL versions and externally supplied authority. Produce task details with scope, expected result, completion conditions, dependencies and a return location. The assigned planner allocates non-conflicting stable IDs; do not require the user to invent internal labels merely to continue.

Return unresolved product choices, permission or materially ambiguous scope to the external orchestrator rather than handing internal bookkeeping to the user. Proactive clarification, channels and questioning methods belong to that workflow. Express plans in business language with optional trace IDs. The planner may allocate internal task IDs, but feature-key must be supplied externally and cannot be generated alongside them.

## Dependencies and scope

- Split work when scope, owner, candidate version, completion conditions or required authority differ enough to need independent tracking. Do not impose a fixed design/develop/review/test/release chain.
- `depends on` contains existing task IDs and must be acyclic. Add applicable design relationships or versioned `inputs`; IDs do not need to match the design-point ID.
- A dependency being DONE means its work was recorded as completed, not that its outcome passed. Express any required successful outcome or approval in the consuming task's completion conditions or the externally defined GATE.
- When scope changes, examine affected dependencies, review/test targets and remaining work. Keep an explicit disposition for deferred or replaced work rather than silently dropping it from the plan.

## Create through the supplied state interface

Read current IDs and source revisions, prepare the detail, then update the TASKS table and dependency topology with the script in [generated-region rules](generated-indexes.md). Leave new work PENDING unless an actual assignment has begun. The state maintainer coordinates concurrent writers; ID allocation and writes are not made atomic by this skill.

Follow the required maintenance in [SKILL.md](../SKILL.md) for index synchronization and record checking on every operation. The checker detects duplicate IDs, missing/cyclic dependencies, local-reference mismatches and preview drift; it does not allocate IDs or write business records. Report failed/partial writes for repair rather than treating them as created tasks. For later lifecycle changes, read [transitions.md](transitions.md).
