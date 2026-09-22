**Capstone 设计与代码深度优化方案**

评审日期：2026-09-22。源码基线：`1a788a491c77b20845bf09de30a7a08b460b1c12`。

本文是代码审查与后续工作建议，没有启动生产代码改造。它补充工作区已有的[同日评审草稿](../status/2026-09-22-capstone-review.md)，保留其内容；后续获选工作仍应回填[现有优化计划](../superpowers/plans/2026-09-05-capstone-optimization.md)，避免形成另一份执行账本。

**总体判断**

Capstone 已形成有价值的产品边界：模型组合语义能力，领域权威产生事实，Kernel 管理运行、提交与引用，Application 提供公共输出。当前代码和 inventory 独立安装验证支持这一方向。接下来最值得投入的是提交一致性、协议可靠性和新能力包的接入成本。

本轮新增确认两项优先可靠性问题：提交后的附属步骤失败会让持久化状态与返回状态分歧；schema 允许的查询参数组合可以使正式 gridctl 入口退出而不返回协议 JSON。另核实了进程退出语义、输出界限、文件写入、Host 和 UI 链接问题。现有回归通过不能排除这些故障路径。

架构演进应保留以下决定：

- 领域语义与数值运算归 Domain Pack / Authority；Kernel 只接收显式合同。
- `question_id` / `answer_output` 是 grid Application 的兼容投影。
- 引用完整性和提交失败仍是主路径错误；答案评价与报告是独立附注。
- inventory 证明跨域 SPI 接入，不代表已经验证生产企业 API 的认证、分页和时效语义。
- 多域路由、企业写治理、第二正式领域、OP08 arbitrary JSON 扩展和 OP13 分段存储继续遵循当前暂缓决定。

依据：[架构合同](../architecture/capstone-framework.md)、[当前状态](../status/CURRENT-STATE.md)、[恢复说明](../status/RESUME-NEXT-SESSION.md)。

**一、优先修复的代码问题**

下表中 P1/P2 表示实施顺序，High/Medium 表示本地应用范围内的影响判断，不代表已经完成生产安全认证。

| 编号 | 优先级 / 严重性 | 已确认问题 | 用户可见影响 |
| --- | --- | --- | --- |
| F01 | P1 / High | durable commit 后的记录或清理异常向上传播 | 已有成功答案，但应用返回失败、完成计数少算并终止后续题目 |
| F02 | P1 / High | 查询条件缺少字段类型与操作符的组合校验 | schema 合法输入触发 TypeError，gridctl stdout 为空 |
| F03 | P1 / Medium | Python 与 JS transport 忽略进程非零退出 | 子进程执行失败仍可被接受为成功 |
| F04 | P2 / Medium | Python executor 没有输出字节上限 | stdout/stderr 持续输出造成无界缓冲与诊断存储 |
| F05 | P2 / Medium | 部分 materialize / provisioning 写入跟随 symlink | 预置可写路径条件下覆盖或创建到预期目录之外 |
| F06 | P2 / Medium | 本地轨迹 API 接受任意 Host | loopback 监听之外的请求来源边界不完整 |
| F07 | P2 / Medium | Workbench 深链接没有 run 身份 | 刷新或分享非默认 run 时丢失正确证据上下文 |

**F01：用一个明确的提交点决定成功状态。**

在 [turns.py](../../packages/capability-agent-kernel/src/capability_agent/application/turns.py) 459 行，`append_many()` 已提交 `answer.submitted` 和 `turn.completed(success)`。477—484 行随后调用 recorder 并删除 active 文件，这些操作仍可抛异常。调用方 [runner.py](../../packages/capability-agent-kernel/src/capability_agent/application/runner.py) 560—615 行把整个 `submit()` 异常视为失败，而成功答案尚未加入 `completed_answers`。

本轮在临时目录分别注入 recorder 的 `OSError` 与 active draft 清理的 `PermissionError`：两者均让 `submit()` 抛异常；此时答案文件已存在、turn 状态为 success、active turn 为空，replay 与 snapshot 一致。再调用 `fail()` 会得到 `StaleAnswerDraftError`。

进一步使用真实 inventory authority 的两轮 application 装配，注入清理失败，得到：

```json
{"application_status":"failed","reported_completed_questions":0,"requested_questions":2,"durable_turn_statuses":["success"],"persisted_answer_count":1}
```

默认 generic controller 没有配置 recorder，因此 recorder 分支是扩展接口风险；active 文件清理适用于正常 generic 路径，以上应用级探针验证了其影响。

