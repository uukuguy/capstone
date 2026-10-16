# 企业自主执行：前后端契约与状态设计

状态：实现目标设计，尚未实现；与[总设计](2026-10-15-pi-enterprise-execution-design.md)、
[交互设计](2026-10-15-enterprise-task-ui-design.md)共同构成一套设计。
字段和路径为拟定契约，不声称现有API已提供。所有业务知识、指标及数据查询仍由原生资源提供。

2026-10-16定稿修订：以[增量演进与统一组织](2026-10-15-enterprise-design-final.md)为准；
复用现有Thread命令、事件游标、回执及worker，不建立平行Work控制面。下述对象是语义设计。

评审补充：[缺口解决设计](2026-10-15-enterprise-design-closure.md)细化执行桥、资源运输、状态转换、
恢复预算、交付检查及前端缺失状态；其中明确决定优先于本文未细化的概述。

## 1. 概念身份与生命周期

| 对象 | 身份与关联 | 生命周期 |
| --- | --- | --- |
| Workspace | workspace_id，所属应用、用户可访问范围 | 保存能力组配置与资源目录引用；不绑定唯一模型 |
| Thread | thread_id，workspace_id | 一个会话的消息、标题、归档状态及Work列表；归档不取消执行 |
| Work | work_id，thread_id，goal_revision | 一项目标及其修订、研究状态、行动与成果；可以跨多次执行 |
| Attempt | attempt_id，work_id，initial_snapshot_id | 一次持有租约的执行片段；Action各自绑定实际snapshot，取消/故障/暂停后可由新Attempt继续 |
| ExecutionSnapshot | snapshot_id，配置修订与来源摘要 | 不可变，绑定已批准资源及版本；不替代实时授权检查 |
| ArtifactRevision | artifact_id，revision，work_id，producer_action_id | 一个已保存的产物版本；内容不可原地改写，访问与有效性可变 |

Work不按模型ID派生，也不按用户问题文本哈希推断。用户显式新任务创建新Work；
延续当前任务使用work_id。智能体发现需要分支时可提出请求，由宿主保存明确关系。
简单回答也有Work/Attempt，但不要求创建完整研究模型或分析目录。
业务模型只是资源引用，其修订变化影响依赖它的判断，不清空整个会话。

首版一个Work同一时刻仅一个主Attempt持有有效租约；不同Work可按租户配额并行。
子执行有独立action_id及parent_action_id，不能竞争主Work状态写入。
界面切换Thread只改变订阅，不发暂停命令；成果、草稿和模型选择按所属身份隔离。

## 2. 能力组合与执行配置

ApplicationProfile声明身份、版本、DomainBindings、所需资源、允许交接及适用的视图建议。
应用提供整体交付与渲染契约，各Profile贡献约束；合并冲突必须明确拒绝或由应用选择，
不能按加载顺序决定哪个Profile覆盖最终输出规则。

Pack公共声明保留身份、知识入口、资源需求与结果检查。
执行配置采用可判别类型：native使用原生技能/工具和来源/产物检查；authority使用
专业executor、Authority与结果准入。准备器按配置类型验证必需组件，禁止缺失Authority
时自动降级为native。两类配置均有可审计的执行来源，但不共享专业事实保证。
现有专业DomainManifest/DomainRuntimeProfile拆出公共声明，专业字段留在authority配置；
不能用大量无条件可空字段或虚设Authority掩盖差异。

有效权限是应用授权、工作空间选择、Profile/Pack允许范围和任务资源授权的交集。
限定binding身份是profile_id、profile_version、binding_id三元组；工具发布名由宿主生成
稳定无冲突映射。MCP原始工具名及schema保留，不逐个重写业务接口。
工作区原生代码经隔离执行；专业语义会话不直接获得bash或原始模型对象。

配置变更生成workspace_revision。增加能力在下一个行动边界形成新snapshot；
禁用或权限撤销即时阻止新调用，并尝试取消已发调用。旧调用的回执仍可保存，
是否可使用依据当前授权及任务条件重新检查。禁止模型改写Profile配置以自行授权。

