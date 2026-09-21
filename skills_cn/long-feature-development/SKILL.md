---
name: long-feature-development
description: 从项目管理目录恢复并推进跨会话的软件 feature，使用精简 Markdown 状态和 Git refs 处理多仓库或 PR/MR。用于跨会话工作，不用于一次会话可完成的普通修改。
---

# 长程 Feature 开发

本 Skill 使用小型、版本化的 feature 记录续接开发，不依赖旧聊天。项目自行决定 `<Project-Manage>` 的实际路径；不得假定为 MPA 或其他固定仓库。

## 必需结构

```text
<Project-Manage>/<feature-key>/
├── REQUIREMENT.md
├── SOLUTION.md
├── STATUS.md
├── TASKS.md
├── tasks/
│   └── <task-id>.md
└── gists/
```

`REQUIREMENT.md`、`SOLUTION.md`、`STATUS.md` 是项目管理记录。`TASKS.md`、`tasks/`、`gists/` 默认是本地 Agent 材料，除非项目明确改变策略，否则不得上传。

## 初始化

1. 解析 `<Project-Manage>`。尚无正式 ID 时，唯一情况下使用 `NO-FEAT`，可能冲突时使用 `NO-FEAT-<6位随机值>`；不得为编造正式 ID 而等待。
2. 复制四个文档模板，并为每个初始 task 把 `templates/TASK.md` 复制到 `tasks/<task-id>.md`。
3. 替换或删除所有尖括号占位符。每个 task 必须恰有一条 `TASKS.md` 索引和一个详情文件；真实点 ID 替换前保留 `REQ-001`、`SOL-001`。
4. 仅在需要时创建 `gists/`。
5. 为 `TASKS.md`、`tasks/`、`gists/` 添加限定于该 feature 的本地 exclude；未经授权不得扩大规则。
6. 第一次项目管理 commit 前运行 `python <skill-root>/scripts/task_context.py <feature-directory>`，修复全部错误。
7. 需求和方案整体状态由逐点状态派生，不能用一次全局批准设置。

## Feature 身份

`NO-FEAT` 与 `NO-FEAT-<6位随机值>` 都是有效临时 key。后缀使用六位小写字母或数字。正式 ID 的分配时点只由开发者决定。ID 变化时，在一次项目管理变更中重命名目录、更新标题和 `STATUS.md`，并把旧 key 追加到 `Previous IDs`；不得改写历史。

## 开始或恢复

1. 解析准确的 `<Project-Manage>` 映射和 feature ID；有歧义就停止。
2. 运行 `task_context.py`。只有用户明确选择非当前 task 时才加 `--task <task-id>`。它是唯一恢复读取器：校验索引和拓扑，只输出 feature 摘要与 Git 表、当前 task、直接依赖、显式选择的需求/方案点和 gist。
3. 根据输出核对需求与方案状态，再将其视为边界。
4. 对每个仓库分别核对工作 branch/HEAD、日常 integration branch/SHA 和最终 PR/MR source/target refs。
5. 不可访问的远端状态标记为未验证，不得猜测。
6. 记录值与观察值不一致时，先解决漂移再修改代码。

脚本非零退出是硬停止。不得推断缺失的当前 task、索引行、详情文件、依赖、Git ref 或 gist；旧 `STATUS.md` task 表不得静默迁移。

项目管理仓库不能在 `STATUS.md` 内写入“包含该文件的 commit SHA”，因此其工作 HEAD 可使用 `DERIVED:HEAD`。只有文件已跟踪、与 HEAD 一致且无 staged/unstaged 修改时才能解析；其他 Git/PR/MR/task refs 必须是实际观察的字面 SHA。

## 确认边界

- 每个决定点使用稳定 `REQ-*` 或 `SOL-*` ID；“全部同意”不能改变点状态。
- 仅在获授权时，LLM 才能提出推测可确认项，并必须逐项复述准确 ID 与内容，请求二次人工确认。
- 已确认点在人员明确重开前锁定；保留内容和决定历史。
- 被拒绝点可修订并重开；再次确认仍需明确人工决定。
- `CONFIRMED` 与 `BASELINED` 是逐点派生状态。

