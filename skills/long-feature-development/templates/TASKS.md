# <feature-key> Tasks

This shared file is the only complete task-state and dependency index. Keep short details in `tasks/<task-id>.md`. Use the controlled state writer for normal changes; `task_context.py <feature-directory> --sync-topology` is only for explicit repair or import.

## Task index

| ID | Type | Name | State | Owner | Depends on | Started at | Completed at | HEAD SHA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-001 | Requirement | Decide one requirement point | `PENDING` | - | - | - | - | - |
| SOL-001 | Solution | Decide one solution point | `PENDING` | - | REQ-001 | - | - | - |
| GATE-START | Gate | Enter implementation | `PENDING` | - | SOL-001 | - | - | - |

## Dependency topology

<!-- task-topology:start -->
```mermaid
flowchart LR
    T0["REQ-001 · Decide one requirement point"]:::pending
    T1["SOL-001 · Decide one solution point"]:::pending
    T2["GATE-START · Enter implementation"]:::pending
    T0 --> T1
    T1 --> T2
    classDef pending fill:#e5e7eb,stroke:#6b7280,color:#111827
    classDef wip fill:#dbeafe,stroke:#2563eb,color:#111827
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#111827
    classDef recording fill:#fef3c7,stroke:#d97706,color:#111827
    classDef done fill:#dcfce7,stroke:#16a34a,color:#111827
```
<!-- task-topology:end -->
