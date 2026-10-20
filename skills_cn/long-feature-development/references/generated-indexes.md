# 生成式索引与受保护区块

初始化索引布局、更新预览/依赖拓扑/附件清单，或排查生成内容漂移时读取。

## 固定位置

每份文档保留 Feature 标题和简短介绍。每组 marker 各占独立一行，直接放在指定 H2 标题之后，中间只允许空白行；每组唯一、顺序正确，且不能跨章节。

| 文档 | H2 章节 | 生成区名称 | 来源 |
| --- | --- | --- | --- |
| DESIGN.md | preview-table | design-preview-table | design/*.md YAML |
| TASKS.md | preview-table | tasks-preview-table | tasks/*.md YAML |
| TASKS.md | dependency-topology | tasks-dependency-topology-mermaid | 任务 ID、标题、状态及 depends on |
| VERBAL.md | preview-table | verbal-preview-table | gists/ 下实际存在的文件 |

区块使用 `<!-- name:start -->` 和 `<!-- name:end -->`，内部不手工维护。生成章节后用 `## complementary` 按日期保留手写补充；标题、介绍与补充均不属于脚本修改范围。设计/任务事实仍保存在详情中，不在索引里维护重复台账。

表格和章节不使用独立横线包裹；仅 YAML frontmatter 保留分隔行，Markdown 表头分隔行仍是表格所需语法。

## 生成与更新

按 [SKILL.md](../SKILL.md) 的固定步骤，每次内容/状态操作后使用[索引生成器](../scripts/feature_indexes.py)同步，再运行记录校验；不是可省略的收尾。内容由 agent 基于模板编写，脚本不创建新的 SOL、任务判断或决定：

```text
python scripts/feature_indexes.py path/to/feature --check
python scripts/feature_indexes.py path/to/feature --write
python scripts/feature_indexes.py path/to/feature --only tasks --write
python scripts/feature_indexes.py path/to/feature --only verbal --write
```

默认只读检查，索引过期返回非零；显式 --write 只替换生成区正文。--only tasks 同时更新任务表和依赖图。修改详情或附件目录后运行脚本，不手动粘贴维护表格或图。

--write 属于索引生成器，只授权写派生区，不写业务正文；--format json/text 属于记录校验器，只选择报告格式。生成器本身始终输出 JSON 报告，不接受 --format，也不把这些参数解释为内容创作模式。这里的“同步”是文件内派生索引同步，不是默认 Git pull/push 或远端同步。

依赖图保留孤立任务，箭头由依赖指向消费方；它描述依赖，不是另一套生命周期或公司固定流程。任务引用未知依赖或成环时，生成前拒绝。

附件清单只列相对路径、字节大小和文件系统修改时间（UTC），不读取内容，不编造描述、创建时间、保留策略或审批状态；不跟随符号链接。扫描不完整是错误，不算成功的空目录。

VERBAL/gists 仍可丢弃：gists 不存在时生成空表；all 模式跳过不存在的 VERBAL，不重新创建。显式 --only verbal 要求该索引文件存在。正式 Feature 校验不依赖附件索引或其当前内容。

## 安全与修复

写入前预检全部选定目标和生成区。marker 缺失、重复、反向、行内或位置错误，跨章节、来源记录不合法或附件扫描不完整，均先报错。脚本不自动补标题、不用整份覆盖来修布局；保留原文，只修复预期标题/marker 后再运行。

区块外内容逐字节保留，包括 UTF-8 BOM 和换行；结果相同不重写。输出必须是选定 Feature 下直接、非符号链接的文件。单文件原子替换并核对并发修改，但不提供跨文件事务，也不替代维护者的写入协调；中断或并发冲突后核对结果并重新检查，不能假设所有文件都已更新。

生成和结构检查都不修改详情 YAML、STATUS、Project 配置或附件正文，不隐含 commit、网络调用、调度或审批。[记录校验器](../scripts/contract_check.py)核对正式预览/拓扑；--render design/tasks/topology 仍只是输出诊断内容。

实现边界见 [index_blocks.py](../scripts/index_blocks.py)（相对 skill 根为 `scripts/index_blocks.py`），行为测试见 [test_feature_indexes.py](../scripts/test_feature_indexes.py)；模板已经提供正确的固定章节。