建议把 ledger 成功提交作为明确的线性化点：提交前失败执行回滚或失败记录；提交后轨迹通知和清理进入可重试的附属步骤，失败只记录固定诊断。恢复时从已提交 ledger 重建 turn 结果，不能再次提交同一答案或触发重复 authority 操作。active 文件残留必须按 run/turn/nonce 与 ledger 校验，防止残留文件被误认作正在执行的 turn。

验收：在答案写入、ledger 替换、snapshot 替换、提交后 recorder、两种 active 文件删除分别注入异常；返回状态、完成数、答案文件和 replay 一致。提交后的附属故障不得阻断下一题；真正的提交前故障仍然失败。

**F02：让不合法的业务参数得到可恢复的协议错误。**

[model.dataset.query.json](../../packages/grid-simulator/src/grid_simulator/capabilities/definitions/model.dataset.query.json) 19 行允许任意 `filters[].value`，同时允许 `gt/gte/lt/lte/in`。在 [operations.py](../../packages/grid-simulator/src/grid_simulator/operations.py) 1083—1101 行，比较直接作用于 Python 值；[results.py](../../packages/grid-simulator/src/grid_simulator/results.py) 406—422 行有类似实现。

正式 `gridctl request` 探针先创建小网络，再查询 `network.bus`：

```json
{"field":"vn_kv","operator":"gt","value":"100.0"}
```

结果为 exit 1、stdout 长度 0、stderr 含 traceback；异常为 float 与 str 不可比较。该结论不依赖私有 helper 调用。`in` 对非集合值的处理在 model/result 两条路径中也不一致，应纳入同一个合同修复。

建议在 authority 根据 dataset metadata 校验 field/operator/value 的组合，明确 null、bool、数值、字符串和集合语义，复用同一个受控谓词实现。输入错误转换为已声明的领域错误；若引入新错误码，同步 capability errors/recovery 合同。最外层再将未预期异常转换为固定、脱敏的内部错误响应，保留诊断关联 ID。不要通过任意强制类型转换默默改变查询含义。

验收：数值字段传字符串、`in` 传标量、空值、不支持的操作符组合均得到单个 JSON `ok:false`；恢复提示允许模型查询字段描述并修正。真实 CLI 测试须验证 stdout/stderr，不能只断言 helper 抛出哪种异常。

**F03、F04：统一两种 transport 的可观测行为。**

[domain-tools.mjs](../../packages/pi-capability-tools/src/domain-tools.mjs) 763 行的 `close` 忽略 code/signal；[execution.py](../../packages/pandapower-domain-pack/src/pandapower_domain/execution.py) 120—158 行使用 `check=False`，随后没有检查 returncode。两侧临时子进程输出合法、请求关联正确的成功 JSON 后 exit 7，调用方仍接受成功。

Python 使用 `capture_output=True` 收集完整输出；[provisioning.py](../../packages/pandapower-domain-pack/src/pandapower_domain/provisioning.py) 107 行的 `max_output_bytes` 进入 descriptor，却没有传给 Python executor。JS 已有 stdout+stderr 合计限额；Python 目前仅有时间限制。本轮没有执行耗尽内存的压力测试，此项依据代码路径确认。

建议建立共享的协议测试向量，分别驱动 Python 与 JS 实现，规定以下组合的统一结果：正常退出与成功响应、非零退出与成功响应、经验证的业务失败响应、signal、超时、超限、非法 JSON、关联 ID 不匹配。非零退出不能接受 `ok:true`。Python 采用有界流式收集并终止/回收超限进程，诊断仅保留限定长度且脱敏的内容。

共享合同与测试数据即可，不要求把跨语言实现强行合并。将固定 executable、endpoint 和凭据控制继续保留在可信 provisioning 边界。

**F05：统一已经存在的安全文件策略。**

[catalog.py](../../packages/capability-agent-kernel/src/capability_agent/tools/catalog.py) 173 行与 [guide.py](../../packages/capability-agent-kernel/src/capability_agent/tools/guide.py) 96 行的 materialize 使用普通 `write_text()`；两个临时叶子 symlink 探针均覆盖了指向的哨兵文件。[provisioning.py](../../packages/pandapower-domain-pack/src/pandapower_domain/provisioning.py) 198 行附近只检查 workspace 叶子后 resolve，父目录 symlink 探针确认目录会创建到其目标下。

