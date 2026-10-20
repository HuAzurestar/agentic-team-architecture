# 初始化 Feature

创建 Feature 首批记录时读取。已有记录或存在部分写入时，走[续接](continuity.md)与[恢复](checkpoints.md)，不用示例覆盖原文件。

## 输入与标识

取得外部 feature-key、管理根目录映射、获准范围、状态维护者/写入接口及授权来源。标识规则见 [SKILL.md](../SKILL.md#feature-标识)；缺 key 不表示可以发明 NO-FEAT 或使用 example-feature。访问/授权缺失仍是未决项，不能声称初始化状态已可执行。

## 准备记录

1. 确认给定 Feature 位置尚无现有记录，通过指定接口协调写入。按[记录规范](protocol.md)理解 schema，按[生成区规则](generated-indexes.md)准备索引布局。
2. 基于[模板](protocol.md#模板)准备 STATUS.md、DESIGN.md、TASKS.md，以及允许为空的 design/、tasks/ 目录。带上 VERBAL.md 模板作为临时附件索引；实际有附件时再建 gists/。VERBAL/gists 后续删除不影响正式记录。不要把 PROJECT.yaml 放进 Feature 目录。
3. 用外部 key 替换标题/STATUS 中的 example-feature，填写实际焦点、下一步、状态/授权入口及相关 Project 关联。去掉不需要的示例行、任务、设计点和关联，不把示例身份、仓库位置、请求或完成条件当成真实事实。保留章节与 marker，让生成器替换示例预览内容。
4. 只创建当前请求需要的记录。外部请求按[详细设计规则](decisions.md)保存 INT 的原话、来源和真实提出者。INT 为 RECORDED；新提案 REQ/SOL 为 PROPOSED，决定前决定字段为 null。初始化不要求编造 REQ/SOL，也不要求每个设计点都有一个任务。
5. 有初始任务时，按[任务规划](task-planning.md)复用公共任务模板，分配不冲突的内部 ID，填写范围、版本化输入、完成条件和依赖。未分派任务保持 PENDING，owner/时间为 null，不编造提交点。不为填满索引而复制示例 DECISION/FEEDBACK/GATE。
6. 复用已有稳定 Project 定义。获准新增映射时，基于 [PROJECT.yaml](../templates/PROJECT.yaml)在独立 project/<project-key>/project.yaml 中准备配置，替换示例位置并校验。缺映射时明确记录，阻止依赖该映射的仓库作业，不阻止无关记录准备。初始化不隐含克隆、搬迁或同步仓库。

## 完成初始化

按 [SKILL.md](../SKILL.md#每次操作的固定维护步骤)中的绝对路径命令运行索引生成与记录校验。全新 Feature 无需预校验：将首批记录作为一次协调操作准备，再执行这些收尾检查；成功初始化后遵守日常操作前后维护。涉及 Project 映射时传实际注册目录 --project-root。来源或布局错误修复前不声称成功，脚本不补业务事实。

标识/访问入口已明确、正式记录只保留实际范围内的事实、本地关联/依赖可解析、预览与来源一致且校验通过后，才算初始化完成。通过获准状态接口持久化，让 STATUS 指向当前工作与下一步。仓库/remote 不可核实的信息标为 unverified；结构成功不等于设计获批或获得执行/发布权限。后续任务走指定编排或[默认单任务闭环](task-workflow.md)。
