# Capstone 设计与代码评估、优化方案

日期：2026-09-22。源码基线：`1a788a491c77b20845bf09de30a7a08b460b1c12`。

> 历史评审快照：本报告描述上述源码基线。后续修复与 HTTP authority 实验已完成；当前实施状态和验证结果以[优化计划](../superpowers/plans/2026-09-05-capstone-optimization.md)为准。

本报告以 Capstone 能力包封装**企业业务 API、业务 framework 及领域规则**为评价前提。pandapower 是第一种领域 framework；inventory 是接入一致性验证。外部项目与复用建议见[开源调研报告](2026-09-22-capstone-opensource-research.md)。本轮交付评审与方案，不实施生产代码改造。

## 1. 总体评价

**设计方向成立，现有应用实现有较强的边界与回归保障；企业 API 型能力包的通用性仍需要一个完整实例证明。** 当前适合继续发展为业务系统与 Agent 之间的能力集成框架。下一阶段价值最大的工作是降低新能力包的制作与接入成本，验证远端业务 API 的执行和来源记录，而非扩大 Agent 编排或存储基础设施。

本轮没有确认 Critical/High 缺陷，确认 **4 项 Medium 问题**；其中三项有定向探针复现，一项由 UI 状态逻辑直接定位。另列设计限制和已知技术债，不把已明确暂缓的功能列成当前实现错误。评审建议为 **COMMENT，按优先顺序改进**，不是正式生产安全认证。

| 维度 | 评估 | 证据与边界 |
| --- | --- | --- |
| 分层与所有权 | 良好 | Kernel/Pack/Application/Authority 有明确 API 与静态依赖门禁；当前门禁通过 |
| 业务能力供给 | 框架骨架已成立 | 契约、guide、policy、executor、state、admission、output 已分离；接入职责较多 |
| 权威结果与谱系 | 当前本地 authority 路径较强 | run/turn、摘要、结果/证据引用有校验；不等同自由文本语义正确 |
| 应用可用性 | 主要本地离线回归通过 | 默认测试、37 项 E2E、7/10/8 业务验证和 2 项实例化均通过 |
| 企业 API 接入 | 尚未完整证明 | executor/provisioner 可注入；默认 Pi 工具桥采用本地进程 authority bridge，缺 HTTP/SDK Pack 端到端验证与模板 |
| 长运行资源 | 有已知边界 | ledger 累计写入放大已有历史测量；OP13 明确暂缓 |
| 可维护性 | 中等，有收敛空间 | runner、JS transport、report、UI 状态代码集中；兼容实现扩大理解成本 |
| 发布与跨平台保证 | 部分证明 | 本轮为本机验证；未重跑干净 wheel 安装、远端 CI 或付费 Provider |

## 2. 已确认代码问题

### R-01 / Medium：工具进程非零退出仍可被当作成功

位置：[domain-tools.mjs](../../packages/pi-capability-tools/src/domain-tools.mjs)，763 行 `child.on("close", () => ...)`。

`runCapability()` 只解析 stdout JSON，没有接收或检查退出码/终止 signal。探针让子进程输出合法的 `ok:true` 协议响应，然后 `process.exit(7)`，调用方仍收到成功响应。

影响：authority 或包装程序在输出后失败时，transport 隐藏执行故障，轨迹可能将该调用标为成功。这里使用可信 executable，因此不是模型命令逃逸；但它是实际错误处理缺口。

建议：显式处理 `(code, signal)`，非零或异常终止不得接受 `ok:true`。如协议允许非零退出携带结构化错误，只放行经关联校验的 `ok:false`。诊断应保持有界并脱敏，不直接把原始 stderr 全量附加到模型/报告。

验收：正常成功、合法业务错误、成功 JSON + exit 7、signal 终止、非法 JSON、超时/输出限额各走正确类型，且没有未结束子进程。

### R-02 / Medium：目录/guide 索引写入会跟随 symlink

