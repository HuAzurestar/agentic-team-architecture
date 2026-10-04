---
name: review
description: 以主题范围、强审或具体内容点引导的弱审检查软件变更，输出有证据的问题和版本化 REVIEW.md 账本。用于开发自查、独立软件审查及问题复核，不用于科学证明审查或组织审计。
---

# Review

强弱使用同一范围和问题协议。强审逐主题自由探索，弱审逐内容点扫描。一个内容点可以发现零条、一条或多条独立问题；不按问卷答案计分。

## 选择范围

短配置为 `review/v1`：

```text
review/v1 mode=strong exclude=ui focus=权限继承,导出旁路
review/v1 mode=weak topics=core,api,data,auth,regression exclude=ui
```

mode 默认 strong，topics 默认 all，exclude 默认空；从所选主题中扣除排除项。focus 增加重点承诺或设计点，不缩减其他选中内容。记录默认选择；未知协议、字段、模式、主题或重复字段报错。空选择为 INCOMPLETE，不报满分。不从模型名称推断能力。

没有配置时检查本次变更及影响范围的全部适用主题，不扩成全仓库历史审计。披露排除和有依据的 N/A。检查判断选中承诺所必需的依赖，披露排除造成的限制，不悄悄改变范围。

| 主题 | 强审目标 | 弱审 detail |
| --- | --- | --- |
| core | 需求差量与完整性、职责内聚、复用、死代码及当前复杂度必要性。 | [core](references/core_review_detail.md) |
| api | 接口语义、输入输出、错误约定和调用方。 | [api](references/api_review_detail.md) |
| ui | 实际用户任务、信息设计、批处理、默认操作、反馈和恢复。 | [ui](references/ui_review_detail.md) |
| data | 业务不变量、事务、顺序、并发及幂等。 | [data](references/data_review_detail.md) |
| auth | 权限继承、旁路及敏感信息出口。 | [auth](references/auth_review_detail.md) |
| recovery | IO 失败、部分成功、超时、重试、重启和恢复副作用。 | [recovery](references/recovery_review_detail.md) |
| regression | 既有语义、历史数据与配置、直接及间接消费者。 | [regression](references/regression_review_detail.md) |
| observe | 日志/上下文能否定位故障，是否泄露敏感信息。 | [observe](references/observe_review_detail.md) |
| perf | 关键路径规模、复杂度、批处理、无界资源及释放。 | [perf](references/perf_review_detail.md) |

强审不读取弱审 detail。逐选中主题从实际需求构造假设，扫描实现和旁路，尝试有效反例，也可以发现主题摘要之外的实际问题。

弱审仅加载选中主题的 detail，按内容点和证据/搜索方向扫描。YES/NO/UNKNOWN/N/A 可作为内部笔记，不是报告和计分单位。补充适用反例；随机探索只能补充必查点，实际检查内容须记录。

## 保持输入干净

固定仓库身份、实际 base/head、需求/设计版本、环境、范围和 skill 版本。作者自查与独立执行上下文分开，同会话换角色不构成独立审查。无现有授权不创建其他 task/session 或委派；独立能力不足时如实记录，并继续允许的自查。

本轮盲审前不读现有 REVIEW.md、旧报告、findings、分数或摘要，也不通过依赖详情和作者交接间接取得这些结论。代码、现有测试、规范性设计和原始运行证据正常检查。系统约束、真实授权与安全边界保留；若这些边界与旧发现无法分离，披露限制，不声称干净盲审。

使用 long-feature-development 的 Feature，**首次**恢复必须选择 blind：

```text
python <long-feature-skill>/scripts/task_context.py <feature-directory> --review-phase blind --review-input gists/review-input.md
```

不能先运行普通恢复输出。协调者准备有界、已声明的原始输入，包含当前规范性需求/设计摘录、授权和原始证据，并标记 `- Evidence type: original`。标记只是路由声明，不证明内容可信；reviewer 仍检查污染和缺失。blind 显示文档来源及点 ID，不默认输出任意管理全文。没有原始包表示输入不完整，不能 PASS。

若宿主已经把旧 findings 放入上下文，记录污染。保存盲审快照本身不证明独立上下文。

## 扫描

1. 查看真实 diff，识别公共接口、schema、配置、权限、事务、异常、日志及测试变化。
2. 对重要符号追踪定义、调用方、依赖、同类实现及测试。
3. 搜索业务概念和不同表达，不只搜修改函数名。
4. 检查适用 UI/API/CLI/后台任务/恢复/导入导出旁路。同根因再次出现时扩大公共机制检查。
5. 对金额守恒、权限继承、完整预览、恢复不重复等承诺尝试有效反例，不能信任声明字段代替验证。