## 3. 公共API与幂等命令

继续使用同一个/api/v1服务、身份机制、数据库及工件存储。新增路径组织通用对象，
不是增加业务数据API或第二个独立智能体后端。

| 拟定路径 | 用途 | 一致性要求 |
| --- | --- | --- |
| GET /api/v1/workspaces/{id}/capabilities | 已发布Profile、选择、可用性与修订 | 有界公共投影，不返回密钥或内部工具配置 |
| POST /api/v1/workspaces/{id}/commands | 保存使能配置 | command_id幂等，expected_revision检查 |
| GET/POST /api/v1/workspaces/{id}/threads | 多会话列表/创建 | 创建不必带模型；分页，按权限过滤 |
| POST /api/v1/threads/{id}/works | 创建目标与资料引用 | command_id幂等，返回Work及排队回执 |
| GET /api/v1/works/{id} | 任务快照 | 含最后事件序号与实际状态 |
| POST /api/v1/threads/{id}/commands（扩展现有） | 消息、修改目标、暂停、继续、取消，载荷绑定work_id | 沿用现有幂等/回执，增量检查expected_revision |
| GET /api/v1/threads/{id}/events?after={event_seq}（沿用） | 事件续传，附带work_id | 沿用Thread游标衔接、补取、去重；不新增Work事件账本 |
| GET /api/v1/works/{id}/artifacts | 产物与版本目录 | 内容发布完成后才可预览/下载 |
| GET /api/v1/artifacts/{id}/revisions/{revision}/content | 有界预览或流式下载 | 实时授权，正确类型及下载策略，不暴露bucket权限 |

任务命令公共信封：

```json
{
  "schema": "capstone-work-command/1",
  "command_id": "cmd_example",
  "work_id": "work_example",
  "expected_revision": 7,
  "kind": "message",
  "payload": {"text": "请补充依据", "resource_refs": []}
}
```

command_id的作用域为身份主体与目标对象。相同ID及相同规范化请求返回原回执；
同ID不同载荷拒绝。幂等回查先于修订冲突检查，网络重试不因自身已生效而被误拒。
消息、修改目标、暂停、继续、取消采用各自严格载荷，不用开放任意JSON执行指令。
接收回执不等于执行完成；返回command_id、accepted_revision与accepted/applied/rejected状态。
没有获准模型或执行依赖时明确不可用，不临时切换专业worker或示例模型。

## 4. 状态与事件

命令实际wire映射、对象修订与Thread游标区别、答复生效和旧客户端迁移，以
[协议决定](2026-10-16-enterprise-protocol-decisions.md)为准。下面信封保留为语义示例，不直接作为v1服务输入。

Work状态：queued、running、waiting_input、paused、partial、completed、failed、cancelled。
暂停/取消请求属于命令状态，不能提前写成任务已停止；超时或断网不自动视为取消。
Work可在completed/partial/failed后根据新目标修订继续，旧Attempt及结果保持历史状态。
cancelled后显式继续创建新的Attempt，不能复活旧租约。

Action状态：proposed、dispatched、succeeded、failed、cancel_requested、cancelled、unknown。
执行前记录action_id、输入摘要、所用snapshot和外部幂等能力；只有有效租约能写入新决定。
外部返回晚于租约失效时先存回执，再由当前执行者审查，不能直接覆盖Work状态。
unknown恢复查询真实外部状态；无可用查询且有副作用时需要处理决策，不能盲目重放。

任务事件信封：

```json
{
  "schema": "capstone-work-event/1",
  "work_id": "work_example",
  "sequence": 18,
  "work_revision": 8,
  "attempt_id": "attempt_example",
  "execution_snapshot_id": "snapshot_example",
  "type": "artifact.revision_published",
  "occurred_at": "2026-10-15T12:00:00Z",
  "payload": {"artifact_id": "artifact_example", "revision": 2}
}
```