位置：[catalog.py](../../packages/capability-agent-kernel/src/capability_agent/tools/catalog.py)，173 行；[guide.py](../../packages/capability-agent-kernel/src/capability_agent/tools/guide.py)，96 行。

`ToolCatalog.materialize()` 和 `GuideIndex.materialize()` 使用 `mkdir(..., exist_ok=True)` 与 `Path.write_text()`。探针在临时目录设置目标叶子 symlink，调用 materialize 后，symlink 指向的外部哨兵文件被覆盖。

影响与前提：需要目标目录预先可写、被替换或由 public materialization API 接收；默认 `ApplicationWorkspace.create()` 排他创建降低正常路径暴露面。不能把这个结果夸大为任意远端用户可写文件。

建议：复用已有基于 dirfd/no-follow 的写入工具，明确允许覆盖的普通文件及父目录身份，原子发布；统一 runtime materialization 的文件策略，避免另建一套路径安全逻辑。

验收：正常新文件/允许的普通文件写入成功；叶子及父目录 symlink 不导致外部文件被修改。

### R-03 / Medium：本地轨迹 API 未校验请求 Host

位置：[app.py](../../packages/grid-agent/src/grid_agent/trajectory/api/app.py)，85 行；[server.py](../../packages/grid-agent/src/grid_agent/trajectory/api/server.py)，loopback 监听限制。

服务限制监听 `127.0.0.1`、`::1` 或 `localhost`，并设置 CSP/no-store 等响应头，但没有限定 HTTP Host。用 `TestClient` 的 `base_url=http://attacker.example:8765` 请求 `/api/runs`，并携带同值 Origin，实测返回 `200 {"items":[]}`。

影响与前提：监听地址约束与请求来源约束是不同边界；当恶意域名能在浏览器环境中被解析至本机服务时，任意 Host 接受行为增加本地轨迹暴露风险。**本轮仅复现 ASGI 层接受任意 Host，未完成浏览器 DNS rebinding 攻击链**；浏览器网络策略等因素影响实际可利用性。

建议：增加明确的本机 Host allowlist，测试 IPv4/IPv6/端口处理；按本地 UI 使用方式决定 Origin 校验。先完成这个小范围边界修正，无需把只读本地工具扩为企业认证服务。

验收：合法本地 UI 与 artifact 下载继续可用；非许可 Host 被拒绝；错误响应保持固定格式。

### R-04 / Medium：Workbench 深链接缺少 run 身份

位置：[App.tsx](../../packages/trajectory-workbench/src/app/App.tsx)，249、290、301 行。

URL 只保存 `node`；启动加载 runs 后总选择 `items[0]`。用户在非首个 run 查看节点后刷新或分享 URL，会打开另一个 run 中的同名节点，或出现无法定位。`context:42`、`business:7:claim` 等节点名本身没有跨 run 唯一性。

证据：直接追踪 URL 写入、初始化与默认选择代码；现有深链接测试覆盖单个节点恢复，没有证明非首个 run 的恢复正确。本轮未增加或运行浏览器复现脚本。

建议：URL 至少包含 `(run, node)`，初始化先验证 run 再恢复 node；切换 run 时更新 URL 并清理不适用节点。run 不存在应有明确状态，不能自动把同一个 node 套到首个 run。

验收：两个 run 具有相同 sequence/node 时，刷新和分享仍定位原 run；删除或不可用 run 的链接不会展示另一个 run 的证据。

## 3. 设计核查与企业业务接入

### 3.1 应保留的设计

