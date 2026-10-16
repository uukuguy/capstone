# Enterprise Normal Conversation Implementation Plan

2026-10-17UI追加：回答级长内容沿用户给出的来源侧滑窗参考，抽取共享右侧详情面板，
复用原真实引用/结果内容及记录读取。固定标题与关闭、独立滚动、回答身份、
桌面保留对话和移动全宽、Escape/焦点返回/跨回答异步隔离需验证。持续对照的真实
拓扑/报告/图表仍在工作区成果视图，不复制数据源或引入应用模式判断。
用户补充：执行过程先保留现有对话内实时展示，不迁入侧滑窗。本片只调整来源、
引用和结果明细的详情容器；执行中反馈及既有展开折叠行为必须保持。
用户入口及标题统一为“引用资料”，不增加泛称“依据/记录”的按钮。计算结果、
模型版本及校核信息使用各自准确名称。标准宽度1440px，复用原对话字号及行高，
撤回1920主基准与整体放大字号方案。左右工作区支持拖动调宽、键盘调整和比例记忆。
真实任务成果在回答显示卡片，首次新成果可自动打开缺省隐藏的右区；历史恢复与
后续更新不抢占阅读。当前切片仅接真实计算结果投影；通用文档制品协议仍待实现。

2026-10-17最高优先纠正：以下“普通对话切片／企业研究／电网适配”均为研发验证范围，
不是用户必须切换的执行模式。保持同一会话输入和Harness自主组织；Profile只预配
资源、能力与授权，运行时由任务选择通用Pi、专业能力或其组合。回复动作按真实
结果、来源与可执行操作装配，不能按应用名称硬分组；同轮可同时出现电网和报告产物。
电网优先仅意味着先验证已有成熟资产，不新增独立电网会话/规划器，也不引入模式切换前置。

2026-10-17用户调整推进顺序：先以原智能体对话应用适配`grid-analysis`电网分析与决策，
保留成熟专业执行、输入、拓扑、结果和案例功能，跑通原有验证样例。当前native后端切片
完成评审修复后收口，不以完整enterprise-research能力为电网前端适配的前置。
共享回复工具条按实际能力与产物装配：电网图、计算结果和专业证据保留在电网扩展；
企业研究入口保留公共操作，并仅对真实报告、图表、数据与来源提供可用动作。
不得用固定电网图标的整排禁用态替代企业适配，也不复制第二套回复工具条。

> 执行者：逐项采用 TDD，先运行失败用例，再实现最小生产闭环。本计划进入实施；验收结果另行记录。不是已完成或已交付声明。

**Goal:** 用户从企业入口新建一次会话后，发送即真实执行；支持无模型普通问答、连续追问、停止、刷新和会话切换，全部复用现有 Thread/Attempt/worker/Harness/Pi 生产链。

**Architecture:** 两个入口是预配置 ApplicationProfile 的会话入口。Work 是会话后台组织身份；Attempt 是每次执行。沿既有 Thread 命令、对象 CAS、幂等、PostgreSQL 队列、租约、事件和终结链扩展无模型 native 执行，沿已有 IntentRuntimeFactory/DelegatedRuntime 调用隔离 general Pi。专业执行继续使用既有模型选择、Domain Pack 和 Authority，不建第二调度器或总规划器。

**Tech stack:** Python capstone-agent、现有 Kernel ApplicationProfile SPI、PostgreSQL/内存适配、HTTP/SSE、既有 Pi executor/Provider relay；前端复用现有共享会话组件、transport/store/reducer。

## 1. 最高优先交互及交付边界

- 新建任务就是新建一次会话。企业研究与分析、电网分析与决策是预配置会话入口；公共执行基座相同。
- 首次发送在一个事务中创建后台 Work、保存本轮输入、接受真实 Attempt。后续发送在一个事务中追加输入并接受下一 Attempt。没有保存后再启动的用户步骤，没有额外 start 按钮。
- `work_message`/`start_work` 可保留既有协议兼容，但不成为新入口发送路径，不通过浏览器两个请求模拟原子执行。复杂问题也不增加仅保存步骤。草稿仍使用现有 composer 本地机制。
- 普通问答只要求配置有效的对话 Provider、实际可用的 general executor 和已注册的基础 native 运行绑定。选模型、专业技能、MCP、额外内外网资料、研究规划完备、完整工具盘点都不是开聊前置条件。
- 公网检索缺省关闭；内网工具按明确的可用注册能力另行加入。无这些工具仍可正常对话，不宣称完成检索或业务分析。
- 本片交付逐轮对话，不以完整 Task 3 长程研究循环、pause/resume、预算组织、ActionPermit 全体系、混合跨 Pack 分析为前置。需要普通对话的租约、停止、来源、重放安全则在本片完成。
- 研发先执行 macOS 适用门禁；Linux 用户试用前运行双平台完整 release 验证。Provider 与真实外部服务验收另获授权。