仅用允许的环境和数据。记录预期及观察，未运行不能称为实验通过。UI 体验需要实际操作或界面证据，性能判断需要规模假设。证据不足列限制，不制造低优先级 finding。

## 固定结果后核对历史

读历史前先保存独立的本轮盲审报告，绑定目标并记录：

```text
- Review phase: blind
- Review task: REVIEW-01
- Target SHA: 实际审查的字面 commit
- Review scope: review/v1 mode=strong
```

多仓库另列各 base/head。后续核对新增发现不改写该快照。长程任务先声明快照 gist，再运行：

```text
python <long-feature-skill>/scripts/task_context.py <feature-directory> --review-phase reconcile --review-report gists/blind-01.md
```

此时才读旧报告和 REVIEW.md，映射稳定 ID，核验旧修复及对应回归。盲审未发现旧问题不表示已修复。目标变化后重核受影响证据和总分；未变化证据可有依据地复用。

盲审后使用[账本模板](assets/REVIEW.md)。长程账本位于 `<feature-directory>/REVIEW.md`，不可变逐轮报告在已声明 `gists/REVIEW-*.md`；独立使用按用户指定或仓库既有输出目录。后续修复不改写旧分数，账本不存无界日志。

强弱统一格式：

```text
auth-001 (p0=severe): export 单条结果导出绕过权限检查
- location: src/export.py 84; src/results.py 126
- problem: 触发条件、实际行为、影响及支持评级的证据。
- suggest: 最小合理修复或验证建议。
- status: OPEN
- resolution: 尚未解决；后续记录修复/决定版本及复核。
- evidence: 代码、diff、运行或测试引用及对本轮目标的适用性。
```

标题包含 topic-ID、priority、module、具体摘要。priority 为 p0=severe、p1=risk、p2=warning、p3=suggestion，依据实际影响和可触发性，不按代码美观。独立触发、独立修复的问题分条；一个缺陷多位置合并。相似标题不是重复依据。ID 在账本内稳定，跨 Feature 使用账本路径加 ID。核对历史后可显式映射本轮临时 ID。

| status | 含义 | 对当前适用目标计分 |
| --- | --- | --- |
| OPEN | 问题成立且未解决。 | 是 |
| FIXED | 记录版本上修复已独立复核，证据有效。 | 否 |
| REJECTED | 证据证明误报或不适用。 | 否 |
| DEFERRED | 问题成立，本次选择保留或暂缓。 | 是 |

作者可记录修复提交，不能自关独立发现。拒绝修改建议但承认问题存在是 DEFERRED。保留状态/评级变更、理由和旧值。旧关闭证据不适用于新目标时不能沿用。未检查或范围外历史问题单列，排除不得隐藏未关闭的交付阻断 P0。

P0 必须修复并复核，或以明确项目设计点、设计版本及技术依据证明误报。新增文档改变产品语义属于设计变更，不是误报证据。DEFERRED 或静默降级不能绕过 P0。P1/P2/P3 修复可选，保留时仍扣分，说明影响和理由；不能因此忽略已确认需求或数据/授权边界。

## 计分与接续

统计当前适用且唯一的 OPEN/DEFERRED：

```text
score = max(0, 100 - 100*P0 - 10*P1 - 2*P2 - P3)
result = PASS if P0 == 0 and score >= 60 else FAIL
```

显式声明完整性并使用[确定性 helper](scripts/review_score.py)：

```text
python scripts/review_score.py --complete --p0 0 --p1 3 --p2 4 --p3 2
python scripts/review_score.py --incomplete --p0 1
```

范围未完成、缺关键证据或中断时 INCOMPLETE、score=null，保留已确认计数。helper 不读账本、不判断证据适用性；零发现不能单独证明完整。

报告完成、评分结果、强制返工与人工接受分开。有问题的完整报告可以完成；P0 必须返工或有效拒绝，P1/P2/P3 不因低于 60 无限自动返工。PASS 不授权接受、合并或发布。

在既有授权内继续复现、技术修复、测试和复核；产品语义/范围/预算/数据权限变化及最终接受发布保留决定边界，不自动启动缺少授权的独立执行。交付说明基线差量、试用方式、限制、准确下一步和真实待人工决定；阻塞写清证据及谁/什么能解除，工作流列位置不代表质量。
