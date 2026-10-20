# 任务记录与交接

接收或返回工作时读取。

委托提供范围、输入版本、owner、预期产物、完成条件和返回接口。记录到 tasks/<id>.md 的 YAML 与可审核正文。REVIEW、DEVELOPMENT、DOCS、DESIGN、TEST、DECISION、FEEDBACK、ACCEPTANCE、GATE 是任务 type，不是独立模块。

拆分工作读取 [task-planning.md](task-planning.md)，接取、阻塞、完成或重开读取 [transitions.md](transitions.md)。任务共用生命周期，具体调度和状态转换权限由调用方决定。

result 将执行与结果、证据分开。测试做完可以失败，决定处理完可以拒绝。将实际检查、覆盖限制、候选/输入版本和实质验证摘要存入持久任务报告；外部证据也应可确定版本。

测试/评审/返工报告内容读取 [task-contracts.md](task-contracts.md)，验收决定读取 [acceptance.md](acceptance.md)。结束或转交未完成工作前，通过获授权的持久化方式应用 [checkpoints.md](checkpoints.md)。

交接请求与回执写入任务正文或 YAML，指出接收者、请求、输入版本、预期回答、返回位置和后续负责人。受理、接受、执行、效果验证代表不同事实；工单号不能证明动作已经执行。

返回时说明实际发生了什么、产出版本、检查及限制、未决项和后续责任人。未收到回执或请求被拒绝时保持未决，不推断已经执行或获得重试/升级权限；编排者或外部流程负责后续路由与动作。

通过提供的状态接口返回未决项。必要推理、验证和决定评论保存在 design/tasks；正式记录不能引用临时草稿、导出或原始附件。
