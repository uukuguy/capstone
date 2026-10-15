# 企业自主执行：评审缺口的解决设计

状态：评审后的补充设计，未实现。补充总设计、执行契约和界面契约；下面的明确决定
优先于旧文档中的“建议”“按需处理”等模糊描述。本文不把尚未验证的SDK能力或企业资源写成已具备。
适用范围为统一框架，不为Demo1增加业务接口，不为Demo2伪造专业计算能力。

2026-10-16：本补充已并入[定稿v1](2026-10-15-enterprise-design-final.md)。定稿明确复用现有Thread、
worker租约、研究控制器和专业前后端资产；本文逻辑对象不代表另建一套表、协议或调度器。

## D1. 单一持续执行循环与宿主检查点

Pi session拥有一次Attempt内的模型上下文与下一行动选择。Capstone Harness拥有持久Work、
授权、预算、行动准入、检查点及交付准入。Harness不另开一个模型计划循环重复规划Pi的每一步。
简单问答使用相同session入口，允许零工具直接完成；研究记录在需要时增量建立。

新增通用执行桥，提供start/resume、steer、pause、cancel及以下事件：

| 边界 | 必需内容 | 宿主处理 |
| --- | --- | --- |
| action.proposed | action_id、parent_action_id、tool_ref、参数摘要、effect_class | 核对租约、授权、预算、工具schema；持久化后发放执行许可 |
| action.receipt | action_id、执行状态、结果/资源引用、实际用量 | 接纳回执并保存；引用校验后向Pi返回有界观察 |
| research.patch | base_revision、增删改操作、依据引用 | 校验CAS、引用和状态，保存公开研究记录 |
| checkpoint.ready | 消息游标、工作文件manifest、环境身份、未决action | 持久化完成后确认检查点；不把内存session序列化当唯一恢复依据 |
| delivery.proposed | goal_revision、逐项满足情况、产物版本与检查引用 | 按D5决定completed、partial或继续；模型不得自己写completed |

专业能力通过受限语义执行上下文调用，通用上下文只能取得经授权的公开结果交接。
每次工具执行必须在副作用发生前经过桥；仅订阅执行后的日志不能满足准入。
对shell内的外部访问，工具级批准不等于任意出站权限：外部资源只经批准代理，
沙箱无宿主凭据、无业务内网直通。原生read/write/bash只操作私有工作区。

先做SDK边界验证：证明工具执行前可阻断、暂停能在安全边界生效、消息历史可恢复、
错误和退出可回传。现有general-sdk.mjs的inMemory会话不能被当作这些保证。
若当前SDK不提供必需的前置钩子，使用受控tool provider封装原生执行边界；
若原生工具仍可绕过该provider，该执行配置禁止启用，不能退回“靠提示词限制”。
这个验证先于后端大规模改造，失败时产出具体不支持的边界和SDK适配任务。

## D2. 通用资源接入与工作文件交付

Application维护资源注册与授权，Pack只声明需求。MCP、skills、文件保持原生内容及schema。
新增的是通用资源运输与引用契约，不是指标、价格、通道或新能源的业务API。

ResourceRef字段：resource_id、owner_workspace_id、source_kind、source_locator、
version或observed_at、content_digest（可空但须说明原因）、media_type、size（可未知）、
access_scope、allowed_operations、availability、capture_mode、completeness。
source_locator是脱敏可公开定位，不包含令牌或可任意访问的内网URL。
ResourceCapture记录一次实际取得的内容：capture_id、resource_id、producer_action_id、
版本/时间、分页游标或导出回执、observed_count、expected_count（如来源提供）、manifest。
completeness为complete/partial/unknown；无全量证明时不得标complete。

| 接入方式 | 交付方式 | 故障与恢复 |
| --- | --- | --- |
| 原生MCP返回小结果 | 宿主接纳观察，保留调用与来源；向Pi给有界内容 | 协议失败与业务空结果分开 |
| MCP返回文件或分页结果 | 受控适配器读取获准返回资源，流式写私有输入区并登记capture | 保存游标/分片；不能续传则重新获取新capture，不拼接不同来源版本 |
| 用户上传 | 上传会话→流式写入→摘要/大小/类型检查→finalize→ResourceRef | 未完成附件不能提交执行；重试沿用upload_id，不向浏览器暴露bucket凭据 |
| 已批准skill | 固定版本/摘要加载，依赖在镜像或受控环境准备 | 缺依赖明确不可用，不在企业运行中任意安装提权 |

