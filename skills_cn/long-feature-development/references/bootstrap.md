# 首次记录初始化

仅用于尚无已提交管理记录的新 feature。严格恢复要求文件已跟踪且干净，不能先证明尚未提交的初始记录有效。初始化 checkpoint 只表示保存，不代表校验、接受或允许实施。

1. 确认管理仓库与 feature 路径，检查 Git 状态和已有记录；不得覆盖已有 feature 或混入其他任务改动。已有 feature 使用正常恢复，不使用本路线。
2. 注册仓库必须已有 commit 和声明的本地分支。稳定/集成 refs 使用实际观察到的完整 SHA；空仓库先按项目 Git 规范建立基线，不得虚构 SHA。只有管理仓库工作 HEAD 使用 `DERIVED:HEAD`。删除未使用的仓库和 PR 行，不虚构实现仓库或 PR。
3. 填写四个主模板及各任务详情。初始需求/方案任务保持 PENDING，文档 DRAFT，确认点 PROPOSED。等待初始决定时使用 WAITING_HUMAN；ACTIVE 要求当前任务为 WIP/RECORDING。填写 selectors 和实际基线；未接取任务的 start/HEAD/completion refs 为 `-`。Gate 的 Required tasks 与直接依赖一致，不写传递闭包。
4. 同时创建 `tasks/` 与 `gists/`。暂无 gist 时跟踪空的 `gists/.gitkeep`，任务声明 `Gists: none`；占位文件不是证据，不作为 gist 声明。检查文件未被忽略；secret 和原始日志保留在此树之外。
5. 提交前检查精确 diff：无残留占位符、索引/详情一一对应、selectors/依赖一致、仓库身份和实际 refs 正确，没有虚构决定或完成。未改图时保留模板拓扑；自定义初始依赖图时用 `task_context.synchronized_topology` 生成图。这只是准备，不表示严格校验已通过。
6. 只暂存已检查的新 feature 文件，检查 staged diff，创建本地初始化 commit，例如 `NO-FEAT: initial records; validation pending`。不得据此发布、合并、接取任务或推进 Gate。
7. 立即运行 `python <skill-root>/scripts/task_context.py <feature-directory>`，必要时显式指定 `--repo NAME=PATH`。必须成功且 trace mode 为 VALIDATED。非零退出是 feature 执行的硬停止；仅修正初始化记录、分别提交范围限定的修正并重跑。不得删除 registry、关闭脏状态检查，或把结构检查冒充严格成功。
8. 严格恢复通过只表示初始化完成，不代表批准。展示需求提议并等待真实人类决定。后续改动遵循正常 checkpoint/恢复规则；暂存或未暂存残留仍阻塞恢复。

新 clone 恢复前核对仓库身份和注册本地分支：本地 clone 可能把 origin 改为文件系统路径，也不一定创建全部远端分支对应的本地分支。恢复注册时只能使用已验证 refs。

[初始化回归](../scripts/test_bootstrap.py)实际使用发布模板、真实 Git 基线、首次管理 commit、严格恢复、新本地 clone 和后续暂存/未暂存负例。不连接远端，不提供接受决定。
