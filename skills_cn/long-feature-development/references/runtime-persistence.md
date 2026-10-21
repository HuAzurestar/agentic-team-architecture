# Runtime 持久化：项目管理接入与通知接入

随附 `scripts/runtime_state.py` 通过显式 --state-root 和 --runtime-id 实现本地配置持久化。宿主需用实际支持的 runtime 绑定提供这些参数；helper 不安装 Multica daemon 配置加载器。

## 本地 helper 用法

宿主每次提供绝对 state 目录及 runtime 身份。先复制并填写两份模板；模板空值不能直接作为有效配置。沿用已有 PyYAML 依赖。

```text
python <skill-root>/scripts/runtime_state.py --state-root <absolute-state-directory> --runtime-id <runtime-id> configure --kind project-management --input <filled-project-management.yaml>
python <skill-root>/scripts/runtime_state.py --state-root <absolute-state-directory> --runtime-id <runtime-id> configure --kind notification --input <filled-notification.yaml>
python <skill-root>/scripts/runtime_state.py --state-root <absolute-state-directory> --runtime-id <runtime-id> resolve --kind project-management
```

configure 保留不可改写版本，更新已有配置时通过 --expected-revision 核对当前版本；相同内容重复配置幂等，内容变化需要新 revision。并发冲突明确失败，不等待或自动重试。resolve 检查结构和 runtime 身份；返回位置不证明文件/网络可访问或动作已获准。

项目管理 profile：management roots 为名称到绝对路径映射，selected root 为其中一个键，project registry 为绝对路径，state writer reference/commit policy reference 为非空字符串，environment references 为映射。通知 profile：adapter tool reference/failure handling reference/reply correlation contract 为非空字符串，routes/event bindings 为映射，凭据为字符串引用，delivery state reference 为绝对目录。以上均为数据，不作为 shell 命令执行。

## 归属与首次引导

Agent instruction 依赖用户的组织理念和授权，不依赖具体生产环境；不包含机器路径、runtime ID、网络节点、凭据或各机器的通知工具名。开发机/runtime 配置并持久维护本 skill 的接入数据；Agent 迁移后读取目标 runtime 的配置，instruction 保持不变。

runtime 通过其实际支持的引导/工具绑定提供一个明确可读的 skill-state 入口。不能用尚待解析的 PM 根目录寻找这个入口，也不能从 Agent ID、仓库扫描或猜测的用户目录推导。安装相同 Skill 不代表共享状态。分别核验 Skill 已安装、配置入口可读、状态可写；缺项时具体报告，不执行依赖动作，独立分析可继续。helper 不新增 daemon 功能、未公开环境变量或自动发现器。

在 runtime 提供的持久位置维护两类独立配置，放在可被升级替换的 Skill 安装包之外：

① `project-management.yaml`：profile/版本、runtime 身份、命名 PM 映射及明确选择器、Project 注册入口、状态写入方式、获授权的提交策略、非秘密环境引用。

② `notification.yaml`：profile/版本、runtime 身份、adapter/工具引用、路由和凭据引用、流程事件绑定、投递状态位置、回复关联及获准的失败处理方式。

上述是 runtime-state 内的相对文件名，不是全局固定路径；模板空值不是默认生效配置。组织/审批策略作为单独的版本化输入，工具连接不产生授权。

## 项目管理配置 I/O

输入：runtime 身份及配置入口、获授权的初次配置/变更请求、准确 PM 映射和所选 profile。仓库与环境已有配置为可选复用输入。首次配置保存用户/开发机明确提供的事实，日常读取复用；多个根目录无法确定时报告，不自行选择、初始化、迁移或克隆。

输出：解析后的 PM/Project/环境访问方式、配置版本、核验范围和具体缺项。区分位置语法、实际可访问与有权操作。稳定 Project 定义仍位于 `project/<project-key>/project.yaml`，Feature 设计/任务仍属于 PM；runtime-state 不维护第二套 Feature 状态。

机器相关仓库/环境覆盖值由 runtime profile 提供；逻辑仓库身份及共享规则仍放 Project 定义。长期映射修改必须有明确范围、保留旧版本、评估受影响任务并校验；凭据仅引用。并发配置修改先协调，不覆盖。

## 通知配置 I/O

输入：明确 runtime/state profile、runtime 提供的 adapter/工具、路由、接收器契约及获授权投递规则。输出：配置版本、实际验证能力和限制；配置存在不能证明发送或回调已经可用。

事件及回执使用配置的持久投递状态；正式决定和实质执行依据仍保存 PM tasks/design。事件 I/O 见[通知 hook](notification-hooks.md)。其中一种接入不可用时，不猜另一配置作为替代，不阻止无关 PM 或只读工作。

## 迁移与恢复实验

同一份 instruction 从 runtime A 移到 B，B 解析自己的明确配置、PM 映射和通知 adapter。写入前核对共享仓库身份、访问及当前候选，不隐式搬运 A 的端点/秘密。PM 正式状态仍为来源；未决投递或决定请求需先明确交接归属、核对关联后才可重放。比较配置版本，不把旧对象的回复用于新版本。迁移成功不证明旧 callback 或远端权限同时迁移。

## 存储及中断边界

每类配置在 history/<kind>/<revision>.yaml 保留不可改写历史，并由 <revision>.parent.json sidecar 保存前驱。中断更新仅可从对应前驱重试相同revision，不能借历史revision回滚。state-root冲突锁明确失败，不自动抢占；遗留锁先核实记录的操作/进程已经结束，再由人或获授权宿主移除。原子替换保护已完成文件写入，不承诺任意断电瞬间零丢失。
