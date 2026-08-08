# 01 架构划分（v2）

> 组织与角色的分层。本文档定义 OPC 的顶层结构：**OPC → BG（Squad）→ C..O**，并给出 BG 的完整组织与结构。

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

## 2. BG 组织架构

BG 采用**扁平成员制，不设 CEO**，BG 成员为 **AS、HR、CPO、CTO、COO**；其中 CPO/CTO/COO 同时是二级小队（PC 产品中心 / TC 技术中心 / OC 运营中心）的所属。最终决策权归于自然人（个人）；AS 作为个人的代行者推动工作。

```
BG（Squad，不设 CEO；BG 成员 5 = AS、HR、CPO、CTO、COO）
├── CPO — BG 成员；兼 PC 产品中心（二级小队）所属：负责产品的成色设计
├── CTO — BG 成员；兼 TC 技术中心（二级小队）所属：负责如何实现产品
├── COO — BG 成员；兼 OC 运营中心（二级小队）所属：负责产品的长期执行
├── HR  — BG 成员：人事与架构调整（agent 归属、skill 配置），有管理权不可越权
└── AS  — BG 成员：个人代行，推动工作、调动组织行动（杂务），可蠢不可越权
```

### 2.1 各成员定位速览

| 角色 | 定位 / 二级所属 | 核心职责 |
| --- | --- | --- |
| CPO | BG 成员；PC 产品中心（二级小队） | 产品的**成色设计**（需求、体验、质量） |
| CTO | BG 成员；TC 技术中心（二级小队） | **如何实现**产品（架构、研发、交付） |
| COO | BG 成员；OC 运营中心（二级小队） | 产品的**长期执行**（运营、增长、执行闭环） |
| HR | BG 成员（直属） | 架构调整与人员变动：agent 归属、skill 等配置；管理权但不越权 |
| AS | BG 成员（直属） | 代行个人/CEO 职权，推动工作；杂务；可蠢不可越权 |

> 各角色完整规格（权限、产出、红线）见 [docs/02-boundaries.md](02-boundaries.md)。

### 2.2 TC 技术中心（CTO 下属）细分角色

CTO 下属为各层执行单位，并区分**专家角色**与**普通角色**。技术研发覆盖：技术规划、研发（前后端等）、测试、运维、安全审批。

```
TC 技术中心（head = CTO）
├── 技术规划　Architect 架构师（专家）—— 为技术实现划分界限
├── 研发执行　FSE 全栈 / FE 前端 / BE 后端（普通执行）
├── 质量安全　Code Reviewer / Plan Reviewer / Testing Engineer（专家审查）
│              （界面要求高时补：UI Reviewer / UX Reviewer）
├── 运维　　　Operation Engineer（普通执行）
└── 安全审批　安全员（专家，主要负责审批）
```

- **专家 vs 普通角色**：Architect、各类 Reviewer、安全员为**专家角色**（规划 / 审查 / 审批）；FSE / FE / BE、Operation Engineer 为**普通执行角色**（按方案实现）。
- **研发分工**：FSE 全栈前后端都能做，但复杂任务易出错；FE 专职前端 / UI / 页面展示；BE 专职后端 / 数据处理 / API。三者权责不同。
- **质量审查三视角**：Code Reviewer 看代码写得好不好；Plan Reviewer 看计划写得好不好；Testing Engineer 找极端情况、看响应好不好。
- **算法（AE）**：算法问题更难，与前后端协作过多容易造成**上下文危险**——原则上**单独设一个中心**（如 AC 算法中心），不与前后端混编。v2 先记录此原则，具体结构后续定义。
- **PC / OC 细分**：产品、运营当前由 CPO / COO **全权负责**，细分角色待讨论。

## 3. 汇报线与决策

