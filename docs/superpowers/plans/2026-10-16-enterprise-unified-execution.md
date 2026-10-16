# Unified Enterprise Execution Implementation Plan

> For agentic workers: execute this plan task-by-task, with review and focused verification after each task. Use the applicable implementation and review skills. Do not treat the design prototype as production code.

**Goal:** 在保留已有业务能力和数据的基础上，将专用与通用执行接入同一个长程自主组织机制。

**Delivery line:** 原Pi成果已通过PR #31合入dev db167184，后续沿dev执行，产品方向为企业自主执行；Pi是底层生态，不是长期产品分支。
已发布对话应用在main维护，后续研究按具体问题开短期分支。

**Status:** 实施契约修订中。Demo1/Demo2是外部说明与评测实例，不是本计划的应用开发任务。
所有限制须遵循[持续推进审查](../../reviews/2026-10-16-enterprise-progress-constraints-review.md)：局部失败不默认终止任务。
执行前须闭合[边界审查](../../reviews/2026-10-16-enterprise-scenario-boundary-review.md)及此前协议评审问题。
wire协商、对象CAS、命令生效与检查来源采用[协议决定](../specs/2026-10-16-enterprise-protocol-decisions.md)。
2026-10-16前置离线基线：Pi工作树doctor、43项既有协议/研究测试及SDK离线探针通过；
仅完成基线采集，不代表Task 1完整执行桥已实现。

**Architecture:** 复用Thread服务/事件/worker、HarnessRuntime、ResearchController及专业执行和投影。
新增Work目标关联、无模型TaskContext、原生资源及通用成果能力；应用选择Profile，Pack/Authority保留业务语义。

**Tech Stack:** 现有Python/FastAPI/PostgreSQL/私有对象存储、Pi SDK 0.84.4、React/TypeScript/Vite；不新增第二套框架。

## 全局约束

- 以[定稿v1](../specs/2026-10-15-enterprise-design-final.md)为准，修订旧文档中的平行Work控制面提案。
- Thread event_seq、现有命令幂等/回执及worker领取机制继续作为真相来源；Work状态是关联聚合。
- 所有新增生产模块落在现有包中；原型、schema和验收数据属于设计/测试资产，不能直接注册成电力业务工具。
- 专业语义工具、结果准入、当前运行证据和数据隔离不能削弱；不删除var、旧Thread或证据。
- 不因“兼容”保留永久的两套组织循环；以Task 6的统一执行退出条件收敛。
- 每个任务先补对应测试、实现、运行针对性检查，再提交任务所属文件；不提交无关控制模板改动。
- 新工作树按仓库要求setup/install-pi/doctor；当前设计检查不调用Provider或部署。

## 接口映射和任务依赖

三线组织已接受：dev负责共同基座与集成；`feat/business-analysis`负责业务分析与报告；
`feat/model-decision`负责模型分析与决策。分支起点、首阶段范围与回流规则见
[三线推进计划](2026-10-16-three-line-delivery.md)。本文件仍是共享接口和Task 1–6的唯一实施清单。

### 共同基座与应用推进控制（2026-10-16已接受）

本计划的共同基座改造同时服务对话应用和企业自主执行，不是企业应用专属基础设施。
任务编号和既有依赖保持；每个实现切片标记归属、受益应用、受影响入口、验证收据和发布状态。

| 工作包 | 当前任务归属 | 交付与验收 |
| --- | --- | --- |
| 共同智能体基座 | Task 1–4及Task 5的共享通信、状态与成果组件；Task 6组合验收 | 保留已有专业链路；验证对话入口及自主执行入口的受影响行为，包含简单回答、工具执行、恢复和依据展示 |
| 智能体对话应用维护 | 贯穿各任务的回归和适用修复，不另开大改版 | 保留既有对话体验和数据；不强制新工作台、复杂任务计划或文件成果；共享增强按实际影响验证后单独发布 |
| 企业自主执行应用 | Task 2最小入口、Task 3持续执行装配、Task 5任务工作台及Task 6验收 | 共用组织链路；“业务分析与报告”和“模型分析与决策”分别记录能力与视图验收，最后验证跨类组合 |

先完成共同基座的最小纵向闭环，持续回归专业业务，再逐步扩展两类工作视图；
不等待大而全基座，也不为两个应用另建组织循环。共享修改只验证受影响范围，
不把可选专业资源或另一应用尚未完成的功能作为所有修复的阻塞条件。
Task 6收口须有两个实际应用入口的适用验证，不能用底层单测或企业入口替代对话入口。
Demo数据、业务口径和专业模型由外部契约提供，不纳入Capstone专用接口开发。
工作包状态与Git分支分开；dev集成、应用验收、main发布、用户更新分别记录。

