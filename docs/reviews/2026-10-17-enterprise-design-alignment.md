# model-decision：定稿与实现校准

评审基线：model-decision HEAD `b703e37b`。读取当前四份定稿和该提交的实际应用/Kernel/协议代码；当前文档未提交修改不算已集成代码。根工作树 native 普通对话 WIP 未在此分支注册或接线，不计入完成。未运行 Provider、测试或端到端验证，未修改源码。

结论：当前是复用成熟对话、专业执行和 Work 基座的过渡切片，没有发现本片新建第二套企业调度平台。它尚未达到定稿规定的首个企业应用交付下限。后续应补同一基座的配置和执行接缝，不能以另一套企业规划器、Demo 专用数据接口或模式分流补齐。

需先明确的一项入口偏离：合入专业 Work 执行后，ThreadWorkAdapter.tsx:218 的“开始任务”按钮没有 recoveryOnly 条件；它可提交一个全新的 start_work，而不仅回查原 pending 请求。:223 却将同一入口说明为旧协议查看/草稿/原请求确认，且尚不能继续发送。这不等于新建第二框架，但与当前恢复入口定位不一致。若保持恢复入口定义，应仅放行既有 pending start 的精确重试；若确需保留旧协议完整操作，应明确标为临时旧协议控制入口并区分新企业入口。不能把该保存/启动流程当成新工作台正常交互，也不能将一次真实 start_work 回执表述为新应用交付。

交付阻塞与设计错误分开：无模型正常执行、独立 Profile 选择/快照、一次发送原子执行是既定待实现，也是“首个企业应用已交付”声明的阻塞项；不是要求重建架构。持续组织、通用文件成果和多 Pack 协作仍按后续既定切片验收。当前专业 v1 对话和内部 Work 执行可作为明确范围的过渡资产保留。

## 一、已复用：保持并继续沿用

| 定稿要求 | 实际入口及证据 | 判断 |
| --- | --- | --- |
| 同一个 Thread 服务、命令回执、事件顺序和持久账本 | thread_service.py:1214、2497 的 Work 接受路径；host_api.py:155 的版本协商；ThreadProjectionStore 继续使用原 Thread events/SSE | Work 是现有控制面的增量，不是独立 `/works/.../commands` 调度平台。对象 CAS 与 Thread 游标各司其职。 |
| 沿用 Attempt/租约/Harness，不复制生命周期 | thread_worker.py:32、192 复用 run_pending_attempt/serve_thread_attempts；harness.py:601 的 HarnessAttemptRunner；thread_work.py:73 创建真实 Attempt，:47 将其状态回写确切 Work | 专业 Work 已真实入队、领取、续租和终结。不能把这一事实扩大成无模型执行或持续组织已完成。 |
| Work/研究按目标稳定绑定，历史身份不重写 | enterprise_context.py:24、49 的 WorkBinding/TaskContext；attempt_research.py:51 按 thread/work 保存 owner；kernel_pi_session.py:187 消费 claim.task_context；thread_service.py:582、1779 的 Work 历史过滤 | 新 Work 身份不由模型或问题文本推断。旧专业历史仍走原身份，未凭相似度自动并入新 Work。 |
| 本次资源配置真实冻结并消费，拒绝无副作用 | thread_work.py:14、19 预览 pending 资源，:73 固定实际专业上下文；thread_service.py:1214、2497 同锁/事务激活原 pending 选择并写入 Attempt | 已复用原专业选择源，未新增另一份模型配置真相。当前仍只是专业资源选择，不是完整应用 Profile 快照。 |
| 原生与 Authority 配置有明确类型，不虚构 Authority | Kernel domain/profile.py:97、116 的 NativeExecutionConfig/NativeDomainRuntimeProfile；application/profile.py:35、76、85 的 ReferenceGrant/DomainBinding/ApplicationProfile；native_pack_preparation.py:27 | 公共类型和准备接缝已存在。专业配置仍要求真实 Authority；通用配置不靠空 Authority 占位。尚无本分支已运行的企业 native 应用装配。 |
| 复用已有通用输入资源和原生执行资产 | thread_input.py:25 验证 text/skill_invocation、版本化资源角色和显式上下文；general_pi_executor.py:44、54 的私有工作区/原生启动；general SDK 与 MCP 资源装配 | 不应另造 Demo 指标输入层、查询 API 或第二种技能安装机制。已有资源角色不是 ApplicationProfile 本身。 |
| 专业事实与一般观察分开 | 专业 DomainRuntimeProfile、require_authority_profile、原业务 runtime/admission；delegated_runtime.py 对普通子任务观察明确不转移 Authority evidence；现有 ResultProjection/InferenceEvidencePanel | gridctl/PyPSA 仍拥有事实、结果和证据。共享 UI 不给专业会话新增 shell，也不把文件/模型文字变成计算依据。 |
| 复用成熟对话和成果视图 | ThreadLiveEntry.tsx:77 的只读版本发现；v1 进入 ThreadFixtureApp；ThreadWorkspace、CapstoneAssistantThread、ResultExplorer、ResultProjectionCard、NetworkView | 新工作台是现有传输、输入、历史与专业视图的应用适配。新 v1 会话直接使用成熟 send_auto，不先要求用户建立 Work。 |

