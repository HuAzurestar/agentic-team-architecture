# 可选 SonarQube 质量门禁

只有存在持续维护的 SonarQube Server/Cloud 项目、支持的语言分析器、可接受许可证/版本、runner 网络、凭证和团队负责的 Quality Gate 时才使用。它只能补充，不能替代编译器、测试、linter、sanitizer、依赖/安全工具、Lean 证明信任检查或 TeX 构建。

在完成生成 coverage 和 compilation data 所需构建/测试后分析。new-code/blame 分析需要时使用完整 Git 历史；token 放入平台 secret store；固定 scanner integration；只有理由充分时排除 generated/vendor/build 输出；绝不上传密钥。Monorepo 可能需要按许可能力拆成多个 Sonar project/job。

GitHub 上，可用时通过官方支持的 GitHub App/integration 绑定 SonarQube，启用 PR analysis/decoration，并可选择把 `SonarQube Code Analysis` 设为 Ruleset/status required check。优先使用原生 PR Quality Gate 回报；只有确实需要同步阻断时才用 `sonar.qualitygate.wait=true`，尤其适用于部署前。

Gitee 不在 SonarQube 官方原生 DevOps 绑定列表中。在 Gitee Go/外部 CI 运行相应 scanner，显式传入 PR 参数，需要阻断时等待 Quality Gate。不能承诺原生 PR decoration；自定义 Gitee status/comment adapter 属于可选项，必须单独保护和维护。

先以只报告模式采用。只有 Quality Gate 已针对 new code 调优、基线已理解、服务中断/超时行为已定义且误报可控后，才升级为 required。不能把覆盖率百分比单独当正确性目标，也不能让生成代码扭曲门禁。
