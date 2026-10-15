# Unified Enterprise Execution Implementation Plan

> For agentic workers: execute this plan task-by-task, with review and focused verification after each task. Use the applicable implementation and review skills. Do not treat the design prototype as production code.

**Goal:** 在保留已有业务能力和数据的基础上，将专用与通用执行接入同一个长程自主组织机制。

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

Task 1→2→3→4；Task 5依赖2、3、4；Task 6整体验收。
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

**Files:** 新建`packages/capstone-agent/tests/test_enterprise_baseline.py`及
`packages/pi-grid-tools/test/enterprise-bridge.test.mjs`；读取现有`thread_worker.py`、`thread_service.py`、
`thread_application.py`、`resources/general-sdk.mjs`。本任务不替换专业运行器。

**Consumes:** 现有Thread/Attempt接口、固定SDK、已有pandapower/PyPSA验证案例。
**Produces:** `enterprise-baseline`验证回执和桥前置拦截契约；不用新Agent服务。

- [ ] 记录真实入口、既有案例、结果/证据身份、报告和网络投影；从现有fixture复用输入，不复制业务逻辑。
- [ ] 增加参数被扩展修改后的执行边界测试：最终参数须重新验证；拒绝调用时执行计数保持0。

```javascript
// Test the real SDK runner path and the host execution guard, without a Provider.
assert.equal(blockReceipt.block, true);
assert.equal(executeCount, 0);
assert.notEqual(proposedDigest, mutatedDigest);
assert.equal(finalGuard.accepted, false);
```

- [ ] 验证持久session重开、消息追加、abort后的实际操作回执；持久对象放临时私有目录，测试结束清理。
- [ ] Run `node docs/design/probe-pi-design.mjs`；再运行新增`node --test packages/pi-grid-tools/test/enterprise-bridge.test.mjs`。
  前者验证SDK接缝存在，后者必须覆盖完整宿主guard；二者不可互相替代。
- [ ] 若guard不可在副作用前控制所有获准工具，停止后续生产接入，修tool provider；不降为日志后审计。
- [ ] 按仓库现有专业测试路径运行并保存基线，提交测试和回执。

## Task 2：泛化身份与Profile装配，保持同一执行账本

**Files:** 新建`packages/capstone-agent/src/capstone_agent/enterprise_context.py`；修改
`thread_protocol.py`、`thread_service.py`、`attempt_research.py`、`thread_application.py`及
`packages/capability-agent-kernel/src/capability_agent/domain/profile.py`、`application/profile.py`、相关composition装配；
新建`packages/capstone-agent/tests/test_enterprise_context.py`。

**Consumes:** Task 1基线，既有Claim、Profile、Binding、ReferenceGrant。
**Produces:** WorkBinding/TaskContext；`bind_task_context(claim) -> TaskContext`；
专业配置与native配置的严格判别装配，二者共享任务组织接口。

- [ ] 测试无电网资源仍能建立TaskContext；研究归属由work_id固定；两次Attempt同目标复用研究，两个目标不串状态。

```python
assert first.binding.research_id == resumed.binding.research_id
assert first.model_contexts == ()
assert first.binding.research_id != other_work.binding.research_id
```

- [ ] 将AttemptResearch的owner由模型归属改为WorkBinding；历史文件保留原路径，新增显式关联记录，不直接重命名旧目录。
- [ ] 将专业依赖校验保留在authority配置，native只检查自身Pi/资源依赖；缺失Authority的专业配置必须失败。
- [ ] 在现有Postgres服务增加必要元数据和索引；沿用lease_token条件更新、event_seq与幂等键。
  新旧记录读取测试覆盖无Work的历史数据；不能用空模型填充。
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

- [ ] 实现安全边界steer/pause及预算预留；不将abort方法返回当作外部副作用撤回证明。
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
- [ ] 复用现有存储后端流式交付和授权读取；移除4MiB/64项静默跳过，改为配置配额和明确失败。
- [ ] 实现工作文件、Pi消息历史、研究/目标修订和未决动作的检查点；恢复按D4顺序核对。

```python
assert partial_capture.completeness == "partial"
assert failed_publish.visible_in_catalog is False
assert restored_input.digest == saved_input.digest
assert external_side_effect_count == 1  # retry after unknown outcome must reconcile first
```

