# 09 模型与成本参考（HR 用）

> HR 管理 Agent / 模型参数配置与成本评估的参考基准。**原则：优先使用 opencode Go 套餐（廉价/免费）；deepseek 官方 API 成本高，谨慎使用。** 由 HR 跟进维护。**实际发生的数据（任务时长 / 成本 / 预估准确度）记在 [docs/10-cost-ledger.md](10-cost-ledger.md)（成本与绩效台账）。**

## 1. 档位默认（核心产品研发BG v1）

| 角色 | 运行环境 | 模型 | 档位 |
| --- | --- | --- | --- |
| BG 成员（AS / HR / CPO / CTO / COO / CKO） | claude code | deepseek-v4-flash | 普通 |
| Assistant AS | opencode | deepseek-v4-flash-free | Assist（thinking=max，免费） |
| 职员（PC/TC/OC 细分角色，默认） | opencode | deepseek-v4-flash（Go 套餐） | 普通 |
| 质量审查 Assist | opencode | deepseek-v4-flash（Go 套餐） | Assist |
| 质量审查 普通（兼职上线审核） | opencode | mimo-v2.5（Go 套餐） | 普通 |
| 质量审查 Senior | opencode | glm-5.2（Go 套餐） | Senior |
| 高级UI审核（仅前端） | opencode | kimi-k3（Go 套餐，非常贵） | Senior |

> 若需升档，deepseek 官方提供 deepseek-v4-pro（单价高）；Senior Reviewer 替代：minimax-m3 / deepseek-v4-pro / qwen3.7-plus。

## 2. opencode Go 套餐模型与配额（HR 参考）

| Model | 每 5 小时请求数 | 每周请求数 | 每月请求数 |
| :--- | :--- | :--- | :--- |
| Grok 4.5 | 120 | 300 | 600 |
| GPT 5.6 Luna | 2,050 | 5,100 | 10,250 |
| GLM-5.2 | 880 | 2,150 | 4,300 |
| GLM-5.1 | 880 | 2,150 | 4,300 |
| Kimi K3 | 110 | 250 | 490 |
| Kimi K2.7 Code | 1,350 | 3,380 | 6,750 |
| Kimi K2.6 | 1,150 | 2,880 | 5,750 |
| MiMo-V2.5 | 30,100 | 75,200 | 150,400 |
| MiMo-V2.5-Pro | 3,250 | 8,150 | 16,300 |
| MiniMax M3 | 3,200 | 8,000 | 16,000 |
| MiniMax M2.7 | 3,400 | 8,500 | 17,000 |
| Qwen3.8 Max | 160 | 400 | 810 |
| Qwen3.7 Max | 340 | 840 | 1,690 |
| Qwen3.7 Plus | 4,300 | 10,800 | 21,600 |
| Qwen3.6 Plus | 3,300 | 8,200 | 16,300 |
| DeepSeek V4 Pro | 3,450 | 8,550 | 17,150 |
| DeepSeek V4 Flash | 31,650 | 79,050 | 158,150 |
| Hy3 | 4,300 | 10,750 | 21,500 |

- **主力普通测试**：deepseek-v4-flash（Go）与 mimo-v2.5，用量大、配额充足。
- **K3 非常贵**（配额小），**只给前端高级UI审核使用**，其他人不得用。
- kimi-k2.7 可能支持多模态，可作低级 senior reviewer 备选。

## 3. claude code（deepseek 官方）模型与价格

claude code 只挂 deepseek 两个模型（BASE URL = https://api.deepseek.com/anthropic）：

| 项 | deepseek-v4-flash | deepseek-v4-pro |
| --- | --- | --- |
| 模型版本 | DeepSeek-V4-Flash-0731 | DeepSeek-V4-Pro |
| 上下文长度 | 1M | 1M |
| 输出长度 | 最大 384K | 最大 384K |
| 百万 tokens 输入（缓存命中） | 0.02 元 | 0.025 元 |
| 百万 tokens 输入（缓存未命中） | 1 元 | 3 元 |
| 百万 tokens 输出 | 2 元 | 6 元 |
| 并发限制 | 2500 | 500 |

