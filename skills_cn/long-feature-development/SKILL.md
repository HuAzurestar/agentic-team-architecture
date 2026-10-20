---
name: long-feature-development
description: 通过 YAML 详情、Markdown 预览和稳定的 Project 仓库映射，跨会话或跨 agent 管理持久 Feature 的设计与任务。组织、编排、授权和管理根目录位置由外部提供。
---

# 长程 Feature 开发

使用 Feature 现有记录恢复和推进工作。本 skill 定义内容与引用含义，不负责 intent 识别、公司角色、流程编排、状态维护者、开发机或同步方式。

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

## 记录与预览

- DESIGN 统一编号的 requirement、solution、intent。INT 保留外部原话，decided by 记录提出者，title 概括具体意图；RECORDED 不代表后续 REQ/SOL 获批。从中加工 REQ/SOL 属于详细设计；详情 YAML 是状态来源，DESIGN.md 固定展示通用列，专用字段压缩到 detail spec。
- TASKS 管理 development、review、docs、decision、feedback、test、gate 等所有任务。owner 可标识 Human、Agent 或 Platform；仓库、审核、结果等类型专用信息直接添加到 YAML，由 detail spec 自动摘要。
- VERBAL/gists 保存临时草稿、导出与日志。任务仅可在专用 gists 字段登记参考附件，不能作为输入、决定理由、证据或完成条件；删除后不能影响校验与续接。

STATUS.md 是 Feature 的综合状态管理入口，集中管理 repository、feature、dev 等整体状态、当前焦点、阻塞与下一步；不只是一份续接摘要。通过简要状态和链接关联详情，不重复其他模块。

## 每次操作的固定维护步骤

feature-key 只能由用户、平台或上游调用方提供，任何 agent（包括编排者）都不得自行分配、猜测或生成临时 key。未取得明确 key/目录映射时，只保留可用上下文并向外部取得标识，不创建 Feature 目录；模板 example-feature 不是可直接使用的 key。Feature key 与 agent 可分配的内部设计点/任务 ID 不同。

- 操作前：重新读取最新来源版本和写入归属；对已初始化 Feature 运行只读记录校验。纯查询/续接不写文件。首次初始化没有可校验记录时，先取得外部 key，由 agent 基于模板准备记录，再执行下述收尾。
- 内容操作：INT/REQ/SOL、任务正文、判断和状态由被委托的 agent 基于模板产出，通过指定状态接口维护；脚本不创作 SOL、不补需求、不猜 owner/决定，也不选择下一状态。模板复用不要求新增一个固定角色。
- 每次新增、修改、状态转换、反馈/决定记录或交接更新后，必须执行以下两个命令，再声称该次维护完成：

```text
python scripts/feature_indexes.py path/to/feature --write
python scripts/contract_check.py path/to/feature --format json
```

- 仅修改稳定 Project 配置时，对 project.yaml 运行记录校验；操作涉及仓库映射时，给 Feature 校验传 --project-root。同步/校验失败、脚本不可用或发现并发改动时，保留现场并报告，停止依赖该结果的修改/交接/放行动作，不能静默跳过；不阻止无关只读检查。只有派生索引过期且来源明确时，才通过生成器修复索引，不借机重写业务事实。

脚本执行是记录维护纪律，不是公司业务流水线。脚本只做派生同步、结构校验、定位等机械工作，不隐含 Git/远端同步或发布授权，也不替代外部维护者的写入协调。

普通澄清、主动交流、渠道及提问方法属于外部编排者；通用 skill 不绑定沟通工具。仅对[要求用户决定的 GATE](references/gates.md)，规定请求、实际答复和未决时不放行的协议。

## 按当前动作读取参考

只读当前动作所需的参考，不一次加载整个 references。创建/修改记录或遇到 schema 问题时读取记录规范；普通作业不预载全部 schema、报告类型或仓库文档。参考定义记录要求，不意味着必须经历某阶段，也不产生新授权。

| 做什么时 | 读取什么 |
| --- | --- |
| 初始化记录，修改 YAML、预览、STATUS 或 Project 配置 | [记录规范](references/protocol.md) |
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

有效代理决定不固定追加人工二次确认；任务完成、实际结果与后续权限分别表达。组织负责归属、顺序、策略、状态写入及运行环境。

## Project 限定的引用

提交点为 `<project-key>@<head-sha>`，会移动的分支区域为 `<project-key>@<branch>`。支持全写 `<project-key>@<branch>@<head-sha>`，但规范化后的点身份仍是 project+SHA。不能拿分支区域替代提交点。优先完整、实际观察的 SHA；缩写须在对应 Repository 中核实唯一性。

Project YAML 在日常作业中保持稳定；当前 HEAD、工作/汇入分支、评审目标与 PR 两端属于任务，不写回 Project 定义。

## 机械维护命令

使用工具需要 Python 与 PyYAML。[记录校验器](scripts/contract_check.py)只读检查详情、预览/拓扑与本地引用；[索引生成器](scripts/feature_indexes.py)按固定章节生成并局部更新表格、依赖图和附件清单，不手工维护 marker 内内容。更新前读取[生成区规范](references/generated-indexes.md)，保留标题、介绍和 complementary 补充。[Project 定位器](scripts/project_refs.py)只返回仓库映射，不 fetch、不验证 commit。

```text
python scripts/contract_check.py path/to/feature --project-root path/to/project --format json
python scripts/contract_check.py path/to/feature --render design
python scripts/contract_check.py path/to/feature --render tasks
python scripts/feature_indexes.py path/to/feature --check
python scripts/feature_indexes.py path/to/feature --write
python scripts/contract_check.py path/to/project/project-key/project.yaml
python scripts/project_refs.py path/to/project project-key@0123456789abcdef0123456789abcdef01234567
python scripts/project_refs.py path/to/project project-key@main --kind area
```

--write 只允许把已有事实同步到索引生成区，不是创建或改写 SOL/任务正文；默认 --check 只检查。--format json/text 只控制校验报告的机器可读/文本格式，不控制内容创作；--render 只打印派生内容。未核对注册目录仍报告 unverified，工具不认证授权、不判断业务合理性。修改脚本后运行[记录测试](scripts/test_contract_check.py)、[生成测试](scripts/test_feature_indexes.py)与[引用测试](scripts/test_project_refs.py)。