- [ ] 将图表bundle、报告引用和逐项交付检查接入现有报告/产物路径，输入变化递归标记依赖失效。
- [ ] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_enterprise_resources.py packages/capstone-agent/tests/test_enterprise_recovery.py`。
- [ ] 使用11712条外部合成输入核对通用分析与报告图表；不在核心代码写入价格或新能源字段判断。提交。

## Task 5：在现有前端重组统一工作台

**Files:** 修改`ThreadLiveEntry.tsx`、`ThreadFixtureApp.tsx`、`ThreadControls.tsx`、`threadProtocol.ts`、
`threadProjectionStore.ts`、`workbenchPreparation.ts`；新增`WorkspaceCapabilities.tsx`、`TaskArtifacts.tsx`、
`TaskContextHeader.tsx`及相应`.test.tsx`。复用`NetworkView.tsx`、`ResultExplorer.tsx`、`ResearchEvidence.tsx`。

**Consumes:** 现有Thread快照/事件/回执扩展，TaskContext及通用产物目录。
**Produces:** 全宽工作台、任务切换/资料/成果交互；analysis_report/model_decision两个可信视图适配器。

- [ ] 从现有ThreadWorkspace抽出布局与成果区，不另建聊天store或复制Thread传输。
- [ ] 按状态原型补上传、待决答复、冲突、断线、unknown和不可用能力测试；命令accepted不提前显示applied。
- [ ] 无模型任务不加载IEEE-39、不等待无关专业worker；专业任务按真实资源打开既有图表组件。

```typescript
expect(screen.queryByRole('img', { name: '电网拓扑' })).toBeNull() // general task
expect(store.snapshot.lastEventSeq).toBe(serverSnapshot.lastEventSeq)
expect(commandDispatchCount).toBe(1) // reconnect does not resend
expect(selectedResult.attemptId).toBe(selectedCandidate.attemptId)
```

- [ ] 同Work保存成果版本和面板偏好；新成果不抢焦点，输入失效同步标记图表和报告。
- [ ] Run `npm --prefix packages/capstone-app run check`、`npm --prefix packages/capstone-app test`、`npm --prefix packages/capstone-app run build`。
- [ ] 在1440/1600桌面及390手机检查统一入口与两个视图；加入现有专业任务真实入口验收后提交。

## Task 6：统一机制验收与旧分流退出

**Files:** 新建`packages/capstone-agent/tests/test_enterprise_acceptance.py`；扩展现有validation用例入口；
更新`docs/reviews/`验收回执、`docs/status/VERSION-CONTROL.md`和生成图。保留企业输入为外部fixture。

**Consumes:** Tasks 1–5、enterprise-acceptance.json及真实注册专业资源。
**Produces:** 统一组织机制验收回执与旧分流移除条件；不将静态原型作为业务通过证据。

- [ ] 覆盖完整Demo1、缺口/变更、另一类企业任务、问答升级、恢复、多Pack交接和已有专业任务。
- [ ] Demo2用同一真实模型/快照/候选复核拓扑、表格、验证身份；独立AC验证不支持时该项失败，不伪造通过。
- [ ] 真实模型质量评估按已有授权执行，至少三轮记录全部结果；未获授权时保留“质量验证未执行”，不冒称验收。
- [ ] Run仓库集成门禁`make doctor`、`make test`、`make test-e2e`、`make validate`。
- [ ] API/worker/App有改动后执行`make capstone-local-rebuild`，在真实入口跑新旧场景并核对源码/镜像身份。
- [ ] 全部准入通过后，移除按普通/专业选择不同主组织流程的分支；保留专业执行器和结果准入。
- [ ] PR目标dev，合入后验证真实入口并同步控制图。云验证/发布按既有生命周期另行进行，不把本地通过写成部署。

## 失败回退与计划完成标准

任一切片破坏已有专业业务时停在该切片修复，不通过保留两套永久组织框架掩盖问题。
生产切换仅改应用装配选择；加法数据结构和历史引用可被旧装配忽略，不能回滚删除用户数据。
实施完成须覆盖每个切片和所有R1–R7关闭证据；设计资产检查通过仅证明本计划输入一致。