## 2. 已核对的生产资产和阻断点

| 生产源 | 已有能力 | 本片真实缺口 |
| --- | --- | --- |
| `thread_work.py` | Work CAS/幂等、状态、成功才推进消息游标、同 Work 会话历史 | start 当前要求模型+专业 Profile；新增单命令发送，不再靠 save/start |
| `thread_protocol.py` | v2 无模型静态 Thread、v1/v2 协商、可空 Event 模型字段 | AttemptSnapshot.target_model_context_id 必填；ThreadSnapshot/parse_snapshot 禁止无模型 current_attempt |
| `thread_service.py` | 唯一 commands/events/attempts 表、两种 store、冻结输入、严格租约、终结 | Attempt 模型列 NOT NULL、Claim.model_context 必填、claim 按模型 family、部分 snapshot/provenance 假设存在模型 |
| `thread_worker.py` | 同一队列领取、续租、安全取消、Intent→Runtime→Harness | professional guard 直接读 claim.model_context；selected-task reader 只在上一条带模型时安装；native worker 无实际领取入口 |
| `intent_runtime.py` | 正式意图识别、冻结输入/决策、普通与专业共用组织、general 配置固定 | request/current_object/resource 直接依赖模型；ResearchTurnRouter 不能误截 native；native-only 不应走专业 ContextOwner |
| `delegated_runtime.py` | GeneralPiExecutor.execute/cancel、token delta、子任务幂等、有限回执、普通答案 general_knowledge 准入 | 挂入无模型 Claim 和同 Work 研究；空模型历史边界需要显式表达 |
| `general_pi_server.py` / `general_pi_executor.py` / `pi_delegation.py` | 隔离工作区、真实 Pi、Provider relay、身份/配置拒绝漂移、取消进程、持久回执 | 现 general capability 静态列 external_lookup，不能直接冒充普通会话获准能力；基础配置须无增强资源也可运行 |
| `pi_intent.py` | NativeConversationPiSessionBuilder、配置摘要、正式普通会话 | 当前 hosted 的 conversation builder 从专业应用构造 RuntimeHost；native 入口应选应用中性运行配置，不能加载电网 policy |
| `thread_application.py` | ApplicationPiRuntimeFactory、FamilyRuntimeFactory、组合 assembly | FamilyRuntimeFactory 直接按模型 family；不能把 native 填作虚构模型 family |
| `attempt_research.py` | WorkBinding/无模型 TaskContext 组件已可用、持久研究路径、严格归属 | 目前实际 Work 研究接在 Kernel 专业 Pi；DelegatedRuntime 尚无同 Work 研究生产装配 |
| `conversation_context.py` | 同 Work 筛选后的有界16轮/32KiB、每条2KiB、truncated、实际历史读取 | message 值都要求 str；PG native model_context_id=None 会在构造时失败，必须显式支持无模型 provenance |
| `thread_input_catalog.py` | PreparedResourceCatalog 对无模型能返回 native profiles | 外层 catalog_provider 明确拒绝无模型；需真实基础会话可用性投影，不准备全部专业资源 |
| `cli.py` / `worker_wake.py` / `hosting.py` | 同 worker serve 循环、健康/唤醒、运行配置 | 当前 family warmup/prepare/selector 基于 professional_context；必须让 native 可独立被实际 worker 接受 |

`TaskContext.model_contexts=()` 已合法；只修改这个类型不会让生产运行。Attempt 表可空也只是迁移的一部分。上述接缝应在同一可交付分支连通再宣布支持聊天。

## 3. 建议冻结的最小 wire / 内部身份

