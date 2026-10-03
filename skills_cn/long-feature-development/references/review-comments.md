# 可编辑审查意见

`review_comments.py` 提供有界内存 Markdown 编解码、筛选和转换预览，不读取远端权威源、不发布意见、不改变点决定/任务、不评估质量，也不因记录写着 VERIFIED 就证明已复核。这些流程集成仍需完成。

新记录包含 `rv_id=RV-<UUID>`、`Target={feature,ref,selector?}`、`Basis={source_key,source_text,git_basis?,line_start?,line_end?}`、`Status`、`Comment` 及可选 `Resolution`/`Verification`。状态为 PENDING、ADDRESSED 或 VERIFIED。主键为 `(feature,reviews_ref,rv_id)`；意见文档引用独立于被评论目标。`new_review` 只分配一次新 UUID，发布结果不明时须先查同一 UUID，不能直接新建。

## 安全 Markdown 格式

文档以 `# Reviews` 开始。每个 `## RV-<UUID>` 块包含 `- Status: PENDING` 及 Target/Basis 点分标量字段。所有标量均为 JSON 字符串，包括十进制行号，例如 `- Target.feature: "PIRC-31"`、`- Basis.line_start: "1"`。存在 Git basis 时必须为实际完整 SHA，不能拿 REVIEWS 文档版本代替。原文不放在标量中，而置于 `### Source` 下；Comment、Resolution、Verification 使用同名三级标题。每一文本行（含空行和看似 Markdown 标题的内容）均加 `> ` 前缀。换行语义为 LF，接受 CRLF 文档输入并保留原件。未知/未引用正文、重复字段或 ID、无效版本和跨 Feature 内容失败关闭，不静默丢弃。

`parse(text, feature=..., reviews_ref=...)` 返回记录、线性身份/目标索引、原文及摘要。`select(parsed)` 默认 PENDING；显式状态筛选读取指定状态。指定 RV ID 且未指定状态时读取任何状态，请求不存在的 ID 为错误。

## 旧格式与转换

已知旧 `OPEN/open`、小写状态及 `closed` 仅在内存映射。`- Basis: <文本>` 保存在 legacy 元数据，其来源未解析，不猜测。旧记录附 `_legacy` 标记，不能直接 render。保留原件，在提议副本中明确解析 Basis、移除旧标记，并在编辑前调用 `preview_conversion(original, proposed, ...)`。预览保留原件摘要、要求身份不变、返回完整新文档与有界前后变更区间，始终为 NOT_APPLIED。截断差异不等于完整审阅；后续授权条件写之前须展示完整受影响材料。移除标记不代表授权，也不证明用户看过预览。

每次最多 1,000 条/4 MiB，解析和渲染各有 2 CPU 秒限制。编解码器没有 I/O 或日志，尚未实现平台权威读取、条件写、草稿恢复、过期依据核对或 Agent 消费确认。
