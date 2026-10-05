# 可编辑审查意见

`review_comments.py` 是有界内存编解码／筛选／转换层，不是发布器或质量授权。[已实现审查工作流](review-workflow.md)组合远端读取、样本核对、同步和条件发布；VERIFIED 标签本身不证明复核。

新记录包含 `rv_id=RV-<UUID>`、`Target={feature,ref,selector?}`、`Basis={source_key,source_text,git_basis?,line_start?,line_end?}`、`Status`、`Comment` 及可选 `Resolution`/`Verification`。状态为 PENDING、ADDRESSED 或 VERIFIED。主键为 `(feature,reviews_ref,rv_id)`；意见文档引用独立于被评论目标。`new_review` 只分配一次新 UUID，发布结果不明时须先查同一 UUID，不能直接新建。

## 安全 Markdown 格式

文档以 `# Reviews` 开始。每个 `## RV-<UUID>` 块包含 `- Status: PENDING` 及 Target/Basis 点分标量字段。所有标量均为 JSON 字符串，包括十进制行号，例如 `- Target.feature: "PIRC-31"`、`- Basis.line_start: "1"`。存在 Git basis 时必须为实际完整 SHA，不能拿 REVIEWS 文档版本代替。原文不放在标量中，而置于 `### Source` 下；Comment、Resolution、Verification 使用同名三级标题。每一文本行（含空行和看似 Markdown 标题的内容）均加 `> ` 前缀。换行语义为 LF，接受 CRLF 文档输入并保留原件。未知/未引用正文、重复字段或 ID、无效版本和跨 Feature 内容失败关闭，不静默丢弃。

`parse(text, feature=..., reviews_ref=...)` 返回记录、线性身份/目标索引、原文及摘要。`select(parsed)` 默认 PENDING；显式状态筛选读取指定状态。指定 RV ID 且未指定状态时读取任何状态，请求不存在的 ID 为错误。

## 旧格式与转换

已知旧 `OPEN/open`、小写状态及 `closed` 仅在内存映射。`- Basis: <文本>` 保存在 legacy 元数据，其来源未解析，不猜测。旧记录附 `_legacy` 标记，不能直接 render。保留原件，在提议副本中明确解析 Basis、移除旧标记，并在编辑前调用 `preview_conversion(original, proposed, ...)`。预览保留原件摘要、要求身份不变、返回完整新文档与有界前后变更区间，始终为 NOT_APPLIED。截断差异不等于完整审阅；后续授权条件写之前须展示完整受影响材料。移除标记不代表授权，也不证明用户看过预览。

每次最多 1,000 条／4 MiB，解析和渲染各限 2 CPU 秒；codec 无 I/O 或日志。远端读取、条件写、持久草稿及过期依据核对由下述已实现工作流负责，不由 codec 执行。发布不证明 Agent 消费，没有后台消费确认服务。

## 前台权威 Git 读取

进入审查或明确要求读取审查内容时，调用 `review_source.read_for_purpose`，传入独立登记的 Git 绑定（repo、remote 名、精确预期 URL、仓库引用、意见路径、feature 和意见引用）。默认 PENDING，但遵守显式状态/ID 请求。未绑定为 UNBOUND_EMPTY；声明了绑定却无法读取时必须报错，不能假装无意见。已访问的远端树证明文件不存在则是真实空态。其他用途仅在明确请求时读取，没有后台轮询或打断服务。

`read_git_reviews` 核验仓库/remote 身份，实际观察远端 `refs/heads/master`，将精确 SHA fetch 到私有临时裸库，读取有界普通 blob，再观察远端 master 与工作 HEAD。绝不以工作分支或缓存 remote-tracking ref 替代远端 master，不更改工作 refs/index/文件/FETCH_HEAD，不合并、不推送。脏工作区可以读取，但不能据此应用意见。返回来源 SHA 与工作 HEAD，二者不替代被评论目标的 Basis。来源移动、无效来源、master 缺失或远端不可访问时停止读取。

fetch 使用浅历史并请求 blob 过滤。Git 传输/pack 成本不属于 4 MiB 意见文档限制，服务端可能不支持过滤。每次 Git 子进程超时 50 秒，禁用终端询问，含潜在凭据的诊断不返回。仅允许 file/http/https/ssh/git 协议；宿主凭据/传输仍须在实际环境配置验证。本地远端 fixture 证明 Git 行为，不证明真实 forge 认证。临时对象在返回时清理，不合入工作仓库。

结果报告工作历史是否包含观察到的 master，始终 `application_authorized=false`、`agent_consumed=false`。已实现 review_workflow 核对当前权限／干净状态，必要时记录日志同步精确 master，重查样本／来源，再通过下述 Git／原生路径条件发布。一次读取不执行这些写入。

## 应用前置校验

`review_application.assess_application` 核对实际预期分支/HEAD、严格宿主授权和干净状态，重读权威文档并校对所选意见；缺 master 祖先时返回精确 SHA 和 `MASTER_SYNC_REQUIRED`，不合并。脏树检查遵循检出所用的 Git 文本/过滤配置；禁用全局 autocrlf 会将部分正常 CRLF 检出误报为脏树。再次核对配置下的仓库根，并禁用可选 index 写入。