## 二、偏离最终形态：明确的过渡债务及已有行为差距

这些是与最终设计的差异，不能一律解释为本切片新引入的缺陷。定稿第8节允许显式旧/新装配过渡；允许过渡不等于可以宣称最终统一已经完成。

| 最终要求 | 当前实际差异 | 校准 |
| --- | --- | --- |
| Profile 决定能力；普通/专业不是前置的两套组织模式 | intent_runtime.py:160 仍先选 research/direct/recognizer；:335-365 可选 direct DelegatedRuntime、业务 runtime 或 ordinary HarnessPiClient。runtime_mode=pi_reference 仍决定另一运行装配。 | 这是现存过渡分流。不能把同一个 HarnessAttemptRunner 或同一个队列等同于同一个决策—执行—观察循环。退出这些分流需共同 TaskContext/ResearchController/行动准入覆盖现有业务后验收，不能简单删路由。 |
| 普通会话不依赖电网模型或专业 worker | ThreadLiveEntry.tsx:191、223 仍 client.create('ieee39')；:168 调用 prepareWorkbench；AttemptClaim 在 thread_service.py:610、634-650 强制真实 ModelContext 及一致性。 | 当前成熟入口提供的是模型绑定的正常对话，不是已交付的无模型企业入口。沿用它是阶段保险，不能成为最终默认模型设计。 |
| Work/Attempt 为内部组织身份；正常发送原子接受输入并执行 | v2 thread_work.py:131 只接受 work_message/revise_goal/start_work/cancel_work；ThreadWorkAdapter.tsx:147、218、232 仍保留保存与启动内部接缝。工作台 recoveryOnly 禁止新保存，允许历史/原请求恢复。 | 协议定稿已明确两阶段是内部早期接缝。作为旧 v2 数据恢复入口可保留；不能把它重新升格为新企业应用交互或再增加一个“开启对话”动作。 |
| 通用成果不可静默丢失 | general_pi_executor.py:33-40 对大于4 MiB文件直接 continue，达到64项直接 break。 | 这是既有通用收集器与最终成果契约的已知实现差距。专业已有证据链不因此失效；正式通用文件交付前需显式失败/未就绪或有界收集回执，不能说已有完整 artifacts 交付。 |

## 三、未实现：沿既有资产补齐，不视为设计错误

