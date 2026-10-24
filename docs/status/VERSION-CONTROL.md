# 多线版本控制

2026-10-25 分支收口进行中：PR #56 将已验收的工作空间及完整运行依赖并入dev。运行b87ac5d2、界面c34b4780、文档db60bc8d；ae9dd0fe已同步dev。当前PR为草稿，双平台CI与完整回归待完成，尚未合入。dev原控制改动保存在c306060c恢复stash；不删除恢复引用或用户数据。URL命名工作空间和精致空态为后续工作。

2026-10-25 左栏修正：缓存视图恢复时补读置顶偏好，命名空间切换与跨页偏好变更保持同步；收起再展开回归通过。改名输入框13px/30px，Esc取消编辑并保留左栏。941App及最终8项框架测试、构建、doctor、浏览器检查通过。内存策略已改默认10，可选10/20/50，按切换次数与最后打开时间保留。URL命名工作空间及精致空态仍待实现；候选未合dev，cloud/demo不变。

2026-10-24 会话阅读状态与分层缓存：最近5个会话保留内存，可在设置选择1–20范围内的数量；超额按最近访问顺序释放旧视图，浏览器磁盘保留轻量阅读状态，宿主持久化会话和制品。自动释放不执行业务归档、不取消任务。932App/类型/doctor通过；实页主区180px、iframe220px保留，返回完整快照请求0；上限1时释放旧DOM，再开恢复165px及原报告选择。规范重建backendc64fbe52c992/nativeada86461950c，118源码/ready/App通过。未合dev，cloud/demo不变。[验证](../reviews/2026-10-24-session-view-cache.md)

2026-10-24 中断恢复收尾：补齐归档会话“读取更多”，防止关闭后重开时旧请求覆盖新目录；保留返回最近列表的滚动位置。全量 App 927/927（10.77秒）、类型/doctor/diff通过，真实归档接口2→4条不重复分页及1280/375px浏览器检查通过。local-dev规范重建backendc64fbe52c992/nativeada86461950c，118源码/ready/App通过。界面候选仍有跨包未提交依赖，未合dev；cloud/demo不变。[复验](../reviews/2026-10-24-workspace-navigation.md)

2026-10-24：共享工作空间导航/管理本地验收通过：三栏独立显隐、宽度拖动保持、页内切换无空目录/临时当前会话占位、置顶/双击改名/归档恢复/确认删除、电网工具条及紧凑步骤间距。169App/18最终定向/类型、55后端通过，2PG夹具跳过，真实浏览器/本地PG临时会话验收通过并清理。backendcba33ec86225/nativeada86461950c，118源码/ready/App/cleanup通过。未合dev，cloud/demo不变，338秒/59工具基线不变。[记录](../reviews/2026-10-24-workspace-navigation.md)

2026-10-24用户确认当前性能基线：三分支并行338秒/59工具，两分支并行412.4秒/56工具，顺序544.6秒/67工具。后续以当前三路338秒/59工具对照；146秒仅为旧版归档，不再作为当前验收门槛。

2026-10-24：通用独立成果优先并行，原样三路报告336.512660秒/59工具记录/59LLM（顺序544.609189秒，前轮两路412.363329秒）。启动与收尾特殊节点展示主链，空图不再强制续规划；真实直接回答4.182780秒/1LLM/0工具/0图。最终local-dev backendef748ad9dbeb/nativeada86461950c，116源码/ready/App、153SDK/293App/类型/doctor与清理通过。16.6秒主链请求前间隔仍待定位，146秒归档为旧版，未合dev或改cloud/demo。[记录](../reviews/2026-10-24-parallel-outcome-planning.md)

2026-10-23 07:12：返回接纳候选规范重建通过，backend71a06405/nativecfff03d9，112源码/ready/App HTTP和清理通过。真实原样登记71.037秒完成，子节点11.328秒、4LLM/3工具、无错误，宿主已接纳新返回工具。恢复HTML与CSV经显式上传再输出，下载SHA与归档原件一致；没有重写报告。此为接线/保存验收，不是146秒研究性能比较。178JS/148Python通过，99文件冻结；下一步原四文件/原指令顺序后并行对照。

2026-10-23 07:05：062221在结构化返回事件处失败501.792秒，原因是新工具遗漏宿主来源白名单。已补真实宿主子任务限定接纳，并把文件封存移到返回事件之前；178JS/148Python通过。汇总模式不撤销宿主授予的源权限，重复问题/预期输出可派生，调度能力明确提供给引擎。99文件规范重建中；备份恢复出2.3MB报告和CSV，尚未入库，下一步显式上传为新资源并原样登记，不重做报告。无活动模型任务；146秒完整顺序/并行仍待验收。

2026-10-23 06:18：054012顺序测试885.600秒失败，四节点已保存，汇总仍被“有限成果另行接纳”手续阻塞，随后触发无进展保护；不是有效完成基准。现修App可选有限成果消费并保留全链局限，补Python密封句柄校验；新增子任务结构化返回工具，宿主编码元数据，省去模型手写/解析协议JSON。178JS/64Python通过（9跨语言链+1实际固定SDK工具回合，非真实模型替代）。98文件冻结，规范重建中；无模型任务。7份表及6图保留，下一步仅据此汇编报告。146秒基线和顺序/并行对照仍开放。

2026-10-23 05:40：052253三主题历史成果报告已保存，595.066秒仍异常。规划新增了用户未要求的XLSX、图数、章节和自检包，现改结果与输入输出驱动、可省略检查、根来源宿主派生。173JS通过；规范重建7dc8e8d7/native3d178a07，112源码/ready/App HTTP/清理通过。原四文件/原指令顺序测试已启动（thr_a3ad71215eb1751fa8f8），并发1、源码冻结；并行对照及146秒性能仍未验收。

2026-10-23 05:27：增量来源候选规范重建通过，backend c6094093/native edc5e929，112源码/ready/App HTTP及清理通过。172JS通过。three-topic-recovery-052253已在原Work启动，汇编节点选择17份历史成果；尚有两次模型规划格式/来源错误，不宣称性能修复。146秒完整顺序/并行仍待验收。

2026-10-23 05:16：050155已保存4份文件但仅覆盖价格，不能算三主题报告。根因是首批图资料范围被误当永久授权目录，后续任务选其他已授权资料被拒；旧汇总契约又拒历史产物单独输入。现按显式任务选择扩展已用目录，保留宿主授权/每任务版本绑定，允许轻量历史产物汇总；172JS通过，97文件规范重建中。无模型任务，146秒基线及完整顺序/并行验收仍开放。[诊断](../reviews/2026-10-23-lightweight-task-nodes.md)

2026-10-23 04:54：034025最终失败原因是DEBUG原生事件队列满被误判容量超限（257/256），859.119629秒中断，15份入库CSV/Markdown已下载；迟到归档为空，不能算保留通道私有数据。已改有界背压、先保存安全文件后验语义、保守角色归类和增量目标覆盖，140JS/74Python/6Linux通过；当前运行8d791b98/native16d1e8ce，112源码核对通过。043222恢复在约603秒诊断停止，仅保存3份通道成果，报告越入新分析未完成。现显式传任务mode，汇总仅消费保留成果，143JS/29Python通过；97文件新候选规范重建中。没有活动模型任务，146秒基线和完整顺序/并行验收仍开放。[诊断](../reviews/2026-10-23-lightweight-task-nodes.md)


2026-10-23 03:40：真实第三轮仅改标题52.119秒交付，4090正文逐字节不变；此前两轮118.529/158.104秒暴露自行字数配额及未选择已有原稿，均已修指导和来源清单。032707顺序诊断因子任务来源遗漏后查目录而停止（165.848秒、23LLM/27工具）。现保留节点source_refs必填，135JS/9跨语言检查通过；规范重建b0bde166/native23a548f5，111源码/ready/App HTTP/cleanup通过。95文件冻结，新并发1原始请求sequential-autonomous-application-20261023-034025中。完整报告与顺序/并行性能仍待验收，145.914727秒基线不变。[记录](../reviews/2026-10-23-lightweight-task-nodes.md)


2026-10-23 03:10：按用户确认改为持续多轮研究：保留不完整返回，取消轻量任务自动重写，新增显式有限交付，区分内部检查与用户认可。新App1.18/Pack1.15/shared1.5保留历史版本；135JS/137宿主检查通过（1跳过）。规范重建exit0，API/all workers0e5788c1/native47c43dd5，111源码/ready/App HTTP/cleanup通过。95文件冻结，并发1真实README两轮验证中（thr_2f8cb2bd2f0f1398bb01）。021714已于289.147秒失败、无产物；完整原始请求顺序/并行和146秒性能验收仍开放。[诊断](../reviews/2026-10-23-lightweight-task-nodes.md)


2026-10-23 02:18：组织角色/计时投影候选规范重建exit0，API/all workersc8486412、natived1feeef2，103源码/ready/App HTTP/cleanup通过。新顺序对照021714运行中（thr_cd2a50635a1d43f2e872 / attempt_c12a8da4c07b3885）；首任务已改为只读结构观察，无主数据集/全业务计算前置，原生execution_ms已进入实际公开记录。91文件冻结，并发1；不在运行中改源码或开第二轮模型任务。完整交付和顺序/并行性能仍待验收。

2026-10-23 02:13：并发1顺序诊断015900因异常消耗停止，323.523秒取消、无报告；首探查174.317秒、23LLM/161.294秒、23工具/13.513秒，无任务重叠。节点实际承担完整画像/对齐及后续业务计算，说明调用膨胀在并行前已存在。已修轻量主链仍沿用编码助手基础角色、worker漏传execution_ms两处缺陷，125JS/145Python/9真实跨语言链通过；新91文件冻结、并发1规范重建中。待检查新首任务范围及真实计时，再完成顺序和并行对照，未宣称性能修复。[验证](../reviews/2026-10-23-lightweight-task-nodes.md)

2026-10-23 01:59：修正候选规范重建exit0，API/all workers51709301、native47641938；102源码核对、ready/App HTTP及scoped cleanup通过。并发1顺序对照已开始，thr_4af9ff4b803081d84817 / attempt_c02fb5be8242fb37，使用原始4资料及同业务指令，源码冻结期间不修改或启动并行对照。完整交付与性能仍待结果。

2026-10-23：012219原始请求在诊断上限停止，取消终态956.852秒；保存32份CSV/Markdown过程文件，无完整报告。三分析任务实际并行，但各24–37次LLM，未通过146秒基线。已修独立任务丢失可信运行环境说明、补原生工具执行计时并与记录区间分开、轻量空输入数组规范化（保留依赖/授权校验）；125JS/85Python/169App、类型/doctor/diff通过。当前只在model-decision未提交候选，顺序并发1规范重建中，89文件冻结；用户要求先修缺陷，再同代码/模型/资料/指令顺序与并行对照。无新模型试验、Git/cloud/demo变更。[验证](../reviews/2026-10-23-lightweight-task-nodes.md)

2026-10-22 01:54共享过程展示增量：通用ProcessStepRecord已服务执行图和原任务步骤；默认折叠保留真实结果摘要，放大默认展开，手动状态优先并分别保存。顶栏图标、结果/任务/执行同级区块及折叠诊断已实现；290项App与类型/doctor/diff通过，Vivaldi实际页面和放大阅读检查通过。规范本地重建5062a21f/nativeb9124711，55实际源码/ready/App HTTP及scoped cleanup通过。UI验证无新模型请求；005501零子任务的并行验收失败结论不变。未提交、合dev或改云端/demo。

2026-10-22 01:04最终本地复核：并行组标题已加入工具/LLM计量，176App/类型检查及doctor/diff通过；规范重建exit0，API/all workersa83ad0a4/nativeb9124711，55实际源码/ready/App HTTP检查和scoped cleanup完成。最终组标题视觉复核待做，用户正在浏览器输入，未继续切页或操作输入框。真实005501的142.859889秒、0子任务与并行验收失败结论不变。

2026-10-22 当前增量：并行任务按同依赖分组、统一缩进、每项独立细线；组标题显示实际总耗时、工具和LLM计量，176项App/类型通过。子契约增加精确来源文件映射和未完成产物模板，147JS及9项真实SDK跨语言链通过，保留全部准入检查。规范重建72c09568/b9124711及55项实际源码核对通过，最终UI重建复核中。原始请求005501用时142.859889秒、17父/0子响应、761666tokens，报告字节已下载；模型修订合并计划失败后把全部工作放入准备节点，三个并行分支未启动。并行验收失败，不算146秒基线的并行提速；质量未接受。后续先查计划修订恢复和动作范围，不盲目重跑。未提交、合dev或改云端/demo。

2026-10-22：共享规划策略1.0/App1.13/Pack1.11首次适配；旧13发布保留。原始请求235939实际三路并行64.165秒，但218.375秒按failure收口、无报告，19父/43子响应及2120572tokens，不通过146秒（145.914727秒）基线。步骤号、标题行计量和简短状态已修订，282项App检查/类型通过。Python65通过/1可选PG跳过，JS140通过，改动Python类型0错误；全库9处旧错误另列。独立复审不可用，未批准。最终规范重建exit0，55项源码/同源/ready/App HTTP/cleanup通过；API/all workers164f2f2d、native624128c2。未提交/合dev或改云端/demo。

2026-10-21当前实现边界：自主有界执行与确切limited输入已实现，App1.12/Pack1.10尚未部署。初冻206JS/189Python通过、1可选PG夹具跳过，实际跨语言链无跳过；独立审查发现R1异步创建跨截止仍可能发请求、R2仅在评估摘要中的限制未传播，现仅授权这两项窄修并重新冻结。初次阻断与快照保留，不宣称源码通过或整链完成。部署仍为5143/319f；正式实测入口只提交原始业务指令。

2026-10-21：完整应用142026因异常消耗于379.306秒取消，报告尚未执行、无交付。至少111次已完成响应（18父、93子），已知完成用量4,946,619tokens，非完整计费总量。三子任务自动启动跨度0.477秒，但每个承担完整分析与作图，256+8轮预算未收束；limited结果无法供下游消费。当前开展有界子任务与显式受限结果准入设计，源码保持冻结。两次application-path探针附加了并行技术提示，不能证明自主规划；下一次正式验收只用原始业务指令。已部署API/all workers `5143d7c4`、native `319f3de1`及35源码/ready/App HTTP/scoped cleanup通过；185JS/128Python零跳过。整链与性能未验收。

2026-10-21 13:49：上下文稳定位置与面向用户的任务步骤已独立复审并部署，API/all workers `72782e4b`、native `b092d2bc`，33部署源码/ready/App HTTP/scoped cleanup通过；183JS/52Python/277App及类型检查通过。前端隐藏内部图主视图，保留真实步骤、工具及终态。完整应用实测134506于178.509秒因native_receipt_persistence_failed失败，无交付；前置评估后编排器自动启动三分支，首末间隔0.616秒。当前优先修回执持久化阻断，不把失败耗时当提速。按用户新标准验收可用报告、实际并行、步骤工具和完整交付，不增加高质量报告或内部图示门槛。资料/研究主题相同，新增明确并行/可用稿指令，因此不冒称完全同prompt基准。

2026-10-21 13:09：父record完整预检独立spec/quality APPROVE后规范重建完成。API/all workers `52e5a3e3`、native `8a9702dd`，33部署源码检查、ready/App HTTP和scoped cleanup通过；181JS/52Python零跳过，真实模型验收仍待完成。原执行版本拒错后补齐结果的实际Python↔SDK链通过；不把该点解释为整链性能已修复。正在只读核查父输入映射重复注入、版本消费及模型上下文成本，不启动盲目完整重跑。

2026-10-21：原子任务提案反馈已独立复核并规范本地重建，API/all workers ab982c37、native c789e285，31项部署源码/ready/cleanup通过。真实小任务131.632秒交付，P/A/B提案引用登记及精确字节复用通过；显式评估和缓存摘要符合正常契约，严格指定调用路径仍未全发生。相同原始请求完整试验653.573秒取消、48父/0子响应、无交付；模型选择全父执行图，不能解释为三分支调度失效。过程指标84/84独立核对通过，9图报告已保存但未登记交付。发现父record先关闭执行再校验的缺陷，完整机械预检修复中，尚未冻结复审/部署。分析215.170秒和报告195.034秒的额外工作继续审计，不能将全部延迟归因于早期登记错误。263.896秒基线及旧失败均保留；未提交/合并，云端/demo不变，复用Vivaldi已有页。

2026-10-20 摘要修复已部署：backend c7f61994 / native 0cc15445，规范重建ready、源码哈希一致及scoped cleanup通过。27项摘要测试与大结果debug真实SDK用例通过，摘要限额仍65536。完整生成448.99秒失败记录保留，尚未重跑验收；下一焦点为分支范围与收敛。无运行中任务，无dev合入或云端/demo变更。控制图视觉复核因浏览器连接超时未完成。

2026-10-20 后续完整生成未通过：thr_3c61c8a1f8059b2f2535 / attempt_9df5420f36dd4e00 在448.990031秒失败，四分支完成但无完整报告，13次工具错误。自动摘要错误纳入runtime.dispatch内部检查点，触发debug research_summary_chars 96070/65536；已修正笔记投影，不调大限额，不删除原始记录，27项research-tools检查通过。此前118.7秒只证明两项核验，不是完整生成验收。取消请求因任务已经终止被拒，不能称取消成功。新修复正在规范重建，完整生成与分支收敛仍开放。

2026-10-20：确定性子任务调度已本地部署。已接受 subtasks 图自动执行，沿用原线程池、依赖阻断及取消收尾；实际启动不再需要父模型再调用 agent_delegate。同七资料/两问题实测 118.700806 s，两个 auto 分支启动相差 14 ms，13/8 工具，均完成；前次并行对照 140.313103 s，顺序失效候选 182.181694 s。两项结果与独立核对一致，仍有两次错误和父级重复检查，不代表首次完整报告性能验收。75 JS/SDK、58 Python（1 skipped）通过，另补保存回执恢复检查 35 runtime tests 通过。最新 backend c385aac0，同源 ready/scoped cleanup 通过；实测试验 backend 62277db9。dirty HEAD 15980389，无合入、云端或 demo 变更。记录在 ROOT/outputs/research-round-efficiency/parallel-review-deterministic。控制图浏览器复核尚未完成。

2026-10-19：统一 debug 容量候选已本地部署，canonical rebuild exit 0/readiness 通过。API/all workers image 627d9f23aa22713e38d40d508893c104792ac44827035f8578bd9afc07fafda1；native 8ffb64702ea206e9312e02ee45b7d98b2dce7f0a44e3370bc05b666a2001ef77。公开 runtime capacity 与 5 container env 均 mode debug，146 limits；native 实际 memory 2147483648 B / PIDs 512 / tmp 512m，cleanup exit 0。DEBUG 超限 typed fatal 立即中断，不得截断/回退/重试；normal hard/soft 区分保留。外部 OS 限制不保证可被 debug 拦截。仅 scoped source/offline 与本地部署核验，无新 live research/质量/并行/性能验收；350.524 s / 41 参考、旧 limited 报告与失败证据保留。dirty HEAD 15980389，无 commit/tag/cloud/demo。[协议决策](../superpowers/specs/2026-10-16-enterprise-protocol-decisions.md)。


2026-10-19：用户确认显式区分 hard limits / soft thresholds；软阈值不得使整轮失败，通信等待不等于任务截止。诊断/局部校核记错继续并允许 limited delivery；可恢复读取/幂等回执同请求恢复；核心阻断停止依赖但保留可用部分，权限/身份/CAS/必要持久化仍严格。显式审阅 attempt_7e5fab75f575b7bc 于 07:04:28 UTC 在模型前 native_transport_timeout，0 responses / 0 child，cancel_confirmed false，60 s native_exchange 与 1800 s task 的具体失败接缝仍在诊断。App 重建 exit 0：backend 785bb2224b1920262c03bbe94eb955b9a56df94169fc6fa19865e2cb6ff002e4 / native 1a2f56190e24518c86194172c2940d87ed78810b18a1f328e89245c02a8aa2b3，cleanup 已完成。前一生成 263.895887 s / 31 parent / 0 child 为 limited，82 项指标核验通过但非全面质量通过；LIVE CSV-first bug 已留证，重载 HTML 不等于 LIVE 修复验证。App 29 tests/types 通过，隔离 browser replay 因 navigation timeout 未通过。350.524 s / 41 参考不变，无 active trial/commit/cloud/tag。[协议决策](../superpowers/specs/2026-10-16-enterprise-protocol-decisions.md)。

2026-10-19 12:20：active性能切片为producer成功结果内主动返回同一host-inspected checkpoint，原机制只拒NEXTtool导致seq176/201额外LLMturn（检查未执行）。两JS源码冻结，保持实际receipt/cancel/concurrent身份，仍由模型record/assess、不自动过质量；next_action明确先commit再native/followup，旧profile不变。94 focused含17actualSDK、独立 5及adapter兼容通过，不累加。现300s模型270.115/tool11.925/其他17.936、0child仅观测；新提速未验收。重建/tmp/producer-proactive-rebuild.log进行，部署仍ab0ec0a0/7ec01dcf；计划用户现有browser全新四文件实测，未有新Attempt，现报告保留。图待image/results收敛，无App/Provider/Docker/build/commit/cloud动作。

2026-10-19 11:23：fresh 四资料原指令 attempt_e14e 已 completed limited，299.976341 s / 34 parent / 0 child。原运行交付UI曾FAIL（54files roleNone、无主卡/自动开报告），其后可信finalscope/currentSHA投影+App复用修复已规范重建exit0。backend ab0ec0a0136fec7d23a36d9154195dac7b64216022081b60a0df67791cb90615；native 7ec01dcf5d5f197835d4aae34b2f5912b9d9e85262fb8b9801481a78ad7a45de。实际只reload、无reportclick/新Provider，主报告iframe完整自动开、report/CSV主卡及15limitations可见；目录“本轮主要成果”两文件同为limited并保持report选中。reportSHA5ca667…不变，已知2024用户请求归因幻觉仍未修，不冒称clean质量。50 App/tsc、helper当前builder17tests及真实postbuildapply exit0，缓存standingrule本次完成。299.976s仅单次有限草稿观测，无parallelism/新质量基线结论，350.524 s / 41参考保留。dirty HEAD 15980389，无commit/tag/cloud/demo。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 10:50：producer-checkpoint候选规范重建exit0，API/all workers同image 3f752a66f41cebce6ace72ef6073f5fbfa57c87e7a100018087a86da91446841，native fb7183ccfc90ed4799aa5442fddd854e43586afd712c708ec83501e9921c337c；14 native+4 Pack+3 backend实际SHA匹配，5 profiles加载。92 focused+独立 5检查通过；optional product_paths观察实际候选文件后要求真实record/独立assess，并补await后动作race重检，无field legacy不变。fresh用户可见thr_f4fc四文件原prompt就绪，父准备提交，未有新Attempt/验收；必须看真实模型是否声明paths及checkpoint→record→assess，不能仅凭交付成功宣称机制起效。首次生成仍open，旧119s仅后续handoff，350.524 s / 41基线不变。cachehelper15tests/standingrule已核，本次cleanup0，validation/use后root --apply待做。dirty HEAD 15980389，无tag/commit/cloud/demo。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 10:47：Capstone积累构建清理回执已保存：221 exact-project/untagged/无任何container引用镜像以no-force/no-prune删除，30containers/10旧image IDs保留，无volume清理。初始cache2539显式IDs含后继归属推断，经独立指出不足后exit130中断；最终helper仅direct strong-command/reclaimable/nonshared，不推断ancestry。OrbStack448G→303G、hostfree594→739GiB为实际观测。Step5 offline92+独立 5通过，canonical producer-checkpoint重建运行中cleanup0，验证/使用后root再helper--apply；尚无新部署回执，保留1c103072/a3fc1620。fresh thr_f4fc1d7a912a0bdaf5c6四文件及普通prompt仍draft未提交，无新运行。图待部署验证统一更新，firstgen仍open，无新baseline/commit/cloud。

2026-10-19 最新验收边界：主线仍是 FIRST GENERATION 生成问题验证，未关闭。119.669537 s 仅旧字节同会话交付闭环；App 1.5 首次生成未验收，无新性能基线。父正在用户现有浏览器启动新四文件原始指令轨迹，检查首次路径转写、脚本、schema/summary错误与自制checker循环，未收到新Attempt/结果。

