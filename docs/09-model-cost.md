# 09 模型与成本参考（HR 用）

> HR 管理 Agent / 模型参数配置与成本评估的参考基准。**原则：优先使用 opencode Go 套餐（廉价/免费）；deepseek 官方 API 成本高，谨慎使用。** 由 HR 跟进维护。

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