正常 ApplicationWorkspace 的排他创建和祖先检查降低了默认路径风险；guide provider 的新 materialization 路径也已有更强防护。因此这是公开底层路径策略不一致，不能表述为已证明的远端任意文件写入。

建议复用现有 dirfd/no-follow、目录身份和原子发布原则，明确普通文件覆盖是否被允许。验收同时覆盖叶子与祖先 symlink、路径被替换、正常首次创建；目录外哨兵不得改变。

**F06、F07：让证据浏览的来源和定位完整。**

[trajectory API](../../packages/grid-agent/src/grid_agent/trajectory/api/app.py) 85 行创建 app 后只增加安全响应头，没有 Host allowlist。本轮 ASGI TestClient 以 `http://untrusted.example:8765` 请求 `/api/runs` 得到 200。已验证任意 Host 被接受；没有验证浏览器 DNS rebinding 完整攻击链。

建议增加明确的本地 Host 校验，覆盖 IPv4、IPv6、端口与错误响应格式。是否增加 Origin 校验按实际本地 UI 请求方式决定，当前无需扩展为企业认证平台。

[App.tsx](../../packages/trajectory-workbench/src/app/App.tsx) 249、290、301 行只保存 `node`，加载 runs 后默认选第一项。建议 URL 至少保存 `(run, node)`，先确认 run 再定位节点；run 不存在显示明确状态。切换 run 或取消节点选择时同步 URL。验收使用两个 run、相同 context sequence，以及失效 run 链接；本轮该项为静态核对，未做浏览器复现。

**二、降低 Domain Pack 接入成本**

`DomainRuntimeProfile` 已具备 executor、authority、projector、state、output、policy、guide 等接口；`PreparedDomainEndpoint.executor` 支持注入。因此现状不能概括为“框架只能接 CLI”。但 [profile.py](../../packages/capability-agent-kernel/src/capability_agent/domain/profile.py) 23 行的 ExecutorFactory 仍使用 executable/workspace/timeout，默认 [Pi 装配](../../packages/capability-agent-kernel/src/capability_agent/application/runner.py) 1018 行继续依赖 executable descriptor 和 JS subprocess。

推荐先用 inventory 的独立实验变体验证一个固定 HTTP authority，测出实际缺口，再决定 SPI 是否需要调整。该实验只使用 loopback 服务、脚本模型和测试凭据，不选定第二生产领域。

| 接入责任 | 应归属的层 | 建议产出 |
| --- | --- | --- |
| 业务操作、参数语义、字段可见性 | Domain Pack | 少量明确命名的只读能力与字段合同 |
| 固定连接、认证、超时、分页与远端错误 | Pack 的 provisioner/executor 和注册 authority | 受控 HTTP adapter，模型不能选择 URL 或认证信息 |
| 本轮响应、来源、版本及完整性 | Authority 与 Pack admission | 可离线验证的 response receipt |
| turn、提交、轨迹、通用输出 | Kernel | 复用现有生命周期及 current-run 引用合同 |
| 用户界面、业务输出形状 | Application | 领域事实展示与公开兼容接口 |

API receipt 可包含 authority ID、operation/contract version、request correlation ID、observed_at、记录版本、分页完整性、响应摘要和本轮持久化引用。ETag 等元数据不能自动证明所有分页属于同一业务快照；如果来源不提供快照一致性，Pack 应表达这个限制。秘密值不进入 receipt、工具参数、日志或公开 metadata；Provider 凭据不能传给业务 authority。

验收至少覆盖正常两轮、401/403、429、超时、schema 漂移、部分分页、分页期间记录变化、重复读取、凭据隔离、report failure 和 replay。先证明失败语义，再考虑自动重试；重试必须由已声明的只读/幂等操作策略决定，不能对所有失败统一重试。

实验通过后，把 inventory 现有 conformance 提取为稳定的开发者入口与可复制模板。提供 framework/SDK adapter 和 HTTP API adapter 两种示例；生成 schema 候选与资源目录，业务作者仍负责权限、语义和权威选择。发布可机器核对的组件兼容信息与安装测试矩阵，保留当前精确依赖锁定，积累兼容证据后再考虑放宽版本范围。

以接入时间、定制代码量、需要修改的 Kernel 文件数和故障用例通过率评价 SDK。首个目标是新 Pack 在不改 Kernel 业务代码的情况下独立安装、完成两轮并回放，不以脚手架文件数量作为成功标准。

**三、明确证据、事实与答案的保证范围**

