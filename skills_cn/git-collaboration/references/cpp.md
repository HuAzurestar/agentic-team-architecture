# C 与 C++ 检查

识别声明的语言标准、编译器支持矩阵、构建系统、依赖管理器、preset/toolchain 文件、测试框架及生成的库/二进制。使用仓库权威构建命令；不能只为统一 CI 而替换 CMake、Meson、Bazel、Make、Conan 或 vcpkg。

没有更强现有约定时采用以下基准门禁：

1. 使用固定版本 `clang-format` 和已提交 `.clang-format` 做格式检查；
2. 配置并编译且启用警告；只有受支持编译器/平台基线干净后才把警告升级为错误；
3. 基于准确 compilation database 运行 `clang-tidy` 或项目选定静态分析器；
4. 运行单元测试，并在发现零测试时失败（CMake 支持时使用带 `--no-tests=error` 的 CTest）；
5. 对实际构建出的库或可执行文件运行 integration/CLI 测试；
6. 在受支持平台至少维护一个 sanitizer 配置，通常是 AddressSanitizer + UndefinedBehaviorSanitizer；并发代码可行时增加 ThreadSanitizer；
7. 分发库或应用时构建 install/package 目标，并验证使用者能够消费已安装制品。

项目选择 CMake preset 时，使用 `CMakePresets.json` 及对应 test/package preset；不要提交用户本地 `CMakeUserPresets.json`。CI matrix 只覆盖承诺支持的编译器/OS/标准组合：一个快速标准 job 可运行格式/静态分析，build/test 覆盖支持矩阵。Sanitizer 二进制属于测试制品，不是生产 Release。

CD 由交付物决定。Tag Release 为每个受支持平台构建、测试，并按需要 strip/sign，生成校验和后发布库/二进制/归档。记录编译器、标准库、ABI、目标架构、运行时依赖、源 tag/SHA 和构建选项。不能把单个 Linux 构建称为可移植 C/C++ Release。
