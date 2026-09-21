---
name: long-feature-development
description: 从项目管理目录恢复并推进跨会话的软件 feature，使用精简 Markdown 状态与 Git refs 续接多仓库或 PR/MR。适用于跨多个会话的工作；不适用于一次会话即可完成的普通修改。
---

# 长程 Feature 开发

本 Skill 使用一组精简、版本化的 feature 记录续接开发，不依赖旧聊天记录。项目自行选择 `<Project-Manage>` 所代表的具体路径；不得假定它一定是 MPA 或其他固定仓库。

## 必需的 Feature 结构

```text
<Project-Manage>/<feature-key>/
├── REQUIREMENT.md
├── SOLUTION.md
├── STATUS.md
├── TASKS.md
└── gists/
```

`REQUIREMENT.md`、`SOLUTION.md` 和 `STATUS.md` 是项目管理记录。`TASKS.md` 与 `gists/` 默认是本地 Agent 工作材料；除非项目明确改变策略，否则不得上传。

## 初始化 Feature

1. 解析 `<Project-Manage>`。开发者尚未分配 feature ID 时，唯一情况下使用 `NO-FEAT`，可能冲突时使用 `NO-FEAT-<6位随机值>`。不得为了编造正式 ID 而推迟初始化。
2. 只从 `templates/` 复制四个匹配文件：`REQUIREMENT.md`、`SOLUTION.md`、`STATUS.md` 和本地 `TASKS.md`。
3. 替换或删除所有尖括号占位符。`STATUS.md` 中每个 task 行都必须在 `TASKS.md` 有且只有一个对应章节；在被真实点 ID 替换前，必须保留模板提供的 `REQ-001` 和 `SOL-001` 点任务。
4. 仅当 task 确实需要时才创建本地 `gists/`。
5. 为 `TASKS.md` 和 `gists/` 添加精确且限定于该 feature 的本地 exclude；未经授权不得添加仓库级忽略规则。
6. 首次提交项目管理内容前，运行[上下文提取脚本](scripts/task_context.py)：`python <skill-root>/scripts/task_context.py <feature-directory>`。修复所有报告的不一致。
7. 需求和方案保持 `DRAFT`。整体状态必须由各点状态派生，不能通过一次全局批准直接设置。

## Feature 身份

`NO-FEAT` 与 `NO-FEAT-<6位随机值>` 都是有效临时 feature key。随机后缀使用六位小写字母或数字。何时分配正式 ID 只能由开发者决定；可行性确认后分配很常见，但不是强制时点。

ID 变化时，在一次项目管理变更中重命名 feature 目录、更新文档标题和 `STATUS.md` 的 Feature ID，并把旧 key 追加到 Previous IDs。不得重写旧 commit 或远端历史来隐藏临时 key。

## 开始或恢复

1. 解析准确的 `<Project-Manage>` 映射和 feature ID；任一存在歧义时停止。
2. 运行[上下文提取脚本](scripts/task_context.py)：`python <skill-root>/scripts/task_context.py <feature-directory>`。只有用户明确选择非当前 task 时才使用 `--task <task-id>`。该命令是唯一恢复读取器：输出需求、方案、状态、选定 task 章节，以及该 task 明确声明的 gist。
3. 根据输出核对需求和方案的确认状态，再决定能否把它们当作固定边界。
4. 对每个仓库分别核对工作分支/HEAD、日常 task 合并使用的 integration 分支/SHA，以及最终 PR/MR 的 source/target refs。
5. 远端状态不可用时标记为未验证，不得猜测。
6. 比较记录值与观察值；修改代码前先处理过期状态。

`task_context.py` 非零退出是硬停止。不得推断缺失的当前 task 行、task 状态行、`TASKS.md` 章节或声明的 gist。

包含 `STATUS.md` 的项目管理仓库无法在同一文件中写入“包含该文件的 commit SHA”。因此其工作 HEAD 单元格使用 `DERIVED:HEAD`，表示以 checkout 后的 Git HEAD 为事实来源。只有当 `STATUS.md` 已跟踪、与 HEAD 一致且没有 staged/unstaged 修改时才能解析它；否则停止。所有 integration 对手 SHA、PR/MR SHA、task 接取 ref 和完成 ref 都必须是实际观察到的字面 SHA，不能使用移动分支别名。

## 确认边界

