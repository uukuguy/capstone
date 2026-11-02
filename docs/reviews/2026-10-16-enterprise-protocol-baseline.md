# 企业协议细化与前置基线

日期：2026-10-16。运行检查位置：.worktrees/pi-skills-integration。
受检运行源码沿用98e7d0e，当前修改均为设计/检查资产；不代表v2接口已实现。

| 检查 | 结果与边界 |
| --- | --- |
| make doctor | 通过，使用该工作树的受管运行时，无Provider调用 |
| test_thread_protocol.py、test_thread_commands.py、test_thread_application_transition.py、test_attempt_research.py | 共43项通过，覆盖既有严格协议、命令、状态转换和研究隔离/恢复 |
| node docs/design/probe-pi-design.mjs | 通过：工具前拦截顺序、参数修改可见、session保存重开；steer/abort仅确认接口存在 |
| check-enterprise-design.py | 语义schema、状态不变量及外部合成算术检查通过；补答复排队/暂停和目标身份守卫断言 |

新[协议决定](../superpowers/specs/2026-10-16-enterprise-protocol-decisions.md)明确v2协商、对象CAS与Thread游标分离、
命令snake_case映射、答复applied语义及检查来源。决定已有文本与状态矩阵支撑，尚未经过服务端运行验证。

Task 1只完成前置基线采集。实际宿主最终参数guard、真实副作用前阻断、持续会话steer/abort、
租约变化后的执行和完整桥恢复测试仍未完成；不能用离线探针替代这些测试。
本轮未运行完整专业业务E2E、付费模型质量测试或部署验收。

独立设计复审发现并修订两点：答复后排队不能先要求智能体判断下一行动；协议升级不能阻断
已接收旧命令的幂等回查。对应设计与状态断言已更新，实际并发/迁移测试仍属实施任务。