| 未完成契约 | 已有可复用入口 | 真正缺口/边界 |
| --- | --- | --- |
| Thread/工作空间选定 enterprise-research、grid-analysis，配置独立于模型 | ApplicationProfile/DomainBinding/ReferenceGrant、NativeDomainRuntimeProfile、PiNativeBindingPreparer、已有专业应用装配 | 本分支没有 enterprise_application 注册和执行消费；缺独立选择/修订/授权、Profile+version+binding 快照与两类预配置入口。不能用当前 enabled_profiles 或改显示名称冒充应用 Profile。 |
| 无模型的真实正常对话、连续追问、停止和刷新恢复 | ThreadCreator.create(model_free=True) 在 thread_service.py:2351；host_api.py:385 显式 v2 创建；TaskContext.model_contexts 可空；现有 Harness/GeneralPiExecutor | 保存与投影已支持无模型；thread_work.py:24 在无模型时明确 execution_unavailable，create_attempt:77 和 Claim 仍专业绑定。缺中性 Claim/任务配置及真实 native 装配。暂停 native WIP 不算这里已交付，也不要求另建 scheduler。 |
| 单一持续研究循环和 Action 执行准入 | ResearchController、AttemptResearch、PiPromptSession、HarnessRuntime、SDK guardToolExecution | 缺生产主循环的最终参数验证、持久 Action 许可、版本/输入摘要、紧邻调用撤销/租约检查，以及持续交互/恢复装配。已有离线桥和 guard 不是完整持久许可。 |
| waiting_input/paused/答复生效/unknown 外部动作恢复 | 原命令幂等、Work CAS、Attempt取消/租约、研究存储 | thread_work.py 当前命令集合没有 respond_input/pause/resume/resolve_action/increase_budget。应在同 Thread 控制面扩展，不能让 API 另开规划器来证明下一行动或要求资料齐全才恢复。 |
| 企业文件/内网资料等原生输入引用 | 已有输入目录、skill/MCP资源版本、resource_refs、受控原生工作区 | 缺上传/资源 capture/引用授权及版本关联，不是缺 Demo1 专有指标字典。不能把 text+skill 的现有能力描述为完整企业资料接入。 |
| ArtifactRevision 及可用性/有效性/依赖/授权预览下载 | artifacts.py、私有存储、general Pi 文件回执、既有专业报告/结果视图 | 缺统一的不可变产物索引、finalize发布、输入依赖与修订检查、授权内容读取及通用安全视图回退。当前右侧是实际专业计算结果与模型视图，不是完成了通用 document/table/chart/code 工件平台。 |
| 多 Profile/Pack 同 Work 协作及专业候选联动 | ReferenceGrant、专业 Domain Pack/Authority、ResultExplorer/NetworkView、TaskContext/研究绑定 | 缺跨绑定授权交接、共同发现/行动回执及场景候选公开投影。不得把整套旧专业运行器包成不可观察大工具，也不需新增求解器或 Demo 专用端点。 |

## 校准后的实施约束

恢复入口修正范围：禁止建立新目标或发起新的start_work；已存请求允许精确重试。
对已有正在执行且身份匹配的Attempt，保留用户停止操作及真实取消回执。
只读/恢复定位不能剥夺已有执行的停止控制，也不要求用户换入口才能停止。

1. 先贯通同一 Thread 的 Profile 快照与无模型原子输入执行；复用现有队列/租约/Harness/general Pi，用户只发送一次。
2. 同一 Work 维持历史、研究和后续行动；专业资源由 Pack 按需检查，不把模型、完整资料或独立检查器变成所有任务的入口条件。
3. 以实际注册资源及回执验证行动和成果，分别保留一般观察、脚本自检、业务来源和 Authority 证据保证。
4. 只把当前真实能力呈现为已实现。Profile 入口、通用产物和持续组织分别验收；设计 schema、UI 或暂停 WIP 都不能替代真实运行证据。

文档状态注意：protocol-decisions 文件开头仍说生产 Claim/Profile 固定正在后续实施，但 b703e37b 已集成专业 Work Claim 固定；应区分“专业 Claim 已接通”和“独立应用 Profile/中性 Claim 未完成”，避免重复实施或误报整体完成。
