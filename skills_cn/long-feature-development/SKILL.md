---
name: long-feature-development
description: 从项目管理目录恢复并推进跨会话的软件 feature，使用精简 Markdown 状态和 Git refs 处理多仓库或 PR/MR。用于跨会话工作，不用于一次会话可完成的普通修改。
---

# 长程 Feature 开发

本 Skill 使用小型、版本化的 feature 记录续接开发，不依赖旧聊天。项目自行决定 `<Project-Manage>` 的实际路径；不得假定为 MPA 或其他固定仓库。

## 选择当前用途

helper 只取[用途提示](references/prompts.md)中的共同节与当前用途节。修改背景/provider 前先读[能力边界](references/capability-boundaries.md)；只读入口不提供写入引擎。

从 `requirement`、`solution`、`development`、`review`、`delivery` 中选一个，运行 `python <skill-root>/scripts/context.py --task-ref <feature-directory> --purpose <purpose>`，只取该用途与共同约束。需要背景时再读[上下文选段](references/context-selection.md)，用精确标题路径读取；[背景模板](templates/BACKGROUND.md)可选。选段完整不代替下述任务/Git恢复校验。按[独立安装](references/installation.md)安装固定版本、升级或回退，无需 SMMD/UI。

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

当 `<Project-Manage>` 位于 Git 仓库中时，以上六项都是共享项目管理记录。前三个文件是主要入口，后三项是按需聚焦的短追溯记录；不得用 `.gitignore`、`.git/info/exclude` 或等价规则隐藏。原始日志、大型产物和 secret 保存在目录外，只写入有界摘要和安全引用。

## 初始化

1. 解析 `<Project-Manage>`。尚无正式 ID 时，唯一情况下使用 `NO-FEAT`，可能冲突时使用 `NO-FEAT-<6位随机值>`。
2. 复制四个模板，并为每个初始 task 复制 `templates/TASK.md` 到 `tasks/<task-id>.md`。
3. 替换或删除尖括号占位符。每个 task 恰有一个索引行和一个详情文件；真实点 ID 替换前保留 `REQ-001`、`SOL-001`。
4. 初始化时创建 `gists/`；尚无 gist 时跟踪空的 `gists/.gitkeep`，确保 clone 后必需目录仍存在。gist 内容按需创建，必须有界且只用于追溯。
5. 若项目管理目录受 Git 管理，确认 `TASKS.md`、`tasks/`、`gists/` 未被忽略，并与其他 feature 记录一同纳入版本控制。
6. 按[首次记录初始化](references/bootstrap.md)检查初始记录和实际 refs，先作明确标注待校验的、范围限定的本地初始化 commit，再运行[恢复脚本](scripts/task_context.py)：`python <skill-root>/scripts/task_context.py <feature-directory>`。严格恢复通过前不得接取任务、决定确认点或推进 Gate；不得绕过正常脏工作树保护。
7. 需求和方案整体状态由逐点状态派生，不能用全局批准设置。

初始 task 的 ID、类型、依赖和 selector 由 Agent 负责；用户只提供业务意图和决定，不负责内部记账标签。

## Feature 身份

`NO-FEAT` 与 `NO-FEAT-<6位随机值>` 都是有效临时 key。正式 ID 的分配时点只由开发者决定。ID 变化时，在一次项目管理变更中重命名目录、更新标题和 `STATUS.md`，把旧 key 追加到 `Previous IDs`；不得改写历史。

## 开始或恢复

1. 解析准确的 `<Project-Manage>` 映射和 feature ID；存在歧义就停止。
2. 运行 `python <skill-root>/scripts/task_context.py <feature-directory>`。仅在人类明确选择非当前 task 时使用 `--task`。仓库移动或 path hint 不可用时，用可重复的 `--repo NAME=PATH` 显式覆盖。该命令是唯一恢复读取器，会校验 task 索引、拓扑、仓库身份、实际 Git refs 和必需追溯闭合，再输出聚焦上下文。
3. 从输出核对需求和方案逐点确认状态，再把它们当作固定边界。
4. 对每个仓库分别核对工作 branch/HEAD、开发期 integration branch/SHA、最终 PR/MR source/target refs。
5. 无法取得的远端状态标为未验证，不得猜测。
6. 比较记录与观察到的 refs；解决陈旧状态后才能改代码。

