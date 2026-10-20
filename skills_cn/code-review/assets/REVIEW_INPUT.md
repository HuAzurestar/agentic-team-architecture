# 原始审查输入

协调者：复制为本轮新的输入文件，使用前替换所有 `{{...}}`。只包含当前规范性意图、真实授权和原始证据，不放旧 findings、分数、修复提示或作者结论。声明仅用于路由，不证明完整或干净。

- Evidence type: original
- Input ID: {{input_id}}
- Review scope: {{review_scope}}
- Scope source/version: {{scope_source_version}}
- Requirement/design version: {{intent_version}}
- Skill version: {{skill_version}}
- Environment: {{environment}}
- Authorization source/version: {{authorization_source_version}}
- Action boundary: {{permitted_and_prohibited_actions}}
- Release condition: {{evidence_or_human_decision_required_to_release_wait}}

长程任务使用权威设计范围，此包不能覆盖它。无等待时明确说明，不凭空授予权限；边界缺失或无法分离仍是输入限制。

## 候选版本

| 仓库/身份 | 职责 | 分支 | Base SHA | Head SHA | 核验情况 |
| --- | --- | --- | --- | --- | --- |
| {{repository_identity}} | {{role}} | {{branch}} | {{base_sha}} | {{head_sha}} | {{observed_or_unverified}} |

每个相关仓库一行，不能用移动分支名代替 SHA。长程恢复另行核验 registry refs。

## 规范性需求和设计

| 点 ID | 当前承诺/验收条件 | 来源和版本 |
| --- | --- | --- |
| {{point_id}} | {{normative_excerpt}} | {{source_version}} |

说明复用/适配/新增差量、适用用户任务和不变量；保留已确认语义，不加入历史审查结果。

## 原始证据与允许的复现

| 材料/位置 | 观察版本 | 能证明什么/如何复现 | 限制 |
| --- | --- | --- | --- |
| {{original_artifact}} | {{artifact_version}} | {{original_observation_or_safe_command}} | {{evidence_limits}} |

## 缺失输入及责任

| 缺失证据/范围限制 | 对审查的影响 | 责任人/解除条件 |
| --- | --- | --- |
| {{missing_input_or_explicit_none}} | {{impact}} | {{owner_and_next_action}} |

不能把旧报告复制进来补齐未知事实。交给 reviewer 的是代码、原始观察和规范性意图，不是预设答案。
