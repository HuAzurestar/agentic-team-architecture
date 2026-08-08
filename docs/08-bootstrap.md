# 08 启动引导（Bootstrap）

> 从零把本架构落到 Multica 的最小启动清单。以"产品开发运营"BG 为例；其它业务按 [01-org-structure.md](01-org-structure.md) §4 定制（论文 / 文职 / 硬件 / 游戏等）。

## 1. 确认 BG 构成（CEO 拍板）

- 向 **CEO** 确认：这个 BG 需要哪些**职能**、哪些**角色**、每个角色需要**强到什么程度**。
- 确定后，把**三级架构（BG / 中心 / 角色）**发 CEO；**CEO 同意后开始组织**。

## 2. 创建 Squad / Agent

- 创建 **BG Squad**：成员 = 角色 Agent（AS、HR、CPO、CTO、COO、CKO、Assistant AS）+ **CEO（自然人 / 用户）**；head = **AS**。
- 创建中心 Squad：PC（CPO）、TC（CTO / 技术总监）、OC（COO）。
- 各角色落地为 Agent，绑定 Skill / MCP / Hook；**各成员注明汇报人是 CEO**（Assistant AS 向 AS）。

## 3. 创建 Project（上下文容器）

- 创建 Project，绑定本仓库（github_repo）与本地工作目录（local_directory），写入「云↔本地同步与迭代规则」。

## 4. 建立红线手册

- 由 **CKO** 起草首版红线手册（[docs/07-redline-manual.md](07-redline-manual.md)），落地为 issue（挂在本项目下）。

## 5. 配置 Autopilot（触发事件由 CEO 确认创建，AS 跟进）

- **高频 autopilot**：Assistant AS 红线扫描 / 例行推动（10min ~ 1h）。
- **低频 autopilot**：定期推进 CKO 记录（工作流 / skill / 手册 / 快讯）并清理上下文。
- 触发事件（何时触发什么）由 **CEO 统一确认（创建）**；**AS 跟进**（后续执行推进）。

## 6. 首个任务

- CEO 下发 / 确认一个产品需求 → **AS 跟进** → 按核心流程推进（PC 设计 → TC 开发 → OC 上线 / 运营）。

> 完成以上即可"照文档跑起来"；后续迭代按 [docs/05-iteration.md](05-iteration.md) 收口。