2026-10-19 10:19：原可见browser同会话人类反馈后 useful LIMITED handoff 本地验证通过。attempt_1d42df042e409a42 02:15:27.548505→02:17:27.218042 UTC，119.669537 s / 17 responses / 26 tools / 3 recovered failures，record513→assess520→limited523→attempt_completed632。五文件实际可下载，报告1,035,081B SHA0577f6d8…与旧seq368字节一致（新595），未重算/未reviewretry。最终回答明确排名括注错误、8图未目视核对、146/243覆盖空、复现材料未随附及无独立全审，report不是clean；独立saved-evidence audit仍进行。首次fresh attempt取消539.539s，后续119s交付不是新E2E基线，350.524 s / 41保留。部署 1c103072 / a3fc1620不变，dirty HEAD 15980389，无commit/tag/cloud/demo。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 10:15：App 1.5 / Pack 1.4 首稿交付候选已规范本地重建 exit 0。API/all workers 同 image 1c1030720f8ed43b666141e381191d9c571a650c60d4a0c7c08f7a3b1b218e93，native a3fc1620406e81e392fb961a896fd808d1188e84a7eb9227f6514e85f5304046，13 native + 4 Pack + 3 backend 实际文件 SHA 匹配，5 exact default profiles 加载。独立 21 checks 含 actual SDK failed-checker→usable limited 正常闭环通过；旧 policy、历史与 exact retry 保留。产品模型为持续交互会话，先呈现usable draft并显式knownerrors/not_checked供人审阅，不要求autonomous perfection/passall/mandatory cleanreview；完整性/授权/持久化仍严格。根正在原可见browser同Thread thr4b55提交人类反馈以交付已有草稿，Attempt/终态/验收待回执，不声称完整链已过。dirty HEAD 15980389，无新commit/cloud/tag，350.524 s / 41旧基线保留。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 09:49：可用有限交付主线候选已规范重建 exit 0。API/all workers 同 image 3ae9f5d9ab664d5124ac2c1f2170af3ca93e44a1d2febb171021e1a8f11ded7e，native 2d1775bf384f62e06e20784f62aa7ce0c5b4559790cc80904a4e6af179dfe4e9，13 项实际源码 SHA 匹配、4 frozen profiles 加载。现有 limited 并非被 clean-review gate 直接禁止；已修 repair-first feedback、终态具体限制遗漏及 omitted scope 当前版本检查。86 focused、父 5 closure、独立 6 relevant tests 通过，实际 pinned SDK failed-review→limited 正常 agent_end 与文件已验证，均离线。fresh 用户可见浏览器 thr_4b5531ba739f0c20cb4b 四资料已上传 draft，原普通prompt准备提交，完整实测待验。可用成果+显式错误/限制可limited，不冒称clean；350.524 s为调查checkpoint非硬超时，异常重复/底层阻断即停。dirty HEAD 15980389，无新accepted commit/cloud/tag，旧 350.524 s / 41基线保留。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 08:14：选择性 review source 候选规范重建 exit 0，API/App healthy。API/all three workers 同 image ec989494b5f27aef6ac7342e348377abc4aa83ceb3bef9b1a990155a27f6d89c，native 8393263c50a3e9f98c5780f4eb470d71268462aeabda0d804cbf017eb67eabc3，11 项 native 文件 SHA 匹配 source，4 default profiles 加载。backend 67 Node / 72 Python + 1 skip / types 0，独立 40 Node / 15 Python，父 34 Node / 50 Python 与同字节 packet 对比通过，范围不累加。仅本地部署与离线验证，不是质量/性能验收。用户已撤回重建后完整续跑：没有 build 后 Provider 调用，先 exact failed-node 离线 replay，再 ONE isolated real review，禁止 parent read/calc/rewrite；节点通过后才考虑 E2E，按底层bug/同包重复失败/无新证据循环及时停。此前20多分钟故障链是operator策略错误。dirty HEAD 15980389，无新 commit/tag/cloud/demo，旧 350.524 s / 41基线保留。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 08:10：选择性 review sources 修复已源码冻结并独立通过，backend 67 Node / 72 Python + 1 skip / types 0；独立 40 Node / 15 Python，父 34 Node / 50 Python 通过，范围不累加；父同最终字节 packet 对比准确匹配。按可信provenance选择 original/explicit prior、历史 refs 不全注入、SHA/size/type去重保alias、sourceExcerptChars默认16384且不降globalcap、真实覆盖/失败stopreason/usage/fingerprint已验证。model settings 审计不支持“继承父live high thinking”的归因，未调参。规范重建 /tmp/review-source-selection-rebuild.log 运行中，无新 image，部署仍 303176df / d71c9f54，Provider/质量/性能未验收；旧 350.524 s / 41保留，无App/字号/commit/cloud/demo变化。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 07:50：attempt_61fb96d9e2e9c37f 已真实 UI 停止，attempt_cancelled seq 1571 / 23:48:32 UTC，1318.629 s / 56 parent responses / 19 failed completed tools。首个 review 捕获三项重要错误；第二次 model_turn_incomplete（input 137885 / output 65536），第三次 retry 被取消，无活动 Provider。40 产品 SHA/bytes 全过，最终 HTML/metrics 与 r2 审计 SHA 完全一致；339 数值检查 329 通过、10 小舍入偏差，正式限发定义/覆盖及图4小时格与15分钟观测混淆两项实质质量 FAIL。完成边界计时 model 382.59 s / tool 534.36 s，第三review未匹配，余时与token不归因。已确认 prepareDeliveryReview 重注入全部 94 sources，首包 source/history 占约 82%；正设计选择性 bounded sources/dedup，未修复前不再长测；basename collision/continuation reuse 次要。部署仍 303176df / d71c9f54，dirty base 15980389，旧 350.524 s / 41 基线保留，无新 commit/cloud/demo。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 07:25：精确 policy 兼容候选规范重建 exit 0，API/App healthy；API 与全部三个 worker 同 image 303176df5d7a41c16dd01701b928fff83e8d6cee261c59eb8eb49ef232d0938d，native d71c9f54c2ed437c551e728741c4c863b1d4dfe1ea261d98343d162545fc8612。七项实际 native 文件 SHA 匹配 source；四个 default profile catalog，原 5e21 context 在新容器中保留 SHA 6da560c3 原文通过，仍选 App 1.3 / Pack 1.2 / review true。App 1.4 / Pack 1.3 显式 host 指纹协商与旧 variants 保留已验证。独立 90 tests / 1 skip + 3 mutations 拒绝，父 144 Node / 138 Python + 34 skips，范围不累加；容量修复另有 4 实际 PG TEMP 查询通过。新自然修订准备中，Provider/研究质量/性能仍 pending，不因 replay 通过宣称内容已修复。dirty base 15980389，无新 commit/cloud/demo，350.524 s / 41 基线保留。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 07:20：全部源码冻结。精确策略目录/回放独立复核 90 tests / 1 skip 及 3 项越权修改拒绝通过，原 5e21 context 不改字节恢复验证。父 144 Node tests、138 Python tests / 34 skips 范围不累加。App 1.3 / Pack 1.2 exact variants 保留，新 App 1.4 / Pack 1.3 明确 host 指纹协商。续接 SQL 容量修复另有 4 项实际 PostgreSQL TEMP 查询通过，非 full HTTP/deployment。规范重建 /tmp/research-policy-compatibility-rebuild.log 运行中，部署仍 5e21a413 / 60a118c7，尚无新 image/Provider 验收；旧质量失败和 350.524 s / 41 基线保留。dirty base 15980389，无 App/字号、新 commit、cloud/demo 变化。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 06:38：交付范围/审阅修复已规范本地重建 exit 0，API/all three workers 同 image 5e21a4132a86d87dbce7771161c084b4371e5bf3e3ae7789101b6083bc7c4945，native 60a118c7c5446eb6b8e728b8632467be7ed7f2bc432f137b04567d7a5764a7d9，六项实际容器源码 SHA 与 owning source 一致。JS 138 tests、独立 44 tests、Python fresh 80 tests / 1 skip、此前独立 13 tests 范围重叠不累加。原 Thread thr_15b1895b929e344c935f 已在真实浏览器引用 report.html 并提交无数值暗示的自然反馈，新 attempt_8d808d1027b70bf2 正在运行，要求按原资料核对缺失量、省数图和潮流标题/正文并保留已有工作。部署通过不代表质量/性能通过，待终态与独立产品审计。旧失败证据和 350.524 s / 41 基线保留，源码 dirty base 15980389，无 App/字号改动、无新 commit/cloud/demo。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 05:54：恢复候选已完成本地规范重建，API/worker/worker-native/worker-pypsa 同 image 26199f0aadc8c85906cfd07b63448c67f36f6e2296495c6d2c27af3437fe3e8f，native 8ac9b76b3e3f14a9bce64ab798aef97d2c3d69c3b4f8f6a53bf0cb77032f52c0，容器 research-tools SHA 同 owning source 5f29ee7e。恢复/容量联合 117 tests（含 13 actual SDK）及独立 4 targeted 通过，父 37 范围重叠不累加。新四资料真实 UI 试验 thr_15b1895b929e344c935f / attempt_71b524ee54c09fb0 正运行，尚未验收。旧取消试验 audit FAIL：2531 / 2533 数值 cell 通过、2 错及 4 类正文/图形矛盾；42 hashes / 10 PNG 完整，3 delegates 准入失败、0 child started，不代表审阅质量通过。源码仍 dirty base 15980389，无新 commit/merge/cloud，350.524 s / 41 基线不变。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 05:20：独立实际文件审阅已完成离线整合并在 local-dev 部署，真实质量试验待进行。规范重建 exit 0，API/all three workers 同 image 0403007002b917c94ee64e5f0d2c895ce7c0762f3bbf361518a582ee96d3eed3，native image a8c31c5bd5d82ecb13aa138f2047489a71ff128fccba2b868e499eef25d0fc04。health 发布 capstone-delivery-review/1，host/container helper SHA 同为 86cda17d。policy 隔离、HTML 可见文本容量、支持脚本 blocking finding 门禁三项修复已整合；94 Node tests、父 9 SDK/helper tests、35 controller tests 通过，范围不累加。packet 独立检查首稿 9955 / 9955、修订 16755 / 16755 可见字符，三个 CSV excerpt 均非零，prompt ≤262144；不代表内容或视觉检查通过。Task 1/2 离线 verified，Task 3 本地 deployed、真实质量/开销 pending。旧首稿和修订质量失败保留，350.524 s / 41 基线不变。无 App/字号改动、未合 dev、云端/demo 不变。[计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 04:51：报告渲染首稿已完成，304.280305 s / 37 parent / 0 child / 39 tools / 11 failures；869 项数值比对通过，但正文、图注和时区解释失败。自然反馈修订 attempt_e50328c5e341f630 用时 553.179527 s / 68 parent responses，36 文件完整性通过，345 项复算中 337 通过、8 失败，仍有分母、覆盖、图聚合、图注和相关性问题。保留有效数据与已修正内容，不接受新质量或性能基线，旧 350.524 s / 41 不变。Application 1.3 / Pack 1.2 独立实际文件审阅正在实施，host SHA/资料 manifest 绑定、无工具 child、纯文本不宣称图片视觉检查；70 Python tests 通过、1 skip，研究 read 诊断 22 JS tests 通过，backend SDK 尚在收尾，未部署。当前部署仍 backend 4553721e / native 8ccd4e9a；未改 App、未合 dev、云端/demo 不变。[设计](../superpowers/specs/2026-10-19-delivery-review-design.md) · [计划](../superpowers/plans/2026-10-19-delivery-review.md)。

2026-10-19 04:27：capstone-report 候选已规范重建 ready，/tmp/native-report-rebuild.log exit 0。API 与三个 worker 同 image 4553721e20ab922d89ba7f77e9c5db554a292a4ae1a1afe9d8cc600f1a103dd3，native image 8ccd4e9af7713610073123bea2520aa4e91cc478c7a3ea5aa04594f7594be9a0。实际非 root UID 65534 经 PATH capstone-report 1.0.0 生成 CSV/SVG HTML，79.37% / 001 原值及 TOC 锚点通过；host/root 专属环境 receipt 正常读入并提供 helper context，不放宽权限。context red→green 10 tests、renderer/env 33 tests、actual-SDK split-only 离线 1 test 通过，各范围不累加。四原文件/普通指令新 UI 任务 thr_19f3d38d9a4a6eacf1cc / attempt_703085d8273eb9e2 正在运行，已有一次计划前 bash 和一次 expected_outputs 类型拒绝，模型纠正后推进，不能称零错误。部署与功能验证已通过，真实研究质量/性能/最终 helper 采用仍待终态与独立审查。旧 thr425 的 status_note 额外字段纠正历史保留，350.524 s / 41 基线不变；未合 dev，云端/demo 不变。 [渲染器设计](../superpowers/specs/2026-10-19-native-report-renderer.md) · [验收计划](../superpowers/plans/2026-10-19-native-report-renderer.md)。

2026-10-19：thr_425aec0650141837cbf6 / attempt_c7b63063f74a71d6 已完成 417.312842 s，52 parent / 0 child responses，53 tools / 15 failures（14 脚本、1 record 额外字段），零 task_step_error。CSV 288 + daily 183 = 471 / 471 通过，但 HTML 百分比、环比、图注事实和因果结论失败，不接受新质量/性能基线。实际 base64 SHA 已核对；问题是图注写了未画的分位带/箱线/面板等，不能只称图放错。下一用户批准候选是通用 stdlib capstone-report，自由 sections/paragraph/bullets/CSV table/figure，复用 CSV 原值及统一编号/TOC/内嵌资产；不保证语义事实，不改冻结 research policy 或 App。正在实现，未验收 helper 源码/镜像/实模收益；现部署仍 03e64818 / native ef50fbc9，350.524 s / 41 基线不变。图待源码/镜像冻结后统一更新，未合 dev，云端/demo 不变。 [设计](../superpowers/specs/2026-10-19-native-report-renderer.md) · [计划](../superpowers/plans/2026-10-19-native-report-renderer.md)。

2026-10-19 03:44：过程阅读 UI / 步骤真实响应计时 / 连接默认值修复已规范重建 ready。API 与三个 worker 同 image 03e64818fe5b88d4df7e83541e55fd563c30d5e2d741c57c1218e83cb7339f90，general-pi image ef50fbc936b4218793423912e100347c428c2c8de0cc8eea5a1133c5e3d51730；readiness 和实际 v2 stream 均 HTTP 200。有效默认 1024 / 8，旧显式覆盖为空；preflight 空默认及两处旧 32 / 2 配置回归修复。App 123 tests / npm check；计时 104 tests；启动配置 90 tests / 3 不适用跳过，各范围不累加。实际 1440 / 390 阅读检查通过，字号仍 12 / 11 / 10 px；03:37 b165eb3c 启动失败保留历史，不再当当前故障。已通知父代理可开始新研究，本片未发 Provider 任务，无新研究质量/性能基线，350.524 s / 41-response 保留。未合 dev，云端/demo 不变。 [过程阅读计划](../superpowers/plans/2026-10-19-process-reading.md)。

2026-10-19 03:37：执行过程阅读 UI 已冻结，123 App tests、npm check 与实际桌面/窄屏检查通过，字号 12 / 11 / 10 px 不变。含真实 parent response timing / stream defaults 修复的最终规范 rebuild 在启动时失败：worker-native image b165eb3c3cf2c1c6caa1502f129100f4c345c5a7d5b9afdedda4fa5226b22885 未 ready，preflight 拒绝空 CAPSTONE_THREAD_MAX_STREAMS。后端正修复，不并行重建。上一 a01edf58 仅为最近成功 readiness 回执，不代表当前服务健康；没有新 Provider 研究任务或质量/性能验收。控制图待最终修复回执统一生成。[过程阅读计划](../superpowers/plans/2026-10-19-process-reading.md)。

2026-10-19：本轮完成基本环境补齐和真实非 root 功能验证。规范 rebuild exit 0，API/worker 同 image 65b4ef71fb3383904254e62933ed8e03165d081d3df963c28b7c16ec663f6591；general-pi image 45cc05d0d3634babcdb697bf97284733c01a3d38fc6573fefcd984752fb68a57。实际 user 10000:10000 / HOME=/tmp 检查通过 20 capabilities、24 Python packages、14 commands。operation、SciPy、产品/依赖诊断、pipefail 与独立 native_context 导入问题已修，94 Node tests、62 Python tests 分别通过，不与历史重叠结果累加。尚未在本候选运行新 Provider 研究任务，不声明质量或性能改善；旧 350.524 s / 41-response 基线不变。字体固定 12 / 11 / 10 px；另按用户要求折叠失败原因，真实 hover/click 已通过，无布局缺陷结论。未合 dev，云端/demo 不变。 [当前计划](../superpowers/plans/2026-10-18-managed-deep-research.md)。

2026-10-19 02:33：当前本地 image 5ebe17eb31801d48c7054aca652a3ac3359963079ba7b3419496ac2a15611a3e 已部署 ready，API/worker 同镜像；仅含此前 adoption 增量。Thread thr_941f851498fdd8791023 首轮完成 458.674602 s，61 parent / 0 child responses，59 tools / 14 failed。450 CSV checks 中 448 通过，HTML 另有错误，质量未接受；旧产品版本拒绝正确，模型 product-rebind 自行修复 done，非 host 阻断。自然反馈第二轮 attempt_b481c31ea09d0505 已 completed，独立 491 数值全通过、旧正确值保留；HTML 摘要因果措辞、图 4 月时段、丙省负价均值等仍未修，质量/性能基线不接受。未部署 ready-batch source 有 86 Node tests 通过 / 7.06 s，含 9 actual SDK 离线场景。Application 1.2.0 / Pack 1.1.0 三个 plan/record/assess 入口共享 controller 正实施，new tasks split-only，Application 1.1 legacy 冻结请求精确恢复保留；最终整合测试待回执。字体回退 12 / 11 / 10 px 已实际浏览器核对，研究变更不得改 CSS。旧 350.524 s / 41-response 基线不变，未合 dev，云端/demo 不变。[当前计划](../superpowers/plans/2026-10-18-managed-deep-research.md)。

2026-10-19 01:54：6347完成任务产物独立检查：56月度数值52按展示精度正确、4个CSV覆盖统计错；另566应为省×时段而非501去重时段、1461应为每省配对小时而非4383省小时总量、触底记录月度5/6放置口径需改。HTML10内嵌图片均加载、8anchors目标存在、1280无溢出，但质量未通过，不将覆盖错误扩大成全部计算错误。证据ROOT/outputs/research-round-efficiency/enterprise-question-cycle/thr_99bdb32734caa89ea50d/independent-content-check.{json,md}。最新未部署SOURCE新增assess.question_adoptions，将finding来源问题追加pending目标，严格状态/来源/容量及审计；focused planning_context和显式operation提示、research-method同步。只补发现→行动衔接，未实现兄弟目标并行，无实模/性能改善结论。组合Node80/80 5.3038秒含pinned SDK离线通过、diff通过，backend只读兼容review通过、9Python专项通过，实际adoption状态通过checkpoint/progress/child admission，伪造未提交derived_from拒绝。当前已部署仍6347，旧350.524秒41响应基线不变；未合dev，云端/demo不变。[增量设计](../superpowers/specs/2026-10-19-enterprise-owned-research-cycle.md)。

2026-10-19 01:47：第二次规范rebuild exit0，API/worker同镜像6347fcac9336a35fb7797af99b33f400322b06d4fbf2e36d734f93a0e6438bb5，App5173 ready。新UI线程thr_99bdb32734caa89ea50d / attempt_5ddba49a149157e1实际上传四原文件、一条普通任务指令，17:38:53.562890Z→17:46:22.383417Z完成，448.820527秒（约7分29秒）；终态响应计数59parent/0child/59total，59tools/10failed，不等同token/费用总量。ordering修复后执行恢复，但5个语义研究目标串行，无新followups/subagents；动态研究与性能未验收，产物质量待查。旧350.524秒/ 41响应基线不变，不把本次完成当研究验收成功；取消历史/未知usage保留。未合dev，云端/demo不变。[复测状态](../superpowers/plans/2026-10-18-managed-deep-research.md)。

2026-10-19 01:31：本地576d580e4550c514dcbb4a8462f97f568cd371c87ddaacb74b413771420ab43f规范重建ready/API-worker身份核验通过；新thr_fa0f88ee3f5d2e37e96d / attempt_3af0d87e200af4b9因seq75步骤排序缺陷及时UI取消，78.897642秒/14observed parent/122events，终态17:28:12.265621Z、无active Attempt，无terminal usage，不能计完整成本或成功基线。seq74已commit旧目标settled，seq75新步因旧cycletool未结束被拒，seq76旧toolend后才close。ordering修复已SOURCE冻结：cycle控制tool不阻挡已确认settlement，真实执行tool仍阻挡；精确replay覆盖met/partial/failed，3重叠suite92通过/1.01秒、pyright0/diffclean。二次规范重建进行中（/tmp/enterprise-cycle-ordering-rebuild.log），尚未验新修复image/live。Node最终73/73 5.61秒含actualSDK7脚本离线，App118/tsc等保留独立scope不累加。旧350.524秒41响应质量基线不变，无新质量/性能/成本接受结论。未合dev，云端/demo不变。[中断与修复计划](../superpowers/plans/2026-10-18-managed-deep-research.md)。

2026-10-19 01:21：本轮SOURCE已冻结待重建实测。Backend185通过/1deselected、6module及pyright0，parent_step_id已按真实tracker含alias投影；App不猜归属。actualSDK新增7场景/5.50秒通过，覆盖发现→reflection/derived followups→替换旧pending→双child实际重叠→综合→报告保存/deliver；模型回答脚本化离线，不能称真实推理接受，勿与既有Node72等重叠选择累加。App最新118通过/5.58秒、tsc通过；实测旧成功答案inner p12px/19.2→16px/26.4（zoom1/无transform），步骤/分支14px、辅助12px，1440/390无溢出，toolbar不变。规范rebuild进行中（/tmp/enterprise-question-cycle-rebuild.log），上次已核验部署仍10ae，新候选身份与实模结果待确认。取消历史/usage未知/350.524秒41响应原基线保留，未合dev，云端/demo不变。

2026-10-19 01:15：发现驱动研究增量已实现SOURCE：pure questions/reflection/derived followups与pending replacement、controller保留产品修复、受grant通用child及真实branch events接实际SDK。Node整合72通过/4.43秒含6actualSDK离线模型，Pack3通过；App118通过/5.67秒及tsc，1440/390离线组件无溢出，工具默认折叠而语义/失败常显，子完成不等于研究验收。stale outputMode/record-assess合并/manual progress冲突已源修复。Backend临近冻结，真实parent step/alias投影整合待确认；前端不猜归属。当前未部署，local仍10ae8afe476d，父待整合/规范重建/真实任务验证。两次取消和未知usage保留；无新质量/速度/成本基线，未合dev、云端/demo不变。[当前计划](../superpowers/plans/2026-10-18-managed-deep-research.md)。

2026-10-19 00:51：首轮自有cycle真实任务thr_e6861bac615d28e000d2 / attempt_b0e423051217709b已UI取消，至取消7m41.59s，观察64parent/87tools/28failed，无最终usage，不能计完整成本或成功提速。52项数值spotcheck按展示精度通过，但图2裁切丙省与约54%写绝大部分，质量也未接受。resolves合同误解、narrative step阻断接管、product record覆盖导致deliver永久失败三缺陷修复中，修复未部署。用户否定固定read/calc/report为deep research；验收要求发现驱动问题演进、独立subagent分支、综合冲突/缺口后追加研究。复读上游确认漏迁移prefilter问题元数据及questioning驱动下一轮执行；当前adapter不调用上游engine，不得声称完整引入研究能力。先短回归修通再长测；已部署本地仍10ae8afe476d，云端/demo不变。[计划与失败证据](../superpowers/plans/2026-10-18-managed-deep-research.md)。

2026-10-19 00:33：自有enterprise cycle已接实际SDK（SOURCE），不再import旧phase engine；generic child继承grant，native/MCP计划前阻断、inflight barrier、CAS确认后推进、source owner及真实产品active/history隔离已实现。49JS通过含6actualSDK离线模型；整合Python169通过/1跳过（/tmp/enterprise-owned-python-integration.log）；delegated public文件56通过，后续步骤/stages/delegated专项77/78通过，均为重叠范围不得相加。App109通过/tsc通过，partial/failed/limited/cancelled不伪completed。本地规范重建日志末尾ready候选10ae8afe476d，父已核验API/worker/native同镜像且general-pi controller aa4d910e... / state803727ab...与源码hash一致，本地候选部署ready已验证；新UI线程thr_e6861bac615d28e000d2四附件待发送、尚未启动。真实模型质量与整体性能尚未验收，无新速度结论；旧154parent/70tools取消事实及未知usage保留。未合dev、云端/demo不变。[实施与验收边界](../superpowers/plans/2026-10-18-managed-deep-research.md)。

2026-10-19 00:07：用户接受选择性复用上游、自有企业研究loop与通用child。旧集成真实任务 thr_bcf52cb2fb396acfee13 / attempt_6d22e8b8bea6a169 已按用户要求取消，观察到154次parent响应/70次工具调用；无终态usage回执，token未知，不写0。旧本地候选镜像40703433d9c896b092a8f4091c78b18b41ef29c957cd9942b1b6a99a75dd3ee7保留失败证据，不重启该任务。当前仅SOURCE：NativeStepTracker保留task_step_error（14测试），Python无进展错误透传（100测试）；JS防空转35测试已过但usage失败保留仍回归中，自有pure cycle仍在实现。整体loop尚未部署/验收，无新速度或质量结论。继续既有CAS/Work/Attempt与真实receipt，禁止第二账本/调度；子工具实时事件尚未接通。详见[接受的loop设计](../superpowers/specs/2026-10-19-enterprise-owned-research-cycle.md)和[实施计划](../superpowers/plans/2026-10-18-managed-deep-research.md)。未合dev，其他环境不变。

2026-10-18 23:21：研究增量已接入实际SDK：pinned阶段引擎、受控child runner与enterprise controller复用既有ResearchChannel CAS/回执及目标步骤，无第二账本。明确仅复用阶段引擎与受控执行子集，不是整套上游扩展。两个HIGH恢复缺陷已复现修复并复审：确定拒绝可纠正、未知回执精确重试、未确认终态不done；JS/Python共用可发布路径策略，prompt/frame/answer采用初始化容量。25项JS与50项Python（general server/executor，NO_PROXY）通过；子工具实时事件尚未接通。本地规范重建及真实同输入比较进行中，尚无新速度/质量结论，保留350.524秒/ 41响应基线。恢复标签不变、未推送；未合dev，云端/demo不变。详见[研究实施计划](../superpowers/plans/2026-10-18-managed-deep-research.md)。

2026-10-18 22:36：按用户要求，在新的研究集成前固定三份本地恢复快照（含当时未提交源码/文档），未移动分支或索引。主恢复标签 `pre-deep-research-20261018-223637` → `83e89e33dbce7b9a36a600b820bc0e4b5991efa5`，实现基底仍为 `15980389`；控制与root快照见下方本地恢复台账。三者均为 annotated 本地恢复引用，未推送，不是发布、验收或部署标签，也未执行回滚。当前优先企业研究质量与整体性能：保留已达标的分析、图表、独立报告、核验及版本能力，以pi-deep-research下层运行、enterprise-research上层策略和通用subagent做增量增强；不得双重调度或把现有实现整套替换。真实基线仍为350.524秒/ 41模型响应，后续同输入质量、人类反馈修订与耗时/轮次/token/失败共同验收；新集成尚未实施或验证，其他环境不变。

2026-10-18 21:57：容量链路已在真实上传首轮走通。local-dev规范重建a8e6c4ca4ded ready，API/worker同镜像、API/原生容量指纹一致。新会话33f695bb实际上传四资料，SHA逐一相符；首轮正常完成350.524秒/ 41模型响应，HTML单文件本地打开9图正常，无外部资源。48原始指标及44公开CSV对应值独立核对全通过；相对488.375秒/77轮基线，此次耗时少28.23%、轮数少46.75%，仅为单次实测。另发简短人类反馈澄清省小时/去重时长与缺数电量，修订不混入首轮提速。最终后端1658通过/138环境跳过；未合dev、云端/demo不变。[容量验收证据](../reviews/2026-10-18-application-capacity-audit.md)。

2026-10-18 21:30：容量修复为研究交付前置。e14a537c模型完成后被隐藏8MiB制品总量阻断（485.115秒/71轮），不能计成功或提速。已实现统一应用初始化配置及前端安全bootstrap、Kernel/工具中立容量参数、保存失败保留与actual/limit错误透传。冻结后端全套1651通过/138环境跳过，App691、Kernel649、Pi88及独立PG验证通过；规范local-dev重建正在执行，真实上传研究交付待验收。未合dev、云端/demo不变。[容量审计](../reviews/2026-10-18-application-capacity-audit.md)。

2026-10-18 研究长链路：真实模型受控请求稳定复现本地转发累计4MiB截断，39.708秒/4,193,456接收字节、无finish/DONE，明确ValueError响应上限；短请求27.19秒正常。已移除SSE累计文档上限，保留截止/取消/非流式保护，并补安全诊断日志。同Work续跑按文件路径选择跨轮最新版本，保留早期图表。103专项含真实PG通过，规范重建进行中；尚未完成新的实际研究交付/性能对照。流量核对：单轮输入1.396万→8.549万token，21正常响应累计106.6万输入token；三次构建明确依赖下载约1.4GB，不把Clash2GB全归于模型。未合dev、云端/demo不变。[完整证据](../reviews/2026-10-18-research-round-efficiency.md)。

2026-10-18 20:08：local-dev最终规范重建b1547560f635 ready，报告目录页内滚动/减少动态效果/下载原SHA实际验收通过，683 App测试通过。研究续跑311bffe1仍失败：437.593秒/27模型响应，明确model_transport，未完成报告；没有提速成功对照，8m08s/77轮基线保留。图片帧超限未复现，最新attempt来源遗漏更早图表及模型连接稳定性待修。剩余分段回归通过，独立测试PG已停止；无活动 Provider任务。未合dev、未改云端/demo。[诊断记录](../reviews/2026-10-18-research-round-efficiency.md)。

2026-10-18 19:50：报告目录跳空白页已在实际基线报告修复验证。srcDoc页内链接绑定预览自身about:srcdoc#，保持空sandbox与CSP，下载原字节不变；s4目标top=-0.203px、App地址不变，平滑滚动成功。8相关测试、683 App全量及类型通过。研究续跑失败的图片事件帧膨胀与同Work保留文件遗漏均已修复，167集成/6阶段资源检查通过；尚无成功优化对照，8m08s/77轮基线不变。658b1c40e187已规范重建ready，含App修复的最终重建仍进行中。make test原997/244 Python和61 issue通过，grid测试fixture补SDK事件接口后59通过，剩余目标继续。未合dev、云端/demo不变。[详细记录](../reviews/2026-10-18-research-round-efficiency.md)。

2026-10-18 19:15：首个优化对照430.943秒/39模型响应后失败，无完整报告，不能计提速成功。末三轮0用量且无工具执行，固定回执model_turn_incomplete，原始模型错误未保存，不能推断具体原因。已补共享失败响应状态与模型未完成/中断流/服务错误/内容拒绝安全分类，122相关测试通过；23Pack/桥接通过（1 PG跳过）、86工具测试通过，doctor/diff通过。含修正的规范重建进行中；既有基线8m08s/77轮及48值质量核对保留，下一步真实自然续跑及新的成功对照。未合dev、云端/demo不变。[完整记录](../reviews/2026-10-18-research-round-efficiency.md)。

2026-10-18 18:58：企业研究真实上传基线确定为8m08s/77轮LLM，下载报告48项核心值独立核对通过。共享Pi执行组织指导与研究Pack适当复核分别实现，隔离镜像补齐固定版本数据分析/中文绘图环境；86工具、36原生、23Pack/桥接通过（1 PG跳过）、doctor及wheel打包通过。local-dev最终规范重建a4939d24ea0b ready，新UI同四附件/同指令attempt_6e231d5068978875正在运行；性能和交付质量尚未验收。用户要求统一工具/环境/skills/MCP能力基线已记入资源设计，完整覆盖仍待实施。未合dev、云端/demo不变。[长任务验证](../reviews/2026-10-18-research-round-efficiency.md)。

2026-10-18 18:14：local-dev ae5797e27d5e完成流式记录/续租开销修复。原两条普通聊天指令经真实页面及文件上传复测为4.255/10.584秒（原7.398/23.740），文字事件23/44且无重复元数据，完整文字与终态回答一致；实际停止223ms及刷新恢复通过。277后端通过（1 PG跳过）、60 App通过，doctor/diff通过。首字等待未改善，单次结果不代表固定提速；未合dev、未部署云端/demo。[诊断与实际验收](../reviews/2026-10-18-general-chat-latency.md)。

2026-10-18 17:56：普通聊天原7.398/23.740秒记录已逐段核对；第二次工具仅0.246秒。真实worker/隔离PG schema无模型重放相同141/484片段，重复事件+逐片段续租/取消查询耗4.140/14.843秒，确认框架串行开销。下一优先修复流式事件与租约检查频率，并验证停止/回放/失败反馈；尚未部署性能优化，local-dev镜像不变。[诊断证据与边界](../reviews/2026-10-18-general-chat-latency.md)。

2026-10-18 17:47：研究提醒顺序修复已在local-dev 18f11b7062e0规范重建。全新UI上传现货CSV，单句业务请求148.4秒交付，自主发现并修正负价时段判断；一句自然反馈约97秒完成精简/口径修订。下载新版六组月度数值独立复算及展开/刷新恢复通过，文件outputs/shared-step-acceptance/spot-brief-revised.html，10157字节。5项提醒与18项桥接/步骤检查通过（1 PG跳过），真实SDK下一请求检查通过。无活动任务；中间标题泛化及重复输出耗时仍待改善。未合dev、未改云端/demo。[实际操作与限制](../reviews/2026-10-18-shared-native-work-steps.md)。

2026-10-18 17:40：修复同批goal回执误清资料观察提醒的顺序问题，5项提醒测试及真实SDK下一请求检查通过，18桥接/步骤通过、1 PG跳过。local-dev规范重建18f11b7062e0 ready，API/worker同镜像。新页面实际上传spot-prices.csv（1.4MB），单句普通业务请求6a46ee42正在thr_de0d0d76457de53c00d9运行；不要重建或重复发送。已显示结构检查、月度计算、图表与HTML生成的具体工作目的；首个进度参数拒绝后自主修正。交付与独立数值核对尚待完成。未合dev、云端/demo未改。

2026-10-18 17:25：第三轮普通反馈76c5811b用24.7秒补回模拟声明，公开目的与逐字核对观察可见；实际下载diff仅声明及样式，9条事项不变。唯一未标用途HTML/PDF直接显示“生成文档”，不提升为已验收交付；112 App及类型、刷新直接入口/无溢出通过。最终local-dev规范重建dbc5abf08dbd ready，API/worker同镜像，无活动测试任务。最终文件保存在root outputs/shared-step-acceptance/memo-short-notice.html。未合dev、云端/demo未改；部分轮次通用标题、公开记录稳定性和聊天延迟仍开放。[完整验收](../reviews/2026-10-18-shared-native-work-steps.md)。

2026-10-18 17:17：研究公开记录改为开始/首个工作结果/工具失败触发，移除8次调用门槛，规则由Domain Pack持有；进度参数拒绝给出安全的修正说明。local-dev规范重建643d6534905d ready。真实新会话上传会议记录77107fa5完成，公开目标/核对观察可见；自然精简3b9b9264用23.9秒交付新版HTML，5个原生调用全成功、首步骤具体标题、刷新恢复通过。3提醒+19工具+86后端+18桥接/步骤检查通过（1 PG用例跳过）。每轮观察完整性、泛化标题与聊天延迟仍待改善；此前遮挡判定经正常悬浮点击证伪，无需CSS修改。未合dev、云端/demo不变。[共享研究过程验收](../reviews/2026-10-18-shared-native-work-steps.md)。

2026-10-18 16:34：共享步骤与失败反馈local-dev规范重建ready，API/worker镜像75cdcaaf916d。真实聊天5247aeae完成，研究d94eae6e沿用上传会议记录、只一句自然续做即43.8秒交付HTML；6个原生轮次、5/5工具归属及刷新恢复通过。缺组件原因能明确回传，失败/取消不再生成虚构核验阶段。151后端+26worker+23RPC、110App/类型检查通过。研究本轮未发公开工作判断，标题仍泛化；底部按钮被输入区遮挡亦待修。未宣称完整过程可读性、延迟改善或整体稳定；未合dev、未改云端/demo。[验收与限制](../reviews/2026-10-18-shared-native-work-steps.md)。

2026-10-18 16:24：通用聊天/企业研究已补齐原生执行轮次与公共工作记录到共享Harness步骤的传输及App分组。首次真实上传复测暴露隔离镜像缺少Kernel包，失败记录保留；改为复制同一无依赖事件投影模块，实际隔离容器导入通过。新增可操作的缺组件错误提示，失败/取消不再虚构核验完成；151项后端、26项worker、23项RPC及110项App/类型检查通过。含错误反馈的最终规范重建与真实操作复测仍进行中，不能计验收。实现仍model-decision未合dev，云端与demo未改。[共享步骤修复](../reviews/2026-10-18-shared-native-work-steps.md)。

2026-10-18 15:18：成果阅读工具栏统一为单行，普通侧栏与展开阅读共用紧凑布局；外层展示区控制仍独立。目录为浮层，388px 侧栏及展开状态浏览器检查通过，19项测试与类型检查通过。local-dev规范重建ready，镜像ba849478，未合dev，其他环境不变。[阅读布局校验](../reviews/2026-10-18-product-reading-layout.md)。

2026-10-18 14:56：真实上传研究两轮验收通过。新会话thr_36dbeb15686568c7a3e6上传4份原始资料，普通请求5480ae54在5m17s交付报告；自然反馈4e460a12在3m50s完成图7及负价时长口径修订。新版101989字节、9内嵌图/11表，无外部依赖；采用同一任务交付v2、刷新恢复及重新下载SHA一致通过。最终事件3238，无活动任务。当前local-dev仍e8897449，外网关闭；195项通过/15项跳过，未合dev，未更新其他环境。运行环境分析库准备、进程丢失恢复及超600秒真实任务仍未验收。[完整记录](../reviews/2026-10-18-research-chain-repair.md)。

2026-10-18 14:37：研究应用预算、进度确认分页及失败原因回传已规范重建至local-dev，API与三个worker同镜像e8897449f5c3083d5e3f4597d019f3907456e33efc5e75b3fc99ad290834058e。195项通过、15项PostgreSQL变体未执行；实际HTTP覆盖300事件无丢失。企业研究预算由应用配置为1800秒，通用600秒。页面实际上传四份原始资料，以单条普通请求启动5480ae54，尚待报告交付验收；外网关闭。未合dev，其他环境不变。[研究链路记录](../reviews/2026-10-18-research-chain-repair.md)。

2026-10-18 本地存储收敛完成：`.worktrees`由24个减至4个（model-decision、dev-macos-ci、demo-baseline、research-model），其余20个经逐文件归档校验后移除，保留Git恢复引用与未提交改动。项目由最初185GiB降至约30GiB，系统可用约182GiB。历史构建包只留当前交付ZIP，另移除124个无容器使用的历史镜像；API ready、App HTTP200。归档位于主工作区私有`.capstone-agent/worktree-archives/20261018/`。研究预算/分页修复仍未部署。[清理与恢复记录](../reviews/2026-10-18-local-disk-recovery.md)。

2026-10-18 磁盘恢复：项目原占185GiB，已校验保留7份正式离线包并移除52.94GiB重复镜像tar；清理8个闲置干净worktree的虚拟环境目录31.57GiB（硬链接不等于实际释放量），保留全部源码、会话和上传/成果数据。项目占用已降至约100GiB，系统可用约77GiB。两份零字节技能快照已隔离保留并重建；API ready、三个worker及原生执行器均healthy。重建前新增可配置20GiB空间预检，低空间拒绝验证通过。研究应用预算/失败提示/事件确认分页已改源码，尚未重建部署。详见[磁盘恢复记录](../reviews/2026-10-18-local-disk-recovery.md)。

2026-10-18 13:31：新研究24d61c76因固定600秒预算失败；28个文件（含105618字节HTML）已保留但未完成交付。发现进度128条累计封顶造成后续工具不可见；任务寿命和持续记录协议仍待修复。可信服务连接mark网络修复再增14项通过，最终规范重建进行中；不能将局部传输修复标为研究链路验收通过。

2026-10-18 13:19：本地最终规范重建ready，镜像6ba8c13658797164299430a774e4b540fbd44d325ca7b3a31b6b656e323dba23；160项检查通过。四文件实际上传研究24d61c76正在执行，交付尚待验收。修复控制回复网络规则、同任务与同成果传输重试，保留取消后过程文件。外网关闭。磁盘满导致OrbStack退出后已恢复，仅清理可再生成缓存；其他环境源码未改。

2026-10-18 13:02：研究2f81194e原生完成但成果传输失败。已确认控制服务大响应被nft规则阻断，精确reply规则修复后实际115018字节报告可读取；外网仍关闭。新增成果传输重试与明确失败分类，135项检查通过。规范重建遇OrbStack服务退出，正在恢复，候选尚未完成本地部署及真实交付验收。其他环境未主动更新。见[研究链路修复](../reviews/2026-10-18-research-chain-repair.md)。

2026-10-18 12:45：短通信超时现进入原任务重连，不取消研究；137后端和19工具检查通过。上一轮7f6fa94f仍因连接超时失败，单纯调大秒数的方案已纠正。当前规范重建镜像0540d241bfcef9719ff40ee0d71806e9c475477a94e53fb00ef3ab89f838c604 ready。新会话thr_4a5f82035f79affd96c6实际重新上传4文件，attempt_2f81194ef82d5ec3正在执行，尚未验收交付。其他环境未改。见[研究链路修复](../reviews/2026-10-18-research-chain-repair.md)。

2026-10-18 12:02：最终规范重建ready，API/worker同镜像c9cf89e58442fc97d124d7506e92890a95d6a78293d3de1bd80f665678c9a4ad；包含成果切换下载绑定修复。报告预览与刷新恢复再次通过，无活动测试任务。外网仍关闭，其他环境未改。

2026-10-18 12:00：附件实测研究两轮完成：首轮52.8秒/11工具生成HTML，自然措辞修订37秒/7工具完成，无再次追问。下载核对四张表与原版完全相同，修订版SHA a139e19cf8613ace742058f264754bed0f39ad30e5debf8aee3dda18b0f501f5，刷新恢复通过。发现并修复切换成果时短暂保留旧下载链接；新增7项通过，App累计55项。先前异常取消根因仍待定位，不计整体稳定性完成。详见附件review；其他环境不变。

2026-10-18 11:54：附件草稿与技能选择本地修订已验证。真实选择文件和拖放、刷新恢复、逐个删除、发送时原子关联通过；发送前上下文为空，接受后仅选定CSV进入上下文。126项后端（含独立PostgreSQL）、48项App及类型检查通过。规范重建API/worker同镜像b453261e19d73984fd5da8a8082d6b38d9a5be8ce9d9141166b7c58afe2c9965。Anthropic explore-data固定版本已真实加载并生成报告；自然修订曾被链路取消，续跑才交付，稳定性未验收。已新增有界失败原因输出，78项相关检查通过。技能保留原名，选择数收入工具栏；用户安装入口未实现。当前真实上传研究验证仍在执行，未合dev、未更新其他环境。见[附件草稿](../reviews/2026-10-18-draft-attachments.md)及[技能实测](../reviews/2026-10-18-research-skill-live.md)。

2026-10-18 07:44：外网开关本地验收通过。最终规范重建API/worker同镜像02bd859bb90716902c4fd66c5520836fad6abce7304072c2c587fb80105fa2c0；页面小灯开启、刷新保留、关闭通过。真实UI自然指令抓取example.com，attempt_9a1f723460d8fb5f完成，持久化工具观察含HTTP 200与HTML标题。现已通过小灯关闭外网，无活动测试任务。35项后端、7项App及类型检查通过。外部研究技能安装/使用、其他宿主检索通道仍待验收；未合并，其他环境不变。 见[外网控制验证](../reviews/2026-10-18-external-network-control.md)。

2026-10-18 06:18：修复SDK中间结束事件过早截断恢复，以及研究查询nullable参数契约不一致；规范重建65b2ff8f ready。真实ZIP研究经普通续跑生成独立报告，再通过引用报告与自然反馈完成修订；下载、9内嵌SVG、原8图几何保留、任务交付v1及刷新恢复已验证。前两次失败保留。77项后端、17项研究工具、97项App及类型检查通过。进度提交仍不稳定，语义失败状态传播待完善。未合并、其他环境未更新。见[真实资源分析记录](../reviews/2026-10-18-resource-analysis-live.md)。

2026-10-18 05:11：文件拖放与多文件顺序上传共用原上传链路，真实浏览器拖放已写入API；25项定向检查通过，本地08ac005a106ad28e085f5265b26276f9033b88ef8aa27fc40b18a0f21462517c ready。GB分析仍被任务输入tmpfs与记录配额耦合阻断，下一步分离存储；见[拖放验证](../reviews/2026-10-18-resource-drop.md)。未更新其他环境。

2026-10-18 05:02：修正运行中预览的工具调用折叠标题继承大字号。改为独立共享选择器，运行/完成两分支浏览器计算值均10px/15px；95项App测试及类型检查通过。本地规范重建9501e9252c4c21dff2560a7cd6f79a9bb1b27736d51a0079342be2be0657bddc ready，未更新其他环境。

2026-10-18 04:39：原生工具操作/返回摘要真实调用及刷新恢复通过；后端73项、App95项通过。最终规范重建08ac005a106ad28e085f5265b26276f9033b88ef8aa27fc40b18a0f21462517c ready，容器内受保护配置隐藏检查通过。未合并、未更新云端；GB资源分析仍未验收。见[工具记录](../reviews/2026-10-18-native-tool-activity.md)。

2026-10-18 04:30：区分研究/聊天开场，引导与过程字号已调整；原生工具新增有界脱敏操作及返回摘要，绑定原调用。后端72项、App94项通过。规范重建发现资源暂存目录位于只读根路径，已移入受保护持久化目录；修复重建与真实调用验收进行中。尚未合并或更新云端。见[工具记录](../reviews/2026-10-18-native-tool-activity.md)及[阅读调整](../reviews/2026-10-18-session-guidance-process-reading.md)。

2026-10-18 03:32：真实浏览器在独立企业研究会话上传1,077,936,128字节文件，56%暂停、刷新后重选原文件续传完成；服务端SHA与本地一致，刷新后上下文目录可见资源v1。上传入口已接分片进度/暂停/续传/取消，25项相关测试和类型检查通过。规范重建91d65912478d ready。当前只完成存储与恢复；按资源引用接入隔离执行器及按需分析仍待实现，不计GB分析验收。未提交、未合dev，其他环境不变。

2026-10-18 03:10：顶部导航与会话标题合并，统一研究会话状态栏；输入工具合为一行，历史整理收入设置。1440/768浏览器检查无横向溢出，工具栏28px；类型检查及110+29项相关测试通过。资源协议已实现分片、恢复、取消与哈希校验，真实HTTP+PostgreSQL+临时磁盘完成1,077,936,128字节上传及重启恢复（19.19秒，峰值RSS441810944字节）；40项后端检查通过。尚未接通GB浏览器上传及智能体按需读取，不能计完整资源验收。增量未提交、未合dev，云端和用户环境不变。

2026-10-18 02:37：自然反馈修订4ea5fe09正常完成约2分45秒，报告125187字节，7张原图逐字节保留；界面采用任务交付v1并刷新恢复通过，会话标题随交付更新。容量与拒绝反馈修复已在local-dev 3f6b5431b57c验收。详情记录字号及折叠锚点实测通过；GB资源接入、跨类型组合和dev集成仍未完成。

2026-10-18 02:33：修复四份原始资料加成果引用被错误容量限制拒绝的问题，拒绝反馈保留草稿；local-dev规范重建3f6b5431b57c ready。自然业务反馈修订已入列，尚未验收结果。成果区内边距、展开锚点及详情记录阅读字号已修正；后端23项、前端拒绝回归通过。未合dev，GB资源链路仍待实施。

2026-10-18 02:01：真实界面上传后，原始请求中断；自然反馈“请继续完成，先给我一版能看的”续跑正常完成4分53秒，生成7图6表独立HTML报告，右侧预览及文件哈希核对通过。尚未验收后续修订、任务级采用及GB资源链路。指令悬浮预览新增真实状态/耗时，18项专项通过；仅主要输出自动展开。见[自主交付记录](../reviews/2026-10-18-research-autonomous-delivery.md)。

2026-10-18 01:47：当前重点为 enterprise-research 自主研究及自然反馈修订。local-dev镜像a9ed9d26b6ae ready，修复Pi制品模块打包遗漏和前端旧512KiB上传限制；已通过界面上传4份原始资料并发送一条普通业务请求，正在验收。初稿允许不完美，后续采用用户可提出的自然反馈，不用外部操作步骤代替自主推进。成果入口与分组已调整；文件存储容量与上下文预算分离待实施。见[自主交付记录](../reviews/2026-10-18-research-autonomous-delivery.md)。未合dev，云端/用户试用不变。

2026-10-18 00:00：修订报告及9图已保留，61天指标独立核对通过；采用为任务交付v1后，规范重建、刷新恢复和真实后续引用通过（26.7秒、9次工具调用）。长分析仍在600秒截止，未计正常完成。当前API/worker同镜像d39d3ac86bb2。见[验证记录](../reviews/2026-10-17-enterprise-research-demo1-live.md)。

2026-10-17 23:40：Demo1相近合成样例已实际生成报告、9张图和指标文件，62项月度数值核对通过；报告修订续跑仍有运行中断，尚不计完整验收。共同链路已修复RPC累计事件膨胀、HTML/SVG预览、跨镜像文件恢复和统一文本类型接入；本地正在更新故障分类并复验。见[真实验证记录](../reviews/2026-10-17-enterprise-research-demo1-live.md)。全部为15980389加未提交增量，未合dev，云端及用户环境不变。

2026-10-17 22:30：企业研究真实连续文件任务已走通：读取任务交付v1、生成修订报告、保存v2、刷新后引用v2生成新摘要；实际研究状态更新至3/4。三处容器启动接线阻断已修复。local-dev规范重建ready，API/worker同镜像bdae9325a9fb，来源15980389加未提交增量，未合dev。当前按真实链路走通优先推进；电网默认研究循环内Pi委托仍待接入，不宣称全部应用完成。见[真实验证记录](../reviews/2026-10-17-enterprise-research-live-continuation.md)。其他环境不变。

2026-10-17 19:46：过程制品纵向切片已接本地：账本目录保留完成/失败/取消/中断，支持历史结果恢复、原指令定位、下一轮显式引用；系统执行记录仍在侧滑窗。侧栏覆盖菜单无法收起已修复，关闭按钮/外部点击/Esc真实浏览器通过。48项后端、38项App及类型检查通过；真实IEEE39历史引用追问16.4秒完成，无重新潮流。规范本地重建完成，API/两worker同镜像6cb847e4cd71f875f6bf37b7e2d59fd631a3e78d3260c43ec7147d855a553c33；来源15980389加未提交改动，不是纯提交构建，未合dev、未变更其他环境。任务级交付请求、版本与跨任务支撑关系仍待完成。 见[持续会话计划](../superpowers/plans/2026-10-17-continuous-work-session.md)。

2026-10-17 17:48：工作台候选15980389已实现Pack发布的任务结果集合、核查侧滑窗与阅读控制修订；31项后端投影检查通过，App旧制品断言已按新契约修正并通过定向回归，构建通过。规范本地重建进行中，未合入dev。会话类型/工作对象及左栏顶部重设计已确认，入口持久化待实现。PR #54 macOS检查已通过，PR仍OPEN。

2026-10-17本轮已获local-dev真实Provider验证授权。00a8cd85普通问答、IEEE39计算及连续追问三轮通过，刷新可恢复；PyPSA附加试验发现静态负荷与时序需求混淆，未计通过。effc9ccd在所属Authority/Pack修正有效负荷摘要及调度语义，126项PyPSA回归、类型检查与独立评审通过，正在规范重建后复验。共同基座c9e57152已修复native父链，1394项后端及23项真实PG通过，未部署；以下较早“RPC尚未通过”是历史记录。

2026-10-17用户纠正交付标准：新建任务即会话，两个入口仅预配置ApplicationProfile；发送即统一执行，必须完整复用成熟对话功能。a8b4e578仅为内部基座候选，简化界面及保存/开始流程验收已撤回。PR #50转草稿、旧CI已取消；native改动保留待续，RPC父链尚未通过；当前先适配成熟电网对话并回归原样例。同一Harness自主选通用/专业/组合能力，不设应用模式硬切换。研发改为macOS门禁，main/Linux用户发布仍双平台，CI政策PR #51已合入dev a8caeff2，macOS治理CI1分46秒通过；合并树与a14169aa一致。

2026-10-17 PR #48已合入dev d86cc4ef，合并树与受检ed0e2e19一致。CI38930597623双平台shared-agent通过（Linux5分7秒/macOS8分4秒）。运行源码e58ef9a4：v2 Work账本与无模型任务保存；独立任务页已撤掉，改用既有对话组件及定稿布局。后端1427项、App537项与重建同源通过，已集成；两条应用准备分支已快进同源。持续执行及完整工作台仍未完成。

2026-10-17命名已接受：`enterprise-research`（企业研究与分析）与`grid-analysis`（电网分析与决策）。前者缺省内网资源、公网检索关闭，可选增强显式启用；后者复用pandapower/PyPSA专业资产。Profile装配待实现，应用分支仍准备中，分支引用保持不变。


2026-10-16共同基座PR #46已合入dev9eb84a34，合并树与受检cb08ef92一致。CI38916542829双平台foundation通过（Linux8分49秒/macOS10分22秒）；按需准备保留完整Profile与授权，native无需电网模型。local-dev源码20226bf0同源及实读Pi资源验证通过。生产Profile持久化、v2、无模型前端与持续执行仍待实施。[切片报告](../reviews/2026-10-16-application-pack-selection.md)。

2026-10-16共同基座PR #41已合入dev85b6706f，合并树与受检08556cc2一致。模型无关Work研究身份及开发CI分层已集成；Linux/macOS CI38898130414分别6分4秒/6分3秒通过。旧38894817486已被替代取消，不计验收。生产Profile/Thread v2/前端仍待接入，两应用线保持准备阶段。local-dev精确源码055a335f，其他部署不变。

2026-10-16共同基座Task 2首个切片已集成：055a335f增加模型无关Work身份、研究保存/恢复及Harness内部投影；44项身份/研究测试、1332项后端测试和独立评审通过。生产Claim、Profile、Thread v2与前端入口未接入；两应用线仍准备中。[切片报告](../reviews/2026-10-16-work-research-identity.md)。

2026-10-16控制同步：PR #37双平台CI38886499201通过并合入34cf695e，三条研发分支已快进同源。顶部三线卡片显示生成时实际分支HEAD；图中重要产品合并节点不冒充最新分支头。每次合并及应用分支同步完成后，重新生成并检查本地推进图，再报告对齐完成；生成快照的提交时间与分支HEAD分别记录，不为快照自身反复创建控制合并。

2026-10-16共同基座Task 1已通过PR #36合入dev d8fe6e27：精确711f06a8的Linux/macOS CI38881419651通过，合并树一致。执行接缝与既有基线验收完成；下一阶段为Task 2身份/Profile及前端最小入口，生产持续执行仍待Task 3。local-dev运行源码62f44366（构建711f06a8）已规范重建并核验；两条应用线仍准备中，main及用户/云环境不变。下方较早摘要保留历史，不覆盖当前表格。

2026-10-16已接受共同基座同时服务对话和企业自主执行：三个工作包分别控制共同修复增强、对话维护和企业执行研发；后者含企业研究与分析、电网分析与决策两类可组合形态。设计已接受，实施及各应用验收待推进；发布与部署不变。

2026-10-16图示修订：按祖先层级排列发布与合入来源，保留dev第一父节点主线；分开入边、出边与部署引用端口，检查连线交叉及穿卡。

2026-10-16主线收口已合并：对话应用进入main发布维护，企业自主执行沿dev推进。
原Pi分支正在验证并准备PR，尚未合并。见[收口设计](../superpowers/specs/2026-10-16-main-dev-convergence.md)。

2026-10-16协议细化：[迁移/命令/检查来源](../superpowers/specs/2026-10-16-enterprise-protocol-decisions.md)
已写明新旧wire、对象CAS、答复排队及暂停语义。Pi工作树doctor、43项既有协议/研究测试、SDK离线探针通过，
见[前置基线](../reviews/2026-10-16-enterprise-protocol-baseline.md)。未改运行代码；完整执行桥与业务验证仍开放。

2026-10-16执行约束修订（已保存Pi本地f4369eca，未推送）：[持续推进审查](../reviews/2026-10-16-enterprise-progress-constraints-review.md)
将缺资料、未知动作、上传和检查失败按依赖局部处理；启动不要求全部输入就绪，检查建议不自动升级为硬门槛。
状态矩阵与实施计划同步；运行代码、Git节点和部署身份不变，实际恢复与业务推进仍待实施验证。

2026-10-16边界复审（已保存Pi本地f4369eca，未推送）：[审查记录](../reviews/2026-10-16-enterprise-scenario-boundary-review.md)。
Demo1/Demo2仅作外部实例；改为可扩展视图、原生输入协议及按需交付检查，解除新增示例求解能力与框架门禁绑定。
架构基线确定，实施契约修订中；前后端协议迁移、命令状态映射和检查来源已细化，运行验证仍开放。
本轮仅文档，Git节点为f4369eca，运行源码、部署及既有验收身份不变。下方定稿记录保留为历史。

2026-10-16设计定稿v1：[统一组织与资产复用](../superpowers/specs/2026-10-15-enterprise-design-final.md)
及[实施计划](../superpowers/plans/2026-10-16-enterprise-unified-execution.md)补齐R1–R7的设计交付。
固定SDK离线探针、严格语义schema/状态检查、11712条外部合成数据核对、七类交互状态检查通过。
复用现有Thread/worker/研究控制器/专业前后端，取消平行Work控制面；运行实现和真实业务验收仍未开始。
下方未提交记录为定稿前的演进记录，精确设计提交以Git节点为准。部署身份不变。

Demo2拓扑调整（未提交设计）：复用现有NetworkView导出的IEEE-39电气拓扑，39母线/46支路；支持缩放与平移。记录拓扑与合成分析示例分离，未叠加虚构结果。[来源说明](../design/ieee39-recorded-topology.md)。

Demo2设计补充（未提交）：场景/候选切换联动网络、负载率、电压与验证记录，约束修订后旧结果失效；桌面与手机交互、刷新恢复和合成SVG导出检查通过。仅设计原型，无专业计算、运行实现或部署变化。

设计工作区补充（未提交）：[执行与成果契约](../superpowers/specs/2026-10-15-enterprise-execution-contracts.md)明确通用任务协议、恢复边界及Demo1专业图表验收；原型加入本地会话保存、模拟进展和合成图表的数据查看/SVG导出。此项不改变Git节点、运行或部署身份。

当前设计提交：Pi本地f4369eca8cecc4d73aef7ef89676021e892c75cb（未推送）保存统一组织、局部失败推进与v2协议决定：Demo1报告、Demo2模型/决策、普通对话共用框架；运行源码仍等同98e7d0e。设计文档检查通过，不代表运行实现。[设计契约](../superpowers/specs/2026-10-15-pi-enterprise-execution-design.md)。

历史Pi方向（2026-10-15）：Pi分支已通过保留历史的合并98e7d0e5959a810b7ee3b16f862e4f2f3131f8ac接入dev f209fb1。旧38e19db保留为archive/pi-before-dev-baseline-20261015；本地代码与独立审查通过，尚未合入dev或部署。用户要求从最佳架构讨论独立通用的长程组织能力；已确认统一Pack治理、Pi生态与长程自主组织结合，Demo1作为通用能力验收案例，不开发专用业务接口。[适配验证](../reviews/2026-10-15-pi-dev-baseline-adaptation.md)；[核心讨论](../superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md)。

历史控制核对（2026-10-15）：dev已通过PR #29正常合入f209fb18d7abb122b689e1b1a52c54fa13bf5371；Linux/macOS CI38728722421均SUCCESS。相对f300d1f，packages无差异，仅验收文档及控制工具变化。App5173实读f209fb1、dirty=false；后端仍为已验证f300源码及6c616058镜像。修复和验收文档分支已关闭。e2原包、19173、cloud-dev和两个demo不变。下方f300 App记录为重建时的历史验收身份。

当前工作：PyPSA派生结果投影和AC调度输入两项修复已实现、独立审查及针对性检查通过。精确候选c638e0992e49d300e760e89d07aff63ef6eca1c5在Apple ARM宿主的Linux AMD64模拟环境完成原区域三轮及补充AC-only第4轮；没有重新dispatch，5个operations投影completed且模型修订/证据正确。南部机组第3时段增量9.999984503 MW，最大AC残差约0.00004649 MW，小于0.01 MW。PR #28的Linux/macOS required CI run38723131332全部通过，已正常合入f300d1f375ef20af005840a60af47b5e33ea62e8；root dev已快进，packages与受检c638完全一致，local-dev规范重建exit0、ready通过；API与双worker同镜像6c616058e643，各1060个受管后端文件SHA256等同f300；镜像源码标签仍development，未将该标签冒称精确提交；App5173为f300、dirty=false；候选已停止，数据保留。回答文字仍有“+5应为+7.5”的算术问题；source-modeling投影仍未实现，不称所有回答或所有Pack通过。e2交付包不含这两项新runtime修复，原包和校验值不变。执行[后续计划](../superpowers/plans/2026-10-15-pypsa-runtime-followup.md)，见[限定实测报告](../reviews/2026-10-15-pypsa-runtime-followup-verification.md)。

2026-10-15更新离线包已交付：精确源码e2eaee2403cb6d780b3f7564da86e0d083890673，根runs/user-local-offline/capstone-delivery-e2eaee2含归档、同名.sha256及README.md三文件；归档1368607944字节，SHA256为9d7c3b215b9c45631bf3142aaad8f8066ba43831380b43b2ccf8146ee1eebfe7。新README默认pandapower IEEE39，PyPSA清单在末尾可选说明；旧7c已撤回、不可交付，证据目录及原校验值保留。新包12项内部SHA与源码检查通过，runtime packages相对28020aa无差异，可复用已记录的handoff/dispatch限定实测证据；29377单次新安装及ready检查通过，六角色均linux/amd64，API与双worker同e2源码镜像；检查后正常停止并保留数据。本轮按用户要求不重跑全量测试或Provider；公开投影与AC第3时段一致性两项仍开放，不声称完整业务验收。

2026-10-15旧7c包曾交付后撤回，现不可交付：精确来源7c1976659a46fdf3f19abd565a0198bb60a0b8cd，目录为根runs/user-local-offline/capstone-withdrawn-7c19766，原归档、README及SHA256保持不变。完整安装、重启、重复安装、数据保留和九请求/独立回放检查通过；这些链路检查不等于所有业务样例通过。7c的区域样例没有实际调用operations.dispatch，调度业务失败保留。README原文1–9已用OPENAI方式完成运行记录，10–12未运行；12的完整发电N1研究及排序仍待验证，不宣称全样例通过。

PR #27在来源7c的Linux/macOS CI run38700786813全部通过后，正常合入dev37529efa2f0b0e10f641a65706b330b1d94255af。root dev已快进f300d1f，local-dev规范重建及真实源码核验通过，运行来源f300；local-dev现为f300，其余三个部署及19173用户安装保持原来源。验证环境是Apple ARM宿主Docker中的Linux AMD64模拟运行；用户取消VM/cloud验证，原失败记录保留。独立fix/user-local-network-view分支文档收据6064103；交付冻结源码e2eaee2（runtime packages同28020aa）：61a418d图场景/相机修复已推送，未建PR或部署；28020aa公共Pi handoff schema修复16项合同/82项检查及审查通过；ce47532默认IEEE39/可选PyPSA文案54+5项及审查通过，分支e2eaee2已推送，未PR或部署，均不在已撤回7c包内。独立29375候选使用AMD64后端28020aa与App7c，原三轮OPENAI实测handoff/dispatch通过：基准与增长目标1300/1900，均optimal，两次AC校验均converged。第3轮4个operations公开投影不可用，AC第3时段与调度增量一致性待查，不宣称PyPSA整体通过。候选已停止，0运行容器，数据保留；四部署不变。见[限定验证报告](../reviews/2026-10-15-pypsa-handoff-verification.md)。见[验证记录](../reviews/2026-10-15-user-local-offline-verification.md)、[设计](../superpowers/specs/2026-10-15-user-local-offline-design.md)及[计划](../superpowers/plans/2026-10-15-user-local-offline.md)。

2026-10-15当前增量：PR #23经Linux/macOS检查正常合入dev b7e68dd，local-dev已规范重建同源。user-local标识、Git版本选择、capstone.sh共享数据管理及兼容发布门禁已交付；精确合并源码双架构镜像完成匿名拉取、旧数据升级/读取/报告证据回放、重启、浏览器和兼容回退验收，公开安装包下载/校验/启动/管理实测通过。新版本user-local-b7e68dd与受管旧版user-local-7832134已公开；原用户安装和数据保留，cloud-dev/demo未改变。

2026-10-15 原版交付记录（历史）：无源码试用实现经PR #22双平台检查正常合入dev7832134，local-dev已规范重建；四类精确摘要镜像及最终七文件包完成双架构验收并公开发布。注释标签dev-trial-20261015-7832134指向实际冻结来源，公开install.sh已实测下载、校验、安装及自动启动。默认目录~/capstone、端口19173，与开发5173/demo15173隔离；成功提示地址、配置及四条运维命令。实施分支已关闭、数据与恢复引用保留；用户LLM/业务试用待验证，cloud-dev及两个demo不变。

2026-10-14 当前：自主智能体独立登记为 `autonomous`，十二项功能与验收明细已对齐。
PR #18已正常合入dev，最新开发基线faa6af9；候选2b6ae7b双平台PR和完整发布门禁通过，合并提交的完整Git树与其一致，合并后dev双平台门禁也通过。
local-dev、local-demo和cloud-demo均已部署faa6af9；cloud-demo三注册用例九轮、报告证据回放与原Thread恢复通过。local-demo三角色运行身份与已验证local-dev一致，六个原Thread及事件序号保留；两个demo均完成三用例九轮和报告证据回放，正式标签demo-20261014-2028-faa6af9已推送并核对。
cloud-dev保持24d9a32。主图突出当前活跃节点、四部署来源、实际在研分支和重要云部署/大分支合并；普通中间提交保留在历史详情。
下方较早日期的摘要保留历史依据，不覆盖当前环境台账与本包功能明细。

2026-10-12：PR #14候选bc08169精确双平台CI通过，已合入dev6ff7094形成新开发基线。local-dev已同源重建6ff7094；Pi38e19db及Research Model2b0b0a5接入该基线并完成适配。真实复验出现一次普通请求误路由，失败保留；代码集成不等于整体业务验收，未新增本地验收标签。

原1013dd2及更早修复只保留历史证据，不再作为当前验收依据；预热、任务编译、覆盖判定、回答重写和增强复用均已撤回。PR #13已关闭；PR #14合入后关闭恢复分支，精确来源及旧候选归档保留。main、demo及云端未更新；Research R1尚无代码。

更新日期：2026-10-12。当前登记范围包含基线一本地验收、基础修订、全部现存分支进展及未提交存储工作；云端未更新运行版本。

main保持723b8e8发布快照；dev经PR #11/#12治理集成后，PR #14恢复基线合入6ff7094。B2标签仍是不可变历史记录，不能认证已撤回的回答闭环。local-dev使用6ff7094，local-demo及云端保持ed2524f。两实施分支已接入新开发基线；R0原始记录保留，R1尚未实现。

当前全局记录以dev为准，main副本是发布快照。功能、修复、文档与治理PR面向dev；发布PR面向main。实验保留原始证据，按范围整理后集成，不能批量合并。两条永久分支禁止强推/删除、要求PR与原两平台Actions检查、0人工审批；管理员应急绕过仍保留，本次未使用。dev文档/治理按范围检查，未知改动走产品回归，main发布集成走完整门禁。详见[已批准设计](../superpowers/specs/2026-10-11-dev-integration-design.md)和[实施计划](../superpowers/plans/2026-10-11-dev-integration.md)。

本文件是固定、持续更新的分支、公共修复、基线和发布台账。每次建立分支、合并、验证、发布或回滚，都更新对应条目；验证证据链接到原始报告。部署边界以[开发与发布生命周期](../architecture/capstone-development-lifecycle.md)为准。

main轻量保护已开启并回读核验：PR＋GitHub Actions两平台检查，审批数0，不强制追平main，禁止强推/删除；管理员保留应急处理，小石无常规绕过。现有PR等待CI，不增加本地迭代门禁。收据：`runs/task-answer-closure/main-protection-readback.json`。

推进控制双向对齐是默认交付流程。代码、分支、PR、验收和部署变化必须更新图；通过图确定的范围、归属、顺序和完成标准必须同步到所属设计、实施计划、总任务清单和实际工作分支。不能只改图后报告已对齐；不得以计划更新冒充代码已实现。Pi 的完整业务上下文与数据共享已归入其设计及 Tasks8–9；统一回答增强仍在独立分支。

视觉标识固定：本地部署用浅绿底色，云端部署用浅橙底色，main发布节点保留浅蓝底色；部署边框和环境名称略突出。精确部署提交号及dev/main工作线前缀保留，前缀不表示部署了分支最新HEAD。节点、环境名称、验证状态和图标均保留，不能只靠颜色区分。主线用较粗深青实线，分支用紫色曲线，部署来源引用用细虚线；统一使用小型开放箭头和边框外留白，端点按实际卡片边界计算。

以 dev 工作区中的本文件为当前台账；main副本为发布快照。功能分支内的副本可能较旧，操作前须读取 dev 的最新版本；合并时不能用旧台账覆盖当前记录。

## 项目推进控制图

布局以两侧视觉均衡为准：共同基座及应用研发节点优先放在dev右侧，结合节点高度、部署卡片和留白调整整组位置；不为固定左右分类造成一侧拥挤或大面积空白。布局调整不改变Git祖先关系或部署来源。

可见Git节点只保留必要和重要的主轴基线、分支交付点与实际部署来源。
部署来源节点与其他Git节点使用同一祖先图，不建立独立的来源卡片链。
当前自主智能体链为dev6ff7094 → 24d9a32 → 94349e6 → bfb2e83 → bd2a200 → 07d618a → 2b6ae7b；
Pi38e19db从dev6ff7094分出。所有可见Git节点从共同基线可达，不得孤立。
中间提交可在主图压缩，但真实祖先关系与历史详情必须保留；压缩连线不声称直接父提交。
四部署分别从其精确Git提交节点连出，不改变源码、合入或验收状态。
每个可见节点同时展示变更主题、简短功能说明、当前验证状态与提交号。
重要交付版本各自建立独立精确源码节点，直接显示交付状态、限定验证和包/README入口；撤回版本及中间文档收据放在历史详情，不为每次提交增加主图节点。
试用点说明统一研究/任务执行与证据范围；对话启动基线说明缓存、线程池与启动预热。
完整变更、测试和计时放入该节点详情，不以孤立提交号代替开发进展。
所有Git节点复用同一内容规范：变更主题、所属分支与提交号、两项功能增量、
验证状态、变更与验证详情、功能与验收入口。来源节点不使用另一套简化卡片。
卡片功能说明使用10px，部署辅助说明使用9.5px；标题、状态和提交号保留层级。

当前图层主线（2026-10-14）：aff8319已实现基础断开开关、母线联络开关、孤岛内部线路着色、关注区域相机及可追溯N−1最高线路负载率场景；128项模型/契约、44项App检查和类型通过。local-dev规范重建中；上次部署为9dca4ab/506a94bba5dd。真实调用仅使用原Thread thr_98b1c23a7ce472de5dc1。节点边际价格图层和模型生命周期仍待完成；最新孤岛回复物理失电推断有缺陷，整体科学验收未完成。固定端口5173/8767、cloud-dev/demo不变。

当前效能主线（2026-10-14）：73bef5b字段增强已规范重建并实测通过。原Thread新OPF26.052秒，两次结果查询均成功，无字段错误、重试或describe调用；计算回执实际附带母线8字段/线路16字段，完整35线路/39母线及证据保留。18项Authority测试、类型和doctor通过；整体科学验收仍未完成。回复受控试验35工具与零工具，输入减少39%，近等输出6.120/6.234秒，无明确延迟收益；独立回复切换保持移除。固定5173/8767，API/双worker镜像a778d62e6145，cloud-dev24d9a32和demo不变。

当前执行检查点（2026-10-13）：local-dev已规范重建f09a0c8，API/双worker同镜像a1eb9faf0552，固定5173/8767。模型首次打开绑定默认能力、打开时在所属worker准备、连续切换复用已实测；重建后第一次切回IEEE39用4.041秒，随后切回已准备的mv_oberrhein用0.038秒。新对话首条指令资源获取0.000017秒；概况实际25.462秒仍待优化。73b6c07的配置冲突修正和云部署迁移检查记录在Railway说明及测试中；回收后的快速恢复仍待实现，未宣称完整生命周期收口。

2026-10-13 当前补充：03b8d96已实现跨Thread能力上下文的内存压力回收，默认取消60秒空闲清除，固定4个名额改为内存调度与独立1024防护上限；92项检查通过，尚未部署。打开模型即准备、回收后快速恢复仍未完成，不计为生命周期收口。0494ef7 local-dev后端同镜像cc775c0f894c已重建；2a5a51e前端移除遗留追问绑定，62项及类型通过。原Thread新OPF实际33.799秒；连续复用准备4.825秒降至0.775秒，资源获取3.893秒降至0.000014秒，无新求解。云端仍24d9a32。

[PROJECT-OVERVIEW.html](PROJECT-OVERVIEW.html) 是双方对齐项目开发与发布的固定全景入口。本文件提供功能包、分支、PR 和部署台账；Git 与验收收据提供事实。持续更新同一 HTML，不另起一份进度图。

建立或调整功能分支、完成关键实现或验收、提交或接受 PR、部署、回滚以及优先级变更后，在汇报前更新台账并运行 `python3 tools/render_project_overview.py`。重要变化直接挂在图上的对应功能包与提交点；图中保持已实现、已验收、已合入和已部署的区别。待建分支、待合入关系不能画成已经发生的 Git 合并。

主图以当前活跃节点、四部署精确来源和实际在研分支为主体；dev推进主线补充重要云部署及大分支合并节点，普通修订、文档提交和中间候选放入历史详情。待启动与归档参考不冒充在研。已合入的自主智能体历史按真实祖先关系进入dev推进主线，未合入分支保留分支线。

dev主图登记最新接受的运行/大分支合并基线。纯控制文档提交不产生新的运行版本；实际分支HEAD在分支详情保留，不能因记录推进而把已验收部署误判为旧产品。

每次更新同时重新排版，不能只换内容。采用宽幅画布，保留居中的纵向dev/main中轴，历史基线在下、当前开发在上；Pi在左，自主智能体连续提交链与四部署在右。优先完整显示当前焦点和重要发布，按可用宽高缩放，避免桌面图内滚动。main发布点保留浅蓝底色，部署按精确来源引用连接。已合并分支按PR、源码等价和未提交工作核对后关闭，恢复来源留在详情。

每次更新控制图调用 `ui-ux-pro-max`，核对紧凑字号、间距与视觉层级、左右平衡和参考实现降级。状态不能只靠颜色。保留深青主线、紫色分支曲线、棕色虚线部署引用、小型开放箭头、dev/main居中纵轴、main发布点不同底色和四环境独立来源。生成后检查桌面一屏、间距两端、重叠、来源边、移动端与离线交互；有问题先修正。

连接到同侧主线的分支和部署按来源顺序排列，避免倒置造成交叉。检查独立边交叉和穿过卡片，共享端点分叉不算交叉。local-dev挂dev基线6ff7094，demo及cloud挂ed2524f；两实施分支挂真实新基线祖先，不画R0参考代码已经合入。

已确认推进顺序：收口基础修订 PR #6 并更新 local-dev → 核对数据兼容后恢复 local-demo 与 cloud-demo 的 `ed2524f` 基线对齐 → 从最新 main 建“任务理解与回答闭环”增强分支 → local-dev 分阶段验收 → 合并并冻结下一发布候选 → local-demo 产品验收 → cloud-dev 验证 → cloud-demo 计划发布。Pi/skills 和统一输入命令保留各自开发状态，不混入回答增强包；旧存储实验已归档。当前授权推进本地开发与验证，云发布仍需独立授权；尚未发生的合并、对齐和发布不得登记为完成。

## 自主智能体演进讨论

当前统一方案见[自主研究统一设计](../superpowers/specs/2026-10-12-autonomous-agent-design.md)；
详细讨论保留历史与依据。统一设计仍为草案，接口核对后形成实施计划。
已补首期接口落点：研究读写需持久提交回执，Pi实际请求需读到研究视图，
结果投影复用并核对全量覆盖，推演证据补结构化关联；均未实现。

更新：2026-10-12。本章持续记录双方讨论结论，由同一HTML生成图示。
已确认的是演进方向；详细契约、验收尺度与迁移步骤仍待讨论。
概念图表示职责和工作关系，不表示固定执行顺序或实际Git合并。
当前运行基线及两条实验分支的实现状态，仍以本文件的提交和部署台账为准。
详细依据见[核心能力演进笔记](../superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md)。
实现级讨论见[自主智能体设计讨论](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md)：身份、状态、证据关系、更新恢复和验收行为；均区分提案与已确认决定。

| ID | 类别 | 状态 | 标题 | 说明 |
| --- | --- | --- | --- | --- |
| C01 | 概念 | 基础抓手，名称提案 | 研究模型 · Research Model | 参照WorldMap：组织目标、对象、条件、假说、证据关系与缺口；与Authority物理模型区分。 |
| C02 | 概念 | 基础抓手，名称提案 | 研究笔记 · Research Notes | 参照NOTES：保留探索线索、失败经验和方法理由；未证实陈述保留其身份，不自动升级为事实。 |
| C03 | 概念 | 基础抓手，名称提案 | 实验工作台 · Experiment Workspace | 参照IPython：构造实验、组织执行和分析结果；具体执行形式与授权交接待定，不直接开放Authority内部对象。 |
| C04 | 概念 | 基础抓手，名称提案 | 行动策略 · Action Policy | 参照策略网络的职责：依据研究状态提出、选择下一步行动；不要求独立模型或每轮固定调用。 |
| C05 | 概念 | 基础抓手，名称提案 | 进展评估器 · Progress Evaluator | 参照估值网络的职责：判断目标覆盖、证据缺口与继续探索的价值；模型自评不能替代计算证据和结论核验。 |
| M01 | 核心 | 本轮设计提案 | 问题与适用范围 | 研究模型是随证据演进的工作认识。保存用户目标、对象引用、场景条件与完成依据；允许未知项，不要求入口先编译完整任务。普通查询保持轻量。 |
| M02 | 核心 | 本轮设计提案 | 判断及其证据关系 | 一个判断说明内容、适用条件、来源及支持或反对的证据。猜想、条件假设、实际观察、分析判断分开；先后发生不自动构成因果支持。 |
| M03 | 核心 | 本轮设计提案 | 有效性与研究缺口 | 判断可处于待检验、有条件支持、被反驳或待重验状态；结论只覆盖实际评估范围。缺口影响下一步，但不是每个缺口都要解决后才能回答。 |
| M04 | 核心 | 本轮设计提案 | 按需展开与连续性 | 一个研究可跨多轮与多次执行；一个对话可关联多个研究。追问读取适用结果，条件变化建立场景分支；只重验受影响的依赖，历史不覆盖。复用仍经当前运行接纳。 |
| M05 | 核心 | 本轮设计提案 | 从变化产生进展 | 新发现、反例、实验完成和方案修订形成用户可读事件；证据绑定通过后才能发布数值发现。已发布记录保留，后续明确修订，不静默改写。 |
| M06 | 核心 | 本轮设计提案 | line7示意：从问题到结论 | 解析对象与场景 → 复用适用基准或按需计算 → 执行停运实验 → 核验收敛与线路阈值覆盖 → 形成限于该场景的判断。此为设计示例，无实际计算结果，不预写固定业务路线。 |
| M07 | 核心 | 自主原则已确认，契约提案 | 工作节点与观察反馈 | Agent按当前认识提出局部目标和动作；运行时校验执行、接纳真实观察，再由Agent修订后继。策略与评估是同一循环职责，不强制独立模型或固定流程。详见设计讨论D04。 |
| M08 | 核心 | 接入设计提案 | 一个主循环，按需方法资源 | 复用dev的Pi会话、工具目录、上下文与证据机制，增加有界研究状态及领域方法供给；不叠加外层固定规划器。自动入口改造先对照验证，详见D07。 |
| U01 | 呈现 | 本轮已收窄 | 复用demo工具调用链 | 用户确认现有调用链可体现业务思路；本轮展示正确的解题逻辑即可，仅必要时补短说明，不新增复杂展示或逐工具LLM摘要。 |
| U02 | 呈现 | 架构建议，待定契约 | 研究事件与用户表达 | 执行层产生任务级事件，绑定研究节点、模型版本及可用证据；应用组织流式表达。工具日志保留为辅助详情，可核验工作说明与隐藏思维分开。 |
| U03 | 呈现 | 后续方向，非本轮前置 | 持久记录与修订 | 中间发现标明暂定或已验证，反例显式修订并保留来源；完整任务级流式契约后续细化，本轮复用既有运行记录与展示。 |
| D01 | 原则 | 已确认方向 | 自主组织工作 | 主智能体持续维持用户目标，根据已有信息、观察和证据选择下一步；意图识别可作辅助，不是强制总开关。 |
| D02 | 原则 | 已确认方向 | 按需要展开 | 请求理解、与当前工作的关系、所需上下文与资源，在工作中逐步明确；简单问答可直接完成，研究状态按需建立。 |
| D03 | 原则 | 已确认方向 | 方法可修订，历史可追溯 | 知识包与工作流提供可选方法；智能体可组合、委派和修订后续安排。已执行动作、版本及证据保留，不改写历史。 |
| D04 | 原则 | 已确认方向 | 自主选择与执行约束 | 模型选择工作方法；框架持续检查授权、对象版本、工具契约和证据。研究记录保存可核验决策，不要求暴露隐藏思维。 |
| L01 | 循环 | 概念关系 | 理解当前工作 | 用户目标、当前模型、已有成果及未解决问题。 |
| L02 | 循环 | 按需选择 | 选择并执行下一步 | 读取资料、查询结果、调用领域工具、更新研究状态或委派子任务。 |
| L03 | 循环 | 依据实际观察 | 检查观察与证据 | 检查所得信息是否支持目标；识别反例、失败、能力缺口与版本变化。 |
| L04 | 循环 | 可结束或继续 | 回答、修订或继续 | 已有充分依据就回答；需要更多信息则修订安排；必要时询问用户或保留明确缺口。 |
| R01 | 职责 | 已确认方向 | Capstone主智能体 | Pi作为底层推理执行引擎，Harness管理运行、上下文、授权与证据；主智能体保持目标并组织整个工作过程。 |
| R02 | 职责 | 按需建立 | Research Model | 保存对象、条件、假设、证据判断和缺口；支持跨轮延续、分支与失效处理。R1尚未实现。 |
| R03 | 职责 | 复用既有能力 | 受委派Pi与skills | 接收有界任务和上下文，执行后返回观察或成果；主智能体负责整体判断和回复。现有实验不等于自主组织已验收。 |
| R04 | 职责 | 保持所有权边界 | Domain Pack与Authority | 领域包组织知识、方法和语义能力；Authority提供模型事实、计算结果和证据。通用执行产物不自动成为数值证据。 |
| B01 | 组织 | Kernel与Pi链路通过 | 从dev建立统一演进分支 | feat/autonomous-agent从dev4f15cfc建立；7df7180接入Pi研究读写、回执及上下文恢复；Python3.12下609项Kernel、60项Pi工具及类型检查通过。App生命周期与引用准入待接入，未合入或部署。 |
| B02 | 组织 | 基线对齐，设计推进 | Pi与Research两分支 | Pi运行基线98e7d0e接入dev f209；本地设计提交f4369eca，未推送。ApplicationProfile组合与使能方向已确认，Research分支未移动。 |
| P15 | 方向已确认 | 具体契约待评审 | 业务能力组与统一推演 | ApplicationProfile使能并组合Pack，Capstone统一组织Pi生态与专业能力；前端覆盖任务、进展、成果和恢复。 |
| B03 | 组织 | 回归底线 | 保持已有轻量与专业能力 | 轻量专业查询、潮流、对象解析和前轮结果复用保持回归；首个新增交付按B04的一次复杂指令闭环推进。 |
| B04 | 组织 | 用户明确优先级 | 一次复杂指令的自主推演闭环 | 优先完成复合问题的自主组织、计算验证、阶段进展与结论；双线路停运孤岛评估作为设计场景，能力与数据须核验。完整跨轮研究管理后续展开，既有问答保留回归。 |
| S01 | 首版样例 | Authority实测，智能体待复验 | IEEE39 · OPF与完整结果 | 隔离OPF成功，35条线路和39节点结果完整可查；CLI计算调用1.308秒，非端到端。lam_p单位为空须追溯；不代表智能体展示已验收。 |
| S02 | 首版样例 | 用户指定，待实现验收 | IEEE39 · N-1与最优缓解 | 发现过载后组织出力调整或切负荷优化，再以AC计算回验0.95至1.05电压等约束；故障范围、目标及方案适用范围须明确。 |
| S03 | 首版样例 | 拓扑实测，领域缺口待补 | mv_oberrhein · 双停运综合研究 | 同修订停运149/59，连通分量2→4；未证明可持续带电孤岛。两外部源短路参数为空，稳定性方法待核验；不以稳态电压冒充稳定性。 |
| Q01 | 待讨论 | 尚未定稿 | 研究状态的建立与延续 | 何时建立Research Model，怎样识别延续、新建与方案分支，模型版本变化后如何重验。 |
| Q02 | 待讨论 | 尚未定稿 | 上下文、资源与方法选择 | 能力描述常备到什么程度，何时按需发现工具，如何选择技能与委派上下文，避免重复初始化。 |
| Q03 | 待讨论 | 行为原则已确认，待实现 | 结束判断与验收尺度 | 同一主智能体按目标覆盖、适用条件和真实检查收束；关键变化才更新研究记录。无需逐步评审模型；结合回答、证据、轨迹和耗时验收。 |
| Q04 | 待讨论 | 首期计划已保存，未实施 | 分支迁移与首版契约 | 从最新dev按基线盘点、研究状态、Pi接入、统一循环、领域缺口、四视图、本地验收推进；两参考分支保留，不整支恢复旧入口。 |
| Q05 | 待讨论 | 后续细化，非本轮前置 | 任务级流式呈现契约 | 本轮复用demo调用链展示；完整事件与呈现契约以后细化，不为进度叙述增加固定LLM调用。 |
| D05 | 原则 | 用户已明确 | 正确性与合理耗时 | S01保护已有实现；S02/S03聚焦真实研究与验证。按任务规模记录端到端及各阶段耗时，排查重复准备、重复计算和无效循环，不承诺未经实测的秒数。 |
| D06 | 原则 | 用户已明确 | dev起步，长期通用框架 | 当前dev为研发起点，demo仅作体验参考；三个问题是首批验证集，不限定能力范围。通用研究契约与领域方法分层，首期一次请求闭环，长期可扩展。 |
| D07 | 原则 | 用户明确约束 | 五概念统一设计，保持简洁 | 整体设计实现应能解决三个问题；样例用于验证，不反推专用实现。五概念不等于五个模块或模型，节点等支撑结构按必要性裁减。 |
| D08 | 原则 | 收敛提案 | 五概念，一个主循环 | 研究模型与笔记保存认识；工作台复用授权能力；策略和评估由同一主智能体承担。只保存有用变化，不增加固定规划/评审调用。详见设计讨论D08。 |
| D10 | 原则 | 工作台设计提案 | 自主组合，真实执行 | 工作台复用检视、场景构造、分析和比较核验；策略选择实验，Authority提供事实。不增加专用题目脚本或强制编程环境；按需复用结果。详见D10。 |
| D11 | 原则 | 策略与评估提案 | 按信息价值行动，按依据结束 | 同一主智能体选择动作、解释观察并检查目标；沿用硬契约与领域核验，不新增回答裁判或固定评分。区分完成、部分结果、受阻与预算停止。详见D11。 |
| D12 | 原则 | 用户建议纳入核心设计 | 结论可追溯，采纳有边界 | 复用既有轨迹与证据记录，关联调用参数、实际结果和重要结论；授权分析自动，建议自动生成并验证、采纳由人确认，当前不开放真实下发。详见D12，非新增架构层。 |
| D13 | 原则 | 首期整体设计提案 | 最小闭环，五概念一起验证 | 复用Pi/工具/证据，补研究视图和笔记的读写恢复；同一主循环选择与评估。协议、真实自主性、数值与耗时分别验证；技术接口尚待落定，未实现。详见D13。 |
| U04 | 呈现 | 前端操作提案 | 对话、停止、结果与恢复 | 复用dev对话和三动作短窗，明确运行/部分完成/等待输入/停止；草稿不热改当前研究，断线不重复提交，历史绑定原场景。无真实下发按钮，详见D14。 |
| U05 | 呈现 | 用户明确优先级 | 单条指令完整，追问自然延续 | 首期集中完整完成一个任务；必要补充接续原目标，结果追问复用适用证据，条件变化派生场景。无新增研究管理界面或并发任务体系，详见D15。 |
| U06 | 呈现 | 融合展示提案 | 保留工具链，补充任务含义 | 已认可的三动作短窗与完整过程为主体；同一过程补充必要目标、关键发现和结果关联，不新建重复进度流，不隐藏工具细节。完成后结论优先、原过程折叠，详见D16。 |
| U07 | 呈现 | 名称由用户确认 | 正式回答／执行过程／计算结果／推演证据 | 正式回答给结论，过程保留工具链，计算结果提供完整数据，推演证据按判断与检查组织；共用真实来源，不复述流水账，保留技术追溯。详见讨论记录“当前前后端展示契约”。 |
| U08 | 呈现 | 用户明确要求 | 结构化事实，客观简明 | 三类依据以字段、数值、单位、状态和来源为主，技术引用可见可追溯；说明借鉴ASD-STE100简明原则，不用AI润色替代数据，不宣称中文正式合规，详见D18。 |
| U09 | 呈现 | 记录读写边界通过，交互在研 | 全局覆盖、细节追问 | 概览覆盖成功/失败/未执行，展开简洁；解释读原记录，改条件另建执行。54f6f13记录接口真实PG通过；a77e180前端身份/游标校验13项通过。任务概览、追问交互和完整私有轨迹读取待接入。 |
| M09 | 核心 | 实际Pi离线链路通过 | 研究认识可保存、可读回 | 7df7180接入有界研究视图、读写工具及可靠回执；实际Pi压缩、会话恢复后取得最新状态，缺失状态时阻止续推。App与业务验收待完成，不逐工具写笔记。 |
| M10 | 核心 | 失败观察可续行，待完整验收 | 失败也是研究结果 | ec913ac统一准入失败反馈并关联请求轨迹；d9f1879保留工具失败原因，结果面板含失败项。后端173项通过；整链记录受控查看、取消及真实业务回归未完成，未部署。 |

本章后续按稳定ID更新：新增结论保留日期，改变已确认方向时记录原因；
实现与验收须另有提交和证据，不能仅修改讨论状态即登记完成。

## 已确认的规则

`dev` 是开发集成主线，`main` 是发布基线主线；local-dev/cloud-dev是开发环境，demo是经过发布验收的稳定范围。四个环境不对应四条永久代码主线。日常功能PR面向dev，发布PR面向main。

local-dev 对应 cloud-dev，是线下开发测试、集成及版本发布验证入口，允许明确记录的开发候选领先 cloud-dev。local-demo 对应 cloud-demo，是线上版本的线下复现测试、紧急修复及版本发布验证入口；日常保持 cloud-demo 的精确源码和启用范围，不随 local-dev 的开发改动部署。

紧急修复从 cloud-demo 已验收来源建立；计划发布从已验证并合入 main 的来源冻结候选，临时在 local-demo 验证。必须标明线上基线、候选来源、用途和差异；发布成功后对齐新的 cloud-demo，候选失败或延期时在确认数据兼容后恢复当前线上基线。两套本地版本相同只可能是有明确用途的候选验证结果，不是默认目标。公共修复保持同一份实现，分别记录开发验收与 demo 发布验收，不以同时更新两套本地代替传播和发布。

当前已对齐：local-demo 运行 cloud-demo 的 ed2524f，兼容读取和实际入口验收通过；原有对话及证据保留。旧版 App 缺少环境标识，随下一计划发布更新。增强分支中的部署检查兼容修订尚未合入 main。

控制图中四个环境使用独立部署框，分别挂接实际 Git 提交；相同提交不合并环境框。树上提交号用深青色，部署提交号用紫色；连线不重复标注。local-dev 挂完整增强候选2473e48，其余三个环境挂 ed2524f；无本地/云端配对线。local-demo 紧急修复直接挂接已验收 cloud-demo 来源的主线提交，当前为 ed2524f，不从部署框连线；没有修复任务时内容留空，虚线只表示预留流程，不表示已有分支。

主图采用 main 居中的紧凑布局，默认在当前屏幕内显示完整图，可切换原尺寸；开发明细在底部按需展开。布局位置可以为平衡调整，但来源连线和实际版本不可改变。主图保留关键功能、状态、PR 和部署，避免重复下一步长段落挤占总览。

| 分支类型 | 用途 | 进入 main 的条件 |
| --- | --- | --- |
| `feat/<topic>` | 新功能；纯 Pi、skills 和资源扩展目前属于开发中功能 | 明确范围和依赖；通过集成检查；实验功能可隔离，默认能力保持可用 |
| `fix/<topic>` | 框架或领域公共缺陷修复 | 复现、回归、依赖闭包和实际入口验证 |
| `improve/<topic>` | 框架加固、性能、资源生命周期和体验增强 | 记录前后行为、影响范围和验收指标；兼容性及回归检查通过 |
| `hotfix/demo-<topic>` | 当前 demo 的紧急修复 | 从当前已验收 demo 提交建立；修复回归 main，并同步受影响的开发分支 |
| `release/demo-<version>` | 固定候选提交、配置和功能清单 | 验证期间冻结；修改后重新验证；不承载长期独立功能开发 |
| `integration/<topic>` | 必要时整理跨分支依赖或历史差异 | 临时使用；通过检查后合并 main |
| `experiment/<topic>` | 用户授权的架构与计算研究实验 | 实验报告、证据与独立审查明确后，分别决定保留、演进或抽取通用能力；不自动发布 |

PR 的提交、审查和接受由当前 AI 负责：本地验收、独立审查和精确提交的远端检查通过后，按合并流程执行，不逐项等待维护者确认。此授权不自动包含云端发布。

main 可以包含实验功能，但必须标明状态并能隔离。合入 main 不等于 demo 已验收。无法隔离、破坏默认行为或尚未通过集成检查的实验变更继续留在分支。

demo 的稳定子集由固定提交、配置和功能清单定义。不能靠复制目录或遗漏依赖来拼接。发布必须记录 API、各 worker、App 的来源与身份，以及启用的功能范围。

## 三线研发组织

两条应用分支已从dev `6c0b0ae74b523763b8d47bb1cd2f686afdeb12f0`创建并推送。
这是创建来源，不是应用独立实现或新部署。共同基座尚不足，当前实现聚焦dev；
应用线先做准备，按具体依赖逐段启动。控制文档同步后仍无应用业务代码。
每个功能阶段提供可运行前端入口、来源身份、样例与人工观察记录。
[三线阶段计划](../superpowers/plans/2026-10-16-three-line-delivery.md)。

| 分支 | 职责 | 当前状态 | 下一步 |
| --- | --- | --- | --- |
| dev | 共同基座与集成；同时服务对话应用 | 共享工作台已集成f5eda4e4；持续会话候选未集成 | 优先企业研究质量与性能；标准研究下层、企业上层策略与通用subagent增量结合 |
| feat/business-analysis | 企业研究与分析 | 应用分支仅准备；实际研究增量在现有工作台候选推进 | 保留350.524秒/ 41轮质量基线；不另建研究调度或聊天应用 |
| feat/model-decision | 电网分析与决策 | 00a8cd85已在local-dev验证；PR #53已合入f5eda4e4 | 成熟对话、真实历史与拓扑已接通；无模型与通用成果继续按协议推进 |

## 功能包前沿

全局视图从线上已部署 `ed2524f` 开始，先前沿革仅保留在详情中。下表是全景页的功能包来源；分支和提交是交付依据，不是主视图的组织单位。

| ID | 功能包 | 阶段 | 状态 | 交付内容 | 来源 | 下一步 | 对比起点 | 新增或更新 | 交付记录 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev-trial | user-local无源码试用与版本管理 | 8 | 离线包已交付，PR #27已合入；业务缺口单列 | 固定镜像安装、版本管理、数据兼容及内网离线安装 | dev37529ef；fix/user-local-network-view | root dev已快进f300，local-dev规范重建与真实源码核验通过；跟进独立候选的公开投影与AC一致性，不覆盖已撤回7c包 | 四部署及19173保留原来源 | 默认openai；双digest/层校验、元数据权限、共享指南；7c安装和数据保留通过 | 九请求/回放不等于业务全过；7c无dispatch；README1–9已运行，10–12未跑，完整N1排序仍待验证 |
| autonomous | 自主智能体 · 统一实施 | 4 | 已合入dev；两个demo已发布，整体业务未验收 | 单Pi研究循环、持久研究状态、Authority计算与来源、执行过程、结果证据、电网场景图层和模型资源管理 | origin/dev | 两个demo已验收faa6af9，从dev推进N−1与交互缺口 | dev4f15cfc及6ff7094业务基线；旧Research Model分支仅作参考 | 研究读写及Pi真实上下文；受控失败交付；任务与工具两级过程；完整结果字段；场景与孤岛图层；模型打开准备与内存回收；对话创建后台预热 | PR #18双平台PR门禁通过，合并dev faa6af9；2b6ae7b候选59项及本地完整PR门禁、云三角色身份、三用例九轮、报告证据回放与旧Thread恢复通过；完整发布及合并后双平台通过，两个demo已同源验收并推送正式标签，不冒充科学业务验收；详见本包明细及首期计划 |
| live | 线上共同基线 | 0 | 线上在用 | 电网静态分析、证据结果、智能体对话与工作台 | 线上部署 | 保持线上稳定；后续版本按发布计划推进 | 当前线上部署 | 本页起点；更早沿革仅在详情中保留 | 以 cloud-demo 部署台账为准；本次未重新探测云端 |
| main | dev研发 / main发布 | 0 | 发布基线已收口 | main维护阶段完整对话应用；dev承接企业自主执行研发 | dev | Pi已合dev；后续按具体问题开研究分支 | 既有业务与交付资产 | PR #30发布范围为f209fb1；用户安装与交付包保留 | cf72393b已正常合入main，CI38861900687双平台完整release通过；main不安排近期大升级 |
| foundation | 基础体验与开发治理 | 1 | 已集成，本地开发验收通过 | 连续浏览历史、环境与版本识别、反馈处理和修订流程 | main | 后续随正式用户发布验证；不单独定义功能增强基线 | 线上共同基线 | 历史对话连续浏览；明确环境与来源版本；规范反馈与修订流程 | PR #6 合并 c3b78bc；精确候选两平台检查与审查通过；local-dev 实际入口验收通过；云端未发布 |
| answers | 回退与选择性补回 | 2 | 已合入dev，业务缺陷保留 | c3业务链；独立LLM路由；三动作小窗；普通轻量无工具回答；正式消息与过程隔离 | dev | 路由可靠性与现存业务缺陷单列；研究按已适配计划推进 | main c3b78bc | 用户批准收口；不恢复任务编译；无凭据装配修正bc08169 | PR #14双平台通过并合入6ff7094；506项同源及两次完整集成通过；新真实复验一轮普通误分，保留失败，未称整体通过 |
| business-analysis | 企业研究与分析 | 1 | 分支已创建，准备中 | 企业资源、分析成果、图表与报告视图 | feat/business-analysis | A1准备；等待相应基座闭环后实施 | dev6c0b0ae7创建来源 | 无独立业务代码；沿共同协议推进 | 未实施、未验收、未部署；阶段需可运行前端供人工观察 |
| model-decision | 电网分析与决策 | 1 | 共享工作台已在local-dev验证，PR #53已合入f5eda4e4 | 既有专业能力、拓扑、结果、案例与公共对话组件 | feat/model-decision | 集成共享切片；继续按既定协议补齐无模型对话与通用成果 | devf5eda4e4及专业Work来源a8b4e578 | 6f1c3412恢复原型层级；00a8cd85兼容混合版本列表 | 570项App、88项真实PG、构建及独立复审通过；真实Provider普通问答/IEEE39/追问三轮及刷新恢复通过；PyPSA语义修正另验 |
| shared-agent | 共同智能体基座 | 1 | native父链离线验证通过；前端及部署待接入 | 同时服务对话与企业执行的组织、资源、恢复、证据及共享前端组件 | feat/work-attempt-binding | 保留c9e57152已验证切片；先收口当前专业工作台试用 | 已有Harness、Thread、专业执行及Pi资源 | 长回答和长指令保存有界摘要，原文保留；旧专业信封预算不变 | 1394项后端、23项真实PG及类型检查通过；RPC两轮原文恢复通过，独立审查通过；未合入或部署 |
| conversation-maintenance | 智能体对话应用维护 | 1 | 阶段已发布，维护范围已明确 | 接收适用的共同修复和增强，保留现有对话体验 | main | 按实际修复形成小版本，不强制采用企业新工作台 | main cf72393b；原用户包未替换 | 与企业入口共同验证受影响共享行为；保留将来对话场景演进空间 | 发布基线已验收；新增共享增强尚未实现或发布 |
| pi | 企业自主执行 | 3 | 基础能力已合入dev | Capstone长程组织配合Pi原生生态，统一机制待实施 | dev | 先推进共同基座Task 1；分别验收企业研究与分析、电网分析与决策，再验证组合任务 | 已保留专业链路与原生资源 | PR #31合入db167184；统一循环、无模型v2协议和新工作台仍待实现 | CI38865540607双平台通过；local-dev规范重建与同源检查通过，不代表新设计完成 |
| commands | 统一输入命令与快捷操作 | 3 | 待设计，已有局部原型 | Capstone 前端统一操作入口：会话、模型、执行、结果及技能操作 | — | 盘点现有前端操作；设计共享命令目录、参数、可用状态和键盘交互，再建立增强分支 | 当前前端按钮与 Pi 分支命令原型 | 跨运行模式的快捷入口；中文检索与命令发现；上下文和权限检查；草稿保持与明确反馈 | 独立开发包；Pi 分支三个命令只是复用来源；新分支未建立，未部署 |
| case | 独立 Case 模块产品接入 | 3 | 待范围设计 | 独立案例执行、状态查看与恢复入口 | — | 核对已有 Case 服务与当前对话入口，确定独立模块范围 | 已有独立 Case 执行基础 | 将 Case 作为完整模块接入产品；明确与普通对话的关系 | 底层已有能力，当前对话入口尚未组装完整模块；不视为从零开发 |
| context | 长任务存储优化（历史归档） | 3 | 已归档，适用性未确认 | 9 月 5 日 OP-13 分段写入/恢复实验；保留未提交代码 | archive/context-segment-storage-20261011 | 当前不开发；真实场景证明需要后，基于最新 main 重新设计 | 历史性能实验 | 文件式 Kernel 日志仍有全量重写开销；当前 Thread 历史采用 PostgreSQL，不能直接套用旧问题 | 原计划 DEFERRED；已归档并移出活动与待推进区；未合入或部署 |
| wake | 启动与恢复体验 | 3 | 初步诊断，待复现信息 | 减少启动等待和对话中断，改善恢复体验 | improve/issue-4-active-recovery | 核对切后台或锁屏触发，再确定优化方案 | 当前线上体验（规划对比） | 减少启动等待；改善对话中途恢复 | Issue #4 已询问触发条件；4项生命周期检查与本地热态测量通过，不代表云端根因或修复 |
| research | 围绕研究模型的自主推演 | 3 | 起点及依赖已适配，R1待实现 | 研究模型＋可组合工作流＋自主推演；领域知识与结论验证支撑 | feat/research-model | R1契约与生命周期；R4按真实能力缺口盘点；R2/R3随后推进 | dev恢复基线6ff7094 | 2b0b0a5更新设计/计划；使用既有Thread/Attempt/模型身份与Authority接纳，不依赖撤回链路 | 精确Git祖先6ff7094；文档审查及本工作区准备/doctor通过；R1无代码；R0bf678f2原始证据保留，未部署 |

全景文件：[PROJECT-OVERVIEW.html](PROJECT-OVERVIEW.html)。更新功能包、合并或部署台账后运行 `python3 tools/render_project_overview.py`，同步更新这一个 HTML；打开 HTML 不需要构建、联网或额外文件。生成器读取本表、环境台账、Git 来源和本地公开版本信息；不能把计划推断为已交付。

## 开发包明细

详情用于核对开发与验收，不重复树上摘要。各项区分已有代码、验收缺口和待设计工作；下列验收要求不是通过声明。实现依据见[功能核对](DEPLOYMENT-FUNCTION-SCOPE.md)、[资源验收](../reviews/2026-10-09-business-workspace-resources-verification.md)及[回答闭环草案](../superpowers/specs/2026-10-10-shared-intent-and-goal-answer-design.md)。新设计仍需收口。

| 功能包 | 开发项 | 当前状态 | 已有实现或依据 | 剩余工作与依赖 | 验收要求 |
| --- | --- | --- | --- | --- | --- |
| dev-trial | 无源码Compose与镜像交付 | PR #22合入7832134，公开包安装验收通过 | 受限Provider；同源静态App；四类镜像；每实例0600私有状态；精确Git和资产；实际平台/同镜像/App源码/就绪检查；安装结束运维提示 | 用户自己的LLM Key、业务样例及Windows/WSL2仍待实际验证；停止保留数据 | 一条命令安装并启动至~/capstone；App默认19173，可改.env；API/App无Provider Key；三backend同镜像；停止保留数据；全部镜像来源一致 |
| dev-trial | AMD64离线安装与OpenAI兼容内网配置 | e2更新包已交付；旧7c已撤回、不可交付 | e2归档检查、单次新安装及ready通过；runtime同28020复用限定handoff/dispatch实测，不重跑全量测试或Provider | 公开投影及AC第3时段一致性两项开放；PR #28已正常合入f300且双CI通过；local-dev规范重建与真实身份核验通过 | Apple ARM宿主AMD64模拟；原7c只保留撤回证据，唯一当前交付为e2；四部署及19173未变 |
| autonomous | PyPSA派生结果投影及saved-dispatch AC输入 | c638候选限定实测通过，PR #28 ready、CI待完成 | 可选中性revision resolver保留应用lineage与Pack exact equality；PF用p_set恢复Generator调度，不支持的组件显式拒绝；5个operations投影完成并绑定正确修订/证据；三轮+AC-only第4轮验证通过 | PR #28已正常合入f300且双CI通过，local-dev规范重建/真实身份核验通过；回答+5应+7.5仍待跟进，source-modeling投影未实现 | 验证只覆盖所述operations及AC路径；不重建e2包，不称所有PyPSA/回答通过，不更新四部署或19173 |
| dev-trial | user-local版本管理与共享数据升级 | PR #23合入b7e68dd，最终双架构验收和公开安装通过 | Git选择、版本管理、单活跃项目、共享数据及停止前检查；原7832134项目/卷/私有配置/安装记录保留；旧新报告证据可读可回放，兼容回退独立验证 | 用户自有LLM与业务样例；格式变化须开发提供已验证迁移 | 不兼容或缺少声明不能停止旧服务；不创建空卷绕过；原用户数据保留；用户不用处理数据库迁移 |
| autonomous | 研究状态、笔记与持久回执 | 已实现，离线重放与接线已验证 | 8d636a4最小研究记录；7df7180实际受管Pi请求、压缩恢复与持久回执验证；a3895a5研究记录及388fa89参数追溯；版本冲突、重复更新及来源准入保留 | 完整多轮研究、反例依赖修订与共享存储恢复尚未整体验收 | 后续实际请求读到最新有界研究视图；研究判断不冒充Authority事实；迟到或冲突更新被拒绝；恢复不丢历史 |
| autonomous | 单Pi主循环与复杂指令执行 | 已实现，真实三链执行完成；业务解释未通过 | 复用公开工具、指南、Thread/Attempt与结果准入；OPF、N−1、双停运原句均已有真实调用和正式回复；8bf9ada撤除附加回答生成 | N−1电压判定、方案约束与引用错误；孤岛短路/电源/稳定性解释缺口仍开放 | 单条原始指令可独立完成；失败、能力不足和部分成功按真实回执表达；不得使用样例专用路由或固定答案 |
| autonomous | 失败后的部分成果与来源边界 | 基础交付已实现；完整恢复未验收 | 3f2f111保留受限回答；失败观察与已准入结果、证据保留；c9387ee短路参数及失败诊断；6c9f9c1区分计算来源与物理状态 | Provider不可用时的完整应用保障、跨存储恢复及全部失败组合仍待验收 | 后续失败不清空已有有效成果；null不等同失电；没有执行或准入的计算不成为事实 |
| autonomous | 正式回答、计算结果与推演证据 | 已实现，实际入口可读 | dab1dbe证据展示与分组结果；参数、失败项、模型/场景版本及原始诊断可读；fe67bdc结果面板互斥并复用Markdown；29daa7d单条原因与诊断入口 | 结论到结果、证据和调用的全覆盖关联及失败结果完整恢复仍待验收 | 当前运行来源准确；结果和失败记录可追溯；历史浏览不切换当前模型；展示完整不等于科学结论正确 |
| autonomous | 执行过程、动作目的与真实计时 | 已实现，局部实际链路已验证 | 980b854原生轮次计时与GRID归属；43f1e73动作目的进入工具记录；ef6ae84目标/步骤分离与紧凑耗时；完成与用户展开状态保留 | 准备、准入及收尾阶段计时未全部覆盖；旧历史不回填虚构目的或时长 | 任务步骤与工具调用分开；实际开始/结束及归属可核对；用户展开选择在刷新与新增事件后保留 |
| autonomous | 模型能力准备、复用与内存调度 | 已实现并部署；完整生命周期未收口 | 03b8d96按内存压力回收；73b6c07打开模型时准备；f09a0c8首次默认绑定与切换；6d229e0复用能力目录并合并概况读取 | 回收后快速恢复、容器文件系统丢失后的共享恢复及整体生命周期仍待验证 | 执行中资源受保护；当前修订/授权一致；关闭资源不删除历史、结果和证据；复用不引入其他Thread的模型状态 |
| autonomous | 工作上下文重置与模型控制 | 已实现，有隔离续接验证 | 780fd70重置恢复打开基准、保留旧回答并绑定新研究；真实重连、历史读取和后续AC通过；f907023完整模型控制回归 | 部署后全部模型开关、重置失败恢复及原研究连续性仍待验收 | 运行中拒绝重置；对象/研究身份分开；旧记录保留；失败后恢复原上下文，不删除用户数据 |
| autonomous | 历史任务追问 | 实验接线有验证，当前Composer入口已撤除 | 889b076及e5369e2验证历史任务绑定；只读历史压缩后读取不重算；2a5a51e移除遗留追问绑定入口 | 必要追问按当前统一主线另验；不将旧选择器算作当前可用功能 | 指令解释引用正确原任务与版本；历史文字不冒充新计算证据；条件改变后重新执行并准入 |
| autonomous | Authority数据查询与完整结果字段 | 已实现并实测，OPF数据输出有验证 | 73bef5b及a4c0ca5计算回执公开精确可查询字段；本地原Thread OPF26.052秒，35线路/39母线保留，查询无字段失败或重复describe | N−1对象引用、输入膨胀与科学因果解释未解决 | 所有数值来自当前准入结果；明确表、列、单位及覆盖；不把不同场景或模型修订混用 |
| autonomous | 有来源的电网场景与图层 | 已实现并部署，局部真实派生检查通过 | bf7a309场景/连通分量；aff8319断开开关、母线联络、孤岛线路着色与关注区域；9dca4ab强调样式；94349e6跟随已完成任务并保留短路不可用状态 | 节点边际价格图层与三复杂样本全图例验收未完成；孤岛物理解释仍有缺陷 | 场景切换绑定实际结果与模型修订；颜色/标记只表达已记录状态；不凭无数值推断设备失电 |
| autonomous | 对话恢复与新建性能 | 修复已部署，发布身份核对待完成 | 20f8a0e/bfb2e83兼容空断开列表及JSON字段顺序；原Thread在线恢复；bd2a200基础图缓存；07d618a先发送201再预热；云端POST0.447–0.698秒，点击新建2.085–2.718秒 | 云端模型准备细分日志未取得；后台准备与首任务复用的部署身份核对尚未闭合 | 新建不等待模型准备；首次任务等待并只准备一次；诊断失败不损坏已保存操作；历史、端口和数据保留 |
| autonomous | 部署、回放与整体科学验收 | 候选及PR门禁通过，已合入dev；科学未验收 | 2b6ae7b四角色成功，三后端身份与本地529文件验收一致；三用例九轮、报告证据回放和旧Thread恢复通过；PR18合并faa6af9；cloud-dev保留24d9a32 | 两个demo正式发布同一dev合并提交、独立demo标签；后续三复杂原句与连续变体内容回归 | 实现/验证/合入/部署分开；通过所需发布检查后才建标签；终态完成不能替代科学核验 |
| foundation | 历史连续阅读 | 已合入并在local-dev验收 | 跨事件页合并完整问答；旧消息锚点、返回最新与翻页失败状态 | PR #6已合入；demo按用户发布计划另行验收 | 少量问答但大量工具事件时不丢早期回答；翻页保持阅读位置；原有消息及事件不变 |
| foundation | 执行租约 | 已合入并在local-dev验收 | 模型目录准备先于领取租约；数据库按实际时钟起租 | 基础包已集成；不归因为用户所有卡顿的根因 | 准备时间超过短租约仍能执行；续租与取消正常；冷启动失败须独立诊断 |
| foundation | 四环境与源码身份 | 双本地生效 | local-dev/local-demo 名称及源码身份已显示 | 云端仍为 ed2524f；按发布流程带入 cloud-dev/cloud-demo | 可见环境、产品版本及来源提交；API/worker 来源一致；名称不能掩盖不同部署提交 |
| foundation | 小石反馈与修复流程 | 已实现并合入 | 命令触发、独立App身份、中文回复、隔离修复与PR管理 | PR #6已合入；保持命令触发，不启用无人值守 | 用户短句及截图可登记；回复说明实际处理结果或必要缺失信息；不能冒充维护者回复 |
| foundation | CI 与合并收口 | 已合入，开发入口验收通过 | cfd6ad6 两平台检查与独立审查通过；合并 c3b78bc；local-dev 注册用例/报告/证据回放通过 | demo 发布随回答增强计划另行验收，不跟随日常开发 | 后续改动通过对应检查；按范围选择门禁，不重复无关全套验证；合并与部署状态分别记录 |
| answers | 任务语义理解 | 已实现，本地技术验收通过 | 2473e48包含typed v2、无工具识别、领域解析和目标准入；336项实际PG及完整本地门禁通过 | PR #9已集成并登记B2技术基线；人工问答验收单列 | 区分介绍、单场景分析、全量比较及排序；歧义时询问必要信息；专业任务不靠关键词分流 |
| answers | 执行范围与覆盖核对 | 已实现，本地技术验收通过 | 2473e48的Pack证明绑定目标、对象、指标、场景及当前结果；缺口不伪装完成；未认证兼容结果显式保留边界 | PR #9已集成；发电设备全量N-1计算能力仍需独立补齐 | 完成单场景不冒充完成全量N−1；基态结果不替代故障或负荷变化结果；能准确报告未计算范围 |
| answers | 运行过程窗口 | 完整候选2473e48已生效 | 9px描述、8px元数据、4.5px行距；执行中1条动作短窗32px与完整窗160px切换；完成折叠；380项App检查与实际浏览器通过 | local-dev实际工作台已显示2473e48；人工体验验收继续保留 | 不持续展开；完整历史可滚动；完成后为次要信息 |
| answers | 结果引用与诊断 | 旧候选有防护，待复用 | 结果/证据保留、类型检查、引用缺失和非收敛等诊断已有旧实现 | 按最新契约重整，分清计算、引用查询、证据及答案阶段；不原样合入归档代码 | 后续查询失败不抹掉已完成计算；只给有证据的原因；未知原因明确未知；必需持久化失败仍按合同处理 |
| answers | 正式回答与尺度 | 真实业务样本失败 | 2473e48真实澄清和普通概况失败已留痕；修复通过48项focused、674项App后端、28项Pack和28项回答E2E；概况读取并冻结注册模型元数据，未部署 | 整体样本含四类IEEE39问题和连续对话；更新专项覆盖字段校验、混合目标、证据和运行窗；脚本筛查不能替代真实Provider与语义复核 | line7分析直接指出已证实的重载线路；负荷变化只用该场景结果；概览先给简明全貌；不能用基态表或状态文案代替回答 |
| answers | 公共链路验收 | 新增强未验收 | 用户电网问题暴露共同缺口；旧本地人工试用未通过 | 覆盖能力不足、工具失败、部分场景成功、结果查询失败与完整成功；检查受影响 Domain Pack | 同一机制在多个指令和受影响领域生效；local-dev 阶段验收，合入后按计划在 local-demo 产品验收；旧候选不视为通过 |
| pi | 普通/专业路由与共享上下文 | 实验代码保留 | 语义路由、有限历史、选中对象与版本快照已有实现 | 核对与新任务理解契约的关系，避免两套冲突的语义判定 | 普通任务无业务 Authority 权限；混合任务只授予相关目标上下文；对象切换和重试保持正确版本 |
| pi | 三种执行角色 | 离线组合已验证，未发布 | Harness、委派 Pi 与直接 Pi 有独立路径；原生工具在私有任务空间运行 | 明确默认入口、依赖与开关；验证真实模型行为和部署运行路径 | 角色切换保持草稿及工作区；原生 Pi 不接触主机凭据或 Authority 对象；通用输出不冒充业务证据 |
| pi | 原生 skills/MCP | 真实工具调用已验证 | 已加载真实技能正文及 MCP；示例网络调用不等于当前业务模型分析 | 核对技能安装来源、资源版本、可用状态和当前模型输入 | 能区分示例与当前模型；记录使用的技能与版本；未安装或不兼容时有明确反馈；取消释放资源 |
| pi | 专业结构检查 | 选中模型 Authority 路径已验证 | Harness 专业适配经注册 Authority 执行结构诊断并保存证据 | 明确复用范围；泛化专业适配需单独设计，不能绕过注册能力 | 专业结果绑定当前模型与运行证据；禁止使用通用观察替代数值或拓扑事实 |
| pi | 输入命令原型 | 已接入实验输入框 | /skills 选择技能；/skill:<name> 指定技能任务；/context 选择上下文材料 | 将可复用部分交给统一前端命令包设计；保留跨角色兼容规则 | 未知命令能选择按原文发送；不兼容技能不被静默丢弃；打开面板不创建虚假消息；草稿保留 |
| pi | 配置间效果比较 | 产品效果未验收 | 现有受控模型响应检查证明组成和工具执行，不证明真实回答质量 | 固定共同业务任务、输入及评价方式，比较 Pi、技能 Pi 与 Harness 配置 | 分别记录答案质量、证据有效性、耗时和失败情况；不把受控夹具通过算作真实模型效果通过 |
| commands | 全前端操作清单 | 待设计 | 有会话、模型、运行、结果等按钮；Pi 已有局部命令原型 | 逐项盘点入口及服务合同，确定首版必要操作和命名，不一次加入所有设想 | 用户能发现常用操作；不同模式下入口和结果一致；已有按钮仍可使用 |
| commands | 共享命令目录 | 建议方向，未实现 | 10-09 资源设计有可用状态及操作目录思路 | 为操作定义标识、参数、适用模式、可用条件及反馈；按钮/斜杠/快捷键复用 | 相同操作不因入口不同而行为不同；不可用时说明具体原因；服务端再次校验权限及输入 |
| commands | 输入交互 | 待设计 | /skills、/skill:<name>、/context 可作为交互原型 | 设计中文检索、参数提示、键盘选择、退出与移动端；确定斜杠与普通文本歧义处理 | 不误执行普通文字；取消后草稿完整；参数错误可修正；键盘和触摸均能完成必要操作 |
| commands | 执行与业务边界 | 待设计 | 界面动作和注册业务操作已有各自服务入口 | 分清纯界面动作、真实任务与需确认的状态改变；接入现有运行/取消合同 | 界面操作不调用模型或伪造对话；业务执行不新增任意 shell/Authority 访问；失败反馈能定位到操作 |
| pi | 完整业务上下文与当前模型数据 | 后续研发待实现实现 | 现有公开上下文只有身份、版本及有限历史；没有完整网络数据投影 | 在 Pi 分支确定任务所需表、字段及大小限制，由 Domain Pack/Authority 提供显式投影；补齐真实业务输入 | 数据属于当前选中对象和确定版本；示例数据不得替代当前模型；不传原始 DataFrame 或网络对象；记录实际使用的数据 |
| pi | 数据共享、资料与授权交接 | 后续研发待实现 | 有受控材料契约验证；不表示所有业务资料已可读取 | 在 Pi 分支明确可用资料、应用授权、跨领域类型交接和资源有效期 | 无授权不可读；对象版本变化可识别；资料不足能准确说明缺口；通用 Pi 观察不冒充 Authority 证据 |
| case | 独立模块范围 | 已有执行基础，产品接入待设计 | 独立 Case 执行能力已有；当前默认对话入口未组装完整模块 | 确定创建、执行、状态、结果和恢复入口，与普通 Thread 明确分工 | 模块可独立操作；不靠重复发送对话模拟 Case；旧 Case 与普通对话保持兼容 |
| case | 执行与恢复接入 | 待范围确认 | 现有 Case/Harness 设计包含顺序执行及恢复合同 | 核对现用服务状态、取消/重试、结果及证据展示，列出实际缺口后实施 | 单项失败有准确状态；重试不重复提交；恢复保持步骤、来源与证据，不把未执行项标为完成 |
| wake | 启动与中途恢复诊断 | 初步诊断，ai:needs-info | 隐藏页面恢复路径符合已接受设计；截图来源版本未知，本地热态准备检查约8–24ms不能说明云端冷启动 | 等待切后台/锁屏触发信息，关联实际尝试与组件时序；不修改线上睡眠配置 | 有可复现的分阶段时序；明确等待在哪里；不凭总耗时断言网络、休眠或模型错误 |
| wake | 睡眠策略与恢复体验 | 待诊断后设计 | 已有恢复提示和历史保留路径；体验仍被用户反馈 | 比较休眠成本和等待；确定活跃对话/执行的保活条件及就绪提示 | 执行中不被空闲策略打断；输入与历史不丢；恢复状态准确；前后等待数据可比较，不编造优化指标 |
| research | 研究模型与自主推演 | R0通过；R1–R5计划 | bf678f2已验证执行与证据基础；研究模型尚未实现 | R1契约/生命周期 → R2多轮研究 → R3自主选择与修订 → R5应用验收；R4领域方法与计算缺口并行推进 | IEEE39四指令及多轮变体；版本失效、方案分支、反例修订、证据重放；发电N1仍有计算与约束缺口 |

上述答案闭环实现与旧运行窗口规格为历史盘点；现行范围以回退/选择性补回行及dev6ff7094节点为准。

## 全景关键提交

主视图按功能交付区间合并关键提交；精确节点用作来源与部署绑定。完整功能盘点见 [线上到本地的功能范围核对](DEPLOYMENT-FUNCTION-SCOPE.md)。归档只放底部详情。

| ID | 提交 | 通道 | 名称 | 状态 | 功能增量 | 功能包 |
| --- | --- | --- | --- | --- | --- | --- |
| dev-head | dev | main | dev · 当前研发位置 | 当前Git HEAD，验收范围见对应里程碑 | 动态绑定本地dev实际提交并连接真实祖先；不将分支HEAD当作部署或业务验收。[当前状态](CURRENT-STATE.md) | shared-agent |
| workspace-integration | fix/workspace-reading-type | feature | 工作空间 · 集成候选 | PR #56草稿；CI与完整回归待完成 | 已提交已验收界面及运行依赖；同步dev并保留未交付方案，不更新cloud/demo。[集成](https://github.com/uukuguy/capstone/pull/56) | model-decision |
| workspace-app-source | c34b4780 | feature | 工作空间 · 已验证App来源 | 942App测试、构建及浏览器通过；待集成 | 稳定导航、会话缓存和阅读状态恢复已提交；保留实际App源码身份。[验证](../reviews/2026-10-25-left-navigation.md) | model-decision |
| workspace-outputs | 15980389 | feature | 共享工作空间 · 稳定导航、阅读状态与分层缓存 | 本地修正已验证；命名工作空间待实现；未集成dev | 内存默认10，可选10/20/50；按切换次数和最后打开时间保留，释放不改变归档状态。补读置顶偏好，收起展开保留列表；改名Esc保留左栏。942App/构建/doctor及实页通过；规范重建e18d8e7d33f2、ready及清理通过。原阅读状态与零完整快照复验保留。[验证](../reviews/2026-10-25-left-navigation.md) | model-decision |
| pypsa-demand-fix | 4120e57b | feature | 专业试用修复 · 结果解释与会话恢复 | local-dev同源ready；PR #54检查中；IEEE39发电机归属解释缺陷仍开放 | effc9ccd修正有效时序需求；e0c8d246修复旧会话准备；6415a57d补充平衡电源解释；4120e57b区分元件名称与表索引，无具体样例硬编码 | model-decision |
| native-conversation | c9e57152 | feature | 共同基座 · 无模型对话执行 | 离线验证通过；未合入或部署 | 同一账本、租约和Harness承接原生对话；长文本收尾修复及两轮RPC原文恢复通过，前端接入另行验收 | shared-agent |
| shared-workspace | 00a8cd85 | feature | 共同工作台 · 成熟对话与专业执行适配 | local-dev已验证；PR #53检查中 | 6f1c3412恢复定稿原型与成熟对话，00a8cd85兼容混合会话列表；570项App、88项真实PG及历史结果拓扑检查通过，无模型和通用成果仍待完成。[验证记录](../reviews/2026-10-17-shared-dialogue-adaptation.md) | model-decision |
| work-ledger-dev | d86cc4efb83780917daa536c66cf3a43fe0a0851 | main | dev · Work账本与共享对话入口集成 | PR #48双平台通过，已合入 | 无模型v2 Work保存、幂等恢复及共享对话前端；合并树同受检ed0e2e19；生产执行绑定与持续推演待实施。[切片报告](../reviews/2026-10-16-thread-work-ledger.md) | shared-agent |
| work-ledger | e58ef9a4 | feature | 共同基座 · Work账本与任务入口 | PR #48双平台通过，已合入dev | v2无模型会话；Work保存、对象CAS及幂等恢复；旧专业历史只读；未启动持续执行。[切片报告](../reviews/2026-10-16-thread-work-ledger.md) | shared-agent |
| pack-selection-dev | 9eb84a341a148572cfbfc49db483e8e184dad522 | main | dev · Pack按需装配集成 | PR #46双平台通过，已合入 | native/authority声明与按需准备合入；合并树与受检cb08ef92一致；生产存储、v2及持续执行待接入。[切片报告](../reviews/2026-10-16-application-pack-selection.md) | shared-agent |
| pack-selection | 20226bf0 | feature | 共同基座 · Pack按需准备 | PR #46已合入，local-dev同源通过 | native/authority统一声明；选择准备保留Profile授权；Pi资源回执与旧专业边界；cb08ef92将共同基座CI限定依赖范围及15分钟步骤。[切片报告](../reviews/2026-10-16-application-pack-selection.md) | shared-agent |
| thread-version-dev | 32f18d2444fee2d1ab0cb9bd8d3157c8854f7526 | main | dev · 协议协商与恢复集成 | PR #44双平台通过，已合入 | v1服务/客户端协商及恢复提示合入；合并树与受检1a695af4一致；继续Profile/v2及无模型入口。[切片报告](../reviews/2026-10-16-thread-version-negotiation.md) | shared-agent |
| thread-version | a2efb791ff80ce8306ab6cc36393e88af5c8bcc5 | feature | 共同基座 · 协议协商与恢复 | PR #44已合入，local-dev同源通过 | 2d3f86c6实现v1 JSON/SSE协商，a2efb791补正升级状态；旧服务兼容、历史与草稿保留；v2及无模型入口待实施。[切片报告](../reviews/2026-10-16-thread-version-negotiation.md) | shared-agent |
| work-identity-control | 977601f9f4c3d316174e9d632fcc72a638b0f8fa | main | dev · Work基座三线同步 | PR #42双平台文档检查通过，已合入 | Work研究身份里程碑与CI验收记录对齐；三条研发分支快进同源，生产Profile/v2前端继续实施。[切片报告](../reviews/2026-10-16-work-research-identity.md) | shared-agent |
| offline-e2-delivery | e2eaee2403cb6d780b3f7564da86e0d083890673 | feature | 已交付离线包 · e2eaee2 | 已交付；最小安装ready通过，原归档未升级为f300 | 已交付linux/amd64归档1368607944字节；单次新安装/ready及同源身份通过，API与双worker同e2镜像，六角色AMD64，正常停止保留数据；runtime packages同28020，复用限定handoff/dispatch实测；公开投影与AC第3时段一致性两项开放，本包未重跑全量测试或Provider。历史：7c曾交付后撤回、不可交付，证据位于capstone-withdrawn-7c19766且原SHA保留；6064103仅为分支文档收据，不是交付源码。[包README](../../runs/user-local-offline/capstone-delivery-e2eaee2/README.md) [下载归档](../../runs/user-local-offline/capstone-delivery-e2eaee2/capstone-user-local-offline-e2eaee2-linux-amd64.tar.gz) [SHA256](../../runs/user-local-offline/capstone-delivery-e2eaee2/capstone-user-local-offline-e2eaee2-linux-amd64.tar.gz.sha256) [限定验证报告](../reviews/2026-10-15-pypsa-handoff-verification.md) | dev-trial |
| dev-current | f209fb18d7abb122b689e1b1a52c54fa13bf5371 | main | dev · 修复验收记录合并 | PR #29合入，双平台文档检查通过 | 验收文档与控制工具合入，packages与f300无差异；App5173实读f209fb1、dirty=false；后端保持f300验证来源与6c616058镜像；e2原包和其他环境不变。[限定验证报告](../reviews/2026-10-15-pypsa-runtime-followup-verification.md) | autonomous |
| offline-merge | f300d1f375ef20af005840a60af47b5e33ea62e8 | main | dev · PyPSA运行修复合并基线 | PR #28合入，双平台与local-dev重建核验通过 | c638真实区域3轮+AC-only第4轮通过，5operations投影正确；CI38723131332全过，root dev已快进且packages一致；local-dev ready/API双worker同镜像，各1060文件SHA256同f300，App f300无dirty；源码label仍development；e2归档未升级，算术及source建模投影边界保留 | autonomous |
| user-local | b7e68dd | main | dev · user-local版本管理合并基线 | 已合入，双架构验收及公开安装通过 | Git选择与capstone.sh共享数据管理；停止前兼容/配置检查；最终源码匿名拉取、旧数据升级/回放/回退、重启和浏览器通过；user-local-b7e68dd已公开 | dev-trial |
| dev-trial | 7832134 | main | dev · 用户试用交付合并基线 | 已合入，公开试用包已验证 | 无源码Compose、受限Provider、同源App、私有实例及精确源码/镜像检查；最终双架构各三案例九轮/回放/重启/浏览器、匿名拉取与公开安装入口通过；标签dev-trial-20261015-7832134 | dev-trial |
| cloud | ed2524f | main | 线上运行能力 | 已发布 | 电网静态分析、智能体对话、工作台与结果证据；当前用户试用起点 | live |
| baseline | a076b04 | main | 运行基线重整与本地隔离 | 已验收 | ed2524f → a076b04：实验 Pi/skills 与未验收回答实现移出运行代码；修正模型拓扑/历史接口；建立隔离 local-demo | main |
| main | cf72393bd6377d1de11d02a93728cdaa746a75d4 | release | main · 对话应用阶段发布 | PR #30已合入，完整release通过 | 用户确认f209fb1范围，含已验证PyPSA小修复；合并树与f209完全一致；CI38861900687双平台成功。实际e2交付包与用户安装保持原版，未进行新部署。[收口验证](../reviews/2026-10-16-main-dev-convergence-verification.md) | main |
| dev-business-base | 6ff7094 | main | dev · 恢复后开发基线 | 已集成，双平台通过 | PR #14候选bc08169两平台通过；恢复c3业务执行并保留独立轻量路由；三动作9px短窗与160px滚动；普通轻量路径与最终消息隔离；local-dev506项三角色同源；两实施分支接入此基线；已知业务缺陷及一次普通误路由保留，未作整体验收 | main |
| dev | faa6af9 | main | dev · 自主智能体合并基线 | PR #18已合入faa6af9 | 双平台PR门禁通过；统一研究/执行/结果证据、模型资源、场景图层和对话性能合入；正式两个demo按同一合并提交收口；旧控制文档已保留恢复来源 | autonomous |
| work-identity-dev | 85b6706f75994ff509cf73cf3d0003c385ab1eb4 | main | dev · Work研究身份集成 | PR #41双平台通过，已合入 | Work研究身份组件与开发CI分层合入；合并树与受检08556cc2一致；继续生产Profile/v2及前端接入。[切片报告](../reviews/2026-10-16-work-research-identity.md) | shared-agent |
| work-identity | 055a335f | feature | 共同基座 · Work研究身份 | PR #41已合入，local-dev同源验证通过 | 无模型研究、跨Attempt/Run/模型变化恢复、目标隔离；旧模型历史不迁移不删除；生产Claim/Profile/v2/前端仍未接入。[切片报告](../reviews/2026-10-16-work-research-identity.md) | shared-agent |
| dev-control | d4600ddc2e593ea3e0020b1b4685913c189ecd6a | main | dev · 研发控制基线 | PR #39双平台通过，已合入 | 三线HEAD显式展示，历史控制与产品里程碑区分；研发控制规则已固化到AGENTS.md；无运行代码或部署变更。 | shared-agent |
| shared-foundation-dev | d8fe6e2738639161525a66bce7a8f0a9588e2872 | main | dev · 共同基座执行接缝集成 | PR #36双平台通过，已合入 | 合并树与受检711f06a8一致；共同执行接缝及已有基线验收完成；Task 2身份/Profile及前端最小入口待实施。[基线报告](../reviews/2026-10-16-shared-execution-baseline.md) | shared-agent |
| pi | abf2f797c98f953a402aa25597018d6d5dfea0af | feature | 企业执行 · 已合入来源 | PR #31双平台通过并合入dev | 原生资源和专业资产保留；资源摘要及超时分类已修复；local-dev同源核验通过。统一循环和新工作台仍待实现。[收口验证](../reviews/2026-10-16-main-dev-convergence-verification.md) | pi |
| enterprise-dev | db16718445fb33ea242310076dd068b90b1996a6 | main | dev · 企业自主执行研发主线 | PR #31已合入，双平台通过 | 合并树与受检abf2f797一致；长期Pi分支已关闭，工作树与数据保留；后续按统一执行计划推进。[收口验证](../reviews/2026-10-16-main-dev-convergence-verification.md) | pi |
| research | feat/research-model | feature | Research Model · 实施分支 | 起点与依赖已适配，R1未实现 | 开发起点6ff7094；2b0b0a5适配现有对话/模型身份与证据接纳；独立审查、源码等价与doctor通过；不依赖撤回的编译/覆盖/预热；R0bf678f2保留历史参考；R1尚无代码，未部署 | research |
| autonomous-trial | 24d9a32 | feature | 自主智能体 · 试用部署点 | local-dev与cloud-dev基本试用通过 | 固定部署来源24d9a32；三任务链路终态已保存；业务结论尚有缺陷；后续源码变化未部署 | autonomous |
| topology-display | df69cda | feature | 拓扑显示修复 | local-dev前端已验证 | 小跨度坐标全图适配；放大上限与符号尺寸修正；41项检查及类型通过；真实179母线浏览器验证；后端与cloud-dev仍24d9a32 | autonomous |
| research-reset | 780fd70 | feature | 工作上下文重置 | 隔离界面与续接验证通过 | 复用模型重开事务，恢复打开基准、隔离新研究并保留历史；运行中拒绝；41项后端、71项App、21项真实PG及类型通过；真实重置、重连、历史读取和19.941秒后续AC通过；用户部署未更新 | autonomous |
| task-followup | 889b076 | feature | 任务追问绑定 | 历史执行解释链通过 | 明确引用同一Thread已结束任务；原模型版本保留，历史文字不冒充计算证据；重试保留引用；22项真实PG、141项App、74项后端及类型通过；真实选择/刷新/取消/390px验证通过；普通解释上下文缺口已修；历史只读投影与存储筛选43项及真实PG通过；原任务2467条缩至30条公开执行记录，历史保留；双路径只读工具已接入，69项及绑定、64项JS及类型通过；真实追问29秒读取成功且无仿真，解释未全证实；c886真实追问20.477秒通过，1次历史读取、无新仿真；重置前原上下文保留，回复与中文过程手机展示通过；原任务科学解释未全验收；用户部署未更新 | autonomous |
| integration-check | 053fa4e | feature | 自主智能体 · 整合检查 | 端到端及离线验证通过 | 39项grid端到端与3项Worker通过；7项离线、10项核心、8项完整脚本通过；能力矩阵24/24；保护摘要对齐已提交Authority改动；真实业务解释缺陷仍在；未合入或更新部署 | autonomous |
| autonomous-demo-repair | bfb2e83 | feature | 自主智能体 · demo恢复修订 | 云端已验证 | 原Thread恢复；只更新前端，后端94349e6；标签demo-20261014-0607-bfb2e83；后续性能候选尚未部署 | autonomous |
| autonomous-demo-first | 94349e6 | feature | 自主智能体 · 首次demo发布 | 基本发布检查通过，科学解释未验收 | 统一研究循环、任务执行与结果证据试用上线；三注册用例九轮及报告证据回放通过；旧Thread恢复缺陷由后续bfb2e83修复；标签demo-20261014-0552-94349e6 | autonomous |
| dialog-async-candidate | 07d618a | feature | 自主智能体 · 新建等待修复 | 86项相关检查及类型通过；local-dev同源ready | 创建响应后预热；本地POST0.145/0.025秒；真实阶段计时，demo已运行但验收未完成 | autonomous |
| autonomous | 2b6ae7b | feature | 自主智能体 · 发布身份与合并门禁 | 候选检查通过；已随PR #18合入dev | 安全身份回执进入启动日志；泛化来源文案断言；流式报告采用确定时钟验证；该候选已验证，正式发布采用dev合并faa6af9 | autonomous |
| dialog-demo-baseline | bd2a200 | feature | 对话启动 · 已验收基线 | demo已验收 | 缓存基础图与线程池创建；新建7.4/8.1秒，仍等待模型预热；保留回退来源 | autonomous |

| interaction-update | 687afbf | feature | 对话展示 · 紧凑结果与指令定位 | local-dev局部界面验证通过 | 内嵌有界结果、顶部表格切换、失败记录、滚动/靠右指令标记、悬浮定位、隐藏未完整追问入口；77项及类型、实页不跳位/不溢出通过；固定5173/8767，同镜像5f4409aeb0d9；整体目标未验收 | autonomous |
| node-timing | a3345ea | feature | 执行链路 · 节点耗时记录 | 诊断实测完成 | 已定位逐片段同步保存阻塞；原应用处理36.206秒、队列积压31.226秒；不把全部工具外时间当作模型推理 | autonomous |
| stream-batch | de543f2 | feature | 执行链路 · 保留片段的批存 | 局部性能实测通过 | 复用OPF25.759秒；新求解32.592秒，analysis.run1.456秒；保留全部片段，积压低于0.07秒；概况32.725秒仍待优化 | autonomous |
| execution-display | 42828fe | feature | 执行过程 · 真实计数 | local-dev已重建 | 工具调用与任务步骤分开计数，定位保留内联结果；138项及类型通过；尚未补齐原子动作全过程 | autonomous |
| execution-verified | 980b854 | feature | 执行过程 · 原生计时实测 | local-dev局部链路通过 | 真实OPF31.620秒，7轮全部结束并记录耗时，9项GRID有归属；默认最后展开、点击状态保留；动作目的待接入，准备与收尾未覆盖 | autonomous |

| context-memory | 03b8d96 | feature | 模型能力上下文 · 内存调度 | 局部检查通过，未部署 | 新对话共用worker缓存；容器/主机内存不足时回收空闲资源，保护执行中与当前复用资源；取消默认60秒清除和4个名额；92项检查通过；打开时准备与快速恢复待完成 | autonomous |
| context-deployed | 73b6c07 | feature | 执行链路 · 打开时准备 | local-dev已重建；切换修正重建中 | 同镜像cffcc357bd57；新对话打开8.487秒，首指令上下文获取0.000017秒；概况仍25.462秒；首次打开默认绑定f09a0c8已提交，25项真实PG通过；回收后快速恢复待完成 | autonomous |

| context-defaults | f09a0c8 | feature | 模型能力 · 打开与切换 | local-dev同源重建及真实切换通过 | API/双worker同镜像a1eb9faf0552；首次打开默认绑定、切回保留选择，25项真实PG通过；已准备模型切回0.038秒；原Thread新OPF28.801秒，回复10.445秒；回收后快速恢复待完成 | autonomous |

## 用户自安装试用版本

仅登记精确来源、已验收并公开的安装包。最新可安装运行版本不随普通文档提交漂移。

| ID | 精确Git提交 | 版本 | 发布地址 | 安装命令 | 验收状态 |
| --- | --- | --- | --- | --- | --- |
| user-local | b7e68dd83a580a713b09fa6d0c4aac0186252a84 | user-local-b7e68dd | https://github.com/uukuguy/capstone/releases/tag/user-local-b7e68dd | sh ~/capstone/capstone.sh install b7e68dd | 已验证可安装 |
| dev-trial | 783213489abd383bbf79225b29d9d718451dc597 | user-local-7832134 | https://github.com/uukuguy/capstone/releases/tag/user-local-7832134 | sh ~/capstone/capstone.sh install 7832134 | 已验证可安装 |

## Git节点展示规范

2026-10-14用户最新基线原则：PR #18已合入dev faa6af9 → 两个demo已正式发布同一dev合并提交并验收 → 从dev推进后续任务。2b6ae7b只保留候选验证记录；双平台PR、完整发布及合并后dev检查通过，正式标签demo-20261014-2028-faa6af9已推送。

本表是主图节点内容的唯一展示来源。全览角色确定必要和重要节点；
当前焦点、历史重要发布及部署来源同时保留。功能摘要使用两项简短说明，
详细验证和关联发布/部署标签由关键提交记录及实际Git标签提供。
新增部署来源时同时登记其节点内容，不由模板猜测当前功能或验证状态。

| ID | 全览角色 | 所属分支 | 功能摘要 | 展示状态 |
| --- | --- | --- | --- | --- |
| offline-e2-delivery | 当前交付重点 | fix/user-local-network-view | 已交付Linux AMD64更新包、单次安装ready通过；f300源码已修后续runtime问题，e2原归档未升级 | 已交付e2，保留原包及原校验值；包内仍是旧runtime，不冒充f300验证 |
| dev-current | 已验证发布范围 | dev历史来源 | 两项修复验收记录与控制工具合入；产品packages与f300一致 | f209fb1作为PR #30发布范围；local-dev已验证合入来源abf2f797 |
| offline-merge | 最新产品修复合并基线 | dev | 派生模型结果投影按验证修订展示；AC使用保存的Generator调度输入 | f300d1f已合入，双平台通过；local-dev ready、三后端文件SHA与重建时App身份核验通过 |
| user-local | 重要试用发布与开发基线 | dev | Git选择、管理命令与共享用户数据；双架构旧数据升级回放及回退、公开安装通过 | 已合入并发布，用户业务待验证 |
| dev-trial | 重要试用发布与开发基线 | dev | 无源码安装启动、同源App及受限Provider；双架构公开包已验证，用户正在试用 | 已发布试用包，用户业务待验证 |
| cloud | 历史重要发布 | main | 电网静态分析、智能体对话与工作台；计算结果与证据随运行保留 | 历史发布起点 |
| main | 已发布应用基线 | main | 阶段完整对话应用及已验证小修复；短期维护，保留未来对话场景发展 | PR #30合入cf72393b；双平台完整release通过 |
| dev-business-base | 开发分支起点 | dev | 恢复业务执行并保留独立轻量路由；Pi与自主智能体的共同业务基线 | 已合入，业务缺陷保留 |
| dev | 重要demo发布与大分支合并 | dev | 统一研究、执行、结果与证据合入主线；两个demo固定该基线，保留发布验收与回退来源 | 两个demo已验收 |
| dev-head | 当前研发位置 | dev | 实际dev分支头及真实祖先连线；产品验收与部署来源独立标记 | Git位置随生成更新，验收范围见对应里程碑 |
| workspace-integration | 集成候选 | fix/workspace-reading-type | 运行支持、会话导航与阅读状态保持已提交；最新dev已同步，PR #56草稿 | 完整回归及双平台CI待通过；未合入dev或更新cloud/demo |
| workspace-app-source | 已验证App来源 | fix/workspace-reading-type | 会话导航、缓存与阅读状态恢复；置顶恢复和Esc取消编辑修正 | 942App/构建/浏览器通过；尚未合入dev |
| workspace-outputs | 当前开发焦点 | fix/workspace-reading-type | 稳定三栏与会话管理；本地真实交互验收通过 | 当前三路338秒/59工具基线不变。会话切换无临时当前会话占位，目录连续显示，恢复电网工具条。宽度/置顶本地保持，名称/归档/删除宿主持久化。运行中会话不能被删除动作取消，文件保留范围明确。[验证](../reviews/2026-10-24-workspace-navigation.md) |
| pypsa-demand-fix | 当前试用修复候选 | fix/pypsa-inspection-semantics | 区分实际需求与静态默认值，恢复已保存会话；平衡电源解释按通用指南修正 | PR #54检查中；以IEEE39原有样例为主复验 |
| native-conversation | 无模型对话基座候选 | feat/work-attempt-binding | 复用账本与Harness完成无模型逐轮执行；完整原文保留，研究笔记按协议摘录 | 本地c9e57152；1394项后端及23项真实PG通过，未部署 |
| shared-workspace | 当前共享工作台候选 | feat/model-decision | 按定稿复用成熟对话、专业Work与拓扑；无模型与通用成果仍待实施 | local-dev 00a8cd85；570项App与88项真实PG通过 |
| pack-selection-dev | 已集成按需装配基座 | dev | 按需Pack装配已集成；继续生产存储及无模型前端入口 | PR #46双平台通过，合并树与受检来源一致 |
| work-ledger-dev | 当前开发焦点 | dev | Work保存与共享对话入口已集成；继续生产Claim/Profile绑定 | PR #48双平台通过，合并树与受检来源一致 |
| work-ledger | 已合入基座实现来源 | 共同基座（分支已关闭） | 同一账本承接无模型Work；复用成熟对话组件和定稿布局 | local-dev同源、537项App及真实保存恢复通过；持续执行待接入 |
| pack-selection | 已合入基座实现来源 | 共同基座（分支已关闭） | native/authority按需准备；保留完整Profile授权 | local-dev同源及Pi资源实读通过；持续执行待接入 |
| thread-version-dev | 已集成协议协商基座 | dev | 协议协商与恢复保护已集成；v2及无模型入口待实施 | PR #44双平台通过，合并树与受检来源一致 |
| thread-version | 已合入基座实现来源 | 共同基座（分支已关闭） | 服务与客户端协商v1；升级提示保留会话及草稿 | local-dev同源及浏览器通过；v2、Profile及无模型入口待实施 |
| work-identity-control | 研发控制与三线同步节点 | dev | Work基座验收与后续接入计划对齐；三条研发分支快进同源 | PR #42双平台文档检查通过，运行来源保持055a335f |
| work-identity-dev | 已集成研究归属里程碑 | dev | Work研究身份及开发CI分层已集成；继续Profile/v2与前端最小入口 | PR #41双平台约6分钟通过，合并树与受检来源一致 |
| work-identity | 已合入基座实现来源 | 共同基座（分支已关闭） | 模型无关Work研究保存与恢复；旧历史保留，生产协议及前端待接入 | local-dev同源验证通过；44项身份/研究与1332项后端测试通过 |
| dev-control | 研发控制基线节点 | dev | 三线推进位置与历史里程碑区分；控制规则固化 | PR #39双平台通过；不表示运行或部署更新 |
| shared-foundation-dev | 共同基座执行接缝里程碑 | dev | 共同执行接缝及既有专业基线合入；生产持续执行仍待后续接入 | PR #36双平台通过，合并树与受检来源一致 |
| pi | 已合入研发来源 | 原Pi分支（已关闭） | 原生执行与专业资产已合入dev；统一循环和新工作台仍待实施 | 双平台通过，保留原生执行基础来源 |
| enterprise-dev | 重要研发来源合并 | dev | 原Pi执行基础与专业资产合入；长期Pi分支已关闭 | PR #31双平台通过，合并树与受检来源一致 |
| autonomous-trial | 重要cloud-dev部署 | feat/autonomous-agent | 统一研究、任务执行与结果证据首批试用；cloud-dev运行该版，业务解释仍有缺陷 | 试用已验证，业务未验收 |
| autonomous-demo-first | 历史重要demo发布 | feat/autonomous-agent | 统一研究循环与执行、结果、证据链路上线；注册用例及报告、证据回放通过 | 基本发布检查通过 |
| dialog-demo-baseline | 历史重要demo发布 | feat/autonomous-agent | 基础图缓存、线程池创建与启动预热；新建对话提速，保留上一已验收回退基线 | 历史demo已验收 |

## PR 交付关联

2026-10-13 界面更新：83f2897为最新App候选，结果采用内嵌有界面板，默认一张紧凑表格并保留失败记录；位置标记滚动/靠右显示、悬浮摘要、点击定位、离开一秒淡出。82项相关App及类型通过，实际浏览器确认非模态、工具条不跳位、标记悬浮定位。local-dev后端812a755规范重建，同镜像a26d04e043f2，端口5173/8767不变；App后续两项样式修正已热更新。指定Thread thr_98b1c23a7ce472de5dc1 OPF64.108秒终态，复用旧结果、无求解器调用；研究步骤只发开始未发完成，前端显示“未记录完成”，未伪造时长。cloud-dev仍24d9a32。下一优先级为节点耗时分析优化，三任务整体科学结论尚未验收。

| 编号 | 工作包 | 来源 | 目标 | 状态 | 交付范围 |
| --- | --- | --- | --- | --- | --- |
| 51 | shared-agent | chore/dev-macos-ci | dev | MERGED | a8caeff2；macOS CI38945827751通过1分46秒；合并树同a14169aa；dev只要求macOS，main/显式release保留双平台，治理配置按实际范围检查 |
| 53 | shared-agent | feat/model-decision | dev | MERGED | f5eda4e4；macOS CI39009430704第2次完整通过，合并树与00a8cd85一致；真实Provider普通问答/IEEE39/追问三轮通过；PyPSA附加缺陷单独修正 |
| 54 | model-decision | fix/pypsa-inspection-semantics | dev | OPEN | effc9ccd修正时序负荷和调度语义；已重建同源，旧会话恢复问题补修中；未计PyPSA验收通过 |
| 52 | shared-agent | docs/conversation-delivery-control | dev | MERGED | 45913f1c；macOS文档CI38947256986通过1分28秒；合并树同af05f6e4；前端验收撤回，正常对话及成熟公共能力适配为交付标准 |
| 50 | shared-agent | feat/work-attempt-binding | dev | DRAFT | 旧CI38941770837已取消；后端资产保留，简化对话区与保存/开始验收撤回；正常对话及成熟功能复用实施中，不构成应用交付 |
| 48 | shared-agent | feat/thread-work-context | dev | MERGED | d86cc4ef；受检ed0e2e19与合并树一致；Linux5分7秒/macOS8分4秒；运行源码e58ef9a4，Work保存恢复及原专业入口通过；分支已关闭，两应用准备分支快进同源 |
| 41 | shared-agent | feat/work-research-identity | dev | MERGED | 85b6706f：受检08556cc2与合并树一致；双平台CI38898130414约6分钟通过；Work研究身份及开发期CI分层集成，生产Profile/v2前端仍待实施 |
| 30 | main | release/conversation-phase1 | main | MERGED | cf72393b；用户选择f209fb1，双平台CI38861900687完整release成功；合并树一致，分支已关闭，e2包及部署不变 |
| 36 | shared-agent | feat/shared-execution-baseline | dev | MERGED | d8fe6e27；精确711f06a8的CI38881419651双平台通过，合并树一致；执行接缝与既有基线验收完成，生产持续执行及前端闭环待后续实施 |
| 31 | pi | feat/pi-skills-integration | dev | MERGED | db167184；精确abf2f797的CI38865540607双平台通过；合并树一致，原分支关闭，工作树及数据保留 |
| 29 | autonomous | docs/pypsa-runtime-acceptance | dev | MERGED | 双平台CI38728722421全部通过，正常合入f209fb18d7abb122b689e1b1a52c54fa13bf5371；packages与f300无差异；root dev与App5173为f209fb1；修复和文档分支已关闭；后端、e2原包和其他环境不变 |
| 28 | autonomous | fix/user-local-network-view | dev | MERGED | required CI38723131332的Linux/macOS全部通过，正常合入f300d1f375ef20af005840a60af47b5e33ea62e8；受检c638及合并packages一致；root dev已快进，local-dev规范重建exit0/ready，同后端镜像与每角色1060文件SHA256及App f300身份通过（源码标签仍development）；e2归档未升级，回答算术与source建模投影限制保留 |
| 27 | dev-trial | feat/user-local-offline | dev | MERGED | 来源7c双平台CI38700786813全部通过，正常合并37529efa2f0b0e10f641a65706b330b1d94255af；7c包曾交付后撤回、不可交付，原SHA保留；root dev已快进f300且local-dev规范重建/源码核验通过；业务边界单列，图/Pi修复不在7c包内 |
| 22 | dev-trial | feat/dev-trial-deployment | dev | MERGED | 双平台38596540476通过，正常合并7832134；最终双架构镜像、匿名拉取、三案例九轮/回放/重启/浏览器及公开安装包通过；本地/远端实施分支已关闭，恢复引用和数据保留 |
| 23 | dev-trial | fix/dev-trial-user-feedback | dev | MERGED | Linux/macOS run38628243417通过，正常合并b7e68dd；完整本地及最终双架构升级/读取/回放/回退、重启、浏览器、匿名拉取和公开安装通过；未作用户LLM/整体业务验收 |
| 6 | foundation | feat/issue-operational-readiness | main | MERGED | 对话连续阅读、执行租约修复、环境身份、反馈接入与检查加固；cfd6ad6 两平台检查与审查通过，合并 c3b78bc；云端未发布 |
| 9 | answers | feat/task-answer-closure | main | MERGED | 精确2473e48两平台CI通过；合并f7baef3，树与验收源码一致；人工验收和云发布单列 |
| 10 | foundation | chore/iteration-gates | main | MERGED | 精确513a35e两平台CI通过，约32/26分钟；合并723b8e8；本地迭代/PR/发布门禁分层 |
| 11 | main | docs/project-state-sync | dev | MERGED | 原34文件积累文档及dev治理cfa6c1c已集成50d8ebc；精确CI38126098431两平台通过；68本地检查与独立审查通过；不作为产品部署 |
| 12 | main | docs/dev-baseline-control | dev | MERGED | 合入c857837；B2标签、分支关闭、Research Model旧起点及四环境前缀；不作为产品部署 |
| 13 | answers | fix/deployment-answer-acceptance | dev | CLOSED | 人工回归失败后按用户决定撤回；源码42a647b与旧补丁保留；不再作为验收通过候选 |
| 14 | answers | fix/stable-route-recovery | dev | MERGED | 精确bc08169双平台CI38181053709通过；合并6ff7094；恢复分支已关闭；新基线及两实施分支适配，业务缺陷及Issues2/3保持开放 |
| 15 | main | docs/dev-recovery-baseline-control | dev | 状态见GitHub | 全局基线台账、两实施分支适配报告及控制图；仅文档与图模板，产品来源仍为6ff7094；临时远端分支接受后关闭 |
| 16 | main | docs/autonomous-agent-discussion | dev | MERGED | 自主智能体讨论全览、五个概念、任务级进展流及研究模型详细提案；仅文档与生成器，产品与部署来源不变 |
| 17 | research | docs/autonomous-delivery-records | dev | [由PR #19替代，状态见GitHub](https://github.com/uukuguy/capstone/pull/17) | 2411210的统一设计、首期计划和真实试用报告已保留并更新到PR #19文档收尾；不将旧版状态覆盖当前验收 |
| 18 | autonomous | feat/autonomous-agent | dev | MERGED | 双平台PR38554449840、完整发布38554987581和合并后38558756435通过；合并faa6af9；统一研究循环、执行与结果证据、场景图层、模型资源和对话性能；两个demo同源注册回归及正式标签通过，整体科学业务验收仍开放 |
| 19 | main | docs/dev-integration-closeout | dev | [检查与合并状态](https://github.com/uukuguy/capstone/pull/19) | 687ba80保存23项控制图、设计和审计记录；对齐已合入dev及两个demo验收，保留科学与交互缺口；双平台文档门禁通过是合入条件，替代旧PR #17；不更改运行来源 |
| 20 | main | docs/capstone-cli-dev-trial-design | dev | [检查与合并状态](https://github.com/uukuguy/capstone/pull/20) | 用户不接触源码的固定dev镜像/Compose临时试用；Linux/macOS优先、Windows目标兼容；默认deepseek-flash、注释OpenAI及启动环境Key要求；部署包和可配置LLM未实现，现有四环境不变 |
| 21 | main | docs/aliyun-default-trial-registry | dev | [检查与合并状态](https://github.com/uukuguy/capstone/pull/21) | 阿里北京ACR/uukuguy为默认公开拉取源，GHCR可选备用；只落实设计决定，不创建仓库、构建或上传镜像；镜像构成/体积/架构继续讨论 |

## 全部分支进展

此表给现存分支分类；展示时与实际 Git heads 核对，未知分支显示待登记。archive 是保留的实现或资料，不等于四条永久开发主线。

| 分支 | 类型 | 关键进展 | 下一步 | 功能包 |
| --- | --- | --- | --- | --- |
| feat/user-local-offline | 已合入交付来源 | 精确7c包曾交付后撤回，现不可交付；PR #27正常合入37529ef，来源双CI通过 | 保留归档与原SHA，root dev快进/规范重建单列；业务失败和未跑样例继续验证，不覆盖已交付包 | dev-trial |
| fix/user-local-network-view | 已合入运行修复来源 | c638受检，PR #28双平台CI通过后正常合入f300d1f；root dev已快进，packages一致 | local-dev规范重建及真实身份核验已通过；e2归档未升级，19173/demo/cloud不变；回答算术和source建模投影边界保留 | autonomous |
| refs/archive/20261015/feat-dev-trial-deployment | 已合并实施恢复引用 | 380ede4受检，PR #22合入7832134；本地/远端实施分支已关闭；最终公开镜像/包及安装入口验收通过 | 保存原验收目录、私有状态与卷；用户业务试用待反馈 | dev-trial |
| main | 已发布应用维护主线 | PR #30合入cf72393b，范围f209fb1；双平台完整release通过，合并树一致 | 短期零星修复，未来按对话适用场景发展；用户交付包不自动更新 | main |
| feat/work-research-identity（已关闭） | 共同基座Task 2已合入来源 | 055a335f组件实现及08556cc2 CI分层通过双平台检查；PR #41合入85b6706f | dev继续生产Profile/v2前端接入 | shared-agent |
| feat/thread-version-negotiation（已关闭） | 共同基座协议准备已合入来源 | 2d3f86c6/a2efb791通过本地与双平台CI；PR #44合入32f18d24 | v1协商及升级恢复；v2/无模型入口未实现 | shared-agent |
| feat/shared-execution-baseline（已关闭） | 共同基座Task 1已合入来源 | 62f44366执行接缝与711f06a8回执通过双平台CI，PR #36合入d8fe6e27 | dev继续Task 2；来源提交保留在合并历史 | shared-agent |
| feat/business-analysis | 阶段应用研发，准备中 | 已从dev6c0b0ae7创建并推送，尚无独立业务实现 | A1资源与验收准备；等待基座能力后分批PR回dev | business-analysis |
| feat/model-decision | 定稿架构与原型对齐 | 00a8cd85已推送；PR #53已合入f5eda4e4；570项App与88项真实PG通过 | local-dev规范重建同源；历史结果、拓扑及新建会话入口通过；无模型与通用成果未完成。[验证记录](../reviews/2026-10-17-shared-dialogue-adaptation.md) | model-decision |
| feat/application-pack-selection（已关闭） | 共同基座按需装配已合入来源 | 20226bf0实现、cb08ef92限定CI；PR #46合入9eb84a34 | native/authority准备通过；生产Profile/v2前端及持续执行待实现 | shared-agent |
| feat/work-attempt-binding | 正常对话基座研发 | 本地c9e57152；PR #50仍为旧来源草稿；native源码已保存 | RPC父链及23项真实PG通过；前端、真实Provider及部署另验；非应用交付 | 研发macOS；发布保留双平台 |
| feat/thread-work-context（已关闭） | 共同基座Work账本已合入来源 | e58ef9a4实现与复用修正；PR #48合入d86cc4ef | v2/无模型任务保存入口；生产Claim/Profile与持续执行仍待实现 | shared-agent |
| dev | 默认开发集成主线 | PR #52合入45913f1c，交付标准与设计对齐；macOS研发/main双平台发布 | local-dev已验证00a8cd85共享界面切片；PR #53已集成f5eda4e4，完整业务对话验收另列 | main |
| docs/dev-baseline-control | 收口状态同步 | 从接受的dev50d8ebc建立；登记B2标签、分支关闭与研究实施起点 | 仅文档和控制图，轻量检查后集成dev | main |
| feat/research-model | 起点与依赖已适配 | 2b0b0a5；精确祖先dev6ff7094；设计及推进计划排除撤回的编译/覆盖/预热依赖；本工作区运行时准备与doctor通过 | R1尚无代码；按R1–R5及真实依赖路径验收，不将旧R0实验当作本分支成果 | research |
| recovery/autonomous-agent-merged-faa6af9 | 已合并分支的本地恢复引用 | 原feat/autonomous-agent已通过PR #18合入dev faa6af9；保留2b6ae7b与原工作树全部未提交文档和运行数据；远端已合并分支关闭 | 非在研分支；后续从dev推进，科学与交互验收仍开放 | autonomous |
| recovery/dev-control-pre-faa6af9 | 旧dev控制文档恢复引用 | 9472edf及2411210两项未推送文档提交保留；改动快照与stash另存 | 不作为运行来源；保留至文档整合完成 | main |
| docs/dev-integration-closeout | 文档入dev收尾 | PR #19对齐控制图、部署/验收及设计审计记录，保存所有剩余根工作区文档 | 门禁通过后合入并关闭；运行来源不变 | main |
| docs/capstone-cli-dev-trial-design | CLI部署讨论记录 | 用户本地临时dev试用；Linux/macOS优先、Windows目标兼容；pip/npm及脚本入口写入统一CLI设计 | 仅文档，安装包、脚本及部署工件未实现；按文档门禁接入dev | main |
| docs/aliyun-default-trial-registry | 默认镜像仓库决定 | 用户已确认阿里北京ACR/uukuguy公开拉取为缺省，GHCR可选备用；只记录设计，不构建/发布镜像 | 文档门禁后接入dev；镜像构成、体积和架构仍在讨论 | main |
| fix/deployment-answer-acceptance | 已撤回的回答增强候选 | 42a647b保留，archive/answer-recovery-before-rollback-20261012固定恢复点；未提交补丁已备份 | 人工回归失败；用户取消本轮增强；不得继续作为可靠基线或验收通过版本 | answers |
| fix/stable-route-recovery | 已合入并关闭 | PR14源bc08169合入dev6ff7094；本地及远端引用关闭，refs/archive/20261012/fix-stable-route-recovery保存精确源 | 代码继续在dev维护；原七轮业务失败及新普通误路由保留，不重启撤回的任务闭环实现 | answers |
| fix/deployment-answer-acceptance | 已撤回，来源保留 | PR13关闭；42a647b保留原分支及已推送archive/answer-recovery-before-rollback-20261012 | 不继续此候选；仅保留恢复和核对依据 | answers |
| improve/run-process-window | 已被完整候选取代 | 22acf1b为早期界面验收来源；后续2473e48及当前d7ac7d9包含更紧凑窗口 | 保留来源参考，不继续作为当前部署候选；随PR #9收口 | answers |
| improve/issue-4-active-recovery | 诊断工作区，产品源码未变 | 来源c3b78bc；4项生命周期检查确认隐藏页面恢复路径符合既有设计；Issue#4为ai:needs-info | 核对切后台/锁屏触发和实际时序；不猜测云端冷启动原因，不修改在线睡眠策略 | wake |
| feat/pi-skills-integration | 已合入并关闭 | PR #31合入dev db167184，双平台通过 | detached工作树与数据保留；refs/archive/20261016/feat-pi-skills-integration保存abf2f797 | pi |
| archive/pi-before-dev-baseline-20261012 | Pi适配前恢复引用 | 精确749e0b8；本地及远端保留 | 仅恢复/对照，活动实施在dev | pi |
| archive/research-before-dev-baseline-20261012 | Research旧起点恢复引用 | 精确50d8ebc；本地及远端保留 | 仅恢复/对照，活动实施在feat/research-model | research |
| archive/dev-recovery-control-staging-20261012 | 台账准备检查点 | 39ffe2b；保存收口期间的全局记录，当前根工作区detached继续整理 | 当前全局台账通过临时文档PR集成dev；不作为产品部署或活动功能分支 | main |
| experiment/autonomous-research | R0参考实验 | 来源c3b78bc；代码bf678f2；基础实际实验与独立审查通过；未提交记录保留 | feat/research-model承接R1实施，R0保持参考；不直接合入或部署 | research |
| archive/context-segment-storage-20261011 | 历史归档，适用性未确认 | 9 月 5 日 OP-13 未提交存储实验；现用执行账本仍承担答案绑定、状态回放与交接，Thread 历史另走数据库 | 保留现用账本与实验代码；有当前场景证据后重评估，不直接续做旧设计 | context |
| archive/answer-chain-unaccepted-20261010 | 已归档，未验收 | 3e3bbfb旧回答修复；已有结果/证据保留、诊断及展示防护，正式回答未过人工验收；用户2026-10-12要求移出当前推进图 | 仅保留历史恢复与核对依据；不再列为当前待重整或活动复用来源，不原样合入或部署 | answers |
| archive/dev-before-baseline-20261010 | 旧 dev 快照 | 保存基线调整前的 Pi/skills/资源/旧修复全集；当前实验已提取到 Pi 分支 | 仅作对照与恢复来源，不继续在快照开发 | pi |
| archive/multi-binding-notes-20261010 | 资料保留 | 已提交能力在 main 中；还有未提交历史记录和 lock 文件 | 保留资料，不作为新增功能开发 | main |

## 提出但未实施

控制图的“待推进的开发包”只保留尚未挂入树上开发分支的内容。开发包进入分支后，将范围、未完成工作、验收条件和 PR 关联迁入对应分支框及详情，从本区移除。已有分支中的待完成内容不重复列入本区；旧回答候选已挂树并明确待重整，因此后续完整回答增强也在该框中管理，不因新分支尚未建立再次列为待推进包。

| 项目 | 当前缺口 | 记录 |
| --- | --- | --- |
| 长期CAPSTONE CLI安装分发 | 临时dev部署已合入7832134并发布验证；长期pip/npm命令入口仍为设计，未发布 | [CLI开发设计](../superpowers/specs/2026-09-29-agent-interaction-discussion.md#2026-10-14capstone-cli-安装与用户本地-dev-试用) |
| 统一输入命令与快捷操作 | 独立前端增强包，覆盖 Capstone 各模式的必要快捷操作；先设计统一目录和交互，Pi 三个命令仅为局部原型 | 2026-10-11 用户范围确认；10-09 业务工作区资源设计 |
| 独立 Case 模块产品接入 | 已有执行基础；当前对话入口未接入完整独立模块，范围需确认 | 核心演进讨论；10-09 资源验收 |
| 启动与中途恢复体验 | 需测量复现，休眠策略和恢复方案未确定 | Issue #4 |
| 下一稳定发布 | 基础包有已验收部分；尚未冻结包含正式回答增强的发布候选 | 发布计划待定 |

## Git 分支整理

2026-10-10 清理了 16 个已合入 main、已归入基础修订包或重复指向同一候选的本地分支名。提交保留在 `refs/archive/20261010/<原分支名>`；已有工作区只转为 detached，未删除目录、数据或文件。已关闭 PR #7/#8 的远端分支和已合入 main 的截图文档远端分支已移除。详细映射见[分支清理记录](GIT-BRANCH-CLEANUP.md)。

当前活动分支以上方完整分支分类表及实际Git heads为准，不沿用早期三分支列表。旧OP-13存储实验归档为 `archive/context-segment-storage-20261011`，未提交代码已存入20261018私有校验归档，展开工作区已移除；当前适用性未确认，不列为待开发或回答增强依赖。旧回答候选3e3bbfb已移出当前推进图，保留在 `archive/answer-chain-unaccepted-20261010` 供历史追溯；原multi-binding未提交资料保留在对应归档。历史名称仅用于追溯。

## 两个基线

1. **基线一：最小影响对齐。** 以当前已验收云 demo `ed2524f` 为运行代码起点。先保存现有 dev 成果，再把尚未稳定的纯 Pi、skills 等开发留在分支。必要的本地部署管理工具单独列出；不顺带加入尚未验收的回答链路修复。对齐不修改云端用户数据，也不自动部署。
2. **基线二：修复增强后的稳定版本。** 从基线一推进公共回答链路修复、意图与任务理解、正式回答和故障诊断等工作。每项分别登记、验证、合并，整体经过用户问题验收后才形成下一稳定发布。

代码相同和服务健康只证明对齐或运行通过。正式回答没有满足用户问题时，产品验收仍失败。已知缺陷保留在台账中；基线一不宣称这些缺陷已解决。

## 用户反馈与 GitHub Issues

[GitHub Issues](https://github.com/uukuguy/capstone/issues) 是反馈、讨论和处理状态的唯一主台账。使用[反馈模板](../../.github/ISSUE_TEMPLATE/user-feedback.md)登记环境、版本/tag、操作、现象和期望；原因未确认时保持未确认。仓库版本台账只登记 Issue/工作包与分支、提交、基线和发布的关系，不另建重复反馈台账。

用户可只提供截图和一两句话，由 AI 补充维护字段；当前模板的长表不是用户必填要求，简化在自动处理方案实施时完成。未说明环境的用户反馈默认指 `cloud-demo`，明确说明可覆盖；默认环境不能代替发生时版本的证据。

1. 每条独立问题建立 Issue，先分流再开发。阻断使用或数据/结果错误评估 `hotfix/demo-*`；普通缺陷进入 `fix/*`；体验、性能或框架增强进入 `improve/*`；新能力进入 `feat/*`。不是所有 bug 都需要紧急发布。
2. 优先使用已有 `bug`、`enhancement`、`question` 标签。PR 按同一维护目标、依赖和验收范围组织一组修复，小改动保留为内部提交；不同设计或发布范围分组。一个 PR 可关联多个 Issue；一个 Issue 跨越明确分开的范围时可关联多个 PR。重复反馈链接原 Issue，保留原始用户事实。没有明确依赖时不为每条反馈创建分支。
3. 开发前补齐负责人、来源、依赖、目标基线和用户可观察的验收标准。提交 PR 前完成对应本地验证；公共 API/worker/App 变化先规范重建并验收受影响的 local-dev 入口。local-demo 的候选部署和产品验收属于用户发布计划。已知本地失败继续在分支修复，draft 不代替该前置条件。相关 Issue 编号进入 PR 和版本台账。
4. 按本文件合并队列和发布流程集成。普通改进随计划发布；紧急修复完成主线和受影响分支回归。记录各环境实际生效版本，不能用“已修复”代替“demo 已部署”。
5. Issue 阶段分别记录待确认、已确认、已修复、已集成、已部署、用户已验证。关闭前明确验收范围；若仍需 demo 发布或用户验证，保持打开，避免 PR 自动关闭掩盖待办。重复或不处理也必须写明理由。

历史浏览已登记为 [Issue #1](https://github.com/uukuguy/capstone/issues/1)：用户在远少于 50 条消息时就需要点击“查看之前的对话”。实际本地对话读取确认 4 条提问对应 353 条公开事件；最近 128 事件页遗漏较早问答。归入公共历史浏览工作包，在独立分支处理完整问答恢复、按需连续加载与阅读位置保持，当前不走紧急发布。

用户已授权按[Issue 处理设计](../superpowers/specs/2026-10-10-github-issue-automation-design.md)实施，采用 AI 修复到 PR、维护者确认合并；[实施计划](../superpowers/plans/2026-10-10-github-issue-automation.md)记录验证与接入。最新要求：第一阶段由用户命令或 AI 适时提醒发起，当前 AI 会话处理，不启用定时/无人值守或额外付费模型 API。实现和远端发布分别记录，不由设计获批推断后台已运行。

## 分支合并流程

1. 建分支前登记来源提交、目的、负责人、影响模块、依赖、实验开关和验收范围。公共非功能变更也必须登记。
2. 开发与针对性验证在分支进行。需要验证分支时，让 dev 环境明确记录该分支的提交；环境名称不能代替来源身份。
3. 合并按队列串行执行：依赖提供者先于使用者；公共契约变更先于依赖该契约的功能。同一模块有冲突时先确定共同契约，再处理冲突。
4. 普通开发合并前同步最新dev；发布PR核对main差异，检查并验证冲突解决。不得直接用整侧覆盖来消除冲突。记录合并提交、验证报告、默认和实验启用范围。
5. 公共框架变更验证受影响的 Domain Pack、Authority 边界和 local-dev 入口。按变更范围选择验证；稳定基线与发布执行完整验收。仅文档或 CI 配置变更做对应检查，不因未改变运行代码的修改重复整套发布测试。local-demo 在发布候选阶段验收。
6. demo紧急修复优先进入合并队列。同一修复任务内完成main与dev回流；受影响功能分支再次合并前同步修复。阻塞时记录原因和下一动作，不能标记闭环。

## 两种 demo 发布流程

**计划发布：** 登记计划日期、功能清单、实验功能排除或启用范围、候选来源及回滚目标；从 main 冻结候选；local-demo 验证用户问题；cloud-dev 验证同一候选；按生命周期将精确来源或工件提升到 cloud-demo；通过检查后创建独立的 demo 验收标签。

**紧急修复：** 从当前 cloud-demo 已验收标签建立专用分支；记录事故与最小修复范围；先在 local-demo 验证，再按云端验证与发布门禁发布。任何用户明确授权的流程例外必须记录，但不放宽证据、身份和数据隔离要求。发布后完成 main 与相关分支回归，登记对应提交及验证结果。回滚保留历史标签，创建新的验证记录，不能移动已有标签。

当前任务仅调整本地来源与管理流程，不包含新云端部署。计划发布周期和日期尚未约定，每次发布先登记，不能据此自动发布。

## 标签规范

基线使用 annotated tag 固定精确提交；冻结分支不能代替标签。标签与产品版本、环境名称分别记录，基线编号不表示产品语义版本。

| 标签类型 | 命名 | 验收条件 |
| --- | --- | --- |
| 本地基线 | `baseline-b<N>-local-<YYYYMMDD-HHMM>-<short-sha>` | 指定范围的完整检查、本地入口及工件身份验证通过；记录已知缺陷，不表示云端发布或全部产品问题已解决 |
| 云开发验收 | `cloud-dev-<YYYYMMDD-HHMM>-<short-sha>` | 云开发部署及生命周期规定的检查通过 |
| 云 demo 验收 | `demo-<YYYYMMDD-HHMM>-<short-sha>` | 精确候选完成 demo 部署与规定验收；计划发布、紧急修复和回滚均遵循此规则 |

时间统一使用 Asia/Shanghai；提交缩写至少七位，存在歧义时延长。所有标签必须指向实际验证的完整提交，不指向随后推进的 main HEAD。相同提交在不同阶段通过验收时，各建独立标签。实验分支、未完成验收的候选不能获得上述验收标签。

标签注释必须包含：类型与基线编号、验收范围、完整提交、运行来源及工件身份、启用/排除功能、验证报告路径及报告提交、部署标识（本地注明 Compose 项目）、已知限制、前一基线或回滚目标。不得包含凭据或用户数据。

创建前核对源码与验证收据；创建后核对对象类型为 `tag`、解析提交及注释。发布标签时只推送明确列出的标签，再核对远端解析提交；不能使用 `--tags` 顺带发布实验标签。云阶段验收标签按生命周期要求推送。本地标签的远端同步状态单独登记，不能由标签存在推断已发布。

标签不可移动、覆盖或复用，不使用强制推送。撤回时保留标签，台账注明撤回原因和替代标签；修改后的候选重新验证并建立新标签。回滚以已有精确提交为来源，完成阶段检查后建立新的阶段验收标签。

### 本地恢复快照（非发布或验收标签）

三份快照均为本地annotated标签，保存创建时工作区的未提交源码/文档；它们是固定恢复点，不是活动研发分支，没有移动原分支、索引或部署，也没有推送远端。按用户要求先完成快照，再继续研究增量集成。恢复收据：`ROOT/outputs/recovery-checkpoints/pre-deep-research-20261018-223637.json`；该私有操作收据不进入公开发布工件。

| 本地标签 | 快照提交 | 原工作区与基底 | 状态 |
| --- | --- | --- | --- |
| `pre-deep-research-20261018-223637` | `83e89e33dbce7b9a36a600b820bc0e4b5991efa5` | model-decision实现区，`159803897127b33d791ef77298ba9fbe5da13a2b` | 本地恢复快照；未推送；非验收/部署 |
| `pre-deep-research-20261018-223637-control` | `906f33137bf9899c118045be87aba068f74165ea` | dev控制区，`7b2adbc604f6e92a2103a246fe820593bb96773f` | 本地恢复快照；未推送；非验收/部署 |
| `pre-deep-research-20261018-223637-root` | `988ce35bba792aba223a52fd56e36c652be635bd` | root工作区，`c9e571521a687f15598c626b0b239e28bf41ad7e` | 本地恢复快照；未推送；非验收/部署 |

### 基线标签台账

| 标签 | 精确来源 | 范围与状态 |
| --- | --- | --- |
| `demo-20261014-2028-faa6af9` | `faa6af9b4a6fe567c559d0b68ab1c4e5aa1bd4fe` | PR #18合入dev后的正式demo；已推送并核对annotated对象与远端精确提交；两个demo各三用例九轮、报告证据回放及旧Thread入口通过，零Provider；源码/运行身份一致，原数据保留；[发布记录](../reviews/2026-10-14-autonomous-demo-release.md)；科学与交互缺口仍开放 |
| `baseline-b1-local-20261010-1431-a076b04` | `a076b0419788b3a67e5a2c8937fc0dcd7e927af1` | 本地基线一；运行代码 `2540bdc` 加已验证的环境忽略规则；已推送并核对远端解析提交，注释保留创建时历史状态；[对齐验收](../reviews/2026-10-10-version-baseline-alignment.md)；云端未更新，正式回答及历史浏览体验仍待改进 |
| `baseline-b2-local-20261011-1648-2473e48` | `2473e4860dcaf11d575e8d009caeb088756a4cd2` | 已推送并核对annotated对象与精确来源；正式回答/覆盖核验/运行窗口本地技术基线；完整门禁、336实际PG、独立审查、精确双平台CI、同镜像512文件、三案例九轮与浏览器通过；[报告](../reviews/2026-10-11-task-answer-local-dev.md)来源69f7825；人工回答验收待完成，未新增发电N-1，云端未更新 |

## 环境台账

下表区分历史验收与当前操作；不是四个环境都已重新验证的声明。

| 环境 | 最近记录的来源 | 状态 | 入口或证据 |
| --- | --- | --- | --- |
| local-dev | 基于 `159803897127b33d791ef77298ba9fbe5da13a2b` 加共享导航、会话管理、分层会话缓存与阅读状态恢复；未提交，精确源码见缓存验证回执 | backendc64fbe52c992/nativeada86461950c，118源码/ready/App及cleanup20261025-000145-64738通过 | 932App/类型/构建/doctor通过。真实热切换保留主区/iframe位置，完整快照请求0；上限1释放后恢复165px及原报告选择。自动释放不归档或取消任务。[验证](../reviews/2026-10-24-session-view-cache.md) |
| local-demo | App/API/两worker `faa6af9` | 规范重建ready，三角色同镜像3a2d87862325，运行身份与已验证local-dev一致；六个原Thread及事件序号保留；三用例九轮及报告证据回放、旧Thread图与Composer通过 | 固定App http://127.0.0.1:15173/，API18767；App dirty=false；数据库、存储和原数据保留 |
| cloud-dev | `24d9a32`，开发试用候选；已推送标签cloud-dev-20261013-1045-24d9a32 | 用户授权的基本功能检查通过：四角色SUCCESS、API就绪、前端来源与真实中文对话；非正式发布或科学解释验收 | App https://capstone-app-production-83ef.up.railway.app/；[部署记录](../reviews/2026-10-13-cloud-dev-autonomous-trial.md)；demo不变 |
| cloud-demo | App/API/两worker `faa6af9` | 四角色SUCCESS；三后端身份与dev本地529文件验收一致，安装工件与受检候选一致；三用例九轮、报告证据回放通过；local-demo已同源验收；正式标签demo-20261014-2028-faa6af9已推送 | App https://capstone-app-production-975e.up.railway.app/；上一正式标签demo-20261014-0744-bd2a200；双平台完整发布38554987581通过；cloud-dev不动 |

基线一已完成本地对齐。云端仍为 `ed2524f`，没有部署本地新增的最小契约修正；不能宣称四个环境已更新到同一提交。`release/demo-baseline-1` 固定在 `a076b04`，包含 `2540bdc` 的运行代码和已验证的环境文件忽略规则，是本地验收的冻结候选，不是新的云 demo 验收标签。台账/文档提交可以推进 main 的 HEAD；运行来源、镜像和工件身份以最后重建收据为准。

两个本地环境各完成三个注册案例、九轮执行及报告/证据回放。六个角色的运行契约、源码工件与安装工件 SHA-256 完全一致；两套环境的数据和存储保持隔离。510 个 dev 对话与两个 demo 对话的快照/历史可读取，原有 8,682/362 条事件及所有存储卷保留。详情见对齐验收报告。

撤回的 `demo-20261010-1150-2ea2266` 保留审计用途，不代表当前版本。四个环境未来统一显示 `local-dev/local-demo/cloud-dev/cloud-demo`，同时保留产品版本和来源提交；此次不单独修改云端显示。

## 分支与公共变更台账

| 项目 | 来源/当前提交 | 状态与下一步 |
| --- | --- | --- |
| 现有 dev 的纯 Pi、skills、资源扩展及相关实验 | 原始快照 `archive/dev-before-baseline-20261010`：`ca062df`；`feat/pi-skills-integration` 实验代码 `fba1f51`；规范同步提交 `331f71c` | 从事故前 `e9aca89` 重新应用在共同基线上；测试文件仅清理末尾空行；已同步公共忽略规则与 main 管理规范；未重新部署或获得稳定发布验收；后续拆分依赖和合并范围 |
| 公共回答链路修复 | [Issue #2](https://github.com/uukuguy/capstone/issues/2)；旧PR #13候选42a647b保留；回退30a3ecb | 用户撤回未稳定增强；local-dev恢复c3b78bc业务链，独立意图识别保留；原技术标签不可变，人工回归失败不计新验收；云端未更新 |
| 基线一整理 | 云 demo 起点 `ed2524f`；运行基线 `2540bdc`；`release/demo-baseline-1` 固定候选 `a076b04`；整理分支 原 `integration/demo-baseline` 已归档，管理提交已在 main | 完整离线、集成、打包及两套本地实际入口验证通过；候选补入已验证的非运行忽略规则修复；已合并 main；云端推广未执行 |
| 基线必要契约修正 | 归档 `fix/baseline-contracts`：`2540bdc` | 五个文件修正空事件/可选拓扑接口/凭据契约；13 个类型错误归零，Thread 46 项、pandapower 5 项、PyPSA 7 项针对性检查通过；不包含新 Pi 或回答策略 |
| 本地 demo 管理守护 | 归档 `fix/local-demo-secret-ignore`：`a076b04` | 历史提交保留受保护环境文件的忽略规则；针对性检查通过；已回归 main、基线整理分支和 Pi/skills 分支；不改变运行代码或工件身份 |
| 语义任务意图与回答尺度 | [Issue #3](https://github.com/uukuguy/capstone/issues/3)；PR #9源码2473e48；[设计](../superpowers/specs/2026-10-10-shared-intent-and-goal-answer-design.md) | typed v2识别、目标准入和对象/指标/场景证明已实现并在local-dev技术验收；普通/专业路由仍不等于完整任务理解。人工业务问答体验及云发布另行验收 |
| 启动和对话中恢复体验 | [Issue #4](https://github.com/uukuguy/capstone/issues/4)；[初步诊断](../reviews/2026-10-11-issue-processing.md) | ai:needs-info；4项检查确认既有隐藏页面恢复路径，已询问后台/锁屏触发；未确认云端根因，未修改睡眠策略 |
| 对话历史浏览 | [Issue #1](https://github.com/uukuguy/capstone/issues/1)；PR #6 合并 `c3b78bc`；原 PR #8 保留历史记录 | 连续历史、阅读位置及返回最新验收通过；已进入 main/local-dev。当前 local-demo 恢复线上旧版本，此功能随下次计划发布验收；云端未发布 |
| GitHub 反馈与 AI 修复 | 首版 `d70fc27`；基础修订 PR #6 合并 `c3b78bc` | 独立身份、中文回复及命令触发工具已集成；无人值守和额外模型调用仍关闭。云端未更新；[验收范围](../reviews/2026-10-10-issue-workflow.md) |
| Issue 接入准备与基础修订包 | PR #6 精确候选 `cfd6ad6`，合并 main `c3b78bc` | 本地门禁、独立审查、Python 3.12 双平台 CI 38074539207 通过；local-dev 合并来源实际入口验收通过。旧 PR #7/#8 已关闭并关联替代；无云发布 |
| 远端 CI 可移植性修复 | 旧 `bbc8811` 保留归档；[Issue #5](https://github.com/uukuguy/capstone/issues/5)；PR #6 合并 `c3b78bc` | 租约、ANSI、测试预算、缺 rg、模型依赖及浮点比较修复已集成；精确最新候选双平台检查通过。旧四项矩阵为历史证据，不代表当前门禁要求 |

上述历史功能分支的已提交 tip 均为 main 的祖先，现已按本页分支清理记录归档；这不表示功能已从 main 移除。原 capstone-optimization 工作区的未提交存储实验保留在 archive/context-segment-storage-20261011，不列为活动开发。旧回答候选只改归档名称，代码和验收失败记录仍保留。

## 每次更新的必填记录

- 分支或变更：类型、来源、当前提交、影响模块、依赖、负责人、实验状态和默认启用范围。
- 合并：目标、顺序、冲突说明、合并提交、测试与实际入口验收。
- 公共修复：主线、受影响分支和 demo 候选的对应提交；哪些已生效，哪些仍待发布。
- 发布：精确提交/工件、功能与配置清单、各角色身份、验收报告、部署标识、阶段标签及回滚目标。
- 阻塞：失败属于构建、运行、契约、计算、证据还是产品回答；未知原因明确标记未确认。

不将“开发中”“已集成”“实验可用”“demo 已验收”合并为一个完成状态。详细过程记入 JOURNAL，后续动作记入 RESUME；本文件维护当前版本关系和闭环状态。

推进图的四环境卡片使用紧凑宽度（分支卡片的 64%，上限 220px），保留独立底色、服务器/云图标和实际来源挂接；左侧环境靠主线对齐，避免无内容的宽框。

回归审计修正：原六轮整体验收撤回；概况、范围、索引、混合目标、AC诊断、场景排序修复保留。760整体10轮业务通过但缺项探针失败；f0整体筛选AC故障结果被丢弃，判失败。51f4715补齐整体负荷语义、待澄清提案与部分证据保留，84项与55项检查和审查通过；同源重建镜像00e64fdf，各角色511项与App来源通过；实际整体10轮独立业务复核与三类缺项探针通过；浏览器运行/完成窗口通过。筛选AC分支由原失败工件复放和focused反例验证，最新Thread使用完整四类检查，不能声称它覆盖了筛选分支。待人工验证，Research R1后置。