- **Domain Pack 拥有业务语义。** manifest/contracts、执行、状态、policy/guide、准入和输出独立，适合封装业务 API 或已有框架。Kernel 没有加入 pandapower 数值计算语义。
- **注册权威拥有业务事实。** `gridctl`/simulator 负责模型、计算与 evidence；Python/JS 模型侧工具不直接拿到 pandapower 对象或 DataFrame。
- **执行与交付分工明确。** 模型写 reader-facing 文本，controller 绑定本轮引用并提交；兼容 CLI 是 application projection。
- **评价是附注。** 当前设计明确 evaluation/reporting 不能撤销有效主答案，引用完整性和提交失败仍独立处理。这是产品决策，优化不能恢复旧的阻断评价方案。
- **第二种 Pack 已有一致性验证。** inventory 证明包可以独立实现 SPI，但它仍是本地只读验证域，不能由此宣布企业 API 接入已全面证明。

依据：[架构合同](../architecture/capstone-framework.md)、[DomainRuntimeProfile](../../packages/capability-agent-kernel/src/capability_agent/domain/profile.py)、[Provisioning SPI](../../packages/capability-agent-kernel/src/capability_agent/domain/provisioning.py)、[Authority SPI](../../packages/capability-agent-kernel/src/capability_agent/domain/authority.py)。

### 3.2 真正的接入缺口在默认 transport，而不是整个 SPI 都被锁死

`CapabilityExecutor.invoke(capability, arguments)` 不要求 shell/CLI；`PreparedDomainEndpoint` 也已经提供可注入 executor 与 metadata。因此“Capstone 不能接 HTTP API”的判断不成立。

但 `DomainRuntimeProfile.ExecutorFactory` 的参数仍是 `(executable: Path, workspace: Path, timeout)`；默认 Pi 路径经 `descriptor_from_endpoint()` 读取 executable/search path，JS `runCapability()` 实际 spawn 子进程。企业 API 可以藏在受控 authority bridge 后面，但目前没有完整 HTTP/SDK 接入验证，也没有统一说明哪种接入方式是公共推荐路径。

位置：[profile.py](../../packages/capability-agent-kernel/src/capability_agent/domain/profile.py)，18 行；[execution.py](../../packages/capability-agent-kernel/src/capability_agent/domain/execution.py)，4 行；[descriptor.py](../../packages/capability-agent-kernel/src/capability_agent/runtime/descriptor.py)，356 行；[runner.py](../../packages/capability-agent-kernel/src/capability_agent/application/runner.py)，1020 行附近。

建议：先做单个 API authority 的端到端验证，测出 bridge 的实际成本。若它足够简洁可先保留；只有实验证明需要时，才将 executor 初始化收敛到 typed endpoint/execution context。不能为了“通用”让模型传 URL、HTTP method、凭据或 Python callable。

### 3.3 远端业务 API 需要来源与时效合同

当前 `VerifiedArtifact` 要求 `reference/document/path`，成熟 grid authority 以本地内容摘要工件验证结果。这个方式可以保存 API 响应 receipt，并非远端 API 不可用的根本障碍。

企业 API 的额外问题是：记录可能在两次调用之间改变；分页可能不完整；ETag 未必代表完整查询快照；HTTP 200 未必表示业务成功。**内容摘要能证明保存了哪些字节，不能证明远端来源真实性、业务口径或查询时点的一致性。** 这些需要 Domain Pack 与注册 authority 定义。

建议把 API 结果 receipt 的候选字段放进新 Pack 的合同：权威标识、业务操作、API/schema 版本、相关 ID、记录版本/ETag、采集时间、分页完整性、脱敏后的结果摘要。凭据和敏感请求头不进入 receipt。原始结果保留范围由业务合同决定，不要求把整个企业数据库复制到 runs。

不要先取消当前 digest/path 保证或引入任意远端引用；先证明 current-run receipt 能支撑提交、报告和离线 replay，再讨论新的 reference scheme。

### 3.4 能力包开发体验是当前更值得投资的方向

`DomainRuntimeProfile` 为完整应用要求多个组件，事实边界清晰，但新开发者必须理解大量协议、工厂和运行文件。Kernel `runner.py` 2,166 行、JS `domain-tools.mjs` 1,752 行、Workbench `App.tsx` 1,038 行、旧 report 1,512 行，关键责任集中。这些行数是导航和维护信号，不是缺陷的单独证明。

