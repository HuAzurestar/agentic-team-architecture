# 面向用户的验收

创建、接取或展示验收 task 时读取本文件。

从 `templates/ACCEPTANCE.md` 在 `gists/` 下创建受版本控制的短验收 brief，在 task 的 `Gists` 中声明，并在类型合同的 `Acceptance brief` 中记录。每个章节都用有界、自然语言填写；内部 task ID、point ID 和原始日志保留在追溯记录中，不是用户作决定的前提。

请求决定前，由 Agent 内部运行：

```text
python scripts/task_context.py <feature-directory> --task <acceptance-task> --format acceptance
```

主动展示这份短输出。用户可以用自然语言表示接受、要求修改，或说明还要检查什么而暂不决定。Agent 把自然语言映射为内部决定并记录准确人工来源；不得要求用户编辑合同或理解 `ACCEPT-*`。

验收 task 在 PENDING、WIP 或 BLOCKED 时保持 `WAITING`。人工作出决定后进入 RECORDING，持久化决定，再完成 refs。只有验收 task 为 DONE 后 gate 才能继续。