- 每个决策点使用稳定的 `REQ-*` 或 `SOL-*` ID。“全部同意”一类宽泛表述不能改变点状态。
- 只有获得授权时，LLM 才能提出它推测可确认的点；随后必须逐项复述准确 ID 和内容，请求第二次人工确认。
- 已确认点在人员明确重开前保持锁定。保留其内容和决定历史，不得静默替换。
- 被拒绝点可以修改并重开，不需要额外撤回；重新确认仍需明确的人类决定。
- 需求 `CONFIRMED` 与方案 `BASELINED` 是派生状态：每个活动点均已单独 `CONFIRMED`，且不存在活动的 `PROPOSED` 或 `REOPENED` 点。

新增、决定、修订或重开需求/方案点时，才读取 [confirmation.md](references/confirmation.md)。

## 处理一个 Task

- Task 只使用 `TODO`、`WIP`、`BLOCKED` 和 `DONE`。
- 需求、方案、开发、测试和评审都是同一张 `STATUS.md` 表中的 task 类型；不得建立彼此独立的状态机。
- 每个需求点或方案点都要建立同 ID 的 task。只有记录该点的决定 commit SHA 后才设为 `DONE`；拒绝、范围外和不可行的决定同样可以完成点任务。
- 接取时把 task 改为 `WIP`，并在 `STATUS.md` 记录所有相关的 `repo@branch@SHA`。
- 从对应 `TASKS.md` 章节读取范围和完成条件。额外本地上下文放入 gist，并在该章节显式引用。
- 实现 commit subject 以 feature 和 task 开头，例如 `PIRC-23/DEV-01: add feature templates`。
- 每个决定 commit 只处理一个点。Subject 格式为 `<feature-key>/<point-id>: <RESULT> <summary>`；`RESULT` 只能是 `CONFIRMED`、`REJECTED`、`OUT-OF-SCOPE`、`INFEASIBLE` 或 `REOPENED`。
- 一个 task 可以产生多个 commit。不得自动合并实现分支。
- 完成时更新 `STATUS.md` task 行，记录所有输出 `repo@branch@SHA`、设为 `DONE`，并写明下一 task 或动作。
- 中断时保持 `WIP` 并写准确下一步。阻塞时设为 `BLOCKED`，写明原因和解除条件。

仅当 task 状态或 feature 下一流转发生变化时，读取 [transitions.md](references/transitions.md)。

## Git 与托管平台边界

- 每个仓库独立处理。一个 feature 可以跨多个仓库。
- 每个受影响仓库使用一个 feature integration branch，最多形成一个最终实现 PR/MR。
- 分别记录三类 refs：
  - **工作 HEAD**：task 当前 checkout 的分支和 SHA；只有项目管理仓库可以在满足干净文件规则时使用 `DERIVED:HEAD`；
  - **integration 对手**：开发过程中 task branches 合并或 rebase 所依据的分支和字面 SHA；
  - **最终 PR/MR refs**：最终评审与合并使用的 source/target 分支和字面 SHA。
- 不得用一个通用“当前 SHA”代替三种含义。
- integration 或 PR/MR 分支前进时，比较完成前保留旧 SHA；比较后更新为新观察到的字面 SHA。不得使用 `LIVE:<branch>`、`latest` 或其他移动标记。
- 代码工作提交到实现分支，不自动合并。
- 项目管理变更单独提交。只有获得授权后才能合并和上传。
- 仅在创建分支、commit、同步、PR/MR、评审或配置 CI 等 Git 策略边界调用可用的 `git-collaboration` Skill；普通恢复时不加载其完整参考资料。

## 上下文边界

把逐点确认的需求视为已批准意图，把逐点确认的方案视为保留的实施计划，把 Git 视为实现状态，把 `STATUS.md` 视为 task/ref 索引，把 `TASKS.md` 视为本地 task 细节。它们不一致时报告冲突，不得改写已决定点来掩盖冲突。

不要预加载全仓库文档。根据当前 task、引用的 gist、实际 diff、符号、manifest 和仓库说明发现代码上下文。

## 结束一次运行

留下可续接状态，其中包括：

- 当前 task 和状态；
- 已观察的本地分支和 SHA；
- 已观察的 PR/MR source/target refs；
- 本轮产生的 commit；
- 准确下一步；
- 阻塞及其解除条件。

结束前为当前 task 重新运行 `task_context.py`。上下文检查失败表示状态不可续接。

## 验证本 Skill

修改上下文规则或 helper 后，运行[上下文回归测试](scripts/test_task_context.py)和确定性审计：

```text
python scripts/test_task_context.py
python <skill-quality-reviewer>/scripts/skill-audit.py <skill-root> --format json
```