新增、决定、修订或重开需求/方案点时才读取 [confirmation.md](references/confirmation.md)。

## 处理一个 Task

- Task 只使用 `PENDING`、`WIP`、`BLOCKED`、`RECORDING`、`DONE`。
- `TASKS.md` 是唯一 task 状态与依赖索引；`STATUS.md` 只保存 feature 状态并指向当前 task。
- 需求、方案、开发、测试、评审、返工、验收和 gate 共用同一 task 状态机。
- 每个需求/方案点建立同 ID task；其决定 commit SHA 登记后才能 `DONE`。
- 接取前要求直接依赖均为 `DONE`；接取时写负责人、开始时间、所有 start refs 和当前 HEAD。
- 范围与完成条件读取 `tasks/<task-id>.md`，额外材料放入显式 gist。
- 详情中必须恰有一行 `Requirement points` 和一行 `Solution points`；值为逗号分隔 ID 或 `none`。缺失、歧义或未知 selector 都是硬错误。
- 实现 commit subject 以 feature/task 开头。决定 commit 每次只处理一个点。
- 一个 task 可产生多个 commit；不得自动 merge 实现分支。
- 工作完成后先进入 `RECORDING`，创建最终 task commit 或登记已接受 commit，再为每个受影响仓库写唯一 completion SHA，然后进入 `DONE`。
- 中断保持 `WIP` 并更新 resume action；阻塞写原因和解除条件。失败/放弃 attempt 保留历史，重开时追加 start refs。
- `TASKS.md` Mermaid 必须由表格派生；修改行后运行 `--sync-topology` 再校验。

改变 task 状态或 feature 流转时读取 [transitions.md](references/transitions.md)。创建、接取、记录或完成质量/验收/gate task 时读取 [task-contracts.md](references/task-contracts.md)。创建/执行 gate 或改变 feature phase/condition 时读取 [feature-gates.md](references/feature-gates.md)。详细测试输出和 review comments 只写入结果 gist；gate 不替代人工验收。

## Git 与托管平台边界

- 每个仓库独立处理；每个受影响仓库使用一个 feature integration branch，最多一个最终实现 PR/MR。
- 分开记录工作 HEAD、日常 integration 对手和最终 PR/MR source/target refs；不得用一个“当前 SHA”混用。
- 对手分支前进时先保留旧 SHA 完成比较，再更新为新观察 SHA；不得使用 `LIVE:<branch>`、`latest` 等移动标记。
- 代码只提交到实现分支，不自动合并。项目管理变更单独提交，只在获授权后 merge/upload。
- 只在分支、commit、同步、PR/MR、评审、CI 等 Git 策略边界调用 `git-collaboration`；普通恢复不加载其全部引用。

## 上下文边界

逐点确认需求是意图，逐点确认方案是实施计划，Git 是实现状态，`STATUS.md` 是 feature 状态，`TASKS.md` 是 task/ref 索引，`tasks/` 是聚焦详情。它们冲突时报告，不得改写已决定点掩盖冲突。

不要预加载全仓文档。根据当前 task、显式 gist、实际 diff、符号、manifest 和仓库说明发现代码上下文。内置 Markdown focus 不依赖 PIRC-14；未来 PIRC-14 adapter 只能生成相同聚焦 schema，不得扩大 selector、绕过校验或成为恢复必需项。

## 结束一次运行

留下可续接状态：当前 task/状态、观察到的分支和 SHA、PR/MR refs、本轮 commits、准确 resume action、blocker 及解除条件。结束前重新运行 `task_context.py`；失败表示不可续接。

## 验证

```text
python scripts/test_task_context.py
python <skill-quality-reviewer>/scripts/skill-audit.py <skill-root> --format json
```
