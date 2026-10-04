# 合成模板示例：重复现金事件

- Evidence type: original
- Input ID: template-demo-01
- Review scope: review/v1 mode=strong topics=data exclude=ui
- Scope source/version: 本示例请求 demo/v1，不是生产设计决定
- Requirement/design version: replay/v1 的现金去重承诺
- Skill version: template-demo/v1；计分协议为 review/v1，实现版本见 PR
- Environment: Python 标准库，纯内存合成记录
- Authorization source/version: demo/v1，仅隔离示例验证
- Action boundary: 允许读取合成 candidate.py 并运行现金函数；禁止网络、真实用户数据、写外部系统。报告只写隔离示例目录。
- Release condition: 无外部等待；扩大到真实系统或外部访问须取得新授权。

## 候选版本

| 仓库/身份 | 分支 | Base SHA | Head SHA | 核验情况 |
| --- | --- | --- | --- | --- |
| HuAzurestar/agentic-team-architecture 的合成回放模块 | feature/pirc-39-review-skill | 393607006df9e91000bf632617f1ae6cb38a5fb6 | 9da5125751785e248db5edc101975bd15136936d | candidate 内容未变；这不是 PR 全范围审查 |

## 规范性需求

DATA-01：由 duplicate links 连接的记录代表同一现金事件，每个连接分量计一次金额；链接允许有向、乱序和循环，同分量金额相等，互不相关事件仍分别计入。来源：合成原始请求 replay/v1 第 2 条。

## 原始材料及限制

候选：scripts/tests/code-review/replay/original/candidate.py 的 cash_total。
允许用虚构 ID 和整数最小货币单位调用函数。只审查该函数和 DATA-01；未要求审查导入、交付校验、权限或真实产品环境。没有生产数据和浏览器证据。本文件不包含预设缺陷或历史结论。
