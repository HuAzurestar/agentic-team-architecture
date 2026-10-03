# 质量证据与放行边界

任务完成不等于质量成功。审查可以带 blocker 完成；真实 REJECTED/REWORK 接受可以结束任务，却不允许集成。完整质量策略须分别在 pre_accept、pre_merge、post_merge 阶段核对当前审查/测试明细、完整 REQ/SOL 范围、独立缺陷关闭与适用的人类证据；不能把不完整历史记录自动升级。下述读取器不等于该聚合策略及任务/宿主接线已完成。

## 实际 Git 集成对应关系

`quality_git.observe_integration(IntegrationBinding(...), phase, result_sha=...)` 读取实际本地 Git 对象和 refs。宿主独立提供已登记仓库身份、source 分支/SHA/tree、target 分支及冻结的 target-before SHA。校验分支名、仓库根与配置 remote 身份，并在观察前后核对两分支和身份。共享 Git runner 禁用 replace objects，读取器拒绝本地 graft 文件；不 fetch、改 refs、刷新 index、merge 或 push。

接受/合并前，source ref 必须仍为冻结的候选，local target 必须等于 target-before。target-before 必须是 source 的真实祖先，source 的实际整棵树须等于保留的候选树。对于已同步目标的 source，这些事实确定正常 merge 的预期树，但不授权 merge。

合并后，target 必须等于精确 result SHA，source 仍为冻结候选，result 必须以 source 为祖先，且实际整棵结果树等于保留候选树。普通 no-fast-forward merge 因而可以具有新 SHA，不自动使已接受内容失效；fast-forward 同样可满足该对应关系。目标移动、source 未同步目标、结果改树，或 squash/rebase 缺少所需祖先关系时即停止。仅 diff 相似不能转移批准。

返回的 valid 仅表示本地对应关系，并附 source/tree/target-before/result 事实；始终明确 quality_assessed=false、merge_authorized=false、remote_target_verified=false、worktree_verified=false。消费方仍须独立核对权威远端目标、干净应用工作区、当前测试、独立审查关闭、范围、真人决定及真实操作授权，不得把该只读结果标成质量通过。每条 Git 子进程使用共享 50 秒 I/O 预算，与后续纯策略的 2 CPU 秒聚合预算分开。最后一次观察不锁定 refs，实际操作边界仍需重核。