建议提供两类 Pack 模板：业务 framework/SDK adapter、业务 HTTP API adapter；共享“合同/guide/输出/准入/验收”的最小示例。OpenAPI 或 framework 元数据只生成候选 schema，业务作者仍决定能力语义、公开字段、权威和副作用。

把 conformance 整理为独立可运行的开发者入口：未知能力拒绝、参数校验、当前 run 引用、错误协议、报告隔离、replay、wheel 安装。已有 inventory 验证应成为模板依据。暂不增加动态插件市场、多域路由或写操作治理。

## 4. 保证范围与已知技术债

**谱系验证不证明自由文本。** 现有 [E2E](../../packages/grid-agent/tests/e2e/test_answer_admission.py) 177 行明确测试：改成错误数值的文本仍可具有正确的 `lineage_verified`。这是当前保证范围，不列为回归。若增加语义一致性评估，应是可选、非阻断、可失败的附注；不改写答案，不降低已完成计数，不强迫重复仿真。可以先让报告更清楚展示 authority 原始事实和引用供人核对。

**请求捕获覆盖尚未统一。** [CURRENT-STATE](CURRENT-STATE.md) 明确 single-run 未配置 canonical request capture；默认 Kernel controller 适配器缺失 channel 时返回 None，runtime descriptor 的存在不能当作模型请求已捕获。建议形成入口覆盖表，并分别验证 legacy analysis、generic、single-run；本轮未发起真实 Provider 调用，不宣称已验证它们的完整请求审计。

**持久化存在历史测量证明的写放大。** [context_store.py](../../packages/capability-agent-kernel/src/capability_agent/application/context_store.py) 196 行附近读全量 ledger，构造全量新文件并备份。2026-09-05 OP12 记录：10 万事件累计 ledger 写入 79,316,645,345 字节、append p50 70.50 秒，规模十倍时写量约百倍。该数据来自旧基线 `de3a5c7` 的固定合成工作负载，本轮没有重测，不能当作当前生产 SLA。[原始测量说明](../superpowers/plans/2026-09-05-capstone-optimization.md)

OP13 已明确 DEFERRED。当前建议保留容量说明和监测；只有真实业务轨迹触发容量需求才恢复设计评审，不把重做存储当成本轮关闭条件。

**依赖与工程清洁度。** 当前 Pi 使用 0.84.4，风险门禁接受已验证 remediation；不能重复旧报告“0.80.6 的两高两中风险仍未修复”的结论。模拟器本轮有 126 条上游警告，另有 Starlette/httpx 弃用提示；建议按警告类型/来源归类，关注新增变化，不以原始警告数量作为易抖动的绝对门禁。Kernel 源码还发现 3 处 unused import，可随责任模块整理顺手清理。

## 5. 分阶段优化路线

以下是建议工作包与验收条件，没有自动启动实施。工作量为粗略工程估计，不是交付承诺。

| 顺序 | 工作包 | 产出 | 验收与停止条件 | 估计 |
| --- | --- | --- | --- | --- |
| 1 | 修正 R-01～R-04 | transport 退出语义、安全 materialize、Host 校验、run 深链接 | 最小复现转回归；doctor/test/E2E/validate、类型与包边界通过；R-04 增加浏览器两 run 链接场景验证 | 2–4 人日 |
| 2 | API 型 Pack 一致性实验 | inventory 的 HTTP authority 实验变体、运行 receipt | Kernel 不含 HTTP 业务语义；默认工具链、当前 run 准入、两轮/replay/report、干净安装通过 | 3–6 人日 |
| 3 | Pack SDK 与脚手架 | API/framework 两类接入教程、候选合同生成、统一 conformance 入口 | 新 Pack 只实现领域责任；不改 Kernel 业务代码，不依赖主工作树 ignored 状态 | 3–5 人日 |
| 4 | 收敛运行代码与审计覆盖 | 入口捕获矩阵，runner/transport 按职责拆分 | 行为和公共输出不变；观察失败不影响主答案；用已有合同测试验证 | 3–5 人日 |
| 5 | 有条件的外部机制复用 | Pydantic Runner 或业务 connector 小型对照记录 | 权限不扩大、提交单一、引用准入不退化，确实减少维护成本才继续 | 2–4 人日实验 |
| 后续 | 规模/多域/写治理 | 保留现有 backlog | 真实业务需要与明确范围决策后再启动，OP08/OP13 不隐性重启 | 不估算 |

