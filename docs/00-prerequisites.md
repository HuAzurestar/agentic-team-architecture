# 00 基础概念与运行必备条件（v2）

> 运行 agentic team 之前，先约定一组基础概念。以 **Multica 的基本结构**为执行基准（本项目实际运行于 Multica）；其它平台可将本表作为**参考**。

## 1. 概念总览

| 概念 | 定位 | 说明 |
| --- | --- | --- |
| CEO | 一人运营者 | OPC 的最终拥有者与决策者；公司的"一人" |
| LLM | 大模型 | deepseek、GLM、grok、kimi、GPT、claude 等 |
| Agent Program | 智能体程序 | 基于 LLM 制作的、可对话的、具有特定流程使用方式的程序应用：claude code、opencode、codex、gemini CLI 等 |
| Agent | 智能体 | 依托 Agent Program 运行的可运行进程；可挂载 Skill、MCP、Hook |
| Squad | 小队 | 由 1 个 head + N 个 member 组成的团队单位 |
| Skill | 技术文档 | Agent 使用的技术文档；可挂载 MCP、hook、allowed |
| MCP | 协议 | Agent 使用的一种协议，用于接入外部能力 |
| Hook | 运行挂载 | Agent 运行的挂载点/钩子，控制执行时机与行为 |

## 2. 挂载关系

```
Agent（智能体）
 ├── 运行于 Agent Program（claude code / opencode / codex / gemini CLI …）
 ├── 挂载 Skill（技术文档，可再挂载 MCP / hook / allowed）
 ├── 挂载 MCP（协议，接入外部能力）
 └── 挂载 Hook（运行挂载，控制执行时机/行为）
```

- 一个 **Agent Program** 上可运行多个 **Agent**（不同角色/用途）。
- 一个 **Skill** 可被多个 Agent 复用，决定"这个 Agent 会做什么、怎么做"。
- **Squad** 是 Multica 的实现层单位：一个 head 领导 N 个 member，作为 issue 分派服务的 @ 工具。**架构层不定义小队**——架构层的 BG / 中心在 Multica 中以 Squad 落地（见 [docs/06-multica-landing.md](06-multica-landing.md)）。

## 3. 这套概念的作用

- 把"角色"（CPO/CTO/COO/HR/AS）和"实现载体"（Agent + Agent Program + LLM + Skill/MCP/Hook）分开：**架构定义角色，运行前提定义载体**。
- 每个角色落地为一个或多个 Agent；Agent 由具体的 Agent Program + LLM 驱动，通过 Skill/MCP/Hook 获得能力。
- "大小智能管理"（[docs/03-intelligence.md](03-intelligence.md)）靠这套概念落地：不同规格的 LLM 与 Skill 组合，承担不同复杂度的任务。

## 4. 术语表（锁定用法）

| 术语 | 锁定含义 | 不要写成 |
| --- | --- | --- |
| 职级 | **岗位层**：CEO/EVP/VP · Director/Manager · 职员（上下级语义） | 模型成本 |
| 级别 | **模型成本档**：Assist / 普通 / Senior（贵与便宜） | 岗位层 |
| Senior | **高级岗 / 高级档**：作专家角色名或高级成本档（按上下文） | "专家" / Specialist |
| S0/S1/S2 | **红线严重级**：重大事故 / 事故 / 风险（见 [docs/02-boundaries.md](02-boundaries.md) §5） | 任务优先级 |
