# Feature 记录、预览与 Project 引用

调用方提供管理根位置、授权、状态接口及特定编排要求；未指定编排时使用[默认单任务闭环](task-workflow.md)。模板定义共享记录，不定义公司策略。

## Feature 与 Project

`<Project-Manage>/feature/<feature-key>/` 管理跨一组 Project 和需求的持久工作。`<Project-Manage>/project/<project-key>/project.yaml` 标识单个 Repository 的稳定 remote/local 映射与基本规则。Feature 内容不要求处于 Git 仓库。

保留 DESIGN/design、TASKS/tasks、临时 VERBAL/gists 与 STATUS，不再增加独立的 intent、decision、feedback、acceptance、evidence 顶层模块。

feature-key 只能来自用户、平台或外部上游；编排者和其他 agent 不分配、推测或生成临时 key。缺失时不创建 Feature 目录；模板中的 example-feature 必须替换为外部已给出的标识。内部设计点/任务 ID 与 Feature key 不同。

具体 INT/REQ/SOL、任务正文和业务判断由 agent 基于模板编写；脚本仅同步已有事实的派生展示、校验结构或定位，不创作内容。每次操作遵守 [SKILL.md](../SKILL.md) 的固定维护步骤；普通交流方式属于外部编排者，只有策略要求用户决定的 GATE 绑定请求/答复协议。

## STATUS 综合状态

STATUS.md 集中管理当前 Feature 涉及的 repository、feature、dev 等综合状态，包括仓库关联与同步/集成概况、Feature 进展、开发概况、当前焦点、跨任务阻塞和下一步。它是整体管理入口，而不只是恢复工作时的摘要。

只保存整体状态和必要的关联链接：设计正文与决定元数据由 design/ 承载，DESIGN.md 提供预览；任务状态、依赖、提交点与执行报告由 tasks/ 承载，TASKS.md 提供预览；临时附件目录由 VERBAL.md/gists/ 承载。STATUS 不复制这些索引、明细或附件清单，也不成为第二套设计/任务状态台账。摘要与详情冲突时报告并核对，不用摘要覆盖详情。

Project YAML 仍只保存稳定仓库配置；当前仓库综合状态放在 Feature 的 STATUS 中。状态由谁维护、如何写入和同步仍由外部提供；综合状态的项目按实际工作需要增减，不要求固定公司流程。

## DESIGN 元数据与预览

`DESIGN.md` 预览 `design/<id>.md`；详情为带 YAML frontmatter 的 Markdown。REQ-001、SOL-001、INT-001 等稳定 ID 与 requirement、solution、intent 等 type 描述分开。

通用字段为 id、title、type、state、decided by、decided at、decided with。title 概括当前点的具体内容；INT 的 title 是具体意图缩略，不是“原始意图记录”之类的通用标签。记录的 title 及与之匹配的 H1 展示标题属于描述文字，提及作为工作对象的临时路径不等于把它作为证据依赖；正式引用与其余正文仍遵守证据限制。决定字段按类型解释：

- INT：意图提出并留存时为 RECORDED，decided by 必填，标识原始提出者，不是代录者或审批人。身份可以是人、同事、客户、agent、平台或组合，保留提供的身份原文，不规定邮件或账号格式。decided at 可记录已知提出时间，decided with 可记录已知提出原因；未知时可分别为 null，不套用审批三字段同时填写规则，也不新增等待审批步骤。
- REQ/SOL 及其他需判定点：未决定时三个字段为 null；作出决定时同时填写实际确认者、时间和强制判定理由。指定 agent 可按适用 AGENTS.md 的授权确认，遵守[角色授权与重开规则](confirmation.md)，授权不豁免理由。

INT 原话保留在模板的 `## 外部原始说明` 章节（英文模板为 `## Original external wording`）。校验器将该章节及保留历史版本中的对应章节视为来源原文，范围到下一个同级或更高级标题为止，包括空 ATX 标题、以 = 或 - 作下划线的 Setext 标题；代码围栏中的示例标题不会结束该范围。原话提及临时附件路径不代表把附件作为输入或证据。正式引用元数据和其余正文仍不能依赖临时材料，其他记录类型不适用原话章节例外。

