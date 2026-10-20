# 单轮报告示例：现金函数反例

- Review phase: blind
- Target SHA: 9da5125751785e248db5edc101975bd15136936d
- Review scope: review/v1 mode=strong topics=data exclude=ui
- Attempt: template-demo-01
- Input packet: review-input.md / demo/v1
- Requirement/design version: replay/v1 / DATA-01
- Skill version: template-demo/v1；计分协议为 review/v1，实现版本见 PR
- Environment: Python 标准库，纯内存虚构数据
- Reviewer / independence / contamination: 作者执行已知合成夹具实验；不是独立模型盲审，不用于模型质量验收。

## 版本与覆盖

候选为输入绑定 commit 中的 cash_total；base 为 3936070，候选文件内容未变化。独立示例不使用长程 Review task / Review refs 字段。

| 主题 | 覆盖 | 路径/证据 | 限制 |
| --- | --- | --- | --- |
| data | CHECKED | cash_total；以下 3 个实际运行的现金去重反例/对照 | 仅 DATA-01 与合成函数，不是生产全路径正确性证明 |
| ui | EXCLUDED | exclude=ui | 无浏览器体验判断 |
| core/api/auth/recovery/regression/observe/perf | EXCLUDED | topics=data | 不作相关主题结论 |

## 反例与对照

| 输入 | 预期 | 实际 | 结果 |
| --- | --- | --- | --- |
| a=100、b=100，a→b、b→a | 同一分量计 100 | 0 | FAIL |
| 同样金额，仅 a→b | 100 | 100 | PASS，对照 |
| 循环分量加独立 c=250 | 350 | 250 | FAIL，同根因 |

## 发现

data-001 (p0=severe): cash_total 循环重复关系导致现金事件漏计
- location: scripts/tests/code-review/replay/original/candidate.py 11; scripts/tests/code-review/replay/original/candidate.py 12
- problem: 只累计没有出边的记录；循环分量没有此类根，整个事件被丢弃。可用两条虚构记录稳定触发，违反 DATA-01 的核心金额不变量。
- suggest: 按重复连接分量计一次金额，不依赖是否存在无出边根；验证循环、链、乱序和独立分量。
- status: OPEN
- resolution: 合成候选尚未修复；本例不修改刻意保留的回放夹具。
- evidence: 上述 3 次函数执行；candidate.py 11–12；只对绑定版本的 DATA-01 适用。

## 结果与交接

| 字段 | 值 |
| --- | --- |
| 报告完成情况 | COMPLETE：本例有限函数范围的实验及记录已完成 |
| 当前适用唯一 P0 / P1 / P2 / P3 | 1 / 0 / 0 / 0 |
| Score | 0 |
| Result | FAIL：仅合成候选的 DATA-01，不是 code-review skill 质量评分 |
| 必须处理 | 若交付该现金功能，须修复并独立复核，或以当前规范设计和技术证据证明误报 |
| 人工接受/合并/发布 | 未授予 |
| 下一步 | 本例只展示格式；真实产品、其他主题及独立模型行为仍未验证 |

## 历史核对

NOT READ：保存本报告后，才能建立/更新 REVIEW.md。此报告冻结，不随后续状态变化改写。
