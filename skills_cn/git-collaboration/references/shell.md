# Bash 与 POSIX Shell 检查

根据 shebang 和仓库政策识别每个脚本声明的解释器。不得在 `sh` 下运行 Bash 专用代码，也不能静默把 POSIX 脚本改写成 Bash。发现脚本时包含没有 `.sh` 后缀的可执行文件，同时排除 vendor/generated 文件。

基准门禁：

1. 使用脚本声明的 shell（`bash -n`、`dash -n` 等）和/或选定静态解析器解析每个脚本；
2. 以正确 dialect 运行 ShellCheck，并使用已提交、理由明确且范围很小的排除策略；
3. 使用固定版本 `shfmt -d`，按照 `.editorconfig` 或有文档记录的参数检查格式；
4. 使用 Bats 或现有 harness 运行单元/集成测试，隔离文件系统和环境副作用；
5. smoke-test 公共 CLI 的 help、非法输入、退出码、stdout/stderr 分离、引用、空白/路径边界及 cleanup/trap 行为；
6. 存在支持承诺时，在每种支持 shell 和 OS 上运行，不能假定只有 Bash/Linux。

绝不能打印密钥，也不能在凭证附近使用 `set -x`。把下载即执行、未检查变量、不安全临时文件、错误的 `set -e` 假设、pipeline、glob 和破坏性路径作为审查风险；如果会改变预期语义，不得机械强加 `set -euo pipefail`。

Shell 脚本通常没有编译型 CD。如果作为归档、安装器、容器或 Release bundle 的一部分交付，应打包并测试该准确制品，保留 executable mode，按需要生成校验和/签名，并在隔离环境测试安装和卸载。