事件种类包括work.state_changed、goal.revised、resource.observed、action.updated、
finding.recorded、finding.revised、input.requested、artifact.revision_published、
artifact.validity_changed、command.applied。每种载荷单独校验。
工作状态与事件在同一事务提交；上例sequence映射现有Thread event_seq，work_revision用于目标聚合写冲突。
按Work筛选后序号允许间隔，不将其误判为丢事件；完整性检查由原Thread流承担。
两者不冒充外部资源版本。心跳与连接状态不占业务事件，不暴露模型隐藏思维。
快照包含last_sequence；SSE按游标衔接，过期游标返回需要新快照，不以空流假称无变化。
客户端去重、检测缺口并补取，不能直接跳过未知状态事件宣称已恢复。

## 5. 研究状态、工作区与成果

研究状态按需包含问题、判断、依据关系、反例、缺口和方法选择记录。
模型可以提出更新，宿主检查引用存在、所属授权、版本及状态转换。
缺少支持的判断保持待验证；成功的计算不自动证明解释成立。
交付检查读取目标当前版本与已保存产物，分别记录确定性检查、模型评审和人工确认。

私有执行工作区与持久工件存储分离。工作文件可修改；已发布ArtifactRevision不可变。
发布顺序：写临时对象→校验大小/摘要/类型→原子登记内容和依赖→提交发布事件。
数据库和对象存储非同一事务时使用暂存状态与幂等finalize，只有finalized对象可下载；
失败留下可回收暂存对象，不能留下已发布但不存在的文件引用。
配额超限、传输不完整和摘要不符显式标记对应对象失败或未就绪，允许局部重试、分片或其他获准格式。
其他已保存成果仍可交付；必要答案/证据持久化失败不报告成功。不得静默跳过收集。

产物投影包含artifact_id、revision、work_id、title、media_type、kind、byte_size、
content_digest、producer_action_id、input_refs、validation_summary、availability及validity。
kind使用通用document/table/chart/code/model_view类别；业务字段留在实际资料和内容中。
模型公共投影可由专业视图展示；不能把raw网络对象包装为一般文件传到浏览器。
availability描述内容能否访问，validity描述与当前任务/输入是否相符，两者独立。

恢复保存文件manifest、环境身份及任务检查点。模型会话历史可压缩，但目标、引用、
未解决操作和产物依赖不靠摘要保真。缺失输入或环境时指出缺口并按依赖范围处理恢复。
缺失输入/环境只暂停依赖它的恢复分支；可恢复的工作在新租约下继续。unknown动作隔离自身、
依赖及可能冲突操作，不阻止无关工作；不能盲目重放。必要持久化和专业准入边界保持不变。
输入更新使相关派生判断和成果待重验；修订事件保留旧版，新版完成前不能标记已替换。

## 6. 前端视图与动态artifacts

应用登记可信组件；conversation、analysis_report、model_decision仅为首批示例，不是协议的封闭枚举。
视图注册声明view_id、受支持的公开产物schema及版本、所需资源角色与安全回退。
专业选择字段由对应Pack的公开投影定义，不进入通用任务必填字段；新增视图不改变组织机制。
Profile可建议视图，运行时按实际公共资源/成果类型与可用性解析。
模型不得注入任意前端代码，Pack不得通过HTML资源获得应用同源脚本权限。
未知产物类型使用安全下载/通用元数据回退，缺少专业视图不改变专业结果保证。

同一会话保留草稿、视图偏好、选中产物版本与资源选择；服务端保存任务和产物状态。
用户查看旧版时收到新版本提示，不抢焦点；最新版本依赖失效时显示待重验。
多会话列表分别显示后台运行、待补充与已完成，不把当前浏览器订阅当执行生命周期。
会话归档、重命名与任务取消是不同命令。归档不删除产物或停止后台工作。
普通问答无需准备电网worker；专业视图只在有合适资源时出现。

