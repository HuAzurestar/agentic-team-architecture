# 持久 checkpoint 与恢复

开始、恢复、记录 checkpoint 或交接实现工作时读取本文件。

## 自动时机

Agent 无需用户提醒，在以下时机创建本地 checkpoint：完成一个连贯且可测试的工作单元后；长耗时或高风险操作前；正常交接或结束前。

调用 `scripts/task_checkpoint.py` 时显式列出 Agent 拥有的文件。它拒绝目录、疑似敏感路径、预先 staged 的工作、未变化的 include，以及范围外任何改动。它只创建本地 commit，不 push，随后更新 task HEAD、resume action 和 checkpoint 说明。产生的项目管理记录另行提交。

## 恢复行为

`task_context.py` 返回可恢复上下文前检查已解析仓库。实现仓库存在 staged、unstaged 或 untracked 变化时硬停止；项目管理仓库只检查当前 feature 目录，不触碰其他 feature 文件。

停止时先判断残留是否属于中断的 task，检查并测试后再 stage；创建有范围的 checkpoint，或只在确实不属于 Agent 时询问用户；新修改前重新运行恢复。

保证边界是最近一次成功本地 checkpoint。任意断电瞬间零丢失需要宿主、编辑器、文件系统或常驻进程支持，Skill 不作虚假承诺。

## 可选审查断点

完整校验调用[只读审查恢复](../scripts/review_resume.py)，以[真实 Git/进程测试](../scripts/test_review_resume.py)验证版本拒绝及原文保持。该入口仅恢复引用与剩余发现，不做完整报告质量判断、独立性证明、发现关闭或人工接受。没有声明的旧 Feature 不需要新文件或服务。

任务可在顶层声明一次 `- Review recovery: gists/resume.md`，并在同一任务的 `- Gists:` 中列出该文件及全部 packet、report、checklist 和原始证据。引用对象包含 Feature 内相对 `path` 和原始字节的 `sha256`（包括换行编码）。不读取外链。缺材料为 EVIDENCE_MISSING；摘要、目标或 attempt 过期为 STALE_REVIEW。保留旧报告，新候选建立新 attempt，不能改旧 target 转移 PASS。

恢复 gist 使用完整 JSON 对象，或唯一显式标记 `review-resume-v1` 的 fenced block；字段为 `schema`、`feature`、`review_task`、`attempt_id`、`target_refs`、`packet_ref`、`report_ref`、`checklist_ref`。`target_refs` 是已登记仓库名到完整 40 位 SHA 的映射，必须在真实仓库存在且等于观察到的工作 HEAD。Packet/report 同样使用完整 JSON 或 `review-packet-v1` / `report-v1` 显式围栏，schema 对应；feature、review task、attempt、target refs、checklist ref、packet ID 必须一致。这只校验恢复字段，不代表通过 F04 完整报告 schema。

报告另含非空 `evidence_refs`、`findings` 和 `summary`。发现有报告内 `id` 和 `status`（open/addressed/closed），同一报告中完全一致的重复 ID 去重，矛盾重复拒绝；addressed 仍未关闭。摘要或恢复 gist 若提供 `open_finding_ids`，必须与派生集合一致，否则 REVIEW_SUMMARY_MISMATCH。其余质量计数、严重性规则与独立关闭证据交由报告评估器处理。

聚焦输出的 `review_recovery` 给出报告/清单引用、attempt、实际候选、带完整报告作用域的未关闭发现及下一动作。有未关闭发现为 `resume-rework`，否则 `needs-independent-recheck`；绝不授予接受或合并权限，`quality_assessed` 始终 false。默认 Markdown 显示候选及下一动作，JSON 提供相同投影。CLI stderr 的 `review.resume` 事件只含摘要、数量、错误及耗时，不记录意见正文。新进程仅证明持久恢复，不证明真实独立 Agent 审查会话。

本地提交与独立记账需要可恢复意图时，使用可选的[操作恢复](operations.md)模式。旧 CLI 保持兼容；旧检查点未记录 operation 意图时，不补造其历史证据。

工作目录、任务分支或集成观察漂移时，按[迁移与对账](reconciliation.md)先 inspect 再受控 apply。保留历史 refs，未通过真实身份与祖先检查时不得继续；提交管理记录后重新运行严格恢复入口。