[test_answer_admission.py](../../packages/grid-agent/tests/e2e/test_answer_admission.py) 167—214 行明确验证：把模型文本替换为错误数值，正确的 result/evidence 引用仍得到 `lineage_verified`。这符合当前设计，不能把它当成语义验证的证明，也不应恢复阻断式评价。

建议从用户可核查性入手：在 Domain Pack 的 presentation 中形成由已准入结果派生的事实卡片，显示对象、指标、单位、条件、结果定位和引用；保持模型原文，评价单独展示。若增加语义一致性评估，将“引用有效”“源记录覆盖”“文本与事实一致”作为不同字段，允许 unavailable，且不改变成功计数。

先在已有 task suites 中加入单位、排序、比较基线、限定条件的通用错误样例，衡量附注能否发现问题。不能按题号、网络名或预期答案添加快捷逻辑；不能要求模型暴露内部推理或强迫重复仿真补评价。

为以后运行环境差异诊断，可由 authority 增加安全的 runtime provenance：simulator、Python、pandapower 与关键数值依赖版本，contract/model catalog 的内容标识，以及实际生效的求解选项。内容摘要证明字节身份，环境记录提高解释与复现实验的能力，两者不能替代业务正确性。

当前引用摘要的 JSON 键顺序属于既有字节合同。不能直接加 `sort_keys=True` 改变已有 refs；未来若需要新的规范化策略，必须版本化并兼容旧引用。此建议不启动暂缓的 OP08。

**四、按职责收敛代码与运行时接入**

本轮源码计数：Kernel `runner.py` 2,166 行、96 个函数；`run()` 227 行；`TurnController.submit()` 266 行；JS `domain-tools.mjs` 1,752 行；Workbench `App.tsx` 1,038 行。行数本身不是缺陷，问题是生命周期、兼容适配、Provider 初始化、报告和诊断集中变更，扩大了每次修改的验证范围。

建议使用现有 Protocol 作为边界，分批移动责任：

| 当前集中位置 | 建议拆分责任 | 保留的单一决策点 |
| --- | --- | --- |
| Kernel runner | 配置入口适配、Provider session 构造、问题循环、派生报告发布 | turn 成败与最终 ApplicationOutcome |
| TurnController | 引用检查、提交准备、原子提交、提交后附属步骤 | ledger 提交点 |
| JS tools | descriptor 校验、进程 transport、语义事件适配、工具注册 | 发布目录与固定 authority 校验 |
| Workbench App | run/URL 状态、分页加载与取消、选择状态、视图装配 | 当前 run 身份与请求归属 |

内部逐步采用已定义的类型化接口，legacy 形状在入口显式适配；不要再次引入泛化 `getattr`/签名过滤来“兼容一切”，也不要仅为拆文件新增多层空壳。每批沿用真实应用合同测试，不同时改变算法、文件格式和公共输出。

请求捕获应提供入口能力矩阵。当前状态明确 single-run 未配置 canonical request capture；generic descriptor 存在也不等于请求已捕获。将 capture 的 enabled/unavailable/disabled 作为显式诊断状态，分别覆盖 legacy analysis、generic、single-run；仅在被配置为捕获的入口检查请求在 Provider I/O 前持久化。涉及真实 Provider 的验证继续单独授权。

**五、性能优化必须保持 authority 所有权**

优先测量冷启动、authority 计算、序列化、上下文提交、报告与 UI 投影各自耗时，避免用总响应时间推断瓶颈。建议记录每题工具调用数、重复语义调用比例、结果/轨迹字节数、提交耗时和内存峰值；在稳定的代表性任务上建立基线后再设门槛。

存在明确的重复计算机会：[test_analysis_registry.py](../../packages/grid-simulator/tests/test_analysis_registry.py) 28—36 行确认同一分析两次得到相同 result_ref，但 `ac_run_count == 2`。这证明内容寻址并不等于计算复用，没有证明所有实际任务都因此变慢。

若基线证明重复计算占比显著，先在 authority 内实现同一 run 的确定性分析复用。候选键应包含 context/revision、operation、规范化后的实际选项以及 runtime fingerprint；命中仍须校验 artifact/evidence。记录本次 invocation 与 reused source 的关系，让新的 turn 正常走 current-run admission。失败结果、非确定性操作和完整性不成立的条目不能当作有效缓存命中。跨 run 复用需要新的再准入合同，暂不作为这个优化的前置任务。