公共通用端点补齐：GET workspace resources（分页、授权过滤）、POST resource-uploads、
PUT upload content、POST upload finalize、GET upload status。
每个上传绑定workspace、主体、配额和失效时间；最终ResourceRef必须获任务引用授权。
后端内容接收统一检查符号链接、路径穿越、压缩包展开限额；输入副本只读，输出目录单独可写。
跨Pack交接必须保存source_binding、target_binding、reference_kind、purpose、grant_ref、
source_revision、target_admission及receipt_id。双方使能不替代这张交接回执。

Demo1的数据及口径仍由企业提供；缺少时允许补资料或限定交付。不得把“能正确报告缺口”当作
完整任务验收。至少一个资料充分案例必须走真实原生工具、生成可复核报告与图表。

## D3. 配置快照、租约与持久状态

修正原契约的快照基数：Attempt保存initial_snapshot_id；每个Action保存实际使用的snapshot_id。
一个Attempt可在行动边界采用多个不可变快照。Work的active_snapshot_id只表示下一行动的配置，
不能改写已发Action或历史事件。新增授权在边界采用；撤销立即阻断新调用。

持久对象由通用应用服务管理：workspaces/config_revisions、threads、works/goal_revisions、
attempts、execution_snapshots、actions/receipts、commands、work_events、resource_captures、
research_revisions、checkpoints、artifacts/revisions/dependencies。领域内部状态仍由各Pack拥有。
关键约束：一个Work最多一个有效主租约；事件(work_id,sequence)唯一；
命令(principal_id,target_id,command_id)唯一；产物(artifact_id,revision)唯一。

主租约优先复用既有lease_token/deadline条件写入并用测试验证隔离；不足时才增加fencing_epoch。
目标写入增加expected_revision CAS，不重新建设租约系统。
外部调用前先登记Action并提交dispatch记录；分发器消费该记录。旧worker晚到回执可追加，
但不能改变Work或触发下一外部动作。外部系统不支持fencing时，不能保证撤回已发动作，
其结果保持unknown并进入核对，不因本地租约过期声称外部动作没发生。

数据库事务同时保存状态、命令回执与事件；工件暂存/finalize采用原契约的幂等发布流程。
持久化失败不向Pi确认成功，不向前端发送已完成事件。

| 当前状态与命令 | 行动边界处理 | 后继状态 |
| --- | --- | --- |
| queued + start | 取得租约、检查配置和资源 | running；缺资源为waiting_input；不可恢复配置错误为failed |
| running + message/revise_goal | 保存命令，下一安全边界应用目标修订并重验依赖 | running或waiting_input；前端收到applied才视为生效 |
| running + pause | 停止新分发、请求取消、保存可确认检查点 | 未结束操作仍为running且pause pending；安全停稳后paused |
| 任一非终结态 + cancel | 同上，但取消当前目标执行 | cancelled；外部unknown单独保留，不能假定已撤回 |
| waiting_input/paused + resume | 核对输入版本、未决动作、预算与授权 | 新Attempt进入running或保持waiting_input |
| completed/partial/failed/cancelled + revise/resume | 显式新目标修订或继续命令，保留旧结果 | 新Attempt排队；不复活旧租约 |
| delivery.proposed | 执行D5交付准入 | completed/partial，或保留running继续补齐 |

非法转换返回invalid_state；修订冲突返回revision_conflict及当前快照引用；
授权失败返回not_authorized；缺资源返回resource_unavailable；预算不足返回budget_exhausted。
这些是机器码，前端使用读者友好的消息。所有错误保留command_id和可重试性。

## D4. 中断恢复、预算与未决动作

