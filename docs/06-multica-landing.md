# 06 Multica 落地映射（v2）

> 本架构在 **Multica** 上的落地机制：角色 → Squad / Agent 如何实例化，**Autopilot / Issue / Project** 如何管理。其它 agentic system 的落地方式**留空待补**。

> 本架构以 Multica 为执行基准（本项目实际运行于 Multica）。本文件回答「角色如何实例化为 run」：触发方式、状态持久化、谁来唤醒谁。

## 1. 落地总览

| 架构概念 | Multica 载体 | 说明 |
| --- | --- | --- |
| BG（事业群） | **Squad** | BG 是一个 Squad，head 由个人/CEO 指定（当前架构不设 CEO 角色，最终决策归自然人） |
| 二级小队（中心） | **Squad** | PC / TC / OC 各自为 Squad，head = 对应 C..O（或 C..O 指定负责人，如 TC 技术总监/技术主管） |
| 角色（C..O / HR / AS / 细分角色） | **Agent** | 每个角色落地为一个或多个 Agent（可挂 Skill / MCP / Hook） |
| 例行/自动化推进 | **Autopilot** | 节奏性、可重复的触发（定时/手动/webhook）→ 派发给对应 Agent 或 Squad |
| 具体任务 | **Issue** | 每个待办/缺陷/需求以 Issue 承载 |
| 上下文容器 | **Project** | 将仓库/目录资源与任务分组，注入任务上下文 |

## 2. Squad 落地

- **BG → Squad**：创建 BG 对应 Squad；成员 = 角色 Agent（AS、HR、CPO、CTO、COO）。
- **PC / TC / OC → Squad**：各中心为 Squad；CPO / CTO / COO 兼其 head；TC 由技术总监/技术主管实际负责（向 CTO）。
- **Squad 负责人路由**：派发给 Squad 的任务由 leader（head）接收并分派成员；Squad 成员接收各自职责内任务。

## 3. Agent 落地

- **角色 → Agent**：每个角色实例化为一个 Agent，绑定该角色的 Skill（含质量审查三视角的 skill 配置拆分）、MCP、Hook。
- **运行形态（触发方式）**：
  - 由 Autopilot 按节奏触发（例行任务、迭代节奏）；
  - 由 Issue 触发（新任务/缺陷 → 分派到对应角色 Agent）；
  - 由 mention / 直接指派触发（跨角色协作、升级）。
- **状态持久化**：Agent 的上下文与产物落在 Issue 评论、工作区文件与仓库提交中；不依赖常驻内存。
- **谁来唤醒谁**：
  - AS（含 Assistant AS）负责推动与唤醒——Assist 档高频扫描阻塞并上报；
  - 升级链：相关 C..O 协商 → AS 推动 → CEO（个人/自然人）最终确认；
  - CEO 未决策 = 停摆，由 AS 记录并在定期汇报时统一通知（见 [docs/02-boundaries.md](02-boundaries.md) §3）。

## 4. Autopilot 管理

Autopilot 只是**触发器**（不是 Agent 本身）：trigger 触发 → 派发 → 由对应 **Agent 或 Squad** 执行。**保持简单**——不要给 Autopilot 堆复杂逻辑，扫描/审计/报告等各类工作**注意时间留痕**（何时触发、结果落点）。

**两种模式**：
- **创建 Issue**：触发时自动创建 Issue（可指定 Project），有上下文留痕，但**频繁创建会污染 Issue 流**。
- **静默运行**：触发时不创建 Issue，直接派发执行，留痕少但 Issue 污染小。

**规则**：
- Autopilot 本身有**任务描述**；创建 Issue 模式可指定 Project，静默运行模式因无 Issue 不能指定 Project。
- **不用于测试性触发**（trigger 是真实副作用）；创建、更新、查看、触发均通过 `multica autopilot` 命令。
- 例：红线扫描（P0/P1/P2）由 Autopilot 按节奏触发 Assistant AS / 安全小队——10min~1h 到点统一触发，属"创建 Issue（留痕）"或"静默运行"视需要而定。

## 5. Issue 管理

- **任务入口**：每个需求/缺陷/待办创建为 Issue，标题即任务定义，正文含背景/验收标准。
- **上下文**：Issue 用于规定任务的上下文；**Agent 拥有删除 Issue 与 Project 的权限，但强调不能这么做**（删除即丢失上下文留痕）。
- **父子 Issue**：子 Issue 与父 Issue **不共享上下文**；Project 共享上下文——所以 Issue 与 Project 的**描述字段用于收敛条件说明**，需注意管理。
- **分派**：Issue 分派到对应角色 Agent 或 Squad；子任务用子 Issue（stage/backlog 编排）。
- **状态流转**：todo → in_progress → in_review → done（blocked / cancelled 用于异常）。
- **升级记录**：跨线冲突/CEO 未决策的停摆，由 AS 在 Issue 评论中记录并汇报。

## 6. Project 管理

- **上下文容器**：Project 用于规定上下文，承载资源（github_repo / local_directory）与项目描述，注入每次任务上下文。
- **资源映射**：本仓库（agentic-team-architecture）为 Project 的 github_repo 资源；本地工作目录为 local_directory 资源。
- **项目规则**：Project 描述中写入「云↔本地同步与迭代规则」，保证每个 run 都遵守。
- **删除权限**：Agent 有删除 Project 的权限，但**不得删除**——Project 是上下文与收敛条件的载体。

## 7. 其它 agentic system（留空）

> 其它 agentic system 的落地方式暂不展开，留空待后续补充。