Task 1→2→3→4；Task 2同步交付最小前端协议适配与版本协商，Task 5再完成工作台扩展；Task 6整体验收。
共享新增类型放在capstone_agent/enterprise_context.py，禁止各任务重复定义Work或资源身份。

```python
# Target dataclasses; existing Run/Turn/Attempt identities stay unchanged.
@dataclass(frozen=True)
class WorkBinding:
    work_id: str
    thread_id: str
    goal_revision: int
    research_id: str

@dataclass(frozen=True)
class TaskContext:
    binding: WorkBinding
    initial_snapshot_id: str
    resource_refs: tuple[str, ...]
    model_contexts: tuple[ModelContextSnapshot, ...]
```

ModelContextSnapshot导入现有thread_protocol，空tuple合法；专业执行自行要求匹配资源。
操作语义参照schema，实际wire字段由现有parser扩展且显式版本化。不得复制新的commands/SSE服务。

## Task 1：固化已跑通基线与接缝约束

2026-10-16：执行provider接缝与真实SDK离线测试已实现（62f44366）；14项通过，既有Python基线101通过/1跳过。
[基线报告](../../reviews/2026-10-16-shared-execution-baseline.md)区分已验证接缝和未接入生产的许可/租约/完整工具装配。
复用既有Python基线，不新增重复fixture；Task 1尚不代表前端闭环已交付。

**Files:** 复用既有Thread/研究/原生执行Python基线；新增
`packages/pi-grid-tools/test/enterprise-bridge.test.mjs`；读取现有`thread_worker.py`、`thread_service.py`、
`thread_application.py`、`resources/general-sdk.mjs`。本任务不替换专业运行器。

**Consumes:** 现有Thread/Attempt接口、固定SDK、已有pandapower/PyPSA验证案例。
**Produces:** `enterprise-baseline`验证回执和桥前置拦截契约；不用新Agent服务。

- [x] 记录真实入口、既有案例、结果/证据身份、报告和网络投影；从现有fixture复用输入，不复制业务逻辑。范围见基线报告及其既有验收引用。
- [x] 增加参数被扩展修改后的执行边界测试：最终参数须重新验证；拒绝调用时执行计数保持0。

```javascript
// Test the real SDK runner path and the host execution guard, without a Provider.
assert.equal(blockReceipt.block, true);
assert.equal(executeCount, 0);
assert.notEqual(proposedDigest, mutatedDigest);
assert.equal(finalGuard.accepted, false);
```

- [x] 验证持久session重开、消息追加、abort后的实际操作回执；持久对象放临时私有目录，测试结束清理。
- [x] Run `node docs/design/probe-pi-design.mjs`；再运行新增`node --test packages/pi-grid-tools/test/enterprise-bridge.test.mjs`。
  前者验证SDK接缝存在，后者覆盖宿主provider包装边界；生产完整装配及许可检查在Task 3验收，二者不可互相替代。
- [x] 验证原生read/bash/edit/write及扩展工具均可在副作用前拦截。Task 3仍须验证实际装配的完整工具清单，不降为日志后审计。
- [x] 按仓库现有专业测试路径运行并保存基线，提交测试和回执；本地集成、注册案例及24/24能力覆盖通过。

## Task 2：泛化身份与Profile装配，保持同一执行账本

2026-10-16首个切片055a335f：WorkBinding/TaskContext、Work归属研究存储及Harness内部投影已实现，
独立评审通过；44项身份/研究测试及1332项后端测试通过。PR #41经双平台CI38898130414合入dev85b6706f，合并树与受检08556cc2一致。见[切片报告](../../reviews/2026-10-16-work-research-identity.md)。
尚未接生产Claim、历史关联迁移、Profile、v2存储/协议及前端；Task 2整体仍在实施。

2026-10-16协议准备切片2d3f86c6：现有HTTP服务、Python客户端及App接入v1版本协商；
未知版本在执行前拒绝，App显示升级原因并保留已加载会话和草稿。旧跨域服务不支持新增头时，
浏览器沿用缺省v1，收到服务端明确声明后才发送版本头，不为探测重发写操作。
当前仅实现v1；v2、无模型Thread、Profile装配和对象CAS仍待后续成套接入。
PR #44经双平台CI38907004425通过后合入32f18d24，合并树与受检1a695af4一致；
local-dev运行源码a2efb791已规范重建并完成同源/浏览器检查。见[协议切片报告](../../reviews/2026-10-16-thread-version-negotiation.md)。

