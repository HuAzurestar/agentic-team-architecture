# 识别工作流程的通知 hook

workflow_events.py 实现离线持久事件/尝试/回执/回复账本，不发起网络请求或启动 worker；实际投递仍由 runtime 工具承担。runtime adapter 状态见[持久化接入](runtime-persistence.md)，实施前需确认事件映射及接收器/adapter 契约。

## 离线 helper I/O

使用 workflow_events.py --state-root <absolute-state-directory> --runtime-id <runtime-id>，再接 record/attempt/ack/reply --input <json-file>。reply 另需 --current-object-revision <actual-workflow-revision>；inspect [--event-id <id>] 读取持久状态。先配置 notification profile；delivery state 目录保存绑定 runtime 的账本。

- record：event id/type、phase、purpose、priority、feature、task、object revision、occurred at、actor、correlation id 为字符串；decision required 为布尔值，payload 为 JSON 数据。决定请求另需 decider/requested scope/allowed consequences。同事件同内容幂等，冲突内容拒绝。
- attempt：event id、attempt id、occurred at、adapter tool reference、route；adapter 与 route 必须匹配当前明确配置。宿主调用实际工具前先保存 attempt，helper 不代替该调用。
- ack：event id、attempt id、occurred at、status（accepted/failed/unknown），可附 receipt；回执不可覆盖，重试另建 attempt 并保留原 event id。
- reply：event id、reply id、correlation id、object revision、declared decider、original wording、source、occurred at；同时与原请求及显式传入的当前 workflow revision 核对，拒绝旧版本回复。工具不认证身份、不评估业务授权；宿主验证身份，有权角色将实际决定保存 PM。

helper 不按接收器订阅过滤事件，不调用 adapter、不修改正式批准，也不把任意 decision 内容解释为权限。失败/未知回执在重启后仍可读，没有自动重试或后台队列。

## 事件 I/O

输入：实际流程事件，以及 Feature/任务、准确对象版本、调用方提供的适用策略/授权引用、实际操作者、发生时间、待决定问题或结果、证据/限制及关联上下文。输出：持久事件及真实投递结果（not_attempted、accepted、failed、unknown），保留可得回执。按实际发生的事实形成事件，接收器由用户决定订阅、重要程度处理、展示和屏蔽，不由 Agent 因猜测用户偏好而丢弃流程事实；缺项如实表达。

事件信封包含 event id、event type、phase、purpose、priority、Feature/task/object revision、发生时间/操作者、correlation id、是否需决定/实际决定者、请求范围/允许后果及 payload/证据引用。重试保留事件身份，另记 attempt；身份对应实际事件及版本，不能仅凭标题去重。

建议事件族（adapter 绑定是配置数据）：

| 事件 | 含义 |
| --- | --- |
| intent.recorded / intake.routed | 接收、关联、整理及分流，不伪造批准 |
| design.confirmation.requested | 请求对准确 REQ/SOL 版本作决定 |
| decision.recorded | 用户本人或有效代理的实际决定，保留决定者与授权 |
| gate.evaluated / gate.authorization.requested | 条件判定或等待授权 |
| task.planned | 告知将做什么、理由、范围和预期结果；不是已经开始的证明 |
| task.started / task.blocked / task.result.recorded | 实际执行进展、阻塞和结果 |
| review.finding.recorded / test.result.recorded | 绑定版本的发现与验证 |
| feedback.recorded / acceptance.requested | 反馈或指定候选的验收请求 |
| release.action.planned / release.action.result | 按授权处理合并/部署、更新文档、对外通知、公告及实际结果 |

purpose 区分告知、行动预告、请求决定；priority 表示重要程度，均不产生授权，也不决定是否阻断。一次事件可关联多个记录；按实际事件/接收对象去重，不能因此吞掉不同 REQ/SOL/GATE 的独立决策。事件名称和映射为可审阅提案，不成为固定公司状态机。

## 投递与回复

① 工作流程先把真实发生的事件/对象保存 PM，再形成通知；runtime adapter 持久化投递状态并调用配置工具/路由，用户接收器决定展示。行动预告必须发生在其描述动作之前，并说明仍在等待的授权。

② 保存关联、attempt 和真实回执。工具成功/HTTP 受理不证明人已收到或批准。失败/未知返回具体限制，保留未决状态；仅按明确配置重试/恢复，不静默丢弃，不隐含无限重试、备用渠道或后台进程。

③ 回复处理核对实际决定者、请求和对象版本，保存原话/来源/时间，向编排者返回版本化决定；含糊或过期回复保持未决。修改接收器订阅不改变流程授权。

仅适用策略要求的决定阻断依赖动作。即使接收器屏蔽通知，必需的 GATE/REQ/SOL 决定无有效答复仍待定。普通告知发送失败不自动阻断无关已授权工作，按配置报告。hook 不自动合并、部署或批准。

## 建议验收实验

先用不会真实外发的 fixture adapter：同 instruction 迁移 runtime A/B；同事件重放不重复执行决定；屏蔽展示不产生批准；投递失败仍保留事件；旧对象版本回复被识别为过期。真实网络回调、投递保证和重试调度需另行协商实施与测试。

## 策略与集成边界

helper校验已列出的基础字段和请求/回复关联，保留额外JSON数据，不认证授权或回执真实性。调用流程提供并核对适用策略/授权/证据引用；缺少策略元数据不解释成权限。helper不向索引生成器、平台事件或状态流转自动安装hook，由获授权工作流程在真实流转点显式调用。

## 宿主交流规则

宿主选择 `Align-Decide-Disclose`（对齐—决策—披露）时，Align说明背景和当前事实，Decide提出需要对方决定的问题／选项／范围，Disclose报备授权内已自主决定或执行的事项及实际结果。适用于对用户通知和相关Agent间汇报，可省略空项。披露不产生追溯授权；具体交流规则由宿主提供，不增加必填JSON字段、不改变事件身份，也不安装adapter。