API 实验先使用 loopback 服务和测试凭据，不调用实际 ERP/CRM 账户。测试 401/403、429、超时、schema 变化、分页部分返回、revision 改变及日志脱敏；不为证明 API 接入而先建设 OAuth 平台、多租户体系或写审批系统。

外部借鉴优先顺序：业务 framework 封装看 CAP；代码/OpenAPI 插件看 Semantic Kernel；业务连接与身份看 Composio/Arcade；证据模型参考 AiiDA；模型循环/恢复最后比较 Pydantic AI/LangGraph。具体源码、许可证边界和候选映射见[调研报告](2026-09-22-capstone-opensource-research.md)。

## 6. 本轮验证与局限

验证在现有主目录执行，未修改生产代码。保留原有未提交的 JOURNAL/RESUME、未跟踪 `.codex/` 与 framework-guide 计划。仅新增两份评审文档；未提交、推送或调用付费 Provider。

| 命令或检查 | 本轮结果 |
| --- | --- |
| `make doctor` | exit 0；只验证本地运行准备，不包含 live provider probe |
| `make test` | exit 0；agent 817、simulator 165、Kernel 526、pandapower Pack 80、inventory 11/118/1、JS grid 43/generic 34、Workbench 154、verification tools 41；Makefile 合同脚本通过 |
| `make test-e2e` | 37 passed，exit 0 |
| `make check-types` | TypeScript 通过；Pyright 0 errors / 0 warnings |
| `make check-package-boundaries check-protected-paths` | 通过 |
| `validation/run.py --mode offline --suite task-required` | 7/7，通过 |
| `validation/run.py --mode scripted-pi --suite static-analysis-core` | 10/10，通过 |
| `validation/run.py --mode scripted-pi --suite static-analysis-full` | 8/8，通过 |
| `validation/run.py --mode application --suite application-instantiation` | 2/2，通过；含结果谱系、context/replay、answer audit 和报告检查 |
| `tools/capability_matrix.py --check` | 发布矩阵 24/24；仅指已声明范围，不代表 pandapower 全部功能 |

本轮验证报告与主线程日志保存在 [runs/review-20260922](../../runs/review-20260922/)，属于 ignored 本地证据。`validation` 报告使用独立路径；测试/验证工具仍按自身流程产生本地测试运行工件。完整 `make check-release`、wheel/source clean install、远端 CI、多平台、浏览器 E2E 和真实 Provider 本轮未复验。历史通过记录不能替代这些当前环境验证。

三个小型复现脚本也保存在该目录，在仓库根执行：

```sh
node runs/review-20260922/repro_exit.mjs
uv run --project packages/grid-agent python runs/review-20260922/repro_materialize.py
uv run --project packages/grid-agent python runs/review-20260922/repro_host.py
```

本轮输出分别为：exit 7 的子程序仍得到 `ok:true`；catalog/guide 两个外部哨兵文件均被覆盖；任意 Host 的 ASGI 请求得到 200。文件探针仅操作其自身临时目录，Host 探针不启动网络监听。

这是架构边界和关键执行路径的全面主题评审，结合静态扫描、定向源码阅读、独立子评审与现有回归；不是逐行覆盖整个仓库，也不是密码学完整性或浏览器安全的形式化证明。外部框架未安装运行，所有性能和迁移收益仍属待验证假设。
