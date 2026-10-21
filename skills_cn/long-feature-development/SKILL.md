---
name: long-feature-development
description: 通过 YAML 详情、Markdown 预览和稳定的 Project 仓库映射，跨会话或跨 agent 管理持久 Feature 的设计与任务。组织、编排、授权和管理根目录位置由外部提供。
---

# 长程 Feature 开发

使用 Feature 现有记录恢复和推进工作。本 skill 定义记录与默认单任务闭环，不负责 intent 识别、公司角色或公司编排。委托、授权、状态维护和环境由调用方提供；已有编排要求优先于默认闭环。

## Feature 与 Project

调用方解析 `<Project-Manage>`。Feature 是针对一组 Project 和需求的持久工作；Project 标识一个 Repository 的稳定本地/remote 映射与基本规则：

```text
<Project-Manage>/
├── feature/<feature-key>/
│   ├── STATUS.md
│   ├── DESIGN.md
│   ├── TASKS.md
│   ├── VERBAL.md
│   ├── design/<point-id>.md
│   ├── tasks/<task-id>.md
│   └── gists/<attachment>.*
└── project/<project-key>/
    └── project.yaml
```

管理目录不要求是 Git 仓库。实际位置、状态/授权入口和委托由外部提供；缺失或冲突时报告，不编造归属。
首次安装时，在宿主 instruction 或运行绑定中配置确切的 `<Project-Manage>` 位置及写入/提交策略，并明确 Project 映射、环境访问和交流/决定入口，参见[首次使用配置清单](references/initialization.md#首次使用配置)。这些配置由宿主提供；本 skill 不自行发现管理根目录、安装通知路由或授予权限。

## 记录与预览

- DESIGN 统一编号的 requirement、solution、intent。INT 保留外部原话，decided by 记录提出者，title 概括具体意图；RECORDED 不代表后续 REQ/SOL 获批。从中加工 REQ/SOL 属于详细设计；详情 YAML 是状态来源，DESIGN.md 固定展示通用列，专用字段压缩到 detail spec。
- TASKS 管理 development、review、docs、decision、feedback、test、gate 等所有任务。owner 可标识 Human、Agent 或 Platform；仓库、审核、结果等类型专用信息直接添加到 YAML，由 detail spec 自动摘要。
- VERBAL/gists 保存临时草稿、导出与日志。任务仅可在专用 gists 字段登记参考附件，不能作为输入、决定理由、证据或完成条件；删除后不能影响校验与续接。

STATUS.md 是 Feature 的综合状态管理入口，集中管理 repository、feature、dev 等整体状态、当前焦点、阻塞与下一步；不只是一份续接摘要。通过简要状态和链接关联详情，不重复其他模块。

## 初始化 Feature

新建 Feature 时执行[初始化清单](references/initialization.md)，由 agent 使用记录模板，而非内容编写脚本。清单明确最小产物、示例清理、初始状态与完成检查。

- 调用方：“在给定管理根目录初始化 Feature FEAT-42，保留 Lin 提出的无效输入应说明原因的请求。”准备 Feature 骨架和以 Lin 为提出者的 INT，不编造已批准的 REQ/SOL，不复制无关示例任务。
- 调用方：“为这个需求开始一个 Feature”，但未给 key。先保留请求上下文并向外部取得标识，再创建目录，不生成临时 key。

## Feature 标识

feature-key 只能由用户、平台或上游调用方提供，任何 agent（包括编排者）都不得自行分配、猜测或生成临时 key。未取得明确 key/目录映射时，只保留可用上下文并向外部取得标识，不创建 Feature 目录；模板 example-feature 不是可直接使用的 key。Feature key 与 agent 可分配的内部设计点/任务 ID 不同。

## 开始或恢复

按[续接流程](references/continuity.md)解析标识和委托，读取 STATUS 与当前详情，核对记录输入和实际仓库上下文，在相关作业前校验。续接已有记录，不用模板覆盖。

## 作业一个任务

有特定编排要求时先读取并遵守；没有时采用[默认单任务闭环](references/task-workflow.md)：明确范围/就绪条件 → 记录 WIP → 作业与验证 → RECORDING → 持久化并校验 → DONE 并返回结果。保留阻塞、中断和重开路径，不规定公司阶段或新增角色。两种路径都遵守公共状态/记录契约及下述维护步骤。

## 每次操作的固定维护步骤

命令中的 `<skill-root>` 是当前加载的 SKILL.md 所在绝对目录，不是工作仓库或 Feature 目录。`<feature-directory>` 对应 `<Project-Manage>/feature/<feature-key>`，`<project-directory>` 对应 `<Project-Manage>/project`。替换为实际绝对路径，并为含空格路径加引号；这样可从任意当前目录执行，不必切换仓库。

- 操作前：重新读取最新来源版本和写入归属；对已初始化 Feature 运行只读记录校验。纯查询/续接不写文件。首次初始化没有可校验记录时，先取得外部 key，由 agent 基于模板准备记录，再执行下述收尾。
- 内容操作：INT/REQ/SOL、任务正文、判断和状态由被委托的 agent 基于模板产出，通过指定状态接口维护；脚本不创作 SOL、不补需求、不猜 owner/决定，也不选择下一状态。模板复用不要求新增一个固定角色。
- 每次新增、修改、状态转换、反馈/决定记录或交接更新后，必须执行以下两个命令，再声称该次维护完成：

```text
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --write
python "<skill-root>/scripts/contract_check.py" "<feature-directory>" --format json
```

- 仅修改稳定 Project 配置时，对 project.yaml 运行记录校验；操作涉及仓库映射时，给 Feature 校验传 --project-root。同步/校验失败、脚本不可用或发现并发改动时，保留现场并报告，停止依赖该结果的修改/交接/放行动作，不能静默跳过；不阻止无关只读检查。只有派生索引过期且来源明确时，才通过生成器修复索引，不借机重写业务事实。

脚本执行是记录维护纪律，不是公司业务流水线。脚本只做派生同步、结构校验、定位等机械工作，不隐含 Git/远端同步或发布授权，也不替代外部维护者的写入协调。

普通澄清、主动交流、渠道及提问方法属于外部编排者；通用 skill 不绑定沟通工具。仅对[要求用户决定的 GATE](references/gates.md)，规定请求、实际答复和未决时不放行的协议。

## 按当前动作读取参考

只读当前动作所需的参考，不一次加载整个 references。创建/修改记录或遇到 schema 问题时读取记录规范；普通作业不预载全部 schema、报告类型或仓库文档。参考定义记录要求，不意味着必须经历某阶段，也不产生新授权。

| 做什么时 | 读取什么 |
| --- | --- |
| 初始化新 Feature | [初始化清单](references/initialization.md) |
| 执行一个任务，区分指定编排与默认闭环 | [任务作业流程](references/task-workflow.md) |
| 修改 YAML、预览、STATUS 或 Project 配置 | [记录规范](references/protocol.md) |
| 保存外部 intent，提炼和关联 INT/REQ/SOL | [详细设计](references/decisions.md) |
| 决定、部分接受、修订或重开设计点 | [逐点决定与版本](references/confirmation.md) |
| 新增/拆分任务或调整依赖 | [任务规划](references/task-planning.md) |
| 生成或更新 DESIGN/TASKS/VERBAL 索引与依赖图 | [生成区位置与局部更新](references/generated-indexes.md) |
| 接取、阻塞、完成或重开任务 | [任务状态机与记录](references/transitions.md) |
| 接收、委派工作，返回结果或回执 | [交接记录](references/handoffs.md) |
| 规划或报告测试、评审、返工 | [质量任务记录](references/task-contracts.md) |
| 准备/展示验收或记录答复 | [面向用户验收](references/acceptance.md) |
| 检查 GATE 或记录外部策略决定的 Feature 流转 | [GATE 检查与权限](references/gates.md) |
| 定位检出、对比代码点或准备集成/PR 交接 | [仓库上下文](references/repository-context.md) |
| 开始/续接/结束工作，处理反馈 | [续接](references/continuity.md) |
| 保存恢复上下文，检查中断残留或准备风险操作/交接 | [检查点与恢复](references/checkpoints.md) |

沿用模板中的空格键名与预览 marker。其他专用字段直接写入 YAML 并自动摘要，不需要增设表格列。保留原 intent、版本与历史决定。

适用 AGENTS.md 中的角色授权可允许 agent 在明确条件下确认 REQ/SOL，但必须记录理由，按[逐点决定规则](references/confirmation.md)执行。有效代理决定不固定追加人工二次确认；任务完成、实际结果与后续权限分别表达。组织负责归属、顺序、策略、状态写入及运行环境。

## Project 限定的引用

提交点为 `<project-key>@<head-sha>`，会移动的分支区域为 `<project-key>@<branch>`。支持全写 `<project-key>@<branch>@<head-sha>`，但规范化后的点身份仍是 project+SHA。不能拿分支区域替代提交点。优先完整、实际观察的 SHA；缩写须在对应 Repository 中核实唯一性。

Project YAML 在日常作业中保持稳定；当前 HEAD、工作/汇入分支、评审目标与 PR 两端属于任务，不写回 Project 定义。

## 机械维护命令

使用工具需要 Python 与 PyYAML。[记录校验器](scripts/contract_check.py)只读检查详情、预览/拓扑与本地引用；[索引生成器](scripts/feature_indexes.py)按固定章节生成并局部更新表格、依赖图和附件清单，不手工维护 marker 内内容。更新前读取[生成区规范](references/generated-indexes.md)，保留标题、介绍和 complementary 补充。[Project 定位器](scripts/project_refs.py)只返回仓库映射，不 fetch、不验证 commit。

```text
python "<skill-root>/scripts/contract_check.py" "<feature-directory>" --project-root "<project-directory>" --format json
python "<skill-root>/scripts/contract_check.py" "<feature-directory>" --render design
python "<skill-root>/scripts/contract_check.py" "<feature-directory>" --render tasks
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --check
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --write
python "<skill-root>/scripts/contract_check.py" "<project-directory>/<project-key>/project.yaml"
python "<skill-root>/scripts/project_refs.py" "<project-directory>" "project-key@0123456789abcdef0123456789abcdef01234567"
python "<skill-root>/scripts/project_refs.py" "<project-directory>" "project-key@main" --kind area
```

--write 只允许把已有事实同步到索引生成区，不是创建或改写 SOL/任务正文；默认 --check 只检查。--format json/text 只控制校验报告的机器可读/文本格式，不控制内容创作；--render 只打印派生内容。未核对注册目录仍报告 unverified，工具不认证授权、不判断业务合理性。修改脚本后运行[记录测试](scripts/test_contract_check.py)、[生成测试](scripts/test_feature_indexes.py)与[引用测试](scripts/test_project_refs.py)。