[context_store.py](../../packages/capability-agent-kernel/src/capability_agent/application/context_store.py) 196—229 行每次构建完整 ledger 并写备份，在持续小批追加下存在随历史长度增长的写放大。现有计划已有历史测量，本文没有重测，也不把旧数据当成本次 SLA。OP13 继续暂缓；当前可以合并自然形成的同一事务事件、记录写入字节与时延。只有真实使用触发容量目标时，再对存储接口、恢复点和格式版本开展独立设计。

**六、建议的执行顺序与验收**

工作量为对熟悉本仓库的开发者的粗略估计，包含局部测试，不是交付承诺。

| 阶段 | 工作包 | 完成标准 | 粗略工作量 |
| --- | --- | --- | --- |
| A1 | F01 提交一致性 | 应用级故障注入后，返回/ledger/replay/完成数一致；后续问题继续 | 1–2 人日 |
| A2 | F02 查询错误、F03/F04 transport | 正式 CLI 参数错误有类型化响应；Python/JS 共享错误向量和输出限额 | 2–3 人日 |
| A3 | F05–F07 文件与证据浏览 | symlink 哨兵、Host、两个 run 深链接回归通过 | 1–2 人日 |
| B | HTTP authority 接入实验 | 脚本模型 + 真实 loopback authority 的两轮、错误、receipt、replay 与干净安装通过 | 3–5 人日 |
| C | Pack 模板与 conformance 入口 | 新 Pack 不改 Kernel 业务代码即可完成安装与应用验收 | 2–4 人日 |
| D | 生命周期与 transport 拆分 | 每批合同等价；入口捕获能力明确；兼容 CLI 输出不变 | 3–5 人日 |
| E | 事实展示与性能实验 | 评价不阻断；提供基线及重复计算是否值得优化的结论 | 2–4 人日 |

A 阶段先稳定可信执行边界；B 的真实接入结果决定 C/D 的公共接口调整。E 中的性能实施以测量收益为条件，不预先承诺缓存、存储迁移或 Provider 框架替换。

行为修改应按仓库合同运行最小复现，以及 `make doctor`、`make test`、`make test-e2e`、`make validate`；SPI/安装修改再运行类型、包边界、应用 conformance 和干净 wheel/source 安装门禁。既有 `.github/workflows/verify.yml` 已定义 Ubuntu/macOS 与 Python 3.12/3.14 矩阵，应保留；本轮未查询远端 CI 状态。

特别需要补充的是实际装配上的故障注入测试：现有部分报告隔离测试使用假 Controller，无法发现真实 Controller 在提交后抛错。为 F01 增加真实 Controller + Store + Application 的用例，为 F02 增加正式 CLI 用例，为 F03 增加真实退出的子进程用例，比增加同构 helper 测试更有效。

**本轮验证与局限**

本轮在主目录进行只读代码审查、临时目录探针及 provider-free 测试。新增本文，未修改生产源码、既有评审草稿和状态文件；没有提交、推送或调用付费 Provider。

| 检查 | 本轮结果 |
| --- | --- |
| `make doctor` | 通过；live_probe=false |
| `make check-package-boundaries check-protected-paths` | 通过 |
| Kernel turns / failure isolation / context store / runner | 115 passed |
| inventory application conformance / contract regressions | 42 passed |
| `make test-e2e` | 37 passed，138.98 秒 |
| 子审查：runtime / Pack 聚焦测试 | 36 passed |
| 子审查：generic JS tools | 34 passed |
| 子审查：simulator datasets / analysis registry | 12 passed；simulator Pyright 0 errors |
| F01 定向探针 | Controller 两种故障均复现；真实 inventory 应用复现成功答案被漏计 |
| F02 定向探针 | 正式 gridctl exit 1、stdout 空、stderr traceback |
| F03 定向探针 | Python/JS 均接受成功 JSON + exit 7 |
| F05/F06 定向探针 | 两种 materialize 覆盖 symlink 哨兵；父 symlink provisioning 可复现；任意 Host 返回 200 |
| 文档检查 | 23 个链接可解析；CLAUDE.md 为指向 AGENTS.md 的相对符号链接；diff 无空白错误 |

以上是源码抽查、独立子审查与定向执行的结果，不是全仓逐行证明。本轮没有重跑完整 `make test` / `make validate`、干净安装、远端 CI、浏览器攻击链或真实 Provider。F07 为静态证据；性能收益及 HTTP 业务接入仍须实验验证。
