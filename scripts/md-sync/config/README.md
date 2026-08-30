# 配置

Token 可以直接写在 `sync.yaml` 的 `token` 字段；也可以留空并使用环境变量：

```powershell
$env:YOUTRACK_TOKEN = "你的 Token"
```

`token` 优先于 `token_env`。包含真实 Token 的 `sync.yaml` 不要提交到 Git。

默认 `mode: remote_authoritative`，本地文件仅作为备份。

已有远端对象按 Markdown 元数据中的平台 ID 定位，不依赖固定的 `project_id`。项目字段属于文档元数据；只有未来显式支持创建新远端对象时，才需要额外配置创建目标。
