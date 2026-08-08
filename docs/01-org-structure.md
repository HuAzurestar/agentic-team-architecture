# 01 架构划分（v2）

> 组织与角色的分层。本文档定义 OPC 的顶层结构：**OPC → BG（Squad）→ C..O**，并给出当前实例 **BG Nexus One**。

## 1. 分层模型

```
OPC（One Person Company）= 一个自然人 + 一个 AI 团队运营一家公司
└── BG（Business Group，事业群）= OPC 的一个 Squad
    ├── BG 成员：AS、HR、CPO、CTO、COO
    └── 二级小队（中心）：PC / TC / OC —— 分别由 CPO / CTO / COO 所属
```

- **OPC**：顶层形态，唯一不变。
- **BG**：业务组织单元，是一个 **Squad**，成员为 **AS、HR、CPO、CTO、COO**。一个 OPC 可含多个 BG，各自命名。
- **二级小队（中心）**：CPO、CTO、COO 同时作为二级小队的**所属（head）**，对应 **PC 产品中心 / TC 技术中心 / OC 运营中心**；中心是 BG 之下的第二层组织。
- **C..O**：BG 的功能负责人。当前定义 3 个：CPO（产品）、CTO（技术）、COO（运营）；BG 下若要加成员，除 HR/AS 外就是其它 C..O。

## 2. 当前实例：BG Nexus One

BG Nexus One 采用**扁平成员制，不设 CEO**，BG 成员为 **AS、HR、CPO、CTO、COO**；其中 CPO/CTO/COO 同时是二级小队（PC 产品中心 / TC 技术中心 / OC 运营中心）的所属。最终决策权归于自然人（个人）；AS 作为个人的代行者推动工作。

```
BG Nexus One（Squad，不设 CEO；BG 成员 5 = AS、HR、CPO、CTO、COO）
├── CPO Nexus — BG 成员；兼 PC 产品中心（二级小队）所属：负责产品的成色设计
├── CTO Nexus — BG 成员；兼 TC 技术中心（二级小队）所属：负责如何实现产品
├── COO Nexus — BG 成员；兼 OC 运营中心（二级小队）所属：负责产品的长期执行
├── HR Nexus  — BG 成员：人事与架构调整（agent 归属、skill 配置），有管理权不可越权
└── AS Nexus  — BG 成员：个人代行，推动工作、调动组织行动（杂务），可蠢不可越权
```

### 2.1 各成员定位速览

| 角色 | 定位 / 二级所属 | 核心职责 |
| --- | --- | --- |
| CPO Nexus | BG 成员；PC 产品中心（二级小队） | 产品的**成色设计**（需求、体验、质量） |
| CTO Nexus | BG 成员；TC 技术中心（二级小队） | **如何实现**产品（架构、研发、交付） |
| COO Nexus | BG 成员；OC 运营中心（二级小队） | 产品的**长期执行**（运营、增长、执行闭环） |
| HR Nexus | BG 成员（直属） | 架构调整与人员变动：agent 归属、skill 等配置；管理权但不越权 |
| AS Nexus | BG 成员（直属） | 代行个人/CEO 职权，推动工作；杂务；可蠢不可越权 |

> 各角色完整规格（权限、产出、红线）见 [docs/02-boundaries.md](02-boundaries.md)。

## 3. 汇报线与决策

- **不设 CEO**：BG Nexus One 无 CEO 角色；重大决策直接归于个人（自然人）。
- **AS 代行**：AS 代为行使 CEO/个人职权，主要职责是**推动工作进行**。
- **HR 管理**：HR 管理组织/人事层面的变动（agent 归属、skill 配置），具有管理权，但不能越权到业务决策。
- **C..O 各管一摊**：CPO / CTO / COO 分别在 PC / TC / OC（产品/技术/运营中心）内决策，跨中心冲突走升级机制（见 [docs/02-boundaries.md](02-boundaries.md)）。

## 4. 扩展与复制

- **多 BG**：以 BG Nexus One 为模板复制；每个 BG 命名（如 BG Nexus Two），成员结构相同。
- **BG 内加角色**：除 HR / AS 外，新增成员一律是 C..O 形态（如 CFO、CMO），各对应一个二级小队/中心（如 FC 财务中心）。
- **BU（事业部）**：跨 BG/产品线的矩阵单元，v2 仍为占位概念，后续版本定义。
