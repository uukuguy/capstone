# Live Session Checkpoint

> Updated: 2026-10-16. Session remains active; this is not a final handoff.

## 当前恢复点

- 以本条为准：PR #36已通过Linux/macOS CI38881419651并正常合入dev d8fe6e2738639161525a66bce7a8f0a9588e2872，完整合并树等同受检711f06a8。Task 1接缝与基线已验收；下方等待CI记录已过时。实施分支已关闭。根目录在docs/shared-foundation-control完成控制图、报告、计划收口；该文档PR通过后返回dev，并将两条应用准备分支非强制快进到dev。
- 下一实施为Task 2：WorkBinding/TaskContext、Profile装配、Thread v2协议/CAS/存储与前端最小入口成套推进。Task 3仍负责生产完整工具装配、许可/租约与持续执行。不可把已验收接缝当作生产闭环；两应用线保持准备状态。旧恢复点仅保留本轮过程参考。

- 最新恢复点：PR #36精确head711f06a8，CI38881419651的Linux/macOS仍在运行。待通过后正常合入dev；不要把工作区控制图改动加入此PR以免重启产品检查。当前dev及两条准备应用分支仍为5f3fd741。
- local-dev已从711f06a8规范重建，实际运行源码等同62f44366；API与双worker同ae5adedf镜像，各1142打包文件一致，App62f44366/dirty=false，ready及既有Thread浏览器入口通过。下方abf来源为历史记录。make check-integration通过，新企业前端闭环仍未实现。
- 未提交控制改动包括报告、台账/INDEX、图与tools/project_overview/template.html。共同基座节点优先置于dev右侧，按用户最新要求居中整组并均衡两侧留白；1920/1280检查15节点20边，无重叠、交叉、穿卡和溢出。合并#36后用独立控制PR收口，再快进两条准备应用分支；勿丢失当前改动。

- 当前实施：feat/shared-execution-baseline，代码62f44366。14项真实SDK接缝测试与101项Python基线通过，独立评审问题已修复。等待集成门禁/PR；生产装配、许可与前端闭环未实现。见2026-10-16-shared-execution-baseline.md，勿将测试接缝当作应用交付。

- 用户确认：main保存阶段完整对话应用，短期小修；dev承接企业自主执行研发。Pi不再作为长期产品分支。
- PR #30已合入main cf72393bd6377d1de11d02a93728cdaa746a75d4；发布范围f209fb1，CI38861900687双平台完整release通过，合并树一致。
- PR #31已合入dev db16718445fb33ea242310076dd068b90b1996a6；CI38865540607双平台通过，合并树与受检abf2f797完全一致。
- 根目录已返回dev并快进。Pi工作树detached abf2f797，全部数据保留；本地/远端长期Pi分支已关闭，refs/archive/20261016/feat-pi-skills-integration保留来源。发布分支也已关闭。
- local-dev按规范从abf2f797重建；API与双worker同d6acc8c镜像，各1139个实际打包文件同源，general-pi健康，旧Thread页面可读。原五个数据卷及会话/事件/工件计数不变。App源码身份abf2f797，repositoryRevision跟随根dev；后端构建来源不能仅因合并而改写。
- 用户e2交付包、19173、local-demo及两云端环境不变。本轮零Provider调用。
- 收口完成：控制PR #32经双平台CI38870266248通过后合入fc3bdada；图示修复PR #33随后合入fccdefca（双平台CI38871600375通过），根目录dev与origin/dev一致，控制分支已关闭。图形14节点/19边在1280和1920宽度无重叠、连线交叉、穿卡及横向溢出，保留dev第一父节点主线；链接、symlink、diff和doctor通过。下一任务为下述统一执行Task 1，不重复已完成合并。

## 验证与恢复依据

- 新报告：docs/reviews/2026-10-16-main-dev-convergence-verification.md。
- 本地check-pr与make test全部目标、check-integration均通过；后端1304、App512、Kernel628、旧CLI997、E2E39。
- 初次macOS CI超时分类失败已由abf2f797修复；65专项和独立审查通过，随后精确双平台CI成功。旧失败不删除。
- 本机代理/Provider环境影响采用进程级隔离。Docker Hub首次认证超时，使用已有代理重试规范构建成功。
- 运行回执：runs/main-dev-convergence/；.capstone-agent/convergence-local-identity.json。
- 根原37文件备份：/tmp/capstone-pre-convergence-root-work.tar.gz；恢复stash a91a148494f520e973f5d63158916b42a5df6773保留，不自动删除。
- Pi工作树仅可能保留本次journal追加；不要删除工作树、忽略的运行资源或var数据。

## 后续研发入口

- 两条应用分支从dev6c0b0ae7创建，PR #35双平台通过后与dev同步至5f3fd741并推送；尚无业务实现。基座不足，当前先在dev推进最小前后端闭环；应用线只做A1/B1准备，按能力依赖启动。阶段交付必须有可运行前端入口供人工观察，具体见三线阶段计划。

- 最新已接受决定：共同基座同时服务对话和企业执行，通用修复增强在两个入口验证受影响行为。三工作包为共同基座、对话维护、企业执行；后者含业务分析与报告、模型分析与决策。简单对话不强制研究或文件成果；dev集成不等于对话发布。设计与计划已通过PR #34合入dev 6c0b0ae7，双平台CI38875364352通过；尚未实施。

- 活动计划：docs/superpowers/plans/2026-10-16-enterprise-unified-execution.md。
- 对话应用旧计划改为交付和维护记录，不是新一轮大升级清单。
- 下一实施切片：Task 1完整宿主guard与持续Pi桥验证；本次收口没有实现新循环、无模型v2协议或新工作台。
- 复用既有Thread、事件/命令/租约、Harness、ResearchController、专业执行和投影；不新增第二套自主组织框架。
- Demo1/Demo2只是外部实例。输入由协议定义；不写业务指标、专用Capstone数据接口、固定流程或封闭视图枚举。
- 仅对受影响动作与声明施加约束；缺失输入、unknown外部动作、可选检查和未就绪附件不阻断独立工作。
- 保留专业Authority边界、当前运行证据及必要持久化要求；通用Pi输出不自动成为专业证据。
- 设计依据：enterprise-design-final、enterprise-protocol-decisions及enterprise-progress-constraints-review；核心讨论笔记保持独立，不自动变成实施任务。