恢复检查点包含Work/goal/research修订、Pi可恢复消息历史引用、资源capture和文件manifest、
环境镜像摘要、依赖版本、未决Action、工件游标、累计用量。敏感内容按授权保存，不公开到SSE。
恢复先获取新租约，核对授权和外部未决动作，再重建工作目录与受控环境，最后恢复Pi上下文。
文件恢复由宿主检查摘要；环境不匹配先重建，不把任意最新依赖当成可复现环境。
生成中的内存状态丢失时，从最近确认边界重新组织；已发副作用不得随消息回放再次执行。

effect_class为read_only、workspace_write、external_write。read_only也可能收费，重试计入预算。
unknown优先使用外部operation_id查询；无查询能力时产生resolution_request，允许用户提供
外部确认或明确授权一个新的动作。解决回执必须引用原action，新的动作使用新action_id。
无法证明幂等的external_write首版默认不自动重试；不宣称端到端exactly-once。

预算由应用配置并在Work开始时冻结：模型调用/令牌或费用、墙钟时间、并发子任务、
CPU/内存、工作区和工件大小。子任务从父预算预留，结束后归还未用部分；并发记账须原子化。
耗尽后阻止新行动并保存状态，已有成果按D5检查后partial，否则paused，reason=budget_exhausted。
用户显式增加预算产生配置修订；模型不能自行放宽。重复无进展探索可提出停止建议，
硬预算始终由宿主执行，不能只靠模型自评“已经足够”。

清理策略按租户配置：活跃Work、检查点、发布产物及其有效依赖禁止被普通临时文件清理回收。
上传暂存和无引用失败产物按过期策略回收；删除与权限撤销留审计记录。
SSE游标过期返回snapshot_required，不删除任务恢复所需的证据关系。

## D5. 交付检查与专业级图表

GoalRevision含可检查的交付要求列表：requirement_id、描述、required、检查方式、
检查资源引用及适用范围。模型可提出细分，宿主记录来源；不能自行删除用户要求。
每项结果为satisfied/unsatisfied/unknown/not_applicable，关联固定产物版本和ValidationReceipt。
not_applicable须有已接受的目标修订或明确适用性规则，不能作为跳过难题的通道。

ValidationReceipt包含check_id、checker_kind、checker_version、input_refs、scope、
status、findings、执行身份和时间。checker_kind区分deterministic、authority、model_review、human。
模型评审不升级为独立数值验证。来源完整性不证明数据本身正确；专业结果也不证明因果解释。
required项全部satisfied或合法not_applicable、产物已finalized且当前有效时才completed。
缺项而存在可用产物时partial并逐项说明；无可用产物则继续、等待或失败，依据实际原因选择。

图表是artifact bundle：data、code或spec、environment、preview、exports、validation receipts。
报告固定引用图表revision，不动态嵌入“最新图”。数据修订向后标记依赖失效，不能原地改旧图。
图表数据校验读取完整计算产物；前端降采样只影响显示，并保存降采样说明。
输出契约选用可独立打开的SVG/PDF及按需要的位图，明确实际版面尺寸、字体和分辨率。
SVG预览禁脚本/外部资源，HTML交互产物放在无同源权限的隔离预览中；模型生成代码不得进入App组件树。
只读数据表及静态图始终作为交互图的可访问回退。导出失败只标导出未完成，不伪装报告全部交付。

检查规则来自应用交付标准和实际外部业务资料；不增加电力指标schema。
新业务任务只换资源、方法和获准检查规则，不改Kernel的判断或工具序列。

## D6. 前端未覆盖路径与专业视图

| 操作/状态 | 确定的交互与契约 |
| --- | --- |
| 同一Thread有多个Work | 头部任务切换器显示当前目标、状态；输入明确“继续此任务”或“新任务”，服务端回执绑定work_id |
| 附件/资源 | 资料抽屉选择授权资源，显示上传/处理中/可用/失败；发送仅引用finalized资源，失败保留草稿 |
| 待补充/未决动作 | 卡片含request_id、问题、影响和允许的回答；答复命令引用request_id与目标修订，旧问题不误应用到新目标 |
| 后台任务 | 会话列表投影显示running/waiting/finished；订阅切换不取消后台执行 |
| 冲突/撤销 | 显示服务端当前配置与本地草稿差异；保留输入，重试用明确新修订，不覆盖远端状态 |
| 动态成果 | 目录按artifact身份显示多个图表/数据/报告；版本选择、来源面板和滚动位置按Work保存 |
| 专业场景 | 选择模型/快照/故障对象，显示前提缺口；候选选择联动真实结果身份，不触发外部调度 |

