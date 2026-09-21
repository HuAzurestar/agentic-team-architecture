# <feature-key> Tasks

本地文件是唯一 task 状态与依赖索引。详情保存到 `tasks/<task-id>.md`；修改表格后运行 `task_context.py <feature-directory> --sync-topology` 重新派生图。

## Task index

| ID | 类型 | 名称 | 状态 | 负责人 | 依赖 | 开始时间 | 完成时间 | HEAD SHA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-001 | Requirement | 决定一个需求点 | `PENDING` | - | - | - | - | - |
| SOL-001 | Solution | 决定一个方案点 | `PENDING` | - | REQ-001 | - | - | - |
| GATE-START | Gate | 进入实现 | `PENDING` | - | SOL-001 | - | - | - |

## Dependency topology

<!-- task-topology:start -->
```mermaid
flowchart LR
    T0["REQ-001 · 决定一个需求点"]:::pending
    T1["SOL-001 · 决定一个方案点"]:::pending
    T2["GATE-START · 进入实现"]:::pending
    T0 --> T1
    T1 --> T2
    classDef pending fill:#e5e7eb,stroke:#6b7280,color:#111827
    classDef wip fill:#dbeafe,stroke:#2563eb,color:#111827
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#111827
    classDef recording fill:#fef3c7,stroke:#d97706,color:#111827
    classDef done fill:#dcfce7,stroke:#16a34a,color:#111827
```
<!-- task-topology:end -->
