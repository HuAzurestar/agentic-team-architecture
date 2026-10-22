# 详细设计与决定

保存 intent、进行详细设计或关联 INT/REQ/SOL 时读取。创建或修改 YAML/预览格式时参见 [protocol.md](protocol.md)。

先把外部意图作为 INT 保存原话、来源，以及已提供的可选 intent type。title 是具体意图的简短概括；decided by 保留原始提出者身份，可为人、agent、平台或组合，不限定格式，不替换为代录者。意图表达并留存时已经是 RECORDED，不等待审批；未知的提出时间/原因可以留空。评审、测试、重构请求也属于 INT，解释后不一定成为新产品需求。从中提炼核心 REQ 与对应 SOL 是详细设计工作，通过版本化输入记录加工关系。

三种类型统一列在 DESIGN，在 design/<id>.md 查看；不再维护 REQUIREMENT.md、SOLUTION.md、INTENT.md 三个独立状态入口。具体内容由被委托的 agent 参考 INT/REQ/SOL 模板编写，不通过脚本创作新的方案或判断。INT 分类与初始意见是外部接入者的可选能力，intent type 和 initial opinion 等字段/正文可按需省略，不是通用必经步骤。共用字段按类型解释：INT 使用来源身份语义，REQ/SOL 使用审批决定语义，详见 [protocol.md](protocol.md)。专用关系汇总到 detail spec。

评论、建议和有权决定是不同事实。DECISION 任务记录目标版本、实际决定者、结论、授权、mode、说明；delegated 模式另记 on behalf of。对于 REQ/SOL 等需判定设计点，将相应结果同步到 decided by、decided at、decided with，再同步表格；不能用后续评审者或确认者覆盖 INT 提出者。

获授权 agent 可以在委托内决定，不固定要求人工二次确认。适用 AGENTS.md 的角色设定可提供有条件的 REQ/SOL 确认权限，按 [confirmation.md](confirmation.md) 中的授权和强制理由规则执行。宿主判断实际范围与授权有效性；自信、难易评估和学习不产生权限，审核能力进化与策略变化由外部负责。

部分决定、修改已决定点或重开时，读取 [confirmation.md](confirmation.md)，其中维护版本与原决定处理要求。面向用户的验收 brief 和答复读取 [acceptance.md](acceptance.md)。这些操作均不依赖临时附件。

TEST／REVIEW执行产生的质量发现使用FEEDBACK记录，不自动创建INT；用户提出的测试／审核请求仍属于外部意图。处置及开发测试与独立TEST的区别参见[任务约定](task-contracts.md)。