> **注意**：deepseek 官方成本较高，当前使用消耗略大。BG 成员因角色需要（claude code 决策质量）保留，其余优先 Go 套餐。HR 评估成本时留意用量与配额。

## 4. 管理规则

- 人事变动（运行时 / Agent / Skill / 参数配置 / 角色描述 的增删与变更）须 **CEO 批准**（docs/02 §1.4）。
- 各 C..O 跟进本中心表现（通过率 / 满意率），结果反馈 HR 调模型配置（docs/02 §1.0）。

## 5. 模型实测评估（下一阶段，HR 牵头）

> 目标：验证质量审查各档模型的质量 / 成本差异，更新档位建议（NEX-13 遗留 #8）。方案先行定下，实测执行依托**首个真实产品任务**（俄罗斯方块，NEX-12）的 PC→TC→OC 流程。

### 5.1 实测对象

| 档位 | 当前模型 | 备选模型 |
| --- | --- | --- |
| 质量审查 Assist | deepseek-v4-flash（Go 套餐） | —— |
| 质量审查 普通 | mimo-v2.5（Go 套餐） | —— |
| 质量审查 Senior | glm-5.2（Go 套餐） | minimax-m3 / deepseek-v4-pro / qwen3.7-plus |

### 5.2 实测方法

- **语料**：首个真实产品任务的交付物——PRD / 技术方案 / 实现代码 / 自测脚本（tetris/self-test.js）。
- **做法**：同一交付物分别交给各档审查 Agent 审查（由 CTO 在 TC 流程内调度，不额外派发）；同一份审查记录三档结论、成本与耗时。
- **指标**（对照 docs/02 §1.7 质量审查衡量指标）：
  - 质量：审查问题发现率、一次通过率、缺陷逃逸率、极端情况覆盖率；
  - 成本：单次审查消耗的 Go 配额（每 5 小时 / 周 / 月请求数）；
  - 效率：单次审查耗时。
- **归口**：HR 定方案 + 记录成本台账；各 C..O 反馈通过率 / 满意率（docs/02 §1.0）；实测由真实任务流程承载，不在任务外另跑。

### 5.3 结论落点

- 实测后按结果调整 §1 档位默认（含 Senior 备选是否启用），并同步 docs/05 变更记录。
- 尚未实测前档位维持现状；**K3 只给高级UI审核用**（配额小、非常贵），其余人不得用。

## 6. open-code-review 配置状态（NEX-13 遗留 #1）

- **现状**：skill（alibaba/open-code-review）已安装；**LLM 配置规格已定、token 已由 CEO 提供（2026-08-09）**。
- **配置规格**（`OCR_LLM_*` 环境变量，需设置在挂载该 skill 的 Agent 上：code-reviewer / CTO / 研发 / 架构师 / 质量审查·普通 / 质量审查·高级）：
  - **OCR_LLM_URL** = `https://opencode.ai/zen/go/v1`（opencode.ai Go 套餐，OpenAI 兼容，**已验证可访问**）；
  - **OCR_LLM_MODEL** = `deepseek-v4-flash`（端点实测只提供 `deepseek-v4-flash` 与 `deepseek-v4-pro`，**无 flash-free**；按 CEO 指示暂只配 flash，其它模型不配置）；
  - **OCR_LLM_TOKEN** = CEO 提供的 opencode.ai Go 套餐 token（**密钥不落文档**）。
- **待办（权限在 CEO / admin，HR 无 agent env 权限）**：
  - ① 用 `multica agent env set <agent-id> --custom-env-file <json>` 将上述三个变量应用到 6 个挂载该 skill 的 Agent（JSON：`{"OCR_LLM_URL":"https://opencode.ai/zen/go/v1","OCR_LLM_MODEL":"deepseek-v4-flash","OCR_LLM_TOKEN":"<token>"}`）；
  - ② 运行端安装 `ocr` CLI（alibaba/open-code-review v1.8.10 发布包，Windows 用 `opencodereview-windows-amd64.exe`，改名为 `ocr` 入 PATH）。
- **当前替代**：上述就绪前，质量审查继续走现有 skill 方案（open-code-review 之外的审查 skill）。