## 7. 专业级图表是通用产物能力

Demo1的正式交付包含专业图表。原生分析工具、绘图库或获准skill产生图表；
Capstone不新增电力图表API，也不强制每个任务使用同一种绘图库或图形模板。
图形选择由分析目标、数据类型和可用方法决定，不能写死价格查询后的图表顺序。

图表产物应组成可追溯的一组资源：原始/派生数据引用、绘图代码或等价可复算规格、
参数与环境身份、预览、矢量或印刷级导出及检查记录。图表数据不由模型凭空填数。
工作台可交互预览，但报告交付必须有独立可打开的静态产物；交互内容不作为唯一结果。
默认优先SVG/PDF矢量输出；需位图时按目标印刷尺寸输出足够像素，报告级默认300dpi。
这是输出配置，不要求所有屏幕预览都使用高分辨率文件。

通用图形检查：标题说明所回答的问题；轴/单位/时间范围明确；图例与系列对应；
缺失值不画成零；聚合与抽样规则可追溯；颜色对比、线型或标记不只依赖颜色区分。
比率的分子/分母、单位换算与加权方式保存在分析依据中，不能仅靠漂亮坐标轴掩盖错误。
同尺度对比、色标、异常标注、置信范围的使用必须有数据依据。无置信估计不画虚构误差带。
数据量过大时预览可降采样，但记录规则并保留完整计算数据；极值与事件区间不得被无声抹去。
跨省比较、事件窗口、时间序列或分布图是Demo1可能的选择，不是必需四张图的固定清单。

前端图表视图提供标题、交互预览、来源/口径、数据查看、版本与导出。
公开投影只返回有界数据或受控资源引用；大表按页取，不把完整企业数据发往浏览器。
图表与报告引用固定revision。数据或方法修订后标识旧图待更新，新图发布才更新报告引用。
下载检查文件可打开、文字无缺字、图例未裁切、单位可读，图中关键数值与计算产物一致。
一次模型评审不能替代计算核对；图表排版和数值正确性分开验收。

## 8. 外部前提与交付边界

### Demo2的专业投影边界

同一Work可引用专业场景产物与通用报告产物。专业Pack拥有场景、候选和验证语义，
Application的受信视图适配器呈现公开投影。Kernel只管理通用身份、状态、版本和依赖；
电压、线路、快照格式和优化目标不加入通用任务协议的必填字段。

专业投影绑定模型修订、快照、场景修订、约束修订、候选修订及实际准入的结果引用。
验证记录绑定候选修订与验证执行，区分计算状态和检查结论。仅在专业契约要求的检查全部满足时，
应用才能显示该适用范围内的验证通过。未收敛、无可行解和未验证都有明确投影，不能以空列表冒充无越限。

约束或输入改变后，依赖图标记旧候选/验证/图形过期；历史引用仍可读，新验证不能覆盖旧版本记录。
前端拒绝把晚到旧选择投影挂到当前候选。通用绘图执行若获准读取有界数据，只生成派生产物，
必须保留父结果引用；不得修改专业结果或将自身输出提升为Authority证据。

Demo2界面验收包括切换候选时图形和验证身份一致、部分检查通过不显示整体通过、
约束变更后旧结果失效、失败/无可行解可解释、选择方案不触发外部动作，以及跨会话恢复不串场景。
当前设计原型仅以合成数组验证其中的呈现与选择交互，不验证上述服务端保证。

### 真实交付前提

企业提供实际可访问的数据、资料、口径与权限，专业系统提供真实计算能力。
Capstone提供通用的发现、执行、研究组织、来源记录、检查和呈现，不建设数据平台。
Demo1通过需要实际工具和独立核对的报告/图表；合成或脱敏数据可以验证机制，但
必须标识其性质。Demo2另行验证选定Authority实际支持的计算与独立校验范围。
本设计不因界面上有场景、进度或图表，就声明后端已经具备这些能力。
