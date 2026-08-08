# agentic-team-architecture

> 一套足够详细、可复用的 **OPC（One Person Company）架构**，用于一人公司。
>
> **一位 CEO（自然人）+ 一个 AI 团队，运营一家公司（OPC）**；以 **Multica** 为执行基准，其它平台可参考本架构。可拓展到**多人多 OPC**——各 BG 有各自的 CEO。

本项目产出的是可复用的 **agentic team 组织架构**，覆盖五大能力：**架构划分、边界管理、大小智能管理、协作模式、可自我迭代**，不产出具体的 skill 或 agent。本仓库以 **Multica 的基本结构**为执行基准（本项目实际运行于 Multica），其它平台可将本架构作为**参考**，不能当作可迁移的直接模板。

## 项目定位

- **形态**：OPC（One Person Company，一人公司）= 一位 **CEO（自然人）** + 一个 AI 团队；可拓展到多人协作（多人多 OPC，各 BG 有各自的 CEO）。
- **基准单元**：BG（Business Group，事业群）。
- **运行前提**：一组基础概念（CEO / LLM / Agent Program / Agent / Squad / Skill / MCP / Hook），见 [docs/00-prerequisites.md](docs/00-prerequisites.md)。
- **内容边界**：只定义"架构"（组织、边界、智能分配、协作、迭代），不绑定除 Multica 之外的 agent 实现或平台。

## 架构的 5 大能力

| # | 能力 | 说明 | 文档 |
| --- | --- | --- | --- |
| 1 | 架构划分 | 组织与角色分层（OPC → BG → C..O） | [docs/01-org-structure.md](docs/01-org-structure.md) |
| 2 | 边界管理 | 权限红线、越权规则、决策权与升级 | [docs/02-boundaries.md](docs/02-boundaries.md) |
| 3 | 大小智能管理 | 任务复杂度 ↔ 模型成本档位匹配（Assist / 普通 / Senior） | [docs/03-intelligence.md](docs/03-intelligence.md) |
| 4 | 协作模式 | 产品/技术/运营/人事/行政之间的协作流 | [docs/04-collaboration.md](docs/04-collaboration.md) |
| 5 | 可自我迭代 | 架构自身持续演进 | [docs/05-iteration.md](docs/05-iteration.md) |

## 组织架构总览

```
BG（组织单元；BG 成员 = AS、HR、CPO、CTO、COO、CKO、Assistant AS；CEO 属 BG 不计入）
├── CPO — BG 成员；兼 PC 产品中心：产品的成色设计
├── CTO — BG 成员；兼 TC 技术中心：如何实现产品
├── COO — BG 成员；兼 OC 运营中心：产品的长期执行
├── CKO — BG 成员（直属）：管理 skills / 知识 / 文档 / issue 关闭
├── HR  — BG 成员（直属）：人事与架构调整（agent 归属、skill 配置），有管理权不可越权
└── AS  — BG 成员（直属）：CEO 代理人 / BG 名义 lead，推动工作；可蠢不可越权
```

- **BG 是组织单元**，成员 = **AS、HR、CPO、CTO、COO、CKO、Assistant AS**（CEO 属 BG 但不计入成员数）；**CEO 是自然人（属于 BG），是实际掌舵人与最终决策者；BG 名义 lead 是 AS（代行 CEO，CEO 可不在场）**。CPO/CTO/COO 同时是中心 **PC / TC / OC（产品/技术/运营中心）** 的所属。**"小队（squad）"是实现层概念（Multica 中为 issue 分派服务的 @ 工具），架构层只定义 BG / 中心。**
- **中心细分**：TC 技术中心（负责人 = 技术总监/技术主管）下设细分角色（技术规划 / 研发与前端、后端 Senior / 质量审查）；PC / OC 细分见 [docs/01-org-structure.md](docs/01-org-structure.md) §2.3 / §2.4（**运维与安全审批归运营中心**），算法建议单独成中心。
- **命名规则**：角色命名采用**三级版本**（最高 CEO/EVP/VP · 中间 Director/Manager · 职员；级别 Assist / 普通 / Senior = 模型成本档位），详见 [docs/01-org-structure.md](docs/01-org-structure.md)。
- **AS 下设 Assistant AS**：AS 的二级能力（Assist 档/便宜），**例行推动 + 红线 S0 扫描同频，10min ~ 1h 一次**（由触发器统一把控时间），遇阻塞 push 不动时上报 AS 并告知严重性（详见 [docs/02-boundaries.md](docs/02-boundaries.md)）。
- **术语锁定**：职级=岗位层，级别=模型成本档（Assist/普通/Senior），专家统一称 **Senior（高级）**，S0/S1/S2=红线严重级（详见 [docs/00-prerequisites.md](docs/00-prerequisites.md) §4）。
- BG 下若要加成员，除 **HR / AS / CKO** 外，就是其它 **C..O**。
- 扩展：多 BG 时以 BG 为模板复制，并可为每个 BG 命名（如 BG A、BG B）。

## 文档结构

| 文档 | 内容 |
| --- | --- |
| [docs/00-prerequisites.md](docs/00-prerequisites.md) | 基础概念与运行必备条件（CEO/LLM/Agent Program/Agent/Squad/Skill/MCP/Hook） |
| [docs/01-org-structure.md](docs/01-org-structure.md) | 架构划分：组织树（OPC → BG → C..O） |
| [docs/02-boundaries.md](docs/02-boundaries.md) | 边界管理：角色规格、权限红线、升级机制 |
| [docs/03-intelligence.md](docs/03-intelligence.md) | 大小智能管理：任务 ↔ 模型/Agent 规格匹配 |
| [docs/04-collaboration.md](docs/04-collaboration.md) | 协作模式：价值流与跨中心协同 |
| [docs/05-iteration.md](docs/05-iteration.md) | 可自我迭代：节奏、反馈循环、版本演进 |
| [docs/06-multica-landing.md](docs/06-multica-landing.md) | Multica 落地映射：Squad / Agent / Autopilot / Issue / Project 管理（其它 agentic system 留空） |
| [docs/07-redline-manual.md](docs/07-redline-manual.md) | 红线手册（v1）：S0/S1/S2 判定基准（CKO 维护） |
| [docs/08-bootstrap.md](docs/08-bootstrap.md) | 启动引导：从零把架构落到 Multica 的最小启动清单 |
| [docs/09-model-cost.md](docs/09-model-cost.md) | 模型与成本参考（HR 用）：档位默认、Go 套餐配额、deepseek 官方价格 |

## 云端 ↔ 本地同步与迭代规则

**架构文档以云端 GitHub 仓库为主源（source of truth），本地工作目录作为它的工作副本；任何一次迭代都要同时落在两边。**

1. **动手前先同步**：修改前先 `git pull`，确保基于最新 commit。
2. **本地完成修改**：在本地工作副本中编辑并提交（`git add` + `git commit`）。
3. **推送云端**：`git push` 到云端主源。
4. **同步回本地**：push 后再次 `git pull`（或确认已一致），保证云端与本地同为最新 commit。
5. **本地材料隔离**：`Skill 下载与审查/`、`新建文件夹/` 等本地材料由 `.gitignore` 排除，不纳入提交。
6. **冲突处理**：若 pull 出现冲突，以云端主源为准解决。

> 每个 run（每个 agent 迭代）开始前执行第 1 步，结束后执行第 3、4 步，确保云↔本地始终同步。

## License

本项目以 [LICENSE](LICENSE) 声明的条款发布。