`task_context.py` 非零退出是硬停止。不得推断缺失的当前 task、索引行、详情、依赖、Git ref 或 gist。项目管理仓库的 working HEAD 使用 `DERIVED:HEAD`，仅当 STATUS 已跟踪、与 HEAD 一致且无本文件改动时才能派生；其余 ref 必须是实际观察到的字面 SHA。

恢复命令是 Skill 内部动作，不要求用户写进 prompt。它也会检查相关 staged、unstaged 和 untracked 变化；实现仓库有残留，或本 feature 项目管理目录有残留时，在新修改前进入恢复流程。此时读取 [references/checkpoints.md](references/checkpoints.md)。

已知工作目录迁移、任务分支改变或集成观察漂移时，先读[迁移与对账](references/reconciliation.md)，按只读 inspect、记录计划、已有授权范围内 apply 的顺序修复。该流程不绕过上述严格恢复检查，也不授权合并或产品接受。

检查点在提交与记账之间中断时，读取[操作恢复](references/operations.md)。保留已经成功的提交，先根据真实意图与副作用对账，再决定是否续做。

## 确认边界

- 每个决定点使用稳定的二级标题 `## REQ-*` 或 `## SOL-*`；“全部批准”不能改变任何点状态，点内三级标题仍属于该点。
- 仅在获得授权时，LLM 才能提出可能确认的点；随后必须复述每个准确 ID 和内容并进行二次人工确认。
- 已确认点在人类明确重开前锁定；保留正文和决定历史。
- 已拒绝点可修订后重开，无需单独撤回，但重新确认仍需明确人工决定。
- `CONFIRMED` / `BASELINED` 是派生状态：所有活动点均逐点确认，且无 `PROPOSED` / `REOPENED`。

新增、决定、修订或重开点时读取 [references/confirmation.md](references/confirmation.md)。

## 执行一个 Task

- 内部 task 由 Agent 创建和连接。正常新增使用 `scripts/task_create.py`，不得要求用户提供 task ID、依赖或 selector。只有真实业务歧义、授权边界或无法安全推导的范围才询问用户；规划时读取 [references/task-planning.md](references/task-planning.md)。
- Task 只使用 `PENDING`、`WIP`、`BLOCKED`、`RECORDING`、`DONE`。
- `STATUS.md` 是 feature 控制入口，保存 feature 状态、当前 task/gate 摘要和仓库/对象注册表；`TASKS.md` 是完整 task 状态与依赖的唯一来源。
- 需求、方案、开发、测试、评审、返工、验收和 gate 使用同一张 task 表，不建立分类型状态机。
- 每个需求/方案点都有同 ID task；只有逐点决定 commit SHA 已记录后才能 `DONE`。
- `PENDING` 表示未接取。依赖全 `DONE` 时派生 `READY`，否则派生 `WAITING`；两者不是持久状态。
- 接取时要求 `READY`，先在详情记录 owner、时间、start refs 和 HEAD，再用 `task_state.py ... --to WIP` 更新索引。
- 从详情读取范围和完成条件；gist 只保存有界追溯材料。每个 task 必须各有一行 `Requirement points` 和 `Solution points`。
- 实现 commit 标题加 `<feature>/<task>:` 前缀；决定 commit 使用 `<feature>/<point>: <RESULT> <summary>`。
- Task 可产生多个 commit；不得自动 merge 实现分支。
- 每个连贯工作单元后、长耗时或高风险操作前、交接前，主动创建有明确文件范围的本地 checkpoint。使用 `scripts/task_checkpoint.py`，不得自动 push，不得吸收无关或敏感文件；记录或恢复 checkpoint 时读取 [references/checkpoints.md](references/checkpoints.md)。
- 完成工作后从 `WIP` 进入 `RECORDING`，记录最终 commit 和每个仓库唯一 completion SHA，再进入 `DONE`。
- 中断时保留 `WIP` 并更新 resume action。`BLOCKED` 只用于已接取且被具体障碍停止的 task，必须写 blocker、impact、release condition；普通依赖等待仍是 `PENDING`。
- 正常跨文件流转依次执行：先准备 task 详情和有变化的 `STATUS.md` 当前 task/condition 字段；再运行 `task_state.py`；最后运行只读 `task_context.py` 并把项目管理文件一同提交。writer 的原子保证只覆盖 `TASKS.md` 行与 Mermaid，不覆盖其他文件；三步之间允许工作树暂时不一致，但不得提交。
- 正常状态修改只用 `task_state.py`。`DONE -> WIP` 时必须在详情持久化非空 `Reopen reason`，并用 `--reason` 传入完全相同的文本。`task_context.py --sync-topology` 仅用于明确修复/导入；只读恢复遇到陈旧图必须失败。

