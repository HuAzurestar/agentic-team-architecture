# 公司工作流部署

版本：`feature-delivery/2026-10-22-v10`。

四角色源文件分别为 `orchestrator_agent.md`、`out_socket_agent.md`、`dev_processor_agent.md`、`release_check_agent.md`。`orchestrator` 亦称 `dev-orchestrator`；实际 Agent 不重建、不改名。

部署时将 `common-rules.md` 正文附加到每个角色；将 `development-workflow.md` 附加到 `orchestrator` 和 `dev-agent`。把角色的公共规则入口指向实际附录，不能留下运行时不可读取的相对引用。协作角色 ID 由 runtime 绑定注入【协作】项，源模板不固定 workspace 身份。

角色说明按【定义】【负责】【关注】【协作】【能力】组织；第二部分逐项写 `Input`、`Process`、`Output`、允许动作、禁行动作和执行条件。派发入口为 `(feature-key, task-key)`，完整执行约束从正式记录和 `Project` 配置读取，不能因参数简化而省略授权核对。

用户账号资料可另保存负责人说明，由用户身份核对后经平台 profile 接口写入；不把个人账号内容提交到本公共模板。账号说明不替代逐项授权。

本目录是组织规则，不安装 Skill、通知 adapter 或编号分配器。首次使用还须配置 PM、项目仓库／环境、notify 与身份绑定。自动申请 `feature-key` 必须另有用户授权及配置好的外部分配接口。

`v8`明确按实际上下文进程隔离DEV／REVIEW／TEST／DOCS；INT／REQ／SOL设计可合并，确认另用干净上下文。所有GATE默认用户批准，仅socket在全量REQ和SOL均由其依特许条件确认、本阶段输入已收口且无未处理INT时可代理START；orchestrator没有代理GATE批准权，COMPLETION永远由用户确认。

`Align-Decide-Disclose`（对齐—决策—披露）用于notify及需要汇报的协作交流；完整含义与例子见[交流规则](communication.md)。空项可省略，披露只报告已有授权内的实际决定／执行，不替代批准。

`Align-Decide-Disclose`（对齐—决策—披露）用于notify及需要汇报的协作交流；完整含义与例子见[交流规则](communication.md)。空项可省略，披露只报告已有授权内的实际决定／执行，不替代批准。

`v10`区分质量FEEDBACK与外部INT、DEV内测试与独立TEST；反馈后的开发统一主类型DEV，子类可为refine／bug-fix／refactor。ADVICE/BUG的类型注册及关系校验仍属feedback-disposition/v2提案范围，工作约定更新不代表其Skill实现已安装。
