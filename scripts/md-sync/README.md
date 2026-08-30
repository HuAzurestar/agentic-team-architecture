# Markdown Multi-Remote Sync

本目录定义以 Markdown 为交换格式的多端文档同步协议。架构文档以远端 GitHub 为主源，本地 Markdown 仅作为工作副本或备份。

## 基本文档格式

```yaml
---
doc_type: markdown

id:
  general: "req-2026-001"
  github_issue: ""
  github_pull_request: ""
  youtrack_issue: "DEMO-25"
  youtrack_article: "183-1"

relations:
  blocks:
    youtrack_issue:
      - DEMO-19

platform:
  youtrack_issue:
    title: "需求标题"
    project: DEMO
    priority: P0

sync:
  primary: youtrack_issue
  order:
    - youtrack_issue
    - youtrack_article
    - github_issue
    - github_pull_request

project: "finance-system"
priority: "P0"
type: "feature"
assignee: ""
status: "in_progress"
parent_issue: "req-2026-000"
related:
  - "req-2026-001-analysis"
  - "req-2026-001-test"
---

# 文档标题

正文使用标准 Markdown。
```

不存在的平台对象不写对应字段。例如没有 GitHub Issue，就不写 `github_issue`，不使用空字段占位。

## ID 与关系

- 当前不要求 `general_id`；平台尚未建立统一基准时，直接使用平台 ID。
- 平台 ID 用于定位对应的远端对象。
- 关系按 `relations.<关系>.<平台>` 保存，例如 `relations.blocks.youtrack_issue`。
- 同步器根据 `general`、平台 ID 和配置中的地址查找对象。
- `sync.primary` 是远端主端，`sync.order` 是远端读取优先级。

## 同步方向

```text
sync-to-remote：本地正文 → 主端 → 副端
sync-to-local：主端 → 备用端 → 本地备份
```

主端失败时整体失败，副端失败时返回 `PARTIAL_SUCCESS`，不能静默报告成功。

```powershell
python -m src.controller.main download --remote youtrack_article:DEMO-A-3 documents/example.md
python -m src.controller.main upload documents/example.md
python -m src.controller.main sync-from-remote documents/example.md
python -m src.controller.main sync-to-remote documents/example.md
```

新建远端对象时必须显式指定目标，使用三级路径：

```powershell
python -m src.controller.main upload documents/example.md --target youtrack/issue/DEMO
python -m src.controller.main upload documents/example.md --target youtrack/article/DEMO
```

格式为 `<平台>/<对象类型>/<项目>`。`upload` 不更新已有对象；已有对象使用 `sync-to-remote`。

## 同步原则

```text
读取 general ID → 读取远端配置 → 按平台 ID 查找 → 下载/更新远端内容 → 保存本地备份
```

默认采用 `remote_authoritative`：远端是事实来源，本地文件不能无条件覆盖远端；找不到远端对象时默认不自动创建。

## 当前格式

当前唯一支持的格式是纯文本 Markdown，YAML Front Matter 中使用：

```yaml
doc_type: markdown
```

暂不定义 `requirement`、`analysis`、`schema` 等专用类型。未来增加专用格式时，再单独扩展解析规则。

## 实现边界

- `src/doc/`：Front Matter 和 Markdown 解析
- `src/providers/`：YouTrack、GitHub 等平台适配器
- `src/controller/`：同步中控、ID 解析和关联处理
- `src/config/`：配置文件加载代码
- `config/`：实际平台地址、认证变量和同步策略；不固定绑定 YouTrack 项目
- `documents/`：本地备份文件目录
- `backups/`：下载前的历史备份目录