改变 task 状态或下一流转时读取 [references/transitions.md](references/transitions.md)。创建、接取、记录或完成质量 task 时读取 [references/task-contracts.md](references/task-contracts.md)。创建/执行 gate 或改变 feature phase/condition 时读取 [references/feature-gates.md](references/feature-gates.md)。验收 task 还需按 [references/acceptance.md](references/acceptance.md) 创建并主动展示普通用户可理解的短验收包；不得要求用户理解 `ACCEPT-*`、point ID、合同或内部命令。

处理决策适用性时，读取[决策证据](references/decision-evidence.md)，使用纯[校验器](scripts/decision_evidence.py)及其[测试](scripts/test_decision_evidence.py)。
使用 [Git 来源读取器](scripts/decision_source.py)读取本地当前材料，覆盖[真实 Git 测试](scripts/test_decision_source.py)。
使用[宿主回读入口](scripts/decision_host.py)及其[接口测试](scripts/test_decision_host.py)，将已认证回复读取、宿主权限和精确解释连接至校验器。
真实宿主传输、写入器与质量策略仍待集成；文件自述不能认证人类决定。

## Git 与平台边界

处理可编辑 RV 意见时，读取[格式与兼容规则](references/review-comments.md)，使用[编解码器](scripts/review_comments.py)与[回归测试](scripts/test_review_comments.py)。
进入审查或明确读取审查内容时，按已登记绑定调用前台[来源读取器](scripts/review_source.py)，见[真实 Git 回归](scripts/test_review_source.py)。
Git 读取不合并、不发布、不授权应用，也不改变点决定；原生平台和条件发布仍待完成。
应用前使用[前置校验](scripts/review_application.py)及其[真实 Git 测试](scripts/test_review_application.py)；通过仍需 F03 intent/writer 集成，不能绕过日志直接合并。
已授权的实现仓库同步使用 [F03 持久化写入器](scripts/review_sync.py)和[中断/冲突测试](scripts/test_review_sync.py)。先阅读评论规则中的边界；管理仓库自身同步及条件发布仍待完成。

- 每个仓库独立处理；一个 feature 可以跨仓库。
- 仓库定位顺序为：显式 `--repo NAME=PATH`、相对项目管理仓库根目录的 path hints、按注册 remote 身份进行 sibling/workspace 发现。不得把历史绝对路径当作定位器；缺失或歧义均停止。
- 对实际 Git 对象验证注册分支、working HEAD、integration opponent、PR/MR 端点、baseline 有序性、start-to-head 祖先关系、completion SHA 和依赖祖先关系；恢复输出包含派生追溯图，缺 commit 或必需路径断开都是错误。
- 当前 gate 依赖闭包之外的 pending task 必须在详情声明明确 disposition，不得静默遗弃。
- 每个受影响仓库使用一个 feature integration branch，至多一个最终实现 PR/MR。
- working HEAD、integration opponent、最终 PR/MR source/target 是三种不同 ref，必须分别记录。
- 分支前进时先比较旧 SHA，再更新为新观察到的字面 SHA；不得用 `latest` 或移动 token。
- 代码提交到实现分支，不自动 merge；项目管理变更单独提交，只有获得授权才 merge/upload。
- 仅在创建分支、commit、同步、PR/MR、评审或 CI 等 Git 策略边界调用可用的 `git-collaboration` Skill。

## 上下文边界

加载、完整校验（含审查引用检查）和聚焦输出共用一次 2 秒计算预算；耗尽返回 RESOURCE_LIMIT，不输出部分上下文或下一动作。仅具体 Git 子进程调用作为外部执行/I/O 排除，其前后的解析与核验仍计入。这是协作式计算上限，不是 Git 的 2 秒墙钟截止时间；重用已耗尽的资料对象不能重置预算。

