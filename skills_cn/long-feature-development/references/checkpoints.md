# 持久 checkpoint 与恢复

开始、恢复、记录 checkpoint 或交接实现工作时读取本文件。

## 自动时机

Agent 无需用户提醒，在以下时机创建本地 checkpoint：完成一个连贯且可测试的工作单元后；长耗时或高风险操作前；正常交接或结束前。

调用 `scripts/task_checkpoint.py` 时显式列出 Agent 拥有的文件。它拒绝目录、疑似敏感路径、预先 staged 的工作、未变化的 include，以及范围外任何改动。它只创建本地 commit，不 push，随后更新 task HEAD、resume action 和 checkpoint 说明。产生的项目管理记录另行提交。

## 恢复行为

`task_context.py` 返回可恢复上下文前检查已解析仓库。实现仓库存在 staged、unstaged 或 untracked 变化时硬停止；项目管理仓库只检查当前 feature 目录，不触碰其他 feature 文件。

停止时先判断残留是否属于中断的 task，检查并测试后再 stage；创建有范围的 checkpoint，或只在确实不属于 Agent 时询问用户；新修改前重新运行恢复。

保证边界是最近一次成功本地 checkpoint。任意断电瞬间零丢失需要宿主、编辑器、文件系统或常驻进程支持，Skill 不作虚假承诺。

本地提交与独立记账需要可恢复意图时，使用可选的[操作恢复](operations.md)模式。旧 CLI 保持兼容；旧检查点未记录 operation 意图时，不补造其历史证据。

工作目录、任务分支或集成观察漂移时，按[迁移与对账](reconciliation.md)先 inspect 再受控 apply。保留历史 refs，未通过真实身份与祖先检查时不得继续；提交管理记录后重新运行严格恢复入口。