后续接入按当前源码定位成套修改，避免只放宽单个解析器：

- `host_api.py`才是服务端Thread路由；`thread_http.py`是Python客户端。创建入口当前会解析默认模型并安排专业模型准备，v2无模型入口必须绕开这两项无关动作。
- `thread_service.py`同时包含内存实现、PostgreSQL实现、ThreadCreator及DDL。现有模型列为NOT NULL；按协议决定增加Work/最低协议版本关联，迁移应保留旧数据和命令幂等回查。不能仅在Python对象上将模型设为空。
- `domain/manifest.py`与`domain/profile.py`目前都含Authority专用必填字段；Profile公共声明及native/authority可判别配置需要一起拆分，专业配置缺件不自动降级为native。
- 前端真实入口为`ThreadLiveEntry.tsx`，传输为`threadHttpTransport.ts`，状态为`threadProjectionStore.ts`，协议为`threadProtocol.ts`；复用现有对话/成果组件。请求与流式事件都必须协商版本，不能只改快照读取。
- 下一切片验收覆盖旧专业Thread可读、无模型Thread创建/Work提交、对象CAS与同键重试、刷新恢复及明确的旧客户端升级提示；完整持续Pi组织仍归Task 3，不扩大本切片为新报告工作台。

**Files:** 新建`packages/capstone-agent/src/capstone_agent/enterprise_context.py`；修改
`thread_protocol.py`、`thread_service.py`、`attempt_research.py`、`thread_application.py`及
`packages/capability-agent-kernel/src/capability_agent/domain/profile.py`、`application/profile.py`、相关composition装配；
新建`packages/capstone-agent/tests/test_enterprise_context.py`。

**Consumes:** Task 1基线，既有Claim、Profile、Binding、ReferenceGrant。
**Produces:** WorkBinding/TaskContext；`bind_task_context(claim) -> TaskContext`；
专业配置与native配置的严格判别装配，二者共享任务组织接口。

### 当前实施切片：Profile声明、选择与按需准备

- [ ] 在Kernel公共SPI抽出Pack身份声明，增加独立native配置；专业DomainRuntimeProfile保留现有Authority必需字段，不用空值或伪Authority适配。
- [ ] 同一DomainBinding/ApplicationProfile/Registry接受两类配置。`prepare_application(required_binding_ids=...)`只解析并准备本次选择；空选择不启动资源，未知身份在副作用前失败。保留完整Profile及跨Binding授权，不能用准备子集覆盖使能组合。
- [ ] native准备经应用注入SPI返回来源明确的资源回执；capstone-agent适配现有Pi执行器发布的受控资源Profile。Kernel不解释技能/MCP业务内容，不改写原始工具schema。未使用的资源不参与准备门禁。
- [ ] 准备结果区分authority/native。旧专业runner在资源或Provider启动前拒绝本次选中的native，不静默过滤；只选择专业时保留原路径。部分准备失败按已有清理语义收回已准备资源。
- [ ] 测试混合选择、无模型native准备、未选Authority不探活、授权声明保留、错误配置不降级、清理和旧runner零副作用拒绝；再跑Kernel及应用依赖检查、独立评审、规范重建、短范围或必要集成CI及dev图同步。此片不声称v2/无模型Thread或持续Pi循环完成。

- [x] 测试无电网资源仍能建立TaskContext；研究归属由work_id固定；两次Attempt同目标复用研究，两个目标不串状态。此项为组件验收，生产Claim接入仍待下述协议/存储切片。

```python
assert first.binding.research_id == resumed.binding.research_id
assert first.model_contexts == ()
assert first.binding.research_id != other_work.binding.research_id
```

- [ ] 将AttemptResearch的owner由模型归属改为WorkBinding；历史文件保留原路径，新增显式关联记录，不直接重命名旧目录。
- [ ] 将专业依赖校验保留在authority配置，native只检查当前行动所需依赖；缺失Authority仅使对应专业能力不可用，
  不阻断其余获准能力。测试资料不齐时仍能发现资源和开展独立工作。
- [ ] 在现有Postgres服务增加必要元数据和索引；沿用lease_token条件更新、event_seq与幂等键。
  新旧记录读取测试覆盖无Work的历史数据；不能用空模型填充。同步修改前端threadProtocol解析与最小入口，
  固定新旧wire映射和回退能力范围；旧客户端不能理解的无模型任务须明确返回不支持，不能伪造模型。
  使用Capstone-Thread-Version协商，minimum_protocol_version阻止旧解析器误读新记录；
  v2对象CAS不使用event_seq，持续进展不能使补充答复反复冲突。