以下命令名称是实施建议，须与共享前端一次冻结，避免并行做两套含义：

```
POST /api/v1/threads/{thread_id}/commands
Capstone-Thread-Version: 2
{
  "schema": "capstone-command/2",
  "command_id": "...",
  "idempotency_key": "...",
  "thread_id": "...",
  "kind": "send_message",
  "target": {"kind": "work", "id": "new", "expected_revision": 0},
  "payload": {"text": "..."}
}
```

已有会话发送使用当前后台 work_id/revision。首次 new 仍由服务端分配 Work/研究身份；客户端不拼接创建+启动。服务端拒绝“new”绕过已有会话主 Work 或活动 Attempt 的并发限制。旧 Thread 中多个 Work 的兼容数据保持原身份，不能自动合并目标或旧专业研究。

- receipt 沿用现有回执 schema，target 包含 work_id/revision、turn_id、attempt_id；accepted_event_seq 对应首次 command.applied。command.applied 和 command_accepted 在同一事务连续写入，携同一 Work。精确同键返回原回执；新键 CAS 冲突不重复输入、不入队；拒绝不部分修改 Work/模型/pending 选择。
- “发送已接受”表示已持久化并入队，不表示已完成。queued/running/终态与既有 Work 更新保持一致。
- v2 snapshot 的中性 current_attempt 必须允许 native Attempt：target_model_context_id=null，真实 active_model_context/selected_model_context_id=null，不造 model、family 或模型列空串。v1 专业解析仍严格，只在显式 v2 边界扩大表达。
- current_attempt 独立于 professionalSnapshot，包含真实 attempt_id/phase/所属 work_id；全局运行锁、停止及会话恢复依赖中性投影。work_id 可作为 v2 current_attempt 扩展或由唯一最新Attempt→Work映射提供；实施时二选一冻结，不让前端猜测。
- 原 `cancel_work` 复用唯一取消机制。UI 先显示停止中；只在真实 cancelled/其他终态到达后结束。刷新只读恢复，不重新发送。
- 不以 event_seq 做 Work CAS。SSE 与历史继续一个 Thread 连续 cursor；旧客户端 upgrade 信号、原键重试先于升级门禁继续保留。

内部需一个**被实际消费**的执行绑定快照（建议 `ExecutionBindingSnapshot`），与模型身份分离：区分 `authority` / `native`，保存真实注册 application/profile/binding 引用与版本、该次 executor identity 和基础 resource-role revision。native claim 的 model_context/model_context_id/selection_revision 为 None，TaskContext.model_contexts=()。校验要求 native 绑定存在且唯一匹配获准应用，拒绝“既无模型也无native绑定”。专业 Profile 仍唯一来自冻结 ModelContext.enabled_profiles/selection_revision，不再复制 selectedProfiles。

Session 只持有宿主注册的预配置 ApplicationProfile 引用；Attempt 固定其实际执行绑定。基础 native 绑定由宿主选定，文本请求不可给出 endpoint、命令、凭据或任意配置对象。不要为了本片加入完整可编辑 Profile 管理器。入口必须最终消费该注册配置，不能只存名字；grid-analysis 继续指向真实现有专业绑定，不用别名冒充完整新组合验收。

## 4. 可执行实施步骤

### 步骤 A：先写一个从发送到正式终态的失败契约测试

Files: 扩展 `tests/test_thread_work_execution.py`，新增 `tests/test_enterprise_normal_chat.py`；复用 `tests/test_thread_postgres.py` fixture。

- [ ] 建立无模型 v2 Thread，注入注册的基础 native 配置和离线 executor fixture。
- [ ] 仅发送一个 send_message，检查同一回执立即包含真实 Attempt，Work queued，表中模型列为 SQL NULL，无专业 prepare 调用。
- [ ] 运行真实 run_pending_attempt→IntentRuntimeFactory→DelegatedRuntime→HarnessAttemptRunner；fixture仅替代 Provider/Pi最外侧I/O，不能用一个直接completed的假 Harness 跨过生产装配。
- [ ] 检查实际 general request 携冻结绑定、当前输入和同 Work 上下文，assistant delta/终态进入同 ledger，答复没有 Authority refs。
- [ ] 先记录当前失败点，再分步实现以下生产链；不能以仅 dataclass/schema 单测替代此验收。

