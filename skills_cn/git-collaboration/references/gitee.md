# Gitee 协作与 CI/CD

本文件用于 Gitee 仓库。先识别社区版、企业版/专业版、Gitee Go、私有化版本或外部 CI；Issue、保护规则、流水线、制品、审批和 API 能力随产品/套餐变化。不能假定 GitHub 文件或设置在 Gitee 生效。通过 [platform-capabilities.md](platform-capabilities.md) 重新核对当前声明。

## 可追溯性与模板

应用 [branches.md](branches.md)：每个普通分支为 `<prefix>/<issue>-<summary>`；Gitee Issue 存在、可执行且具有映射的主类型 label；Commit 和 PR 标题使用相同 Issue 和映射 type；PR 正文引用/关闭该 Issue。

Gitee 公开文档中的社区模板约定主要按 locale 区分：

```text
.gitee/ISSUE_TEMPLATE.zh-CN.md
.gitee/ISSUE_TEMPLATE.en.md
.gitee/ISSUE_TEMPLATE.zh-TW.md
.gitee/PULL_REQUEST_TEMPLATE.zh-CN.md
.gitee/PULL_REQUEST_TEMPLATE.en.md
```

不能声称它们提供 GitHub 式多 YAML Issue Forms。实际 Gitee 产品支持多工作项模板/type 时，为每个主类型分别配置；否则在每个 locale 模板提供类型选择器，要求 `[Bug]`、`[Feature]`、`[Proof]`、`[Paper]` 等权威标题前缀，Triage 时应用恰好一个主类型 label，并链接各类型说明。流水线/API policy check 强制 type ↔ branch ↔ commit ↔ PR 一致。

使用 Gitee 保护/只读分支规则保护 `main` 和其他稳定分支：限制 push/merge 人员，要求 PR 审查及可用流水线/质量门禁，并记录当前产品无法自动执行的行为。

## Gitee Go 或外部 CI/CD

可用且合适时使用 Gitee Go；它支持 YAML/可视化编排、手动/自动/定时触发、串并行 stage、质量/人工门禁、构建及部署插件。否则通过 Gitee webhook/status API 接入获批外部 CI。执行本 Skill 定义的完全相同语言命令。

```text
policy -> language jobs -> integration -> required aggregate
                                      -> package/release/deploy（可信 ref）
```

`policy` 查询 Gitee Issue 状态/type，并验证分支、Commit、PR 链接/模板。检测到时分别运行 Python、C/C++、Java、Shell、Lean 和 TeX job。TeX 始终发布短期 PDF artifact 或按 commit 标识的对象；版本 tag 通过可用 Release/制品存储发布不可变 PDF/源码/校验和。包、二进制和容器只构建测试一次，存入可用 Gitee/外部 registry 后原样晋级。

## 可选 Open-Code-Review 与 SonarQube

满足 [github.md](github.md) 中隐私、凭证和成本条件时，可以考虑阿里 `open-code-review`。其 CLI 支持 base/head 范围和 JSON 输出，因此可能在具有完整 Git 历史的 Gitee Go 或外部 runner 上运行；这是自定义集成，并非有文档支持的原生 Gitee 能力。先在无密钥 smoke test 中证明可用，不能承诺原生 PR feedback。默认只作建议；由独立最小权限步骤发布脱敏摘要/report，绝不向不可信 Fork 代码暴露凭证。

SonarQube 官方原生 DevOps 平台绑定列表不含 Gitee，但仍可在 Gitee Go/外部 CI 中扫描，并通过等待 Quality Gate 让 job 失败；PR 分析时显式传入 PR key/base/branch 参数。不能承诺原生 Gitee PR decoration。只有部署方实现并保护相应 adapter 时，才通过 Gitee API 发布脱敏链接/摘要或 status。参见 [sonarqube.md](sonarqube.md)。

## 镜像

GitHub 与 Gitee 镜像同一仓库时，指定一个 Issue、PR、tag、Release 和部署权威来源。不能创建互相竞争的 Issue 编号，也不能在同一版本下独立构建两套制品。镜像验证可以重跑确定性检查，但镜像 Release 要记录权威 URL 和源 SHA。