- [ ] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_enterprise_context.py packages/capstone-agent/tests/test_thread_application_transition.py`。
- [ ] 运行Task 1专业基线，提交身份/装配改造。此时新能力仍受应用配置控制。

## Task 3：让原生Pi参与共同研究循环

**Files:** 修改`intent_runtime.py`、`general_pi_executor.py`、`resources/general-sdk.mjs`、
`thread_application.py`、`attempt_research.py`、`thread_worker.py`；
新增`packages/capstone-agent/src/capstone_agent/enterprise_actions.py`和`tests/test_enterprise_actions.py`。

**Consumes:** TaskContext、现有HarnessRuntime/PiPromptSession、ResearchController。
**Produces:** `admit_action(context, proposal) -> ActionPermit`、`record_receipt(permit, receipt) -> ObservationRef`。
ActionPermit字段为action_id、snapshot_id、lease_token、tool_ref、argument_digest、grant_refs；
ObservationRef字段为ref、source_kind、producer_action_id、input_refs。

- [ ] 测试同目标先直接问答、再检索、再分析，保留Work/研究身份；不启动另一个总规划器。
- [ ] 将原生行动与专业子执行都接入现有研究更新/准入；不同来源类型不可互换。
- [ ] 工具参数最终校验后登记Action、检查当前租约/撤销并执行；晚回执只入记录，不恢复旧worker控制权。

```python
assert receipt.producer_action_id == permit.action_id
assert resumed_work.work_id == original_work.work_id
assert late_worker.can_dispatch is False
assert native_observation.source_kind != "authority"
```

- [ ] 实现安全边界steer/pause及预算预留；不将abort返回当作外部副作用撤回证明。
  测试unknown副作用及冲突分支保持隔离，无关获准读取继续；正常工具拒绝返回可修正观察，不直接failed整个Work。
  input.respond落库后waiting可排队，paused保持暂停；答复已生效不等于业务问题已解决。
- [ ] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_enterprise_actions.py packages/capstone-agent/tests/test_worker.py`。
- [ ] 在共同循环跑Task 1既有专业案例，保存新旧行为对照，提交。

## Task 4：通用资源、成果与恢复

**Files:** 新增`enterprise_resources.py`、`enterprise_artifacts.py`于capstone_agent；
修改现有`host_api.py`、`artifacts.py`、`general_pi_executor.py`和Thread服务索引；
新建`tests/test_enterprise_resources.py`、`tests/test_enterprise_recovery.py`。

**Consumes:** ActionPermit/ObservationRef、既有对象存储及授权、D2 ResourceCapture。
**Produces:** `finalize_capture(upload_id) -> ResourceRef`、`publish_revision(work_id, manifest) -> ArtifactRevision`、
`restore_checkpoint(work_id, checkpoint_ref) -> TaskContext`；字段以定稿/D2–D5及语义schema为准。

- [ ] 先测试分页中断、只读输入、摘要不符、超限文件、跨租户引用、对象写入失败；任何未finalized对象不可下载。
- [ ] 复用现有存储后端流式交付和授权读取；移除4MiB/64项静默跳过，改为配置配额及对象级失败，
  测试局部导出失败仍保留已保存回答和其他成果；必要答案/证据持久化失败仍不可假成功。
- [ ] 实现工作文件、Pi消息历史、研究/目标修订和未决动作的检查点；恢复按D4顺序核对。

```python
assert partial_capture.completeness == "partial"
assert failed_publish.visible_in_catalog is False
assert restored_input.digest == saved_input.digest
assert external_side_effect_count == 1  # retry after unknown outcome must reconcile first
```

- [ ] 将图表bundle、报告引用和逐项交付检查接入现有报告/产物路径，输入变化递归标记依赖失效。
  检查仅针对实际交付依赖；未指定独立核验时缺检查器可交付并说明局限，指定时保留partial而非自动删要求。
