# 决策证据与适用性

`scripts/decision_evidence.py` 是纯适用性校验器，不是 writer 或质量策略。[decision_source.py](../scripts/decision_source.py)及[测试](../scripts/test_decision_source.py)提供本地 Git 读取；已实现[决定工作流](decision-workflow.md)组合宿主／原生来源适配与持久写入，[质量路径](quality.md)负责独立放行边界。真实身份、解释和权限仍是可信宿主输入。

## 宿主回读入口

`decision_host.inspect_decision` 连接三个宿主拥有的回调：`read_current()` 独立读取已配置目标；`read_reply(ref)` 读取实际已认证会话/平台消息；`interpret(reply, record)` 将该回复及所引材料映射为完整记录摘要和解释引用。宿主 `HumanGrant` 明确枚举 actor、feature、决定类型、来源、范围和允许结果，不从决定文件加载。缺回调、权限未核实、非人类身份、来源/身份/时间/回复不符、解释不明确或消息被编辑均拒绝适用性。入口重新读取回复和当前材料，观察变化时失败关闭，不自动重试。平台异常消息不记录、不返回。

`HumanReply`、`HumanGrant` 和 `HumanInterpretation` 是受信进程内宿主接口，不凭类名认证。宿主须使用实际认证的传输和权限策略，限制来源目的地与网络等待，并先核实人类解释；禁止仅回显上传决定或 `Source: human` 声明。本模块不提供通用网络传输、CLI 导入、决定 writer 或合并授权。合成接口测试及真实本地 Git 连接测试不证明真实人类认证。返回值仍为 `NOT_APPLIED`；后续 writer 须重核，并通过既有点/接受流程条件应用。

## 本地 Git 当前材料

`read_git_current(repo, relative_path, source_key=..., feature=..., decision_kind=..., exact_scope=..., expected_head=...)` 读取已登记本地仓库及独立观察到的完整 HEAD。协调者必须独立解析该绑定，不能直接复制上传决定的目标。读取器核对仓库根、HEAD、普通提交 blob、暂存区和工作文件，再次核对暂存区、文件身份/内容及 HEAD。缺失、脏文件、歧义、变化、链接、不安全或超限来源均拒绝，且不写入。Git 环境覆盖不能重定向读取，路径按字面匹配，禁用替换对象。

提交和工作文本中的 CRLF 均转为 LF，不裁剪或进行其他正文归一化。点读取精确选取一个 H2 REQ/SOL 章节，忽略代码围栏/引用中的标题；其他类型保留全文。返回值是 `check_decision` 的当前材料，不是已核实的人类凭证。它仅证明有界本地观察，不证明远端最新或持续至写入的原子锁。写入器须在变更前立即重新核验并使用自己的条件写协议。

`decision-evidence-v1` 记录保留 `decision_id`、`feature`、`human_source_ref`、`actor`、带时区的 `received_at`、`decision_kind`、`target_ref`、`exact_scope`、`outcome`、`original_reply` 和 `approved_body`。目标标识来源及完整 Git SHA 或实际平台原生条件版本；不得为平台对象伪造 Git SHA。

- `point` 仅绑定一个 REQ/SOL ID，结果为 CONFIRMED、REJECTED、OUT-OF-SCOPE、INFEASIBLE 或 REOPENED。逐项枚举的多点回复须拆分成单独绑定的记录与提交。
- `acceptance` 允许 CONFIRMED、REJECTED 或 REWORK。负面决定可记录，但不授予合并权限。
- `scope-exception` 对明确枚举的范围允许 APPROVED 或 REJECTED，不等同于点确认或整体验收。

当前材料须来自独立核验的来源读取，不能复制决定自称的目标。Feature、类型、范围和来源必须一致。版本或正文变化返回 `DECISION_STALE`；正文变化提供有界线性变更区间差异。保留原回复与原批准材料。适用性不表示已写入，也不表示审查、测试或合并条件成立。

`VerifiedDecisionSource` 是宿主专用事实，不凭 Python 类型完成认证。仅在实际会话或平台回读核实人类身份、权限、解释、回复及批准材料后构造；它绑定整条记录摘要与回读引用。不得从 Markdown/JSON 中自称人类来源的字段构造。测试中的合成实例不是真实决定。本纯模块不提供导入器或来源认证适配器。

记录与当前材料合计限制 4 MiB，范围最多 1,000 个明确 ID，CPU 预算 2 秒。差异每侧最多保留 4,096 字符并标记截断。预算或 schema 失败拒绝适用性。事件仅含决定 ID、适用性与原因码，不含回复、正文、身份或差异文本。