已有声明材料的审查中断，按[检查点](references/checkpoints.md)的可选恢复分支处理。[审查引用 helper](scripts/review_resume.py)及[真实 Git/进程测试](scripts/test_review_resume.py)恢复绑定 attempt/target 的引用，不代做质量判断或授予接受权限。

新审查或复核交接时，读取[审查流程](references/review.md)，准备[审查包模板](templates/REVIEW-PACKET.md)，用 [review_packet.py](scripts/review_packet.py) 校验。材料完整不代表独立审查已执行：必须有真实宿主授权、可核验的新上下文与强制只读权限；本 helper 不派发 reviewer。修改此边界时运行[审查包回归](scripts/test_review_packet.py)。

完整报告按[报告语义](references/review-report.md)、[报告模板](templates/REVIEW-REPORT.md)及纯[报告计算器](scripts/review_report.py)处理。未知/未执行检查及历史 blocker 保持可见；schema/数量有效不等于来源已验证或质量批准。修改时运行[报告测试](scripts/test_review_report.py)和随包[模拟 fixtures](scripts/fixtures/review-report.json)。

仅对未启动 PENDING 任务按[审查流程](references/review.md)使用[依赖 helper](scripts/task_dependencies.py)。先预览，获授权写入前持久化意图，再逐文件替换；中断后使用 F03 对账。运行[规划测试](scripts/test_task_dependencies.py)和[真实文件 writer 测试](scripts/test_dependency_write.py)。依赖 READY 不等于质量批准。

报告交付、版本化返工/复测/复核、在途 attempt 保护和进程骤停恢复运行[真实 Git 返工链夹具](scripts/test_rework_chain.py)。其中模拟 reviewer 声明不构成真实独立审查或人工接受。

[本地原文 loader](scripts/context_loader.py)在完整校验前读取所有任务与声明 gist；`task_context.py` 分离真实 Git 校验和聚焦输出，比较 loader 不能代答本地仓库事实。修改该边界时运行 [loader/真实 Git 专项](scripts/test_context_loader.py)及旧 context 回归。结构化 envelope 使用 `lfd-context-v1`，默认 CLI 保持兼容。loader 分离本身不代替审查断点恢复。

恢复后选择下一动作时，阅读 [references/selection.md](references/selection.md)。[纯函数核心/CLI](scripts/task_next.py)通过[严格读取适配器](scripts/selection_context.py)恢复；运行[核心测试](scripts/test_task_next.py)及[真实 Git/CLI 测试](scripts/test_selection_context.py)验证。选择结果不授予执行权限，也不修改任务状态。

逐点确认的需求是批准意图，逐点确认的方案是保留实施计划，Git 是实现状态，`STATUS.md` 是 feature/仓库入口，`TASKS.md` 是 task/ref 索引，`tasks/` 与 `gists/` 是共享聚焦追溯。冲突时报告，不得改写已决定点掩盖冲突。

不要预载整个仓库文档；从当前 task、显式 gist、实际 diff、symbol、manifest 和仓库说明发现代码上下文。内置 Markdown 聚焦不依赖 PIRC-14；未来适配器不得扩大 selector、绕过校验或成为恢复前提。

## 结束一次运行

保留可恢复状态：当前 task/state、观察到的各仓 branch/SHA、PR/MR refs、本轮 commits、准确下一动作、blocker 与解除条件。结束前先 checkpoint 所有连贯且属于 Agent 的实现修改，再重新运行当前 task 的 `task_context.py`；失败表示状态不可恢复。Skill 只承诺恢复到最近一次成功 checkpoint，不虚假承诺任意断电瞬间零丢失。

## 验证本 Skill

修改初始化说明或模板后，运行真实 Git 的[初始化回归](scripts/test_bootstrap.py)。

修改 task 编排、恢复或 checkpoint 行为后，运行[上下文回归测试](scripts/test_task_context.py)、[task 创建测试](scripts/test_task_create.py)、[checkpoint 测试](scripts/test_task_checkpoint.py)和确定性审计：

```text
python scripts/test_task_context.py
python scripts/test_task_create.py
python scripts/test_task_checkpoint.py
python <skill-quality-reviewer>/scripts/skill-audit.py <skill-root> --format json
```
