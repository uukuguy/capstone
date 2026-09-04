# Capstone 设计与实现评估记录

日期：2026-09-05。评估基线：`5a38c5b`。性质：静态审查、离线测试及有界探针；不是生产事故报告。

## 使用范围

本记录保存优化方案的依据，不表示缺陷已经修复。执行顺序、状态和验收以
[优化实施计划](../superpowers/plans/2026-09-05-capstone-optimization.md) 为准。
评估时已有 `JOURNAL.md`、`RESUME-NEXT-SESSION.md` 修改，以及未跟踪的
`docs/superpowers/plans/2026-08-31-capstone-framework-guide.md`；均属于既有工作。

## 结论

权威系统隔离、语义工具目录、当前运行引用准入、不可变工件和事务恢复值得保留。
优先补齐答案保证、观察故障隔离及工程门禁，再验证规模性能和完整第二领域接入。
不建议整体重写、扩展任意工具权限或立即开启多领域路由。

## 可追踪发现

| ID | 优先级 / 类型 | 证据位置（相对仓库根） | 发现及边界 |
| --- | --- | --- | --- |
| R01 | 高 / 契约缺口 | `packages/capability-agent-kernel/src/capability_agent/application/turns.py:230`；`packages/pandapower-domain-pack/src/pandapower_domain/answer_policy.py:55` | 零投影答案可使 selected bindings 为空，跳过领域策略；真实 TurnController 探针接受无引用数值文本。证明的是准入缺口，不是已有模拟器结果被篡改。引用有效也不自动证明文本语义正确。 |
| R02 | 高 / 路径不一致 | `packages/grid-agent/src/grid_agent/cli/app.py:762` | 兼容 run 在工具事件中准入引用，最后直接输出 Pi 文本，未统一经过答案提交、绑定和归档流程。 |
| R03 | 高 / 故障隔离 | `packages/capability-agent-kernel/src/capability_agent/application/runner.py:296`；`:317`；`:948` | 报告和观察回调失败进入外层失败分支，已接受答案对应 outcome 变 failed/rendered=None；现有 test_runner.py 的报告 symlink 测试明确断言该状态。 |
| R04 | 高 / 验证缺口 | `Makefile:108` | 默认 test 不执行 Kernel、Domain Pack、通用 Pi、inventory、工作台独立测试；跨包 pytest 合并收集存在模块重名。 |
| R05 | 中高 / 复杂度 | `packages/grid-agent/src/grid_agent/trajectory/service.py:195`；`trajectory/api/catalog.py:115` | 每次 open_run 重放、投影并写五份缓存；load_if_current 仅测试使用；list_runs 对每个运行触发投影。尚未测量生产延迟。 |
| R06 | 中高 / 资源边界 | `packages/grid-agent/src/grid_agent/trajectory/api/artifacts.py:45`；`api/app.py:309` | 前端 Range 预览不能限制服务端全量 read/hash/Response；大型工件存在内存及 I/O 放大。 |
| R07 | 中 / 复杂度 | `packages/capability-agent-kernel/src/capability_agent/application/context_store.py:195` | 每事务重读、重写和备份完整账本；固定小批次下累计账本 I/O 近似二次增长。当前恢复机制是优点，不能直接删除。 |
| R08 | 中 / 扩展验证 | `packages/inventory-domain-pack/src/inventory_domain/profile.py:30` | inventory 缺少完整 ApplicationProfile 必需的八类组件；现有证明覆盖 runtime/transport，不覆盖完整应用。没有否定已完成的 grid C.1。 |
| R09 | 中 / 接口维护 | `packages/capability-agent-kernel/src/capability_agent/application/runner.py:127`；`:1221` | 大量 object/可选注入和反射过滤参数导致接口错误晚暴露；按职责收紧，避免按文件行数机械拆分。 |
| R10 | 中 / 查询与错误表达 | `packages/trajectory-workbench/src/app/App.tsx:327` | 证据逐引用 Promise.all 放大请求；错误折叠为 null，与无证据不易区分。 |
| R11 | 中 / 测试竞态 | `packages/grid-agent/tests/runtime/test_rpc.py:168` | fake 子进程不读 stdin 就退出，可能先触发 BrokenPipe 而非预期 ack 异常；整套失败、单测重跑通过。 |
| R12 | 中 / 生命周期 | `configs/runtime/pi-security-risk-exception-v1.json` | 本地记录 2 High/2 Moderate 例外，2026-09-30 到期；不是本次重新查询外部漏洞库的结果。 |
| R13 | 设计澄清 | `docs/architecture/capstone-framework.md:23`；`packages/pandapower-domain-pack/src/pandapower_domain/resources.py:11` | 文档需要区分代码依赖和运行调用，明确 authority 提供的公开契约资源 API。直接导入公开 contract_root 不足以证明非法 raw 实现依赖，不能据此强制新增包或复制契约。 |

## 本次验证

| 命令 / 范围 | 结果 |
| --- | --- |
| `make doctor` | 通过；未发起 provider 请求 |
| `make check-application-boundaries`、`make check-protected-paths` | 通过 |
| Kernel 独立 pytest | 393 passed |
| pandapower Domain Pack 独立 pytest | 66 passed |
| 工作台 vitest | 128 passed |
| 通用 Pi node tests | 34 passed |
| `make test` 的 agent 段 | 733 passed，1 failed：R11；后续目标被中断 |
| R11 单独重跑 | 1 passed；不能把首次整套失败改记为通过 |
| 补跑 simulator | 165 passed；126 条上游 warning |
| 补跑 grid Pi | 43 passed；语法检查通过 |
| 补跑 Makefile application 测试 | 通过 |
| `git diff --check` | 通过 |

未执行：独立发布工件验收、完整 validate/test-e2e 重跑、provider 付费验证、长运行性能基准、浏览器视觉重验、外部漏洞数据库刷新。
测试总数是基线记录，不是今后的固定门槛。所有执行应保留命令、退出码、源码版本、运行环境及报告摘要。

## 评估限制与排除结论

- 符号链接和凭据隔离已有较强实现，本次没有证据支持“整体安全失效”的结论。
- 缓存写入位于内部缓存目录，不等于修改权威 runs 数据；R05 的确定问题是重复工作。
- API 是否应拒绝索引中标为 unavailable 但当下内容可重新验证的记录，需明确状态语义并测试；不直接宣称已证明越权。
- 模型自由文本的全部语义无法靠“存在数字”或“存在引用”做可靠证明；优化必须标明验证覆盖范围。
- inventory 不升级为第二个正式业务产品；GitHub Repository Intelligence 仍是候选。