补齐通用命令：thread.rename、thread.archive、work.message、goal.revise、input.respond、
work.pause/resume/cancel、action.resolve。采用同一幂等信封与严格判别载荷；
input.respond须带request_id、expected_goal_revision和response；action.resolve须带action_id及外部确认引用。
Thread列表增加分页Work摘要；配置目录只返回当前主体可见范围。所有写入口均检查workspace归属。

完成前端设计验收须增加这些状态的可操作样例，不能只看两个成功结果页。
现有原型的localStorage恢复仅证明本机示意状态；不作为跨设备、worker重启或权限恢复证据。

Demo2正式视图直接复用已有NetworkView、模型投影与结果定位能力。记录的IEEE-39 SVG是静态设计素材，
合成A/B是独立交互样本；不得强行将二者绑定。专业验收另选同一真实注册模型/快照的候选和验证结果，
缺少对应结果时显示“无当前结果”。专业能力不支持AC复核或所需优化约束时，该验证项不可完成；
通过注册具备能力的Authority补足，或者用户显式缩小目标，不能让通用代码假扮专业求解器。

## D7. 验收设计与实施边界

先构建不含业务分支的协议验收，再使用外部资源包评估业务任务质量。

| 验收包 | 供给与断言 | 不通过的处理 |
| --- | --- | --- |
| 通用机制 | 替身执行器注入乱序/重复/断线、租约过期、授权撤销、对象存储失败 | 对应不变量全部通过才接入实际Pi |
| 原生Pi桥 | 实际SDK验证D1前置阻断、skill/MCP发现、检查点、暂停和恢复 | 未支持边界关闭配置并修适配，不启动长程成功宣称 |
| Demo1完整资料 | 外部MCP/文件给价格、通道、新能源及口径；独立核对基准与字体/导出检查 | 必需指标/报告/图表缺失或错误为失败，不能仅凭有报告文件通过 |
| Demo1变化/缺口 | 改字段/工具名、分页、口径冲突、反例、缺少消纳依据 | 变化后不改核心代码；正确修订或限定交付，不伪造弃电结论 |
| Demo2 | 已注册模型/一致快照，故障、候选、独立专业复核 | 检查失败不显示可行；无解、未收敛、部分覆盖、旧结果分别验证 |
| 多Pack协作 | 一般资料+专业结果、显式交接、不同历史时刻及撤销授权 | 错时刻/越权交接被拒，来源类型不升级 |
| 迁移与入口 | 现有专业案例与新无模型任务共存，dev真实入口执行 | 旧专业准入不削弱；仅UI fixture通过不算集成通过 |

评测资料、固定日期解释、业务口径、数值容差、软件环境和核对实现作为外部验收manifest版本化。
每个完整资料案例首轮至少运行3次，要求必需交付均满足；该门槛只表示首轮准入，不宣称统计稳定性。
预算、耗时、人工介入和失败轨迹完整记录；未知引用、伪造证据、越权和盲目重复写入零容忍。
真实Provider质量评估需要已有授权，不以离线协议测试替代。

实施采用五个纵向切片，每片同时交付后端投影与最小前端：
1. Pi桥能力验证、Profile公共/专业配置拆分、无模型Work及直接问答入口。
2. 资源/上传capture、持久工件和报告/图表工作区，资料充分Demo1最小闭环。
3. 研究修订、租约/预算/检查点、输入与产物失效，故障注入恢复验收。
4. 专业投影和NetworkView集成、多Pack交接、Demo2验证与失败视图。
5. 外部验收包、现有专业回归、真实模型质量和部署前端到端验证。

旧Thread/模型数据保持可读，新增Work表和协议版本并行接入；不删旧证据或重写历史运行身份。
应用入口切换前必须有显式数据映射与回退配置；无需保留旧CLI，但必须保留既有用户数据。
文件级计划、语义schema与状态矩阵检查已纳入定稿资产；生产wire映射与真实故障注入仍是实施准入，
不能用设计检查冒称运行验收。
