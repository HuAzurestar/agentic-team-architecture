# Java 检查

识别支持 JDK、Maven/Gradle wrapper、多模块结构、框架、格式/静态分析插件、集成测试生命周期、打包形式及部署目标。存在已提交 `mvnw`/`gradlew` 时使用 wrapper，并按项目政策验证其完整性；不能随意使用 runner 自带 Maven/Gradle 版本替代。

基准门禁：

1. 按项目配置的 release/source/target 级别编译；
2. 运行已经选定的格式/风格门禁（例如 Spotless 或 Checkstyle），以及已配置的 SpotBugs/Error Prone 等静态分析；
3. 运行单元测试并保存标准测试报告；
4. 在构建工具预期生命周期（`verify` 或已声明 Gradle task）运行集成测试，只有必要时才配置真实服务依赖；
5. 打包 JAR/WAR/distribution，并对该制品执行 smoke test，不能只测试 IDE/test classpath；
6. 项目风险和发布政策要求时，运行依赖扫描/SBOM。

Maven 优先使用 wrapper；绑定了集成与验证插件时，生命周期运行到 `verify`。Gradle 使用 wrapper 和项目 `check`/`build` task，不能猜测零散 task。测试声明支持的 JDK matrix；昂贵分析通常只在标准 JDK 运行一次，除非兼容性要求覆盖多个版本。

CD 只发布真实交付物：Maven 兼容包、签名归档、容器或服务 bundle。支持时使用可信短期发布凭证，区分 snapshot 和 release 仓库，验证版本与 tag 一致，并晋级同一个已测试制品。不得从 PR build 直接部署。