master 已包含后，独立提供的 `GitSampleBinding` 将每个 Basis 来源键绑定到仓库、相对文件、预期当前 HEAD、目标引用和 feature。实际当前材料来自 Git/工作区事实，不来自评论本身。支持点 selector 或明确行范围，不接受二者歧义组合。记录的完整历史 Git Basis 须存在并包含所引原样本；当前文本变化返回 `BASIS_NEEDS_RECHECK` 和有界差异，不改变意见状态。不支持的 selector、缺失历史版本及原生平台来源仍未核实，不静默放行。去重后的当前材料正文限制 4 MiB，并在远端观察后再次读取。

通过仅表示观察版本的前置条件成立：`NOT_APPLIED`，不授予合并／发布权限或独立审查证明。已组合 review_workflow 使用下述 F03 writer 记录 intent、同步精确 master、恢复冲突／未知、重查样本并条件发布，不以无日志合并替代。

## Git 仓库的持久化同步

`review_sync.prepare(feature, gist, repository, binding, observation, authority_source_ref, authority=True)` 验证完整 F03 上下文、独立登记的仓库绑定、实际权威来源及所选意见原文，在合并前将 `operation-v1` / `review-master-sync` 写入已声明且已跟踪的 gist。记录保留工作分支/HEAD、精确 master SHA、原评论观察与管理文档快照。必须取得真实宿主授权；文档中的字符串不等于权限。同仓库尚未解决的同步必须先核对，不能另建操作绕过。

`review_sync.execute(..., operation_id, authority=True)` 重查原记录/管理正文、干净工作区及远端来源，无 refs/FETCH_HEAD 变更地获取精确 SHA，然后先持久化 dispatch 标记，再执行带 operation UUID trailer 的 `git merge --no-ff`。已包含 master 时不再合并。不推送、不 abort/reset、不自动解决冲突；冲突保留 MERGE_HEAD、索引及文件。响应丢失后只按真实 HEAD、有序 parents 与 UUID 核对；已 dispatch 但没有已证实结果时保持 unknown，不自动重放。F03 以原值/目标值条件幂等修复任务和 STATUS refs；只读 reconcile 不写入。

对于已登记管理仓库，`review_sync_management` 在合并前增加一个仅含操作日志的本地提交。保留的工作 HEAD 为原始 H0；intent 提交 J 的 parent 是 H0，只改已声明 gist，核对完整预期正文/文件模式及 Operation-Intent UUID。合并的有序 parents 必须为 J 与观察到的 master SHA。继续使用同一 F03 coordinator；脏树检查仅排除其精确未跟踪运行时锁，不排除用户文件，也不允许合并时日志仍未提交。拒绝外部已暂存内容；日志提交显式限定单一路径。远端改动日志本身或与 coordinator 路径碰撞时，在 dispatch 前停止，不静默解决或覆盖。

恢复保留管理仓库的 `DERIVED:HEAD`，在任务 refs 记录实际合并 SHA。原值/目标值检查将合并带来的新管理文档内容保留为需明确解决的冲突。允许核对其后一次仅含管理记录的提交并幂等重入；不能借旧成功收据掩盖无关改动。日志提交前后崩溃均按真实 Git 内容检查，未知合并不自动重放。不 reset、不强制 checkout、不 stash、不隐式推送 master。

同步后必须重读来源并检查目标样本，包括合并中/合并后 master 前进的情形。合并记录不等于评论应用权限、质量通过或真人接受。原生 raw-document 适配器及决定写入器已实现；实际端点／凭据、可信身份及权限读取器必须由宿主配置。本地夹具不证明线上 provider 认证或完整正式审查到 Gate 的场景通过，正式证据单独跟踪。

## Git 条件发布

`review_publish.prepare(feature, gist, repository, binding, observation, draft, authority_source_ref, authority=True)` 接收明确授权的完整规范评论文档，核对已登记来源和真实观察，保留既有 RV ID，拒绝隐式删除及非规范/旧格式草稿。旧格式转换必须先通过 codec 明确预览，由宿主授权实际拟写正文。完整草稿、原来源、改动 RV 及不可变候选 commit 保存在已声明且已跟踪的 F03 `review-publish` intent；prepare 不推送。返回 operation ID 和 intent digest，可信宿主独立保留后者作为此次授权的内容范围。摘要不是认证，不能从不可信日志中现算摘要来制造权限。

`execute(..., authority=True, expected_intent_digest=host_retained_digest)` 核对宿主保留的范围及当前上下文，在私有 bare 仓库重建精确候选：唯一 parent 是已观察远端 master，树只改绑定评论文件，不 checkout 或推送工作分支。先持久化 dispatch 标记，再用精确旧 SHA lease 推送。这是条件快进，不改写历史。commit 身份取实际宿主仓库 Git 配置；私有传输仍需真实宿主认证。每次 Git 子进程限 50 秒、输入/输出 4 MiB，完整 F03 intent 限 4 MiB，commit 元数据另限 16 KiB。绑定、草稿和日志均不应包含凭据。

