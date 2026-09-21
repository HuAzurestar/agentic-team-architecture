# <feature-key> Tasks

Task 状态和 refs 保存在 `STATUS.md`。这个本地文件按 task ID 说明具体工作。

## REQ-001 — 决定一个需求点

- 目标：取得并记录 `REQ-001` 的逐点人工决定。
- 输入：`REQUIREMENT.md`
- 工作：消除歧义，请求人类明确指出准确点和决定，并创建一个决定 commit。
- 完成条件：`REQ-001` 已有决定结果，且其决定 commit SHA 已记录在 `STATUS.md`。
- Gists：无。

## SOL-001 — 决定一个方案点

- 目标：取得并记录 `SOL-001` 的逐点人工决定。
- 输入：`REQUIREMENT.md`、`SOLUTION.md`
- 工作：核对引用的需求点、消除歧义、请求准确决定，并创建一个决定 commit。
- 完成条件：`SOL-001` 已有决定结果，且其决定 commit SHA 已记录在 `STATUS.md`。
- Gists：无。

## <task-id> — <task-title>

- 目标：
- 输入：
- 工作：
- 完成条件：
- Gists：无。

每增加一个 task，复制最后一个章节，然后替换或删除所有尖括号占位符。Gist 使用 feature 相对路径并以逗号分隔，例如 `gists/api-contract.md, gists/db-notes.md`。