- [ ] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_enterprise_resources.py packages/capstone-agent/tests/test_enterprise_recovery.py`。
- [ ] 使用可替换的外部资料包验证资源发现、原生schema、定义引用、分析产物及来源关联。
  示例数据规模和业务字段不成为生产常量；Demo1数值核对仅属于独立外部评测。提交。

## Task 5：在现有前端重组统一工作台

**Files:** 修改`ThreadLiveEntry.tsx`、`ThreadFixtureApp.tsx`、`ThreadControls.tsx`、`threadProtocol.ts`、
`threadProjectionStore.ts`、`workbenchPreparation.ts`；新增`WorkspaceCapabilities.tsx`、`TaskArtifacts.tsx`、
`TaskContextHeader.tsx`及相应`.test.tsx`。复用`NetworkView.tsx`、`ResultExplorer.tsx`、`ResearchEvidence.tsx`。

**Consumes:** 现有Thread快照/事件/回执扩展，TaskContext及通用产物目录。
**Produces:** 全宽工作台、任务切换/资料/成果交互、可扩展可信视图注册与解析。
报告和现有专业模型视图是首批复用示例，不是封闭的两类任务枚举；按产物schema/版本匹配，未知类型安全回退。

- [ ] 从现有`ThreadLiveEntry`/`ThreadFixtureApp`及`CapstoneAssistantThread`抽出布局与成果区，不另建聊天store或复制Thread传输。
- [ ] 按状态原型补上传、待决答复、冲突、断线、unknown和不可用能力测试；命令accepted不提前显示applied。
  加入失败附件保留、先发送文本/就绪资料和局部检查失败不显示整会话失败的交互测试。
- [ ] 无模型任务不加载IEEE-39、不等待无关专业worker；专业任务按真实资源打开既有图表组件。

```typescript
expect(screen.queryByRole('img', { name: '电网拓扑' })).toBeNull() // general task
expect(store.snapshot.lastEventSeq).toBe(serverSnapshot.lastEventSeq)
expect(commandDispatchCount).toBe(1) // reconnect does not resend
expect(selectedResult.attemptId).toBe(selectedCandidate.attemptId)
```

- [ ] 同Work保存成果版本和面板偏好；新成果不抢焦点，输入失效同步标记图表和报告。
- [ ] Run `npm --prefix packages/capstone-app run check`、`npm --prefix packages/capstone-app test`、`npm --prefix packages/capstone-app run build`。
- [ ] 在1440/1600桌面及390手机检查统一入口、已注册视图与未知类型回退；加入现有专业任务真实入口验收后提交。

## Task 6：统一机制验收与旧分流退出

**Files:** 新建`packages/capstone-agent/tests/test_enterprise_acceptance.py`；扩展现有validation用例入口；
更新`docs/reviews/`验收回执、`docs/status/VERSION-CONTROL.md`和生成图。保留企业输入为外部fixture。

**Consumes:** Tasks 1–5、enterprise-acceptance.json及真实注册专业资源。
**Produces:** 统一组织机制验收回执与旧分流移除条件；不将静态原型作为业务通过证据。

- [ ] 框架门禁覆盖原生输入协议、缺口/变更、问答升级、恢复、多Pack交接和已有专业任务回归。
- [ ] 外部质量评测至少更换两类业务资料和任务，保持生产代码不变；只按目标、结果和依据判分，不按工具顺序判分。
  Demo1可作为其中一个实例，oracle不注入执行上下文；完整资料评测与缺口处理评测分别记录。
- [ ] 专业扩展协议复用实际已注册能力，检查相同资源/结果修订的投影关联。Demo2如被选作外部评测，
  所需模型、求解和独立验证能力由资源提供者声明。缺少时记录案例不可运行，不把新增该业务能力纳入框架任务。
- [ ] 真实模型质量评估按已有授权执行，至少三轮记录全部结果；未获授权时保留“质量验证未执行”，不冒称验收。
- [ ] Run仓库集成门禁`make doctor`、`make test`、`make test-e2e`、`make validate`。
- [ ] API/worker/App有改动后执行`make capstone-local-rebuild`，在真实入口跑新旧场景并核对源码/镜像身份。
- [ ] 全部准入通过后，移除按普通/专业选择不同主组织流程的分支；保留专业执行器和结果准入。
- [ ] PR目标dev，合入后验证真实入口并同步控制图。云验证/发布按既有生命周期另行进行，不把本地通过写成部署。

## 失败回退与计划完成标准

任一切片破坏已有专业业务时停在该切片修复，不通过保留两套永久组织框架掩盖问题。
生产切换使用已验证的应用装配与协议版本组合；加法数据结构不代表旧解析器自动兼容。
回退须保留新旧任务及证据，未被旧版本支持的任务保持可恢复，不回滚删除用户数据。
实施完成须覆盖每个切片和所有R1–R7关闭证据；设计资产检查通过仅证明本计划输入一致。