源变化返回 `publication_status=conflict`、`http_status=409`，通过 intent 引用保留草稿。冲突永久停止该次尝试，即使 master 后来回到旧 SHA 也不重推。unknown 按实际同一 RV UUID 回读并比较完整记录；execute/reconcile 都不自动再发。`present` 只证明当前回读存在，不伪造原调用收据。F03 `effect` 描述日志更新，不代表远端发布成功；保留 `agent_consumed=false` 和 `decision_effect=NONE`，只读 reconcile 不写入。

取得新的明确授权和最新来源观察后，`prepare(..., supersedes=old_operation_id)` 只在真实回读证实旧版本冲突时建立新尝试，保留旧 intent/草稿及原 RV UUID，拒绝换 ID 重建；旧操作不能再发布。源未变化的 unknown 仍待核对，不静默重试。管理日志提交可沿祖先推进，但 Feature 读取集必须不变；实现仓库 HEAD 变化仍停止。UI 接线、原生 provider 条件发布、真实宿主授权交付、决定写入和质量评估仍须接入。本地 bare 远端测试不证明线上 forge 权限。

## 原生原文档传输层

### 持久化发布

`review_native_publish.prepare(feature, gist, endpoint, observation, draft, authority_source_ref, authority=True)` 在已声明 F03 gist 中保存完整原文、规范草稿、变化的 RV 记录、真实原生版本和 feature/仓库读集。宿主须独立保留返回的 intent digest，绑定精确批准范围，重启时不能从日志自行推导授权。每次调用独立传入宿主配置的端点；日志只保存非敏感身份和 URL 摘要，不保存 URL 或凭据请求头。摘要本身不认证宿主或 provider。

`execute(..., endpoint, authority=True, expected_intent_digest=...)` 核对范围、绑定、feature 上下文及实际来源，先持久化 dispatch，再只发一次条件 PUT。丢失响应或重入时读取同一 RV UUID 并比较完整记录，不重新发送。观察到版本/正文冲突（包括 HTTP 409/412）永久停止该次尝试，完整草稿留在 intent。不可回读保持 unknown；present 只证明记录当前存在，不证明谁写入或原调用成功返回。任何结果都不改变任务决定、质量、接受或 Agent 消费状态。

只有实际冲突观察后，才允许明确新授权的 `prepare(..., supersedes=old_id)`，保留 RV 身份及旧草稿；被替代尝试不能再次执行。来源未变的 unknown 不能另建 intent 绕过。`task_operation.reconcile(..., native_endpoint=endpoint)` 支持只读回查或有授权的日志记录；缺失/不匹配宿主绑定即停止，不从不可信日志解析端点。管理 checkpoint 可在读集不变时推进；实现 HEAD 移动仍须恢复。测试组合真实临时 Git 日志和本地 HTTP，包括远端写入后真实进程突然退出；真实宿主/provider 认证和 UI 工作流接线另行验证。

`review_native.NativeDocument` 是宿主配置的 UTF-8 原文档端点，不是任意 provider JSON API 的通用适配器。只绑定确实实现强条件写的既有端点。GET 返回实际唯一强 ETag 作为原生版本、原文及 SHA-256 内容摘要；摘要不是 provider 版本。[RFC 9110 第 13.1.1 节](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1)要求 `If-Match` 使用强比较，条件不符时不得执行所请求的修改。弱/缺失/重复 ETag 一律拒绝，不伪造 Git SHA 或替换成通配条件。

宿主独立绑定 provider/source/feature/review 身份、HTTPS URL 与凭据，不从评论中取这些配置。拒绝含用户信息、查询串、片段或控制字符的 URL；凭据只放宿主持有的请求头，不进入日志或 intent。不跟随重定向；测试可明确启用仅字面 loopback 地址的 HTTP。仅接收 text/plain 或 text/markdown 的 UTF-8、identity 表示，正文上限 4 MiB。每次请求放入独立 spawn 子进程，连接最多 3 秒、读取最多 10 秒、总预算最多 15 秒并预留清理时间；无轮询或自动重试。异常仅返回脱敏代码。本地 HTTP 夹具不证明真实 provider 身份或权限。

`read_for_purpose` 与 Git 读取使用相同的前台触发、默认 PENDING、显式 ID 选择规则。未绑定才为空；既有绑定返回 404、拒绝访问、重定向或传输错误不是空态。`conditional_put(text, actual_condition, authority=True)` 只发送一次 PUT。200/204 为 `acknowledged`，不是验证后的回读；409/412 统一为 conflict/409；其他或丢失响应为 unknown。始终返回 `draft_persisted=false`、`agent_consumed=false`、`decision_effect=NONE`，调用方仍负责草稿。这个低层方法不是另一条发布流程：持久 intent、dispatch 标记、同 UUID 回读及永久冲突/新尝试策略须走上述原生日志发布器；review_workflow 已提供组合的 Skill-only 调用方，真实端点／认证由宿主配置，UI 可选，不得作为无日志写入的绕行入口。
