# 06 Multica 落地映射（v2）

> 本架构在 **Multica** 上的落地机制：角色 → Squad / Agent 如何实例化，**Autopilot / Issue / Project** 如何管理。其它 agentic system 的落地方式**留空待补**。

> 本架构以 Multica 为执行基准（本项目实际运行于 Multica）。本文件回答「角色如何实例化为 run」：触发方式、状态持久化、谁来唤醒谁。

## 1. 落地总览

| 架构概念 | Multica 载体 | 说明 |
| --- | --- | --- |
| BG（事业群） | **Squad** | BG 是一个 Squad，head = **AS**（BG 名义 lead，代行 CEO；CEO = 实际掌舵人） |
| 中心（PC / TC / OC） | **Squad** | PC / TC / OC 各自为 Squad，head = 对应 C..O（或 C..O 指定负责人，如 TC 技术总监/技术主管） |
| 角色（C..O / HR / AS / CKO / 细分角色） | **Agent** | 每个角色落地为一个或多个 Agent（可挂 Skill / MCP / Hook） |
| 例行/自动化推进 | **Autopilot** | 节奏性、可重复的触发（定时/手动/webhook）→ 派发给对应 Agent 或 Squad |
| 具体任务 | **Issue** | 每个待办/缺陷/需求以 Issue 承载 |
| 上下文容器 | **Project** | 将仓库/目录资源与任务分组，注入任务上下文 |

> **架构与实现分离**：架构层只定义 **BG / 中心**。"小队（squad）"是实现层概念——在 Multica 中为 issue 分派服务的 @ 工具，**按需创建**（只有分配到 squad 才有必要创建）；squad 的 lead 主要起 @ 的作用。

## 2. Squad 落地

- **BG → Squad**：创建 BG 对应 Squad；成员 = 角色 Agent（AS、HR、CPO、CTO、COO、CKO、**Assistant AS**）+ **CEO（自然人 / 用户）**；head = **AS**（BG 名义 lead，@ 目标）。**描述中注明哪位自然人是 CEO**；**各成员注明汇报人是 CEO**（Assistant AS 例外——向 AS 负责）。
- **角色描述 / 汇报对象**：除 Squad 外，每个角色还维护**角色描述**与**汇报对象**；由 **HR 统一管理**（人事变动包括角色描述，见 [docs/02-boundaries.md](02-boundaries.md) §1.4）。
- **BG 定制流程（模板 → 实例）**：角色为模板；创建前**向 CEO 询问**该 BG 需要的职能 / 角色 / 强度；确定后把**三级架构（BG / 中心 / 角色）**发 CEO，**CEO 同意后开始组织**（见 [docs/01-org-structure.md](01-org-structure.md) §4）。
- **PC / TC / OC → Squad**：各中心为 Squad；CPO / CTO / COO 兼其 head；TC 由技术总监/技术主管实际负责（向 CTO）。**中心成员（普通职员）是"按上下文工作"的可复制角色，角色内容不写负责对象**；其迭代由 HR 统一完成（通过**人事变动**）。
- **Squad 负责人路由**：派发给 Squad 的任务由 leader（head）接收并分派成员；Squad 成员接收各自职责内任务。
- **多 BG 下的 HR**：HR 为**跨 BG 共享**角色；涉及**共同资产统一分配管理**的人事变动，须**最高会议**（HR 主持、各 BG CEO 为成员）**一致通过**方可批准；**单人 OPC 不需要**。

## 3. Agent 落地

- **角色 → Agent**：每个角色实例化为一个 Agent，绑定该角色的 Skill（含质量审查三视角的 skill 配置拆分）、MCP、Hook。
- **运行形态（触发方式）**：
  - 由 Autopilot 按节奏触发（例行任务、迭代节奏）；
  - 由 Issue 触发（新任务/缺陷 → 分派到对应角色 Agent）；
  - 由 mention / 直接指派触发（跨角色协作、升级）。
