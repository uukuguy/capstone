# docs/status INDEX

2026-10-15当前：PR #22已合入dev7832134，原无源码试用双架构验收、公开发布及用户安装完成。当前fix/dev-trial-user-feedback修正user-local标识、Git版本选择、capstone.sh管理和共享用户数据兼容门禁；新管理功能未发布，现有用户数据保留。精确检查点见[RESUME](RESUME-NEXT-SESSION.md)，执行[Task 7](../superpowers/plans/2026-10-14-capstone-dev-trial-deployment.md#task-7-user-local-management-and-shared-data-compatibility)。下方较早摘要按当时状态保留。

2026-10-14：用户已同意四类镜像和linux/amd64、linux/arm64目标，执行[dev试用部署计划](../superpowers/plans/2026-10-14-capstone-dev-trial-deployment.md)。6f29b29实现无源码Compose、受限Provider及精确Git构建；69项Python和15项App检查通过，候选镜像构建中。控制图新增当前焦点及真实dev祖先边；未合入、未发布，不改现有四环境。

2026-10-14镜像分发决定：阿里云 `registry.cn-beijing.aliyuncs.com/uukuguy` 为用户试用的默认公开拉取源，GHCR可选备用；本地已有登录验证通过，两个新仓库及试用镜像尚未创建/发布验收。镜像构成、体积和架构继续讨论，见[CLI设计](../superpowers/specs/2026-09-29-agent-interaction-discussion.md#默认镜像仓库与公开分发)。

2026-10-14：用户本地部署入口已记录到[CAPSTONE CLI开发设计](../superpowers/specs/2026-09-29-agent-interaction-discussion.md#2026-10-14capstone-cli-安装与用户本地-dev-试用)。本次固定dev临时试用，用户不接触源码；我们构建镜像，用户通过Compose/配置/薄脚本启动。Linux/macOS优先、Windows目标兼容，pip/npm为以后统一CLI分发方向。当前仅设计记录，未打包或安装，现有四环境不变。

当前：PR #18已合入dev faa6af9；候选、完整发布和合并后双平台检查通过。local-dev、local-demo与cloud-demo均运行该合并来源；两个demo完成三用例九轮、报告证据回放和旧Thread入口检查，原数据保留。正式标签demo-20261014-2028-faa6af9已推送并核对。cloud-dev24d9a32保持不变。

文档入库通过PR #19，包含剩余23项控制/设计/审计记录；旧PR #17由此替代。控制文档提交推进dev HEAD，运行来源与demo标签仍为faa6af9。

推进图显示8个关键Git节点，突出当前活跃节点、四部署来源与实际在研Pi分支；dev主线保留重要云部署和大分支合并，中间候选进入历史详情。统一卡片内容、居中纵向主线、来源连线与两端间距浏览器检查通过。


## Active

当前精确状态见 RESUME / VERSION-CONTROL：产品PR #18已合入，两个demo均为faa6af9并完成注册回归；本轮文档收尾通过独立PR入dev。主图保留中轴、四部署及在研节点。

### 历史实施记录

以下按原验证时点保留，不覆盖上方当前基线；源码已合入不代表科学与交互缺口已全部通过。


594e0b4：local-dev完整阶段计时已实测，准备、推演、核验整理均保存；同排批量展开/收起与状态保留已验证。阶段合计与任务总耗时差17毫秒；准备资源耗时与未记录目的仍待优化。见执行节点审计及版本台账，不代表整体科学验收。

[执行节点审计](../reviews/2026-10-13-execution-node-audit.md)：五连续指令准备复用与结果复用已核对；过程任务说明缺口及默认10动作修正见368ec58，实时业务推进待观察。

84bc0db：表页公共契约22项后端/30项App及类型通过；共享存储与领域分页已实现，交付/API/翻页交互未接。控制图默认可读尺寸和图内滚动，桌面/手机验证通过。

508395f：完整分析表分页的领域投影25项及类型通过，API/App及共享持久化待接入；历史追问c886已实证。现行身份见版本台账。

[三样本任务链验证](../reviews/2026-10-13-three-task-chain-validation.md)：092acb6三项真实API执行收尾完成，回复、过程和结果可打开；包含业务未达成及未证实解释，保留历史失败。仅隔离人工候选，未合入或稳定发布。

人工候选092acb6运行于隔离API8889/App5199。三专项执行闭环完成并可交人工观察，耗时40／379／73秒；概况原句21秒，约10秒目标未达到。研究记录a3895a5及参数追溯388fa89已提交；新隔离API8890/App5201参数与快照展示通过；概况73244c0复测127秒失败；d1767ff复测37秒、无AC仍超时；b49b7a0概况25秒/5只读调用、无失败无AC，10秒目标未达；连续回归中，整体未验收。业务目标和部分解释仍有局限，详见验证记录；不将终态完成写成全部结论正确。

旧回答修复3e3bbfb已归档并移出当前推进图；恢复引用与未验收状态见[版本台账](VERSION-CONTROL.md#全部分支进展)。

[自主研究首期实施计划](../superpowers/plans/2026-10-12-autonomous-agent-first-delivery.md)：人工候选092acb6与隔离部署同源，三专项及概况API验证已结束，结果页面可打开。研究记录a3895a5及参数追溯388fa89已提交；新隔离API8890/App5201参数与快照展示通过；概况73244c0复测127秒失败；d1767ff复测37秒、无AC仍超时；b49b7a0概况25秒/5只读调用、无失败无AC，10秒目标未达；连续回归中，整体未验收。稳定local-dev和demo不变，完整证据、重置与整体回归等尚未完成。

[自主研究能力基线](../reviews/2026-10-12-autonomous-agent-capability-baseline.md)：静态契约事实、未实证能力、历史整体回归与耗时记录要求。

[首期接口落点](../superpowers/specs/2026-10-12-autonomous-agent-design.md#首期接口落点源码核对后的提案)：研究持久回执、Pi实际上下文、既有结果投影及证据关联；标明可复用基础与待核对接法。

[自主研究统一设计](../superpowers/specs/2026-10-12-autonomous-agent-design.md)：五概念、单指令与必要追问、四类展示、证据与授权；含已验证基础实现和未完成范围。

[Pi研究链路验证](../reviews/2026-10-12-autonomous-agent-pi-research-verification.md)：7df7180的实际Pi离线传输、压缩/恢复、回执与上下文检查；不代表业务验收。

故障结果交付已列为优先契约：见[统一设计](../superpowers/specs/2026-10-12-autonomous-agent-design.md)和控制图M10。3f2f111保留受限回答，完整恢复与部分证据交付尚未完成。

[当前展示契约](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#当前前后端展示契约收敛草案)：正式回答／执行过程／计算结果／推演证据为现行名称，覆盖早期命名提案。

[展示关联D20](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d20正式回答与推演证据的展示关联命名已确认机制提案)：正式回答／执行过程／结果明细／推演证据；结论到证据、结果和调用的结构化关联。

[证据命名D19](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d19证据命名与避免流水账用户纠正)：采用“证据”；按结论/检查项组织，与按时间排列的执行过程分工，避免重复流水账。

[结构化表达D18](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d18结构化依据与客观简明表达用户明确要求)：技术追溯保留，三类依据以字段和事实为主，中文借鉴ASD-STE100简明原则。

[四类展示D17](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d17回答执行过程结果明细与验证依据展示提案)：回答、执行过程、结果明细、验证依据；长ID退入技术详情，业务验证必须有真实数据。

[执行展示融合D16](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d16任务展示与已有工具调用展示融合设计提案)：保留用户认可的工具链交互，在同一过程补任务含义和结果关联，不新建重复展示。

[单条主线与追问D15](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d15单条指令主线与最小多轮连续性用户明确优先级)：完整完成一条指令为首要交付，兼顾澄清、结果追问和条件补充；不扩展多研究管理。

[前端对话设计D14](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d14前端智能体对话操作设计提案)：复用现有展示，明确提交、停止、模型绑定、断线恢复和结果语义；需与实际协议核对。

[首期整体设计D13](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d13首期整体设计收敛与实施前验证工作提案)：五概念的复用/增量、最小闭环和实证要求；仍在设计阶段。

[可解释性与人在回路D12](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d12可解释性与人在回路用户建议纳入核心设计)：证据审计贯穿五概念，自动仿真与方案生成、人工采纳、真实执行隔离；不要求本轮全部实现。

[行动策略与进展评估D11](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d11行动策略与进展评估器设计提案)：选择依据、三类检查、结束与停滞，同一主循环完成；五概念工作提案已齐备，接口与实证仍待收口。

[实验工作台D10](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d10实验工作台的最小职责设计提案)：可组合授权能力和真实结果记录；复用dev，无固定工作流引擎。

[研究上下文D09](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d09研究模型与笔记的保存和上下文接入设计提案)：现有存储可复用，研究视图及受控更新待设计实现；验证真实读回和恢复。

[五概念最小协作D08](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d08五概念的最小完整协作收敛提案)：统一此前设计，单一主循环、可用研究记录、既有执行能力；未实现。

设计约束：统一五概念、保持简洁；整体能力接受三样例验证，不按样例倒推专用实现。详见[设计讨论开篇约束](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#设计缺口与讨论顺序)。

[dev接入设计D07](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d07dev接入结构与领域方法供给设计提案)：单一Pi主循环、研究状态与领域方法供给；仅设计，四项实现前缺口待确认。

[架构边界D06](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d06长期通用架构与首期验证范围用户已明确)：当前dev起步，demo仅作体验参考；长期通用框架，三个问题只作首批验证集。

[本轮边界D05](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d05本轮展示与执行时间边界用户已明确)：复用demo调用链，S01为用户确认的现有基线；重点是S02/S03业务逻辑与合理耗时，不扩展展示工程。

[工作节点与观察反馈D04](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d04自主工作节点与观察反馈契约)：局部目标、真实动作、观察、策略与评估、停止及进展；契约提案。

首版聚焦[三条原始业务指令](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d03三条单次请求的业务交付契约)：IEEE39 OPF、N-1缓解与mv_oberrhein双停运综合研究；详细口径与性能待验证。

用户明确首个自主研究交付为一次复杂指令闭环，详见[设计讨论D02](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md#d02一次复杂指令的优先交付目标)；完整跨轮管理后续展开。

[PR #16](https://github.com/uukuguy/capstone/pull/16)交付自主智能体讨论文档；[详细设计讨论](../superpowers/specs/2026-10-12-autonomous-agent-design-discussion.md)保留实现级提案，运行版本不变。

[自主智能体演进讨论](VERSION-CONTROL.md#自主智能体演进讨论)：已确认方向、职责图、统一分支建议和待定细节；讨论完成前不改运行实现。

统一分支已获实施授权；b73c4f4记录失败观察并在结果面板展示失败项。当前实施及待验收范围见
[实施计划](../superpowers/plans/2026-10-12-autonomous-agent-first-delivery.md)，包含用户指定的五条整体回归和耗时目标。
ec913ac补齐准入失败续行、请求留存及轨迹关联；整链追溯入口与业务验收仍在实施。
展示新增已确认约束：全局覆盖与原任务细节追问，详细契约见统一设计和任务5，U09仅表示设计状态。
54f6f13完成原任务记录分页验证；U09更新为记录接口已通过，App追问仍未完成。
a77e180接入前端原任务身份与分页校验；概览/追问交互尚未完成。

2026-10-12用户撤回未稳定回答增强；当前[稳态恢复记录](KNOWN-ISSUES.md)与
[活跃检查点](RESUME-NEXT-SESSION.md)记录新dev基线收口与两分支适配；实际七轮业务整体未通过。
历史整体筛查通过不能替代人工回归；[版本控制图](VERSION-CONTROL.md)登记回退范围。

[回退与真实回归报告](../reviews/2026-10-12-pre-closure-rollback.md)：30a3ecb已部署同源；
七轮真实业务保留失败，整体未验收。原候选与运行数据保留，独立意图识别继续。

[选择性补回验证](../reviews/2026-10-12-selective-ui-and-answer-restoration.md)：82b243c
补回三动作小窗、普通轻量问答与最终消息分离；两轮真实专项通过，整体验收未重做。

[dev恢复基线收口](../reviews/2026-10-12-dev-recovery-baseline.md)：用户批准合入dev及两分支适配；
PR #14双平台通过并合入6ff7094，local-dev同源；两分支适配已推送。首次普通误路由失败保留，已知业务问题继续开放。

[Pi分支适配](../reviews/2026-10-12-pi-dev-baseline-adaptation.md)与
[Research Model适配](../reviews/2026-10-12-research-baseline-adaptation.md)分别登记代码修正和计划修正。

dev默认开发集成主线和main发布主线均启用轻量保护：PR与两平台Actions检查、0审批，禁止强推和删除；main副本为发布快照。详见[组织设计](../superpowers/specs/2026-10-11-dev-integration-design.md)、[实施计划](../superpowers/plans/2026-10-11-dev-integration.md)和[版本台账](VERSION-CONTROL.md)。

[迭代门禁与旧 CLI 退出计划](../superpowers/plans/2026-10-11-retire-grid-cli.md)：513a35e已实现并审查门禁拆分；PR #10两平台CI通过，约32/26分钟并已合入main。用户已撤销grid-agent CLI兼容要求；共用运行模块迁移尚未完成。

[正式回答与运行窗口本地验收](../reviews/2026-10-11-task-answer-local-dev.md)：2473e48已在local-dev规范重建，三角色同源、注册案例和浏览器检查通过；PR #9已通过精确双平台CI并合并，人工回答验收及云发布单列。

[任务理解与正式回答实施清单](../superpowers/plans/2026-10-11-task-answer-closure.md)：契约、识别、领域覆盖与实际应用验收分别留存；当前源码2473e48，本地技术验收通过，主线集成及人工产品验收另列。

[研究模型演进计划](../superpowers/plans/2026-10-11-research-model-evolution.md)：B2为撤回增强的历史记录；feat/research-model现接入dev6ff7094并完成依赖适配，R1尚无代码；R0受控实验保留参考。R1研究模型、R2多轮连续性、R3自主推演、R4能力补齐、R5应用验收。未部署。

| File | Purpose |
| --- | --- |
| [项目推进控制全景](PROJECT-OVERVIEW.html) | 每次更新调用 ui-ux-pro-max 并重新排版验收；默认一屏，图标与标题同排，四环境绑定实际来源；demo 紧急修复直连已验收主线来源。Pi 包含业务数据共享，已合并分支退出主图。 |
| [线上到本地的功能范围核对](DEPLOYMENT-FUNCTION-SCOPE.md) | 功能与分支归属；近期需求遗漏核对和统一前端命令设计范围；现用执行账本仍必要，旧存储优化实验归档。 |
| [Git 分支清理记录](GIT-BRANCH-CLEANUP.md) | PR #6/#9/#10/#11合并后关闭分支名；本地目录、精确归档引用和日志保留；旧存储及R0实验未提交记录保留。 |
| `CURRENT-STATE.md` | Structural project snapshot. |
| [多线版本控制](VERSION-CONTROL.md) | 用户批准PR14合入dev为新开发基线并对齐两实验分支；local-dev6ff7094同源，首次新专项失败与单项重试通过分别保留；精确CI通过，PR13已撤回，demo及云端未变。 |
| [完整回答与结果复用修复验收](../reviews/2026-10-12-answer-and-result-reuse.md) | 原始三轮专项的Authority/工具/浏览器独立核对与逐阶段耗时；整体另验，历史失败不删除。 |
| [GitHub Issues 与后台 AI 修复设计](../superpowers/specs/2026-10-10-github-issue-automation-design.md) | 已授权命令驱动实施：截图/短句反馈，默认 cloud-demo；当前 AI 会话中文处理，定时/无人值守与额外模型调用延期。 |
| [GitHub Issue automation plan](../superpowers/plans/2026-10-10-github-issue-automation.md) | 命令驱动工具已合入 main；小石 App 和独立发布已核对，后续准备 PR 待集成；无无人值守或额外模型调用。 |
| [并行开发运行准备](../superpowers/plans/2026-10-10-parallel-development-readiness.md) | 基础包已合并并关闭分支；当前计划同步了回答增强/Pi 归属、持续 PR 授权和独立发布验收；控制图与实际执行文件双向对齐。 |
| [Issue 工具验收](../reviews/2026-10-10-issue-workflow.md) | 源码审查、测试及真实 App 沙箱检查范围；区分已集成工具、待配置身份和未修复产品反馈。 |
| [Issue 处理规程](../architecture/capstone-issue-workflow.md) | 统一规范：当前 AI 会话按命令处理反馈、中文沟通、专用分支、双线验收及发布状态；不启用无人值守。 |
| [2026-10-11 Issue processing](../reviews/2026-10-11-issue-processing.md) | 独立App身份已核对；#1/#5待发布验收，#2/#3回答包处理中，#4受控诊断后等待一个触发信息；保持Issue打开，无云发布或付费模型调用。 |
| [Baseline alignment plan](../superpowers/plans/2026-10-10-version-baseline-alignment.md) | Preserve experimental development, restore minimal demo foundation and verify local-only alignment. |
| [Baseline alignment verification](../reviews/2026-10-10-version-baseline-alignment.md) | Main and isolated local-demo alignment passes full/local gates; six role identities match; experimental branches and user data retained; cloud unchanged. |
| `KNOWN-ISSUES.md` | Open business-compilation identity/coverage risks, answer-quality and startup/recovery issues; model preparation acceptance is separate from overall and baseline acceptance. |
| [Demo outcomes and failure diagnostics](../superpowers/specs/2026-10-10-demo-outcome-and-diagnostics-design.md) | Approved design, implemented on main and demo baseline; remote acceptance pending. |
| [Demo outcome repair plan](../superpowers/plans/2026-10-10-demo-outcome-and-diagnostics.md) | Incident implementation and two-baseline verification; remote release remains gated. |
| [Demo outcome repair verification](../reviews/2026-10-10-demo-n1-repair-verification.md) | Confirmed defect, tested repair sources, local rebuild and explicit remote acceptance limits. |
| [Demo N−1 repair release](../reviews/2026-10-10-demo-n1-release.md) | Withdrawn 2ea2266 release and verified rollback to ed2524f; image identities, registered cases and retained evidence. |
| [Framework answer correction and local demo](../reviews/2026-10-10-framework-answer-local-demo.md) | Infrastructure and evidence-preservation checks pass; manual goal-based answer acceptance fails. Concise conclusions, scenario relevance and response scale require design. |
| [Shared intent and goal-answer draft](../superpowers/specs/2026-10-10-shared-intent-and-goal-answer-design.md) | 同一回答增强包；稳定源码接入核对已补，实施契约待收口。旧防护复用；来源接纳与普通/专业路由均不证明用户目标完成。 |
| [Business workspace and agent resources](../superpowers/specs/2026-10-09-business-workspace-agent-resources-design.md) | Pi 实验分支拥有既有角色/skills/MCP 原型及完整业务上下文与数据共享的剩余设计；计划 Tasks8–9 已对应落实，未宣称新功能完成。 |
| [Business workspace verification](../reviews/2026-10-09-business-workspace-resources-verification.md) | Offline gates, actual SDK/MCP/Authority integration, retained-resource checks and explicit acceptance limits. |
| [Intent/context local verification](../reviews/2026-10-08-intent-context-local-verification.md) | Semantic node, shared history and real Pi loopback evidence; actual model answer acceptance remains open. |
| [Common execution projection](../reviews/2026-10-08-execution-context-projection.md) | Shared ordinary/business boundary and general evaluation; diagnostic prose does not enter execution context. |
| [Conversation context design](../superpowers/specs/2026-10-08-capstone-conversation-context-design.md) | Active ordinary-answer design: shared dialogue, native Pi configuration and semantic request understanding; keyword routing rejected. |
| [Intent/context implementation plan](../superpowers/plans/2026-10-08-capstone-intent-context.md) | Approved design execution: interchangeable intent node, shared history, Pi adapter, hosted wiring and actual answer acceptance. |
| [Pi reference isolation design](../superpowers/specs/2026-10-08-pi-reference-isolation-design.md) | Deferred CONV-04 draft; actual Capstone ordinary-answer assessment and acceptance must precede review or implementation. |
| [Demo sleep and App version acceptance](../reviews/2026-10-08-demo-sleep-and-app-version.md) | Accepted ed2524f/demo tag; exact cloud promotion, preserved history, per-page idle recovery and explicit live-traffic cold-timing limits. |
| [Cloud-dev App version acceptance](../reviews/2026-10-08-cloud-dev-app-version.md) | Accepted ed2524f/cloud tag; visible exact build identity, local dirty metadata, runtime alignment and release gates. |
| [Cloud-dev automatic sleep acceptance](../reviews/2026-10-08-cloud-dev-automatic-sleep.md) | Accepted 8b88af9/tag: real sleep with an open idle page, 20s first entry, 11s recovery, preserved workspace and small retained resource cost; demo unchanged. |
| `JOURNAL.md` | Append-only durable event log. |
| `RESUME-NEXT-SESSION.md` | Current recovery baton. |
| `INDEX.md` | This discovery index. |
| `DECISIONS.md` | Active architectural decisions, including PyPSA pack boundaries and the multi-binding direction. |
| `climb/research-tree.md` | Generated Workstream C inventory reference-domain scoring summary; resume-load. |
| `climb/session-state.json` | Active Workstream C hypothesis and deterministic next action. |
| `c2-github-repository-intelligence-candidate.md` | 🟡 historical GitHub C.2 candidate; PyPSA pack selection now governs the next approved design direction. |
| `2026-09-05-capstone-design-code-review.md` | Optimization evidence baseline R01–R13; current remediation status belongs to the canonical plan. |
| `2026-09-22-capstone-review.md` | 企业业务能力包视角的历史评审基线；后续修复和验收见优化计划。 |
| `2026-09-22-capstone-opensource-research.md` | 企业业务 API/framework 的历史选型研究；HTTP 测试实验已完成，其他候选仍待独立决策。 |
| `capstone-scope-cleanup-backlog.md` | 超纲实现清理候选、实际位置与风险；静态产物缺口已由7e9b10c补齐，当前不执行删除。 |
| `2026-10-01-capstone-m5-verification.md` | M5 provider-free 双 Authority 验证、完整 release 门禁与 clean-wheel 工件闭包。 |

## External execution anchors

- [Deployment answer acceptance repair](../superpowers/plans/2026-10-11-deployment-answer-acceptance.md): active priority; overall and update sample sets, captured real Provider failures, preacceptance repair and strict handoff states.
- [Deployment samples](../../validation/deployment/README.md): durable8-case/10-turn overall corpus and separate repair-specific criteria. Local-dev beef6d4 passed9 business turns plus1 professional routing turn, independent business review and actual waiting/window checks. [Local verification](../reviews/2026-10-12-lightweight-routing-local-verification.md) records phase timings and execution limits. Generation research and complete opening-time prewarm remain deferred; PR13 remains draft, awaiting manual validation. No new baseline. Local checks do not wait for CI.
- [Recognition latency repair](../superpowers/plans/2026-10-11-recognition-latency.md): user-observed19.48s recognition and absent waiting feedback; independent recognition configuration, bounded reset process reuse, timing and standard overview. f348993 source checks and review pass; exact local rebuild/Provider/browser acceptance pending. No opening-time cross-process prewarm claim.

- [Autonomous research experiment](../superpowers/plans/2026-10-11-autonomous-research-experiment.md): user-approved experimental branch; two-layer knowledge/workflow/verification plus research nodes, IEEE39 four-case corpus, not deployed.
- [Asterion P7 reference](../reviews/2026-10-11-asterion-p7-reference.md): local source and recorded public results; reusable research mechanisms, Capstone boundary adaptations and evidence limits.

- [Task understanding and formal answer implementation](../superpowers/plans/2026-10-11-task-answer-closure.md): approved package implementation; contract, recognition, Pack coverage and actual local-dev acceptance remain distinct gates.

| File | Purpose |
| --- | --- |
| [Ordinary conversation local verification](../reviews/2026-10-08-ordinary-conversation-local-verification.md) | Empty-tool Capstone session, exact selection, loopback Pi RPC, real local capability prompt, current-source rebuild and complete offline release gate; external Provider and remote acceptance not tested. |
| [Capstone conversation completion](../superpowers/plans/2026-10-07-capstone-conversation-completion.md) | Active delivery worklist for gaps in the approved Thread/Harness/Web conversation contracts; CONV-01 covers one-time history folding and individual toggles. |
| [Opened grid models and current model](../superpowers/specs/2026-10-08-thread-open-models-design.md) | CONV-06 approved design: persistent nonempty model collection, current pointer, compact control and atomic close; locally implemented and verified. |
| [Opened models local verification](../reviews/2026-10-08-thread-opened-models-local-verification.md) | Durable model controls, closed-model historical replay, zero-tool access and instruction timestamps/grouping; independent review and cloud acceptance pending. |
| [Model work resume](../superpowers/specs/2026-10-08-thread-model-work-resume-design.md) | Approved continuation rule: stable member identities, saved per-model Context, separate historical views and restored camera; supersedes fresh Context on every switch. |
| [Model work resume plan](../superpowers/plans/2026-10-08-thread-model-work-resume.md) | CONV-06 continuity implementation and local acceptance plan. |
| [Model work resume verification](../reviews/2026-10-08-thread-model-work-resume-local-verification.md) | Local saved Context continuity, scoped follow-up history and actual browser camera/member checks; remote acceptance pending. |
| [Instruction model label verification](../reviews/2026-10-08-instruction-model-label-local-verification.md) | Instruction-owned model short names beside timestamps; historical association and responsive actual-entry checks. |
| [Folded answer cue verification](../reviews/2026-10-08-folded-answer-cue-local-verification.md) | Muted preview text and down/up toggle arrows with unchanged control geometry on desktop/mobile/landscape. |
| [Return current task verification](../reviews/2026-10-08-return-current-task-local-verification.md) | Explicit topology return restores current task and locates its own instruction while retaining draft, focus and folding. |
| [Thread history folding local verification](../reviews/2026-10-07-thread-history-folding-local-verification.md) | Revised history actions, new-answer full display, scroll/draft/copy checks and local acceptance; independent review and cloud release remain pending. |
| [Thread settings and instruction focus](../reviews/2026-10-07-thread-settings-and-instruction-focus-local-verification.md) | Unified useful Settings, subtle folded states and top/bottom instruction focus; current local browser/tests evidence and review/release limits. |
| [Thread system notices](../reviews/2026-10-07-thread-system-notices-local-verification.md) | Message-area errors and recovery, preserved reading focus and drafts; local checks with bounded client-notice limits. |
| [Distinct notices and global history anchors](../reviews/2026-10-08-thread-notice-and-global-anchor-local-verification.md) | Neutral system notices, stable consecutive history actions, no-op preservation and instruction/window-boundary checks; local acceptance only. |
| [Answer icon beside CAPSTONE](../reviews/2026-10-08-thread-answer-header-icon-local-verification.md) | Compact shared label/icon row, hover hints, retained mobile target and stable instruction/focus checks; local acceptance only. |
| [Compact grid-tool settings](../reviews/2026-10-07-thread-compact-grid-settings-local-verification.md) | Flat history/tool sections and public tool names; local UI checks, with unsupported all-off runtime explicitly blocked. |
| [Stable answer toggle](../reviews/2026-10-07-thread-stable-answer-toggle-local-verification.md) | Same-position collapse/expand, retained control focus and corrected final-reply scroll bound; supersedes forced instruction navigation. |
| [Registered tool/history menu correction](../reviews/2026-10-08-thread-tool-menu-local-verification.md) | All registered tool groups visible with compatibility reasons; two history actions without redundant heading/hint rows. |
| [M1–M11 status audit](../reviews/2026-10-07-capstone-m1-m11-status-audit.md) | Bounded milestone closures, deferred successor work and review-record limits; M6 must not be reopened from stale checkboxes. |
| [Capstone core evolution discussion](../superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md) | Secondary research notebook; resume on user request or offer a reminder at an important boundary. Its open questions do not set delivery order. |
| [Thread client recovery design](../superpowers/specs/2026-10-05-thread-client-recovery-design.md) | Approved draft/receipt recovery and Context-bound rollback verification; cloud-dev acceptance precedes manual review and demo promotion. |
| [Network element name consistency](../reviews/2026-10-06-network-element-name-consistency.md) | Shared pandapower diagram/tool names, PyPSA name checks and visible type prefixes; local acceptance and historical replay limits. |
| [Topology name release](../reviews/2026-10-07-topology-name-release.md) | Exact-source cloud-dev and demo release checks for canonical names, display prefixes and hover status. |
| [Thread client recovery plan](../superpowers/plans/2026-10-05-thread-client-recovery.md) | Active local repair and cloud-dev acceptance work; demo deployment waits for manual acceptance. |
| [Thread recovery verification](../reviews/2026-10-06-thread-client-recovery-and-cloud-dev-verification.md) | Draft/receipt recovery, lease/configuration diagnostics and a1f028d cloud-dev evidence; normal Provider configuration blocks manual acceptance. |
| [Harness local verification](../reviews/2026-10-06-harness-provider-configuration-local-verification.md) | Shared188abe3 Provider configuration, adapter ownership guards and passing local App/release checks. |
| [Harness cloud-dev verification](../reviews/2026-10-06-harness-cloud-dev-verification.md) | All four services run188abe3; Provider-free checks pass, while missing worker credentials block ordinary AI conversation and manual acceptance. |
| [Thread session management plan](../superpowers/plans/2026-10-06-thread-session-management.md) | User-requested session controls, recovery and bounded conversation history; local App acceptance precedes cloud-dev. |
| [Thread session management verification](../reviews/2026-10-06-thread-session-management-verification.md) | Local and a2dbb5d cloud-dev acceptance for session controls, drafts and actual deployment recovery; ordinary Provider conversation and human demo approval remain blocked. |
| [Direct Thread entry and cloud Provider recovery](../reviews/2026-10-06-open-thread-and-cloud-provider-verification.md) | Current no-login entry, header correction and real PyPSA handoff/admission repair; local-first acceptance and cloud-dev Provider recovery evidence. |
| [Capstone optimization plan](../superpowers/plans/2026-09-05-capstone-optimization.md) | Canonical delivery record, including completed reviewed A–E work; strict JSON extension and OP13 deferred, no automatic C.2 or cleanup. |
| [Framework guide historical plan](../superpowers/plans/2026-08-31-capstone-framework-guide.md) | Completed architecture, bilingual README, and agent-contract documentation work. |
| [PyPSA pack and multi-binding design](../superpowers/specs/2026-09-25-pypsa-multibinding-domain-packs-design.md) | Approved four-pack boundaries, Network model reference, and multi-binding contract. |
| [Multi-binding implementation plan](../superpowers/plans/2026-09-25-multi-binding-application-implementation.md) | First code work package and later PyPSA activation order. |
| [PyPSA model-library design](../superpowers/specs/2026-09-26-pypsa-model-library-and-business-cases-design.md) | Official model asset boundary, runnable case scope, and presentation contract. |
| [PyPSA model-library implementation plan](../superpowers/plans/2026-09-26-pypsa-model-library-and-cases.md) | Local model library and scripted-case acceptance; container and frontend work remains deferred. |
| [Capstone framework](../architecture/capstone-framework.md) | Layer contracts, current-run evidence and guide-access assurance boundaries. |
| [Agent interaction discussion record](../superpowers/specs/2026-09-29-agent-interaction-discussion.md) | 🟡 Active discussion record for capstone-agent/harness, Thread/Run/Turn/Case, Pi/DSH runtime paths, model context, events, and three-pane App redesign; not an approved implementation spec. |
| [Web Thread UI primary contract](../superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md) | Approved Web conversation contract: typography density, assistant-ui structure, Markdown answers, activity summaries, Composer behavior, and visual acceptance gates. |
| [M6 Harness and Case design](../superpowers/specs/2026-10-02-capstone-m6-harness-case-design.md) | Approved Harness ownership, sequential Case execution, recovery, and public projection boundaries. |
| [M6 Harness and Case implementation plan](../superpowers/plans/2026-10-02-capstone-m6-harness-case.md) | Task-by-task implementation and verification plan; the lightweight Task 9 boundary closeout is recorded in the current-state and resume documents. |
| [M9 PyPSA result/Web projection](../superpowers/plans/2026-10-04-capstone-m9-pypsa-result-web.md) | PyPSA power-operation result projection into the shared Thread/Web contract; topology-specific presentation remains deferred. |
| [M10 PyPSA topology provider](../superpowers/plans/2026-10-04-capstone-m10-pypsa-topology-provider.md) | Registered-model topology projection into the unified Thread model pane. |

## Climb storage and configuration

| Path | Purpose |
| --- | --- |
| `climb/config.yaml` | Versioned Workstream C scoring policy, protected-path baseline, gate weights, and release closure. |
| `climb/session-target.md` | Machine-readable 100% Workstream C inventory reference-domain target. |
| `climb/hypotheses.yaml` | Append-only Workstream C inventory hypothesis state. |
| `climb/runs.csv` | Append-only Workstream C local score ledger. |
| `climb/calibration.json` | Local/online calibration state. |
| `climb/pending-lb.json` | Pending external score state; empty for local-gate mode. |
| `climb/adjudicator-log.md` | Append-only hypothesis decision record. |
| `climb/research-tree.json` | Machine-readable generated research tree. |
| `climb/_archive/2026-08-28-workstream-b-package-extraction/` | Completed Workstream B package extraction climb snapshot. |
| `climb/_archive/2026-08-18-full-capability/` | Completed 2026-08-18 full-capability climb session snapshot. |

- [Domain Pack diff and content audit](../reviews/2026-10-11-domain-pack-sample-contamination.md): scope/completion/evidence repairs, generic instruction cleanup and continuous-overview repair; 8-case/10-turn overall and separate repair criteria under deployed verification.

- 2026-10-13 c9387ee: 短路参数与实现失败诊断已验证，未部署；恢复入口见 RESUME-NEXT-SESSION.md。

- 2026-10-13 8bf9ada: 同版本三链已审计、内容未通过；取消附加回答生成已提交，未部署。
# Verification update: 3ea9cd8 App421 tests pass; backend a439210 isolated; task interpretation remains unaccepted.
- 2026-10-13: VERSION-CONTROL tracks fixed5173 candidate24d9a32 and authorized cloud-dev deployment; prior cloud acceptance remainsed2524f.
- 2026-10-13 cloud-dev trial: [deployment receipt](../reviews/2026-10-13-cloud-dev-autonomous-trial.md); fixed local5173/API8767 and restored original Thread.

- 43f1e73：执行目的随工具参数进入步骤记录，领域参数隔离；真实部署验证进行中，未合并或发布。

- ef6ae84：执行UI紧凑右侧耗时、目标/步骤分离、工具条锚定；ui-ux-pro-max实页检查通过；准入横幅移除，证据门禁保留。

- 57a7b2a：白底辅助面板、结果/证据字号收紧、电网图一次性命令；85App/类型与浏览器通过，local-dev规范重建ready。
2026-10-14 当前：bf7a309首批有来源场景图层已实现，契约/前端/真实派生检查通过，local-dev重建中，尚未完成三个样例图例实测。a3d3be3专用潮流字段及中文错误原因已部署；29daa7d单条原因与原始诊断入口在Vite生效。模型打开/关闭生命周期待修。详见[图层设计](../superpowers/specs/2026-10-14-network-result-annotations.md)及RESUME。
