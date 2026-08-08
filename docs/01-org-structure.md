# 01 架构划分（v2）

> 组织与角色的分层。本文档定义 OPC 的顶层结构：**OPC → BG（Squad）→ C..O**，并给出当前实例 **BG Nexus One**。

## 1. 分层模型

```
OPC（One Person Company）= 一个自然人 + 一个 AI 团队运营一家公司
└── BG（Business Group，事业群）= OPC 的一个 Squad
    ├── 成员 1..N：各 C..O / HR / AS
```

- **OPC**：顶层形态，唯一不变。
- **BG**：业务组织单元，是一个 **Squad**（1 head + N members）。一个 OPC 可含多个 BG，各自命名。
- **C..O**：BG 的功能负责人。当前定义 3 个：CPO（产品）、CTO（技术）、COO（运营）；BG 下若要加成员，除 HR/AS 外就是其它 C..O。

## 2. 当前实例：BG Nexus One

BG Nexus One 采用**扁平成员制，不设 CEO**。最终决策权归于自然人（个人）；AS 作为个人的代行者推动工作。

```
BG Nexus One（Squad，无 CEO，成员 5）
├── CPO Nexus — 产品线：负责产品的成色设计
├── CTO Nexus — 技术线：负责如何实现产品
├── COO Nexus — 运营线：负责产品的长期执行
├── HR Nexus  — 人事与架构调整：管理 agent 所属、skill 配置；有管理权，不可越权
└── AS Nexus  — 个人代行：推动工作、调动组织行动（杂务）；可以蠢，不能越权
```

### 2.1 各成员定位速览

| 角色 | 负责线 | 核心职责 |
| --- | --- | --- |
| CPO Nexus | 产品线 | 产品的**成色设计**（需求、体验、质量） |
| CTO Nexus | 技术线 | **如何实现**产品（架构、研发、交付） |
| COO Nexus | 运营线 | 产品的**长期执行**（运营、增长、执行闭环） |
| HR Nexus | 人事/架构 | 架构调整与人员变动：agent 归属、skill 等配置；管理权但不越权 |
| AS Nexus | 组织行动 | 代行个人/CEO 职权，推动工作；杂务；可蠢不可越权 |

> 各角色完整规格（权限、产出、红线）见 [docs/02-boundaries.md](02-boundaries.md)。

## 3. 汇报线与决策

- **不设 CEO**：BG Nexus One 无 CEO 角色；重大决策直接归于个人（自然人）。
- **AS 代行**：AS 代为行使 CEO/个人职权，主要职责是**推动工作进行**。
- **HR 管理**：HR 管理组织/人事层面的变动（agent 归属、skill 配置），具有管理权，但不能越权到业务决策。
- **C..O 各管一摊**：CPO / CTO / COO 分别在产品、技术、运营线内决策，跨线冲突走升级机制（见 [docs/02-boundaries.md](02-boundaries.md)）。

## 4. 扩展与复制

- **多 BG**：以 BG Nexus One 为模板复制；每个 BG 命名（如 BG Nexus Two），成员结构相同。
- **BG 内加角色**：除 HR / AS 外，新增成员一律是 C..O 形态（如 CFO、CMO），各管一条职能线。
- **BU（事业部）**：跨 BG/产品线的矩阵单元，v2 仍为占位概念，后续版本定义。
