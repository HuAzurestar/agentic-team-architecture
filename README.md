# agentic-team-architecture

> 一个足够详细、可复用的 **OPC（One Person Company）架构**，支撑一人公司形态。
>
> **OPC 让一个自然人用一个 AI 团队运营一家公司**，架构可被多数 agent 系统按此快速起步。

本项目不生产具体的 skill 或 agent，而是沉淀一套**组织架构 + 协作流 + 迭代机制**，让一个自然人（或最小团队）能以 AI 团队的方式运营一家公司。大多数 agent 系统都可以把本仓库的架构作为起步蓝本，快速对齐角色、汇报线、协作方式与迭代节奏。

## 项目定位

- **形态**：一人公司（ONE PERSON COMPANY，OPC）。公司由自然人 + 一组 agent 组成，agent 承担各角色的职责。
- **基准单元**：BG 事业群（OPC，One Person Company）。先以一个 BG 为样板跑通整个组织与协作，再复制扩展。
- **可扩展**：从单一 BG 起步，预留 **BU 事业部**（跨产品线的矩阵单元）与**运营线 / 市场线**的占位，后续迭代补齐。
- **内容边界**：只定义"架构"（角色、汇报线、协作、迭代），不绑定具体 agent 实现或平台。

## 组织架构总览

以单一 BG 为例（OPC = BG）：

```
BG 事业群（OPC）
├── CEO（最高负责人/总指挥）
│
├── P&E 产品中心 —— PD 产品总监
│   ├── SPM 高级产品经理
│   ├── PM 产品经理
│   ├── APM 产品助理
│   └── 产品设计（Designer）
│
├── R&D 研究中心 —— CTO 技术总监
│   ├── 架构师（Architect，向 CTO，与 TL 平级）
│   └── TL 技术主管
│       ├── FE 前端工程师
│       ├── BE 后端工程师
│       ├── AE 算法工程师
│       ├── QAE 测试工程师
│       └── SRE 运维工程师
│
├── 运营中心（占位，v1 先不展开）——产品运营 / 媒体运营 / 会员运营 / 数据运营 / 活动策划 / 内容策划 / 编辑
│
└── 行政线 —— HRD 人力资源总监
    ├── HR
    └── AS 行政专员
```

汇报线：

- BG CEO → PD → SPM / PM / APM / 产品设计
- BG CEO → CTO → TL → FE / BE / AE / QAE / SRE；架构师向 CTO
- BG CEO → HRD → HR / AS
- 运营线、市场线：v1 占位，后续迭代补齐

## 文档结构

| 文档 | 内容 |
| --- | --- |
| [docs/01-org-structure.md](docs/01-org-structure.md) | 组织架构树与 BG / BU / R&D / P&E 说明 |
| [docs/02-roles.md](docs/02-roles.md) | 全角色规格：定位 / 汇报线 / 职责 / 关键产出 / 协作方 / 衡量指标 / 迭代方式 |
| [docs/03-collaboration-flows.md](docs/03-collaboration-flows.md) | 协作流：需求→设计→技术→测试→发布，及产品/技术/行政协同与升级机制 |
| [docs/04-iteration-plan.md](docs/04-iteration-plan.md) | 迭代机制：节奏、反馈闭环、架构版本演进 |

## 云端 ↔ 本地同步与迭代规则

**架构文档以云端 GitHub 仓库为主源（source of truth），本地工作目录作为它的工作副本；任何一次迭代都要同时落在两边。**

操作规则：

1. **动手前先同步**：修改前先 `git pull`，确保基于最新 commit，避免与云端分叉。
2. **本地完成修改**：在本地工作副本中编辑文档并提交（`git add` + `git commit`）。
3. **推送云端**：`git push` 到云端主源，让云端成为最新。
4. **同步回本地**：push 后再次 `git pull`（或确认已一致），保证云端与本地同为最新 commit。
5. **本地材料隔离**：本地工作副本中不属于主仓的材料（如 `Skill 下载与审查/`、`新建文件夹/`）由 `.gitignore` 排除，不纳入提交。
6. **冲突处理**：若 pull 出现冲突，以云端主源为准解决冲突后再提交，并记录解决方式。

> 每个 run（每个 agent 迭代）开始前都应执行第 1 步，结束后执行第 3、4 步，确保云↔本地始终同步。

## License

本项目以 [LICENSE](LICENSE) 声明的条款发布。
