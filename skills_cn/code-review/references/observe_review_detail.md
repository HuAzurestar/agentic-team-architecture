# 弱审：observe

判断真实用户报告失败后，是否可凭现有证据定位。

- 关键成功、失败、部分成功阶段是否可区分？
- 是否用项目 logger 携带 request/job/entity/correlation 上下文？
- retry/recovery 是否关联原操作，能区分首次执行？
- 是否在合理边界记录一次异常、保留堆栈/上下文并使用合理级别？
- 是否吞失败、直接 print 缺上下文或重复噪声掩盖原因？
- 日志/metric 是否排除 secret、凭据、private payload 和受限数据？
- 是否能识别长流程当前/卡住阶段和必要业务事件，不打印无必要内容？

与 recovery 一起追踪 IO/状态变化日志，检查隔离失败和重试的真实输出。从“失败了”定位任务和阶段。搜 print/logger/error/warn 和敏感字段并查同类入口。metric 建议须服务实际诊断需求和项目惯例，不能机械增加埋点。