### 步骤 B：原子输入、可空 Attempt、可复核执行绑定与迁移

Files: `thread_work.py`, `thread_protocol.py`, `thread_service.py`, `enterprise_context.py`（或仅新增一个小执行绑定模块），`host_api.py`, Python `thread_http.py`。

- [ ] 定义单一 send_message 解析/事务，复用现有 Work 更新及 create_attempt，先做资源准入/输入边界再提交全部变更。旧 save/start 兼容不影响新产品默认行为。
- [ ] migration 将 Attempt 模型列可空并增加实际执行绑定快照字段；旧非空行读为 authority，不重写历史。内存与PG同语义。
- [ ] AttemptClaim 的专业分支保持现有模型一致性验证；native分支校验真实执行绑定、Work身份与空 model_contexts。禁止放松为“所有缺失字段都可运行”。
- [ ] 同一接受事务固定当次有效执行配置、TaskContext、输入和有界同 Work conversation；失败不耗CAS、不意外激活 pending 选择。专业 pending activation原逻辑继续原子。
- [ ] v2读取/列表/事件允许 native current_attempt；v1专业读取仍严格升级，保留 exact-key retry。
- [ ] 覆盖原命令/key丢回执、同Work并发、跨Work拒绝、无能力拒绝无半写入、现有专业Work再运行。

### 步骤 C：把 native 领取放入原 worker，而非新执行服务

Files: `thread_application.py`, `thread_service.py`, `thread_worker.py`, `hosting.py`, `cli.py`, `worker_wake.py`；生产装配按下段列明的入口扩展。

- [ ] 用执行绑定种类/注册binding选择 worker，保留现有专业family过滤。native worker 必须只领 native，专业worker不抢native；不要给模型 implementation_family 填 native/general。
- [ ] 复用 serve_thread_attempts/run_pending_attempt、AttemptLeaseRenewal 和 Harness；不用第二张工作队列表、后台任务调度器或 general executor自行扫描Thread。
- [ ] native runtime factory装配已有IntentRuntimeFactory和GeneralPiExecutor；专业family factory仍负责原authority路径。无模型claim不能触发ModelCapabilityContextOwner.acquire。
- [ ] 租约延续最终mint边界；所有准备读取/Claim校验先完成。queued/running取消、失租、中断、旧claim终结晚写全部继续原守卫并回填Work。
- [ ] 原取消由DelegatedRuntime.stop→GeneralPiExecutor.cancel/NodeControl→真实子进程结束闭环，不能把HTTP cancel接收当终态。

生产部署还有一个不可省略的接线：当前 federated API 为 API-only，pandapower/PyPSA worker只领自身family，general-pi控制服务只执行子任务、不领Thread。应新增**中性worker装配角色**，但使用原worker循环和同镜像/ledger；其运行配置来自应用中性Provider/Pi基础配置。`deploy/launch_host_runtime.py` 和其实际引用的runtime contract/Compose角色需精确补该角色及健康/唤醒路由，不能把API误变执行器。若部署资产所有权另行分工，此步骤必须同片完成才称实际入口可用。不要要求所有专业worker就绪才能打开/运行native会话。

ThreadApplicationAssembly 当前强制模型catalog/default_model_id；若复用该类型装配native-only worker，应显式提供“无模型catalog的中性运行装配”分支，并把专业依赖留在专业构造器。禁止造一个虚构默认模型满足构造器。API仍可提供原真实模型元数据。

### 步骤 D：沿既有普通意图与General Pi完成回答，不另造planner

Files: `intent_runtime.py`, `turn_router.py`, `delegated_runtime.py`, `pi_intent.py`, `thread_input_catalog.py`, `general_executor_composition.py`；必要时小改 `pi_delegation.py` / `general_pi_server.py` 的实际契约。

