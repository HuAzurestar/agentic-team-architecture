# example-feature — STATUS

repository、feature、dev 等综合状态的统一管理入口。这里保存整体状态并链接必要详情，不重复 DESIGN、TASKS、VERBAL 的内容。以下概况项目仅作示例，不规定固定流程。

| Item | Current value |
| --- | --- |
| Feature key | example-feature |
| Project keys | example-project |
| Feature state | PLANNING |
| Development overview | 尚未开始，未记录实现候选版本 |
| Integration / release overview | 尚未开始 |
| Current focus | 处理外部意图并开展详细设计 |
| Focused work / record | - |
| State maintainer / access | 由调用方提供 |
| Authority source / access | 由调用方提供 |
| Next action | 取得 INT 来源，安排设计工作 |
| Blocker / release condition | - |

## 入口

- [设计索引](DESIGN.md)
- [任务索引](TASKS.md)

## Repository 状态与 Project 绑定

| Project key | Stable configuration | Repository / sync / integration status | Related work |
| --- | --- | --- | --- |
| example-project | ../../project/example-project/project.yaml | 未核实，尚未记录仓库观察结果 | - |

## 管理边界

当前仓库综合状态保存在这里；稳定的 remote/local 映射与基本规则仍保存在 Project YAML。汇总整体开发进展和跨任务阻塞，但不维护第二套任务台账。设计决定、任务状态/依赖、提交点和执行报告仍在各自详情与预览中，临时附件清单仍在 VERBAL 中。概况与来源冲突时应报告并核对，不用摘要覆盖详情。

不嵌入当前文档自身的 Git SHA。维护方式和同步由外部提供，Feature 目录不要求处于 Git 仓库。