例如 decided by 可以是 myname@mycompany.com、mycollabo@collabo.company.com、codex sol 6.1 high 或 codex luna 6 xhigh & multica。这些是身份示例，不是固定枚举；不能编造未知提出者。source 用来保存来源位置或传递上下文，无需再复制一份 author。

其他 YAML 字段属于专用信息，压缩到 detail spec。例如：

- requirement：intent related to。
- solution：requirement related to，也可有 intent related to。
- intent：原始 source 及其他必要来源；intent type、initial opinion 等分类/初始意见可选，由外部接入者决定是否提供。
- 各类型均可补充 revision、领域说明和关系。

关系可以是单个 ID、ID 列表，或含 id/revision/location 的版本化引用。裸 ID 表示当前关系，不代表冻结版本。例如 SOL-001 中的 `requirement related to: [REQ-001]` 预览为 `relate to requirement: REQ-001`；版本化关系也显示 revision。

INT 保留 review-intent、test-intent、refactor-intent、requirement-intent 等外部原话；加工为核心需求和解决方案属于详细设计，不等于自动批准或开始实施。

沿用适用的 PROPOSED、REOPENED、CONFIRMED、REJECTED、OUT-OF-SCOPE、INFEASIBLE、RECORDED 状态。不要求 class 列；额外分类可作为专用字段。

预览固定为：

```text
## preview-table

<!-- design-preview-table:start -->
| id | title | type | state | decided by | decided at | decided with | detail spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
<!-- design-preview-table:end -->
```

ID 链接到详情。YAML 是状态来源，表格是审核预览；专用字段自动摘要，不用增加表格列。detail spec 省略 null/空值，history 仅显示版本标签。每个完整 detail spec 单元格共用最多 50 个文本字符（包含字段标签和末尾 ...）、最多 3 个生成行的限制；换行和 HTML br 计作行边界，Markdown/HTML 转义不占文本预算。超过任一限制时截断预览并追加 ...，省略号也必须在两个上限内。完整详情仍是依据，生成预览不会截短来源正文或 YAML。

## TASKS 元数据与预览

`TASKS.md` 预览 `tasks/<id>.md`。通用字段为 id、type、title、state、owner、depends on、started at、completed at、head sha；开始时间统一拼作 started at。owner 写实际作业的 Human、Agent、Platform 等主体，depends on 是任务 ID 列表。