- **不设 CEO**：BG 无 CEO 角色；重大决策直接归于个人（自然人）。
- **AS 代行**：AS 代为行使 CEO/个人职权，主要职责是**推动工作进行**。
- **HR 管理**：HR 管理组织/人事层面的变动（agent 归属、skill 配置），具有管理权，但不能越权到业务决策。
- **C..O 各管一摊**：CPO / CTO / COO 分别在 PC / TC / OC（产品/技术/运营中心）内决策，跨中心冲突走升级机制（见 [docs/02-boundaries.md](02-boundaries.md)）。

## 4. 扩展与复制

- **多 BG**：以 BG 为模板复制；每个 BG 命名（如 BG A、BG B），成员结构相同。
- **BG 内加角色**：除 HR / AS 外，新增成员一律是 C..O 形态（如 CFO、CMO），各对应一个二级小队/中心（如 FC 财务中心）。
- **BU（事业部）**：跨 BG/产品线的矩阵单元，v2 仍为占位概念，后续版本定义。

## 5. 命名规则与职级体系

架构的角色命名遵循**外企职级规则**，用于给角色定位档位、控制头衔使用。共分三个职级大层，每个大层下可再细分等级。

### 5.1 职级大层

| 层级 | 职级 | 说明 | 专用名词 |
| --- | --- | --- | --- |
| 最高一级 | 总裁 / 执行总裁 / 副总裁（CEO / EVP / VP） | 公司 / 部门最高管理 | Chief / Officer / President（属管理人员，有上下，不拆架构） |
| 中间一级 | 总监 / 经理（Director / Manager） | 部门 / 团队管理 | Head / Director / Lead / Manager（首席 / 总监 / 主管 / 经理） |
| 最低一级 | 职员 | 执行岗 | 不使用专用词即可 |

### 5.2 职级细分（自高到低）

1. **CEO**（Chief Executive Officer，首席执行官 / 总裁）—— 公司最高行政负责人与管理人，仅一人。
2. **EVP**（Executive Vice President，执行副总裁）—— 各大部门最高管理人，如 CFO（首席财务）、COO（首席运营官）、CHO（首席人事官）等。
3. **VP**（Vice President，副总裁）—— 设于各部门 EVP 之下，分两级：
   - **SVP**（Senior Vice President，高级副总裁）
   - **VP**（副总裁）
4. **Director**（总监）—— 分两级：
   - **Senior Director**（高级总监）
   - **Director**（总监）
5. **Manager**（经理）—— 分两级：
   - **Senior Manager**（高级经理）
   - **Manager**（经理）
6. **普通员工**—— 分两级（以财务部为例）：
   - **Senior Accountant**（高级会计师）
   - **Accountant**（会计师）

### 5.3 级别三级（= 模型成本档位）

每个职级可按 **Assist（助理）/ 普通（标准）/ Senior（高级）** 三级划分，且与"大小智能管理"的模型成本档位结合（见 [docs/03-intelligence.md](03-intelligence.md)）：

| 级别 | 模型定位 | 成本特征 |
| --- | --- | --- |
| Assist（助理） | 最便宜的模型 | 以 free 为目的 |
| 普通（标准） | 初级生产模型 | 有一定价格，频繁使用可以承受 |
| Senior（高级） | 高级生产模型 | 价格极高，频繁使用无法承受 |

### 5.4 在本架构中的应用

- **BG 成员（CPO / CTO / COO / HR / AS）**：位于**最高一级（EVP）**。CPO / CTO / COO 分别对应 PC / TC / OC 中心的 EVP；HR 对应 CHO（首席人事官）定位；AS 为个人 / CEO 的代行（类似 Chief of Staff 定位）。
- **TC 技术中心细分角色**：位于**最低一级（职员）**。Architect、FSE、FE、BE、Code Reviewer、Plan Reviewer、Testing Engineer、Operation Engineer、安全员 均为执行 / 专家岗，不使用专用头衔词；可按 Senior / - / Assist 三级细分（如 Senior BE、Assist FE）。
- **新增角色**：按职责所在层级选用头衔——最高级用 C..O / EVP 系列；管理层用 VP / Director / Manager 系列；执行层用普通岗名。
