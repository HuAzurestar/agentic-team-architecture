# 工作流 01：例行知识管理（CKO 例行轮次）

> 把 CKO 的例行工作固定成一轮固定动作，按 **Autopilot**（低频，定期触发）执行，跑完归档、清理上下文。

## 目的

保持**内外信息畅通**：红线文档最新、可复用流程已整理、skill 状态清楚、外部资讯及时、架构仓库云端与本地同步。

## 触发

- 低频 Autopilot（定期推进 CKO 记录并清理上下文），见 [docs/08-bootstrap.md](../docs/08-bootstrap.md) §5。
- 也可手动触发（CEO / AS 提出）。

## 步骤

1. **红线手册核对**：读 [docs/07-redline-manual.md](../docs/07-redline-manual.md)，对照近期越权 / 升级事件，判断 S0/S1/S2 是否需要补充示例；不在手册的认定后回填（[工作流 04](04-escalation-triage.md)）。
2. **工作流整理**：把近期可复用的流程整理进 [workflows/](../workflows/README.md)；重复流程收敛，变更同步 docs。
3. **skill 维护**：按需制作 / 维护 skill（新增、改描述、停用废弃）；配置变更与 HR 协同（[docs/02-boundaries.md](../docs/02-boundaries.md) §1.6）。
4. **资讯获取 / 新闻快讯**：获取最新资讯，产出快讯；快讯对外发布前按红线手册判定（S1 对外口径）。
5. **架构仓库更新**：改动提交并 **push 云端**，再 **pull 回本地**（[工作流 03](03-iteration-sync.md)）。
6. **清理上下文**：归档本轮记录，控制上下文不过度扩张；可复用过程回填到本工作流。

## 出口物

- 红线手册最新版（vX.Y）。
- 工作流库 / skill 库 / 快讯 各一轮更新记录。
- 架构仓库云端与本地同 commit。

## 负责角色

- **CKO**：全程执行。
- **HR**：skill 配置协同。
- **CEO / AS**：需要确认的事项（如对外发布、配置变更）走汇报。

## 引用

- [docs/02-boundaries.md](../docs/02-boundaries.md) §1.6（CKO 职责与红线）
- [docs/05-iteration.md](../docs/05-iteration.md)（迭代节奏）
- [docs/07-redline-manual.md](../docs/07-redline-manual.md)（红线手册）