head sha 可为 null、空列表、一个 Project 限定提交点，或跨 Project 的提交点列表。无代码任务不需要编造提交。保留 PENDING、WIP、BLOCKED、RECORDING、DONE 生命周期及其[状态机](transitions.md#task-状态机)，具体调度与转换权限由外部负责。

表格按上述顺序展示通用字段，最后是 detail spec，在 ## preview-table 下的 `<!-- tasks-preview-table:start -->` 与 `<!-- tasks-preview-table:end -->` 间生成。## dependency-topology 下另用 tasks-dependency-topology-mermaid marker 生成依赖图；两个区块均来自 tasks/，不手改。专用字段直接写 YAML；开发任务常用 project repository、working branch、integration branch、repository refs、review required、gists、result。评审、测试、文档、GATE、决定和反馈共用通用字段，按需增加自己的内容。

完成、结果和权限分别表达；测试完成可以失败，决定完成可以拒绝。持久报告、验收内容、决定评论、证据与交接回执保存在任务 YAML/正文，不新建顶层目录。

提供 result 时，记录 execution、outcome、summary、evidence、remaining。execution 非空；DONE 时有实际 outcome 和 summary。检查名称、命令、观察和限制写在持久任务正文中，不作为 evidence 的字符串条目。result.evidence 是含 id、revision、location 的版本化引用映射列表；outcome=pass 时必须有非空持久证据。本地引用必须对应实际保留的版本。同一任务内的报告可用该任务的 ID/版本及正文锚点引用，例如：

```yaml
result:
  execution: completed
  outcome: pass
  summary: 已写请求摘要，并与保留的 INT 核对。
  evidence:
    - {id: DOCS-001, revision: v1, location: "tasks/DOCS-001.md#verification"}
  remaining: []
```

只有 DOCS-001@v1 的对应标题下确实保留了实质报告时，才能使用该引用。空引用壳或任务状态本身不证明验证已执行。

## 点与区域

提交点为 `<project-key>@<head-sha>`，会移动的分支区域为 `<project-key>@<branch-name>`。全写 `<project-key>@<branch-name>@<head-sha>` 保留额外分支背景，但规范化后的点身份仍是 project+SHA。

分支名不是不可变的唯一点，也可在多个 Project 中重复；加上 project-key 才能明确所在区域。需要区分命名空间时可用 refs/heads/main 等全 ref。不根据分支名是否像十六进制来猜含义，由字段或明确的引用 kind 区分。

持久点优先使用完整、实际观察的 SHA。语法工具接受缩写，但须在对应 Repository 核实唯一性；分支移动不重写历史点。

## 稳定的 Project YAML

将 [PROJECT.yaml](../templates/PROJECT.yaml) 复制到 project/<project-key>/project.yaml，包含 project key、remote repository、local repository 与可选 basic rules。local repository 可为单个位置，或按设备/操作系统映射，使不同系统保留各自检出路径；这不构成移动或 clone 仓库的指令。

初始化后日常作业保持不变；仅在新增 Project、remote 迁移、长期本地映射或基本规则变更时明确修改。不把当前 head sha、任务分支、审核状态、汇入对手或 PR 两端写回 Project；这些属于任务专用字段，临时 worktree 位置也可记录在那里。

Project 定位器只读取并返回配置位置，不联系 remote、不检查 Git 对象。找到映射不证明 commit 存在，也不证明本地检出已同步。

## 版本、历史与一致性

revision 是可选元数据，冻结输入或报告时填写；版本化引用使用 id/revision/location。ID 在 Feature 内稳定唯一并与详情文件名对应。

可选 history 在同一详情保留 metadata（旧版完整 YAML，不嵌套历史）与 body（旧版正式正文）。实际保留的旧版本仍可引用，不应修改旧报告去声称检查过新版。

只读校验器检查当前/保留版本引用、关系、依赖和 YAML/预览/拓扑一致性；--render design/tasks/topology 只打印。更新索引时使用[生成器及固定区块规范](generated-indexes.md)，由脚本局部替换，不手工维护生成区；不使用 frontmatter 之外的独立横线。标题、简短介绍和 ## complementary 日期补充保留在生成区外。详情状态由指定维护者写入，预览过期不阻止读取单份详情。工具不认证外部引用和权限。

提供 --project-root 后，会根据注册 YAML 核对 project repository、head 点及工作/汇入区域涉及的 Project；未提供时明确报告 unverified。这是结构/位置检查，不是 Git 同步或业务批准。

## VERBAL 与可选 gists 登记

VERBAL/gists 保存可丢弃的日志、导出和草稿。VERBAL 的 ## preview-table 下使用 verbal-preview-table marker，由脚本扫描 gists/ 生成路径、大小和 UTC 修改时间，不手工维护附件表；更新方式见 [generated-indexes.md](generated-indexes.md)。作为仅供参考的例外，任务可在顶层专用 gists 列表登记路径，预览明确标注 reference only；不校验附件存在性，删除不使任务失效。

不能将这些路径放进 inputs、关系、evidence、决定理由或完成条件。正式结论和足够的验证摘要保存在 design/tasks；正式正文与 STATUS 不依赖附件。参考登记不等于证据。

## 模板

这些是结构一致的示例，不是强制流程。首次建立记录按[初始化清单](initialization.md)处理。替换示例 ID、key、位置、关系和正文，删除未使用任务后重新生成预览。

- [设计预览](../templates/DESIGN.md)、[任务预览](../templates/TASKS.md)、[状态](../templates/STATUS.md)、[参考附件](../templates/VERBAL.md)。
- [INT](../templates/design/INT-001.md)、[REQ](../templates/design/REQ-001.md)、[SOL](../templates/design/SOL-001.md)。
- [开发/通用任务](../templates/tasks/DEV-001.md)、[决定](../templates/tasks/DECISION-001.md)、[反馈](../templates/tasks/FEEDBACK-001.md)、[GATE](../templates/tasks/GATE-001.md)。
- [Project 定义](../templates/PROJECT.yaml)：复制到独立 Project 目录，不放进实际 Feature。

通用任务可复用为 review、test、docs、design、acceptance；加载模板不迁移现有管理记录。
