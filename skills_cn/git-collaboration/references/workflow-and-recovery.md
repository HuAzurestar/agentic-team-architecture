# Git 工作流与恢复

本规范吸收了 [Galaxy-Dawn/claude-scholar 的 git-workflow](https://github.com/Galaxy-Dawn/claude-scholar/tree/main/skills/git-workflow) 中实用的操作思路，同时保留本 Skill 更严格的 Issue 强绑定和 trunk-based 默认策略。采用时核对的上游 revision 与许可证 notice 见 [third-party-notices.md](third-party-notices.md)。

## 先选择分支拓扑

默认使用受保护的 `main` 和短生命周期 Issue 分支。只有仓库明确需要独立集成线时才增加 `develop`。下列流程以 `<base>` 表示仓库已经确定的集成分支，因此同时适用于两种拓扑。

记录每类分支的来源、合入目标、合并方式和删除规则。不得把 `master + develop` Git Flow 机械复制到直接从 `main` 发布的仓库。

## 日常 Issue 驱动开发

```bash
git switch <base>
git pull --ff-only origin <base>
git switch -c feature/142-lean-parser

# 完成一个逻辑变更，精确暂存，并运行权威检查。
git add <paths>
git diff --cached
git commit
git push -u origin feature/142-lean-parser
```

尽早创建 Draft PR。强制 Issue 类型、分支前缀、Commit 类型、PR 标题及关闭/引用 Footer 一致。只有必需检查和评审通过后才能通过受保护目标分支合入，随后删除主题分支。

在受保护或共享分支使用 `git pull --ff-only`，避免 pull 意外制造 merge commit。更新私有主题分支时先 fetch，再按仓库策略 rebase 或 merge：

```bash
git fetch origin
git rebase origin/<base>       # 仅限私有主题分支
# 或：git merge origin/<base>  # 共享主题分支或保留拓扑的策略
```

不得 rebase 受保护分支或已被他人使用的提交。确需改写明确属于私有开发者的远程分支时，只能使用 `git push --force-with-lease`，不得使用普通 `--force`。

## 合并策略

- 中间提交没有独立价值时优先 squash merge；必须验证 PR 标题和正文，因为它们会形成落地主提交。
- 每个提交都经过精心整理且可独立成立时可用 rebase merge。
- 只有分支拓扑或发布列车本身有保留价值时才允许 `--no-ff` merge commit。
- 受保护分支必须保持绿色；不得用本地手工 merge 绕过 PR 门禁。

仓库必须选择一种默认方式，在托管平台中对应配置，并让 Commit 校验策略与之兼容。

## Hotfix 流程

先创建 Bug Issue，并添加 `bug` 及仓库规定的紧急度/严重级别标签。从已部署稳定 Tag 或仍受支持的 Release 分支创建 `hotfix/<issue>-<summary>`，不得盲目从最新开发分支开始。

```bash
git fetch origin --tags
git switch --detach <deployed-tag>
git switch -c hotfix/317-auth-bypass
# 修复、测试，并按 #317 fix(auth): ... 提交
git push -u origin hotfix/317-auth-bypass
```

通过加急但仍受评审的 PR 合入。所有发布门禁通过后为修复版本打 Tag。使用 PR 或可追踪的 cherry-pick 将同一修复前向移植到每条受支持的开发/发布线；不得让 `main`、`develop` 和受支持 Release 分支长期不一致。

## Release 流程与标签

项目适用时采用语义化版本：

```text
vMAJOR.MINOR.PATCH[-PRERELEASE]
```

只有确实需要在继续开发的同时进行稳定化时才创建 `release/<version>`；否则直接从 `main` 上验证完成的提交发布。Release 分支只能包含批准的发布修复、版本元数据、CHANGELOG 和生成的发布产物。

在精确的已验证提交上创建附注标签，并尽量签名：

```bash
git tag -s v1.4.0 -m "release: v1.4.0"   # 无法签名时使用 -a
git push origin v1.4.0
```

不得移动已经发布的 Tag；应发布新版本纠正。只从 Tag 构建一次，在平台支持时附带校验和及来源证明，并在各环境之间提升同一不可变产物。

## 冲突处理

编辑前先确认当前操作和冲突路径：

```bash
git status
git diff --name-only --diff-filter=U
```

有意识地解决内容、删除冲突标记、运行受影响语言的语法/格式/测试，只暂存已解决路径，然后继续：

```bash
git add <resolved-paths>
git merge --continue       # merge
git rebase --continue      # rebase
git cherry-pick --continue # cherry-pick
```

无法确定预期结果时中止操作：

```bash
git merge --abort
git rebase --abort
git cherry-pick --abort
```

不得在未确认操作语义时选择 `--ours` 或 `--theirs`；它们在 rebase 中尤其容易产生误解。能够从已评审源文件重新生成时，不得单独手工解决生成文件冲突。

## 安全纠正与恢复

- 只能 amend 或交互式 rebase 尚未发布的私有提交。
- 已发布提交使用 `git revert <commit>` 反向提交，保留审计历史。
- 意外丢失本地引用时先用 `git reflog` 定位，再进行其他状态变更。
- Stash 只用于短期上下文并写清名称：`git stash push -u -m "issue-142 parser WIP"`；`pop`/`apply` 前先检查。
- 使用 `git log --oneline origin/<base>..HEAD` 检查待推送提交，使用 `git diff --cached` 检查暂存内容。
- 将 `reset --hard`、`clean -fdx`、历史过滤、Tag 删除和远程强推视为破坏性操作；执行前必须验证精确目标并获得授权。

## `.gitignore` 与生成物

根据检测到的工具构建 `.gitignore`，不得复制一份“万能模板”。忽略可重建缓存、本地环境、编辑器状态、密钥、日志和一次性构建输出。不得仅因宽泛模板就忽略必需锁文件、源资产、受控测试夹具或发布输入。

修改忽略规则前使用：

```bash
git check-ignore -v <path>
git status --ignored
```

忽略路径不会移除已经跟踪的文件。`git rm --cached` 必须单独审查；未验证精确目标时不得递归执行。个人排除项应写入 `.git/info/exclude` 或用户级全局 excludes 文件，不应进入共享项目规范。