- [ ] intent_request_for_claim 支持objects=[]、current_object_id=None，只暴露本次获准general answer/rewrite能力；没有启用的业务绑定时不发布business capability。
- [ ] 复用现有正式意图识别/冻结/决策/TurnPlan，不加新总planner。ResearchTurnRouter只适用原专业自主路径，不能在native普通对话抢先走professional。
- [ ] routing_input_for_claim 对native使用合法空context_snapshot={}，不把None转成假model对象。professional route guard只在真实professional模型分支要求enabled_profiles。
- [ ] General资源固定由宿主实际发布的executor identity和角色revision决定；基础资源集可为零skills、零MCP、零专业绑定。只校验该次基础运行配置可执行，不能遍历/准备未选增强和Authority。
- [ ] `GeneralPiHost.capability.operations`当前默认含external_lookup；native会话不能直接继承为公网授权。应用允许answer/rewrite，检索能力只有明确部署与选择时发布；不改写语义工具schema。普通对话可继续使用现有隔离native基础运行，不因可选资源缺失封锁。
- [ ] DelegatedRuntime执行原PiTaskRequest，保持子任务身份、冻结配置/receipt重放和取消。保留其普通答复offline_information/general_knowledge准入；不造result/evidence refs。
- [ ] 不将“Pi入口不同”变成用户启动按钮/新UI runtime开关。公共基座根据真实接受绑定选择执行路径。

### 步骤 E：追问、研究和历史恢复必须同 Work 且确实可消费

Files: `conversation_context.py`, `thread_service.py`, `attempt_research.py`, `intent_runtime.py`, `delegated_runtime.py`, `task_record_reader.py`；尽量复用既有研究适配，不复制其存储实现。

- [ ] 宿主ConversationContext显式允许缺少模型的provenance，冻结和JSON解析对称；模型对象列表为空。审查IntentRequest/PiTaskRequest消息契约，对native无模型消息采用明确可空/可省字段，保持旧版本读取；不得用假的模型列或family兜底。若继续使用现有general传输的空provenance约定，必须只限该既有文本传输字段，不能回写成宿主模型身份；优先原生可空表达并测试旧任务兼容。
- [ ] 复用project_conversation同Work筛选，保留history_truncated；输入只含本轮未消费内容，成功后才推进consumed_message_count。失败/失租/取消前后重试不丢该轮输入。首次goal+A+B所有补充都进执行；超界受控拒绝，保留草稿/既存任务，不截断关键本轮内容。
- [ ] 普通追问不仅previous一轮：最近有界多轮进入Pi消息；超出边界的原记录仍保留并由现有SelectedTaskRecordReader实际可访问。安装reader不能再要求previous.model_context存在；读取仍锁定本Work/授权source，不自动引入其他Work或旧模型任务。
- [ ] 生产native装配也打开真实AttemptResearch(task_context=claim.task_context)，绑定同research_id路径。普通对话的历史答复先沿ledger承接，不要求native代理先学会研究工具才能聊天。
- [ ] 需要研究投影时用现有controller记录真实本轮目标/完成信息及native来源的观察，通过现有research_state_updated事件持久化；有工具产物才记录对应真实回执。无工具答复不伪造ObservationRef或Authority证据。
- [ ] 存储归属/必需回执失败保持失败；停止/失租不冒充完成研究，旧claim不能写新Work状态。完整模型自主研究更新和ActionPermit循环继续后续Task3，不在本片复制。

### 步骤 F：共享前端接一次正常发送和中性运行状态

用户再次要求完整适配成熟智能体对话区，而非仅复用组件名。
现企业分支的text输入模式绕过技能/上下文菜单、丢弃InputSubmission，属于待撤回实现。
发送必须保留原结构化输入合同及冻结消费；普通文本仍无需额外资源才能回答。
复用完整对话控制器、工具栏装配与同一渲染树，保留原acceptedDraft、输入门禁、
流式回答/执行记录、停止/重试、消息操作、历史定位/返回最新及响应式行为。
按企业应用设计适配Profile预配置、布局、任务会话导航、措辞和动态成果区；不展示Thread/Work两级新建操作。
完整复用指公共交互能力，并非照搬原应用的全部控件。电网模型选择、拓扑联动、专业案例
与模型修订提示通过共享扩展点按Profile及真实资源呈现；无模型普通会话不以这些能力为前置。

Backend wire consumers: `host_api.py`, `thread_http.py`；前端由App负责人修改现有 `ThreadLiveEntry`、transport、protocol、ProjectionStore、共享composer/stop/history组件。

