# TeX 与 LaTeX 检查

选择命令前，先确定根文档、引擎、参考文献后端、术语表/索引步骤和现有构建配方。优先使用仓库中已提交的 `latexmkrc`、`Makefile` 或项目任务，而不是写死一次编译命令。

与文档兼容时采用以下基准门禁：

1. 风格/静态检查：使用带项目配置和有说明的抑制规则的 `chktex`。
2. 可复现构建：使用所需引擎（`-pdf`、`-lualatex` 或 `-xelatex`）运行 `latexmk -interaction=nonstopmode -halt-on-error -file-line-error <root.tex>`。
3. 检查日志中的未定义引用、未定义 citation 和需要重新运行的信息；进程退出码为零并不能单独证明文档干净。
4. 将成功编译的 PDF 保存为可下载 CI artifact。为分支/PR 预览设置明确的短期保留时间，并在 artifact 名称或配套元数据中标识源 commit。

只有项目已经选用 `lacheck` 时才使用它；它与 ChkTeX 重叠，而且通常可配置性更弱。只有项目明确选择了 Tectonic 的 bundle/可复现模型，并确认其宏包覆盖充足时才使用 `tectonic`。

不要提交辅助构建文件。只有仓库政策明确要求跟踪 PDF 时才把生成 PDF 提交到 Git。如果 TeX CI 只报告编译成功，却不提供可检查的 PDF，那么该 CI 不完整：每次文档成功构建后都要上传 PDF artifact。Release 附加从 tag 构建的不可变 PDF。充分固定 TeX 发行版或容器镜像以保证构建可复现，同时保留计划内更新路径。

## PDF 交付与版本控制

- 每个 PR 和相关分支构建都编译 PDF，并上传短期预览 artifact。使用文档/语言、工作流运行号和 commit SHA 命名；它不是正式发布。由于可以从 commit 重建，保留期可以较短。
- 在 `v1.2.0` 或 `paper-v1.2.0` 等受保护版本 tag 上只构建一次，将 PDF 与所需源文件、参考文献和许可证文件打包，生成校验和，并把不可变压缩包及 PDF 附加到平台 Release。
- 从显式源文件或注入的 tag 元数据生成文档显示版本。CI 不得静默改写受版本控制的 TeX 源文件。
- 如果仓库发布持续更新的 latest PDF，应单独部署（例如 Pages），并标注源 commit。版本化 Release 保持不可变，确保被引用的历史版本可以恢复。
- CI artifact 只用于操作性预览；长期学术版本使用 Release asset 或专业归档仓库。正式发表时，在元数据中记录 DOI、期刊或 arXiv 标识，不能用 Git tag 替代这些标识。

多语言论文需要发现每个受支持根文档或 locale，分别构建和检查每种语言，使用无歧义 artifact 名称（例如 `paper-zh-<sha>.pdf`、`paper-en-<sha>.pdf`），并在同一个版本化 Release 中一起打包所有必需语言版本。如果标题、版本字符串、定理编号、参考文献数据或生成表格应保持同步，则增加跨语言一致性检查。
