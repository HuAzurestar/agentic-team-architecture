# 独立 Skill 的安装与生命周期

## 运行环境

本候选使用 Python 3.12。作者回归已在 Windows/NTFS 的 CPython 3.12.10 和 Linux 的 CPython 3.12.15 上执行；这是已测试环境说明，不是对所有 3.12 补丁版本、操作系统或文件系统的兼容保证。其他 Python 版本及 macOS 未由这些测试验证。Git 必须位于 PATH。安装前运行 `python --version` 和 `git --version`，将实际输出与固定产品 SHA 一同记录；下述检查使用同一个 Python 可执行文件。helper 使用 Python 标准库；仓库独立的 skill-audit 工具有自己的依赖。

## 安装与验证

首次创建项目管理记录时，遵循[首次记录初始化](bootstrap.md)。安装与 feature 初始化是两件事：严格任务恢复要求干净的初始检查点；创建检查点不会确认需求或授予执行权限。

`context.py` 与 `task_context.py` 的命令行 stdout/stderr 使用 UTF-8 和 LF，包括 Windows 重定向管道；消费者必须按 UTF-8 解码。中文路径及 Unicode 背景无需设置 `PYTHONUTF8` 或 `PYTHONIOENCODING`。上下文大小预算衡量 JSON 载荷；末尾 LF 是传输分隔，不属于选段内容。

使用仓库的 `skills_cn/long-feature-development` 中文目录（英文入口为 `skills/long-feature-development`），按宿主的目录式 Skill 安装机制部署。无需安装器服务、SMMD、UI、Docker 或 provider 凭据；本地 helper 需要 Python 和 Git。使用明确的完整 40 位 commit，并在安装目录外记录版本；移动分支不是安装版本。发布/测试证据必须注明实际测试的 commit。

全新安装时，将 `https://github.com/HuAzurestar/agentic-team-architecture.git` 克隆到新 checkout；必要时获取目标已发布 ref，然后运行 `git checkout --detach <full-sha>` 并检查 `git rev-parse HEAD`。将所选 Skill 的完整目录（含 `references`、`templates` 和 `scripts`）复制到新的宿主 Skill 目录。目标必须独占创建：目录已存在时先检查冲突，不得据此覆盖。项目 Markdown、Git 仓库、凭据和背景材料保留在程序目录外。

宿主没有安装机制时，可以把 checkout 作为显式 Skill 根：读取 `SKILL.md`，执行 `python scripts/context.py --task-ref <project-directory> --purpose development`，并对真实项目执行 `python scripts/task_context.py <feature-directory>`。这是显式根目录方式，不证明宿主会自动发现 Skill。

验证已安装副本，而不只是 checkout。启动新进程/会话，读取其 `SKILL.md`，运行其 `scripts/test_context.py`，并取得无背景的 DIRECT 上下文。随后用明确路径选择真实背景，以项目实际 Git refs 执行任务恢复。单独记录实际宿主发现行为：子进程只能证明新进程行为，不能证明 GUI/Agent 会话发现了 Skill；没有观察就不得将后者记为通过。

## 升级、回退与退出

升级时，把新的固定版本安装到独立兄弟目录，保持旧程序目录不变；比较版本、运行检查，再用宿主正常机制明确选择/激活新根。不得递归覆盖旧目录，否则可能残留新版已删除的脚本。若宿主要求固定目录名，先关闭使用它的会话，把旧程序目录移到明确的备份名称，再选择完整新目录。不得移动项目管理根或凭据目录。

回退时，选择保留的旧程序根并重启会话，核验版本，然后对同一个外部项目执行恢复。旧版本可能合理拒绝新版记录格式；应检查兼容性失败，不得重写记录来制造回退成功。退出时在宿主取消选择 Skill，或停止显式调用。删除程序文件是可选操作，须使用精确、已验证的纯程序目标。升级、退出和回退都不得删除用户记录、备份或凭据。

安装测试位于 `scripts/test_installation.py`，仅使用临时目录，检查真实目录复制、新进程执行以及外部文件不变。宿主激活和完整 F03/F04 恢复/审查接受需要各自的实际观察；这些测试不代替它们。
