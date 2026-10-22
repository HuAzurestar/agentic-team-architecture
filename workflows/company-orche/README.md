# 公司工作流部署

版本：`feature-delivery/2026-10-22-v7`。

四角色源文件分别为 `orchestrator_agent.md`、`out_socket_agent.md`、`dev_processor_agent.md`、`release_check_agent.md`。`orchestrator` 亦称 `dev-orchestrator`；实际 Agent 不重建、不改名。

部署时将 `common-rules.md` 正文附加到每个角色；将 `development-workflow.md` 附加到 `orchestrator` 和 `dev-agent`。把角色的公共规则入口指向实际附录，不能留下运行时不可读取的相对引用。协作角色 ID 由 runtime 绑定注入【协作】项，源模板不固定 workspace 身份。

角色说明按【定义】【负责】【关注】【协作】【能力】组织；第二部分逐项写 `Input`、`Process`、`Output`、允许动作、禁行动作和执行条件。派发入口为 `(feature-key, task-key)`，完整执行约束从正式记录和 `Project` 配置读取，不能因参数简化而省略授权核对。

用户账号资料可另保存负责人说明，由用户身份核对后经平台 profile 接口写入；不把个人账号内容提交到本公共模板。账号说明不替代逐项授权。

本目录是组织规则，不安装 Skill、通知 adapter 或编号分配器。首次使用还须配置 PM、项目仓库／环境、notify 与身份绑定。自动申请 `feature-key` 必须另有用户授权及配置好的外部分配接口。