- **状态持久化**：Agent 的上下文与产物落在 Issue 评论、工作区文件与仓库提交中；不依赖常驻内存。
- **谁来唤醒谁**：
  - AS（含 Assistant AS）负责推动与唤醒——Assist 档高频扫描阻塞并上报；
  - 升级链：相关 C..O 协商 → AS 推动 → CEO最终确认；
  - CEO 未决策 = 停摆，由 AS 记录并在定期汇报时统一通知（见 [docs/02-boundaries.md](02-boundaries.md) §3）。
- **跨 BG 共享**：**普通职员为跨 BG 共享角色**（agent 可复用）；**Assistant AS 是 BG 角色**（不属于跨 BG 共享）。跨 BG 协同调动人事时 HR 需注意协调。

## 4. Autopilot 管理

Autopilot 只是**触发器**（不是 Agent 本身）：trigger 触发 → 派发 → 由对应 **Agent 或 Squad** 执行。**保持简单**——不要给 Autopilot 堆复杂逻辑，扫描/审计/报告等各类工作**注意时间留痕**（何时触发、结果落点）。

**两种模式**：
- **创建 Issue**：触发时自动创建 Issue（可指定 Project），有上下文留痕，但**频繁创建会污染 Issue 流**。
- **静默运行**：触发时不创建 Issue，直接派发执行，留痕少但 Issue 污染小。

**规则**：
- Autopilot 本身有**任务描述**；创建 Issue 模式可指定 Project，静默运行模式因无 Issue 不能指定 Project。
- **不用于测试性触发**（trigger 是真实副作用）；创建、更新、查看、触发均通过 `multica autopilot` 命令。

**统一触发（服务于整个 BG）——分高低频**：
- **触发事件确认**：具体触发事件（何时触发什么）由 **CEO 统一确认（创建）**；**AS 跟进**（后续执行推进）。
- **高频 autopilot**：负责**计数触发**与**高频操作**——如 Assistant AS 的红线 S0/S1/S2 扫描、例行推动（10min ~ 1h 到点统一触发）。
- **低频 autopilot**：**定期开启**，推进 **CKO 记录**（沉淀工作流 / skill / 红线手册 / 新闻快讯），然后**清理上下文**（收尾归档）。
- **执行者 = Assistant AS**（成本最低，适合高频例行触发）。
- **每周开一个 issue**：由 Assistant AS 创建，**关闭由 CKO 执行**（见 §5）；触发时用该 issue **@ 相关角色**，实现**群体触发**。
- **运营的自动化另行设计**（与上面分开）。

## 5. Issue 管理

- **任务入口**：每个需求/缺陷/待办创建为 Issue，标题即任务定义，正文含背景/验收标准。
- **上下文**：Issue 用于规定任务的上下文；**Agent 拥有删除 Issue 与 Project 的权限，但强调不能这么做**（删除即丢失上下文留痕）。
- **父子 Issue**：子 Issue 与父 Issue **不共享上下文**；Project 共享上下文——所以 Issue 与 Project 的**描述字段用于收敛条件说明**，需注意管理。
- **分派**：Issue 分派到对应角色 Agent 或 Squad；子任务用子 Issue（stage/backlog 编排）。
- **状态流转**：todo → in_progress → in_review → done（blocked / cancelled 用于异常）。
- **状态推进**：状态由**当前 assignee** 推进（含 blocked / cancelled 的标记）。
- **关闭权限**：issue 的**关闭由 CKO 执行**，不在其他人（AS 负责推动与记录，不直接关闭）。
- **升级记录**：跨中心冲突/CEO 未决策的停摆，由 AS 在 Issue 评论中记录并汇报。

## 6. Project 管理

- **上下文容器**：Project 用于规定上下文，承载资源（github_repo / local_directory）与项目描述，注入每次任务上下文。
- **资源映射**：本仓库（agentic-team-architecture）为 Project 的 github_repo 资源；本地工作目录为 local_directory 资源。
- **项目规则**：Project 描述中写入「云↔本地同步与迭代规则」，保证每个 run 都遵守。
- **删除权限**：Agent 有删除 Project 的权限，但**不得删除**——Project 是上下文与收敛条件的载体。

## 7. 其它 agentic system（留空）

> 其它 agentic system 的落地方式暂不展开，留空待后续补充。