- [ ] 删除本入口save/start两阶段操作，发送只发一个原子命令；新会话创建不产生伪运行活动。
- [ ] 中性current_attempt管理全局运行锁和停止；professionalSnapshot继续只描述真实专业对象。
- [ ] 原键重试保留同一payload/key直到回执；刷新/SSE断线仅补取，不重发。跨会话保留草稿和late-response归属守卫。
- [ ] 不新增企业聊天页、第二store或第二SSE流；专业原页面和证据恢复不退化。

## 5. 离线端到端验收矩阵

Fixture可替代Provider传输或真实Pi子进程输出，不能替代Attempt/Harness/runtime/持久化链。至少一个测试使用真实GeneralPiHost+HTTPGeneralPiExecutor+确定性离线Pi RPC fixture，证明请求、delta、cancel和receipt穿过真实生产适配；不进行付费调用。

| 场景 | 必须断言 |
| --- | --- |
| 无模型首发 | 单命令一个Work一个Attempt、SQL NULL模型、真实runtime调用、一个终态、无专业准备 |
| 丢回执重试 | 完全相同receipt/输入/Attempt，general task不重复执行 |
| 多轮问答 | 第2/3轮看到前面真实答复和本轮输入，研究身份不变，答案来源普通知识 |
| 不同会话/旧专业历史 | 无文本、research或结果串入；切换仅读本会话 |
| 无skill/MCP/Authority | 普通问答仍完成；没有假工具可用性；专业调用明确不可用 |
| executor/配置不可用 | 可恢复错误、不造模型，不部分接受；已冻结配置漂移不静默换配置执行 |
| queued/running停止 | 同Work可请求，跨Work拒绝；子进程cancel确认后真实终态；终结竞态只有一个合法终态 |
| 重启/刷新 | PG服务重建同Claim快照，SSE补取连续cursor，刷新不会重发 |
| 失租/晚写 | 旧worker不能续租/写终态；Work interrupted可下一次显式发送；未消费本轮资料不丢 |
| 长历史/超界 | 正常多轮有界且truncated可见，当前新补充不静默丢失；超界受控拒绝，不500 |
| v1/专业回归 | 旧snapshot/key重试、Profile唯一选择、pending激活、Authority/evidence约束全保留 |

建议focused命令（新增文件后落地）：

```
CAPSTONE_TEST_DATABASE_URL=<独立测试库> uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_enterprise_normal_chat.py packages/capstone-agent/tests/test_thread_work_execution.py packages/capstone-agent/tests/test_thread_postgres.py -q
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_intent_runtime.py packages/capstone-agent/tests/test_delegated_runtime.py packages/capstone-agent/tests/test_attempt_research.py packages/capstone-agent/tests/test_general_pi_server.py -q
uv run --project packages/grid-agent pyright
```

实施时先用 `rg --files` 确认现有测试精确文件名，避免把不存在的测试命令报告为已执行。相关worker部署contract变更另跑对应launcher/Compose边界tests。PG使用临时容器独立数据库，避免与并行full gate固定run_id冲突。

## 6. 实际入口及Provider验收

离线闭环后运行适用共享层门禁、独立评审、`make capstone-local-rebuild`，核对API/worker同image/source。实际浏览器从两种预配置入口新建会话，不出现start；执行真实“你好→再解释一点→停止一段较长答复→刷新→切另一个会话再回来”，验证原共享组件状态和历史。不得拿旧Compose image当本片验收。

真实Provider问答仍待用户显式授权。获授权后记录输入/时间/实际模型公开身份/Attempt/终态/cancel/刷新证据，禁记secret；验证无模型问答不调用Authority，普通知识不含伪造证据。Provider未授权时可报告“离线生产接缝通过”，不能宣称真实问答交付已验收。公网/内网真实检索、完整混合Profile组合与业务质量仍需各自范围的后续验收。

## 7. 完成判据与本片不冒充的范围

本片只有在单次发送贯通实际部署的native worker、Claim、general Pi、同ledger终态和共享App恢复后才算完整正常对话；仅DDL/类型或只存Work都不算。两个预配置入口必须是真实可消费配置，但不要求先交付完整Profile编辑器、所有能力安装器、完整长程自主组织和报告台。没有模型时可正常聊；需要注册模型计算时再走既有专业选择和Authority边界。

本计划以真实正常对话为最小交付；未经实际验收不能声明完成。
