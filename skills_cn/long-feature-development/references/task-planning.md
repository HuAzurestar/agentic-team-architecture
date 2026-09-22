# Agent 负责任务规划

已有 feature 需要新增工作时读取本文件。

## 用户与 Agent 的边界

用户提供业务结果、约束、优先级和必要授权。内部 task ID、类型、依赖和需求/方案 selector 由 Agent 负责。不得仅为了开始或继续工作而要求用户发明或理解内部编号。

只有产品选择、授权边界、破坏性操作或无法安全推导的范围才询问用户。对用户用业务语言展示计划；内部标签只作为可选追溯信息。

## 受控创建

正常创建 task 使用 `scripts/task_create.py`。它按类型分配下一个不冲突 ID，校验依赖和 point selector，创建 `tasks/<id>.md`、插入 `TASKS.md` 行并重建 Mermaid。仓库基线由 Agent 从实际 refs 提供。

不要把内部命令写成用户必须提供的 prompt。创建失败时保留旧索引并移除新详情文件。
