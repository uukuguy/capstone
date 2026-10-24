# 企业执行协议：迁移、命令生效与检查来源

## Unified debug capacity deployed locally — 2026-10-19

Canonical rebuild /tmp/unified-debug-capacity-rebuild.log exited zero and
readiness passed. API and all workers use backend
627d9f23aa22713e38d40d508893c104792ac44827035f8578bd9afc07fafda1; native uses
8ffb64702ea206e9312e02ee45b7d98b2dce7f0a44e3370bc05b666a2001ef77. Public
runtime capacity and the five container environments all report mode debug.
The effective profile has 146 limits. Receipt:
ROOT/outputs/research-round-efficiency/unified-capacity-debug/deployment.json.
Post-rebuild scoped cleanup exited zero, receipt
IMPL/.capstone-agent/cache-maintenance-20261019-194724-54523.log.

The native container has an actual memory limit of 2147483648 bytes (2 GiB),
PID limit 512 and /tmp size 512m. These are externally enforced startup limits,
separate from application JSON processing budgets; debug cannot intercept a
kernel OOM before it occurs. Do not confuse task-workspace tmpfs with /tmp.

In this local debug deployment, exceeding a configured bound must cause an
immediate typed fatal interruption before trimming, fallback, skipping, retry
or reconnect. Diagnostics retain dimension, actual, effective limit, source and
location. Normal-mode hard/soft grades remain distinct. Scoped source and offline
checks are verified; this is not closure of every repository limit or proof of
a new research outcome. Detailed scope: /tmp/unified-limits-app-implementation.md.

No new live research acceptance, clean report, parallelism or performance gain
is claimed. The prior limited generation (263.895887 s, 31 parent responses,
zero children), explicit-review transport failure and saved products remain
historical evidence. The 350.524 s / 41-response reference is unchanged. Root
will return to the user's existing browser; this control update starts no task.
Local dirty source remains based on HEAD 15980389; no commit, tag, cloud or demo
release is implied by image verification.

### Historical source and deployment checkpoints

## 2026-10-19 accepted requirement: unified runtime bounds and debug hard interruption

All runtime upper bounds belong to the existing application-capacity.json
registry, with adequate defaults and application-initialization overrides.
The effective public profile includes mode normal or debug and a fingerprint
that includes mode. Upload/storage, transfer, parsing, preview, history windows
and model-processing budgets are separate dimensions; a polling window is not
a task deadline. Identity, ownership, hash, permissions and CAS remain strict.

In normal mode retain explicit hard/soft grades: soft thresholds can warn,
replan, page, defer or provide honest limited delivery without failing the whole
Attempt. In DEBUG mode every exceeded bound must immediately raise a typed,
fatal interruption before truncation, eviction, fallback, skip, reconnect or
retry. Do not reduce debug to warning-and-continue or hide the exception in a
broad catch. Preserve dimension, actual, effective limit, configuration source
and location through API and App diagnostics. Existing normal failure fields
remain compatible; debug adds mode, fatal, effective, source and location.

The App/API scoped implementation is source-only pending parent integration:
mode bootstrap, typed remote 413 errors, no capacity reconnect, guarded history/
projection/cache/preview windows, upload metadata/chunk/file checks, product
selection and continuation overflow, configurable product scan/input catalog
windows. This does not close the repository-wide audit or prove the worker/SDK
terminal interrupt, deployment or live behavior. Root coordinates those owners.
No App font/layout, model, Provider or deployment change is authorized by this
documentation section. Earlier browser replay remains unverified.

Scoped offline checks: 237 App tests across nine files passed; final pending-
request/history seam checked separately (overlapping scope), tsc passed. API
checks: 97 passed / 35 PG-dependent skipped; scoped pyright has zero errors.
No live PostgreSQL or Provider acceptance is implied. Audit and owned-file
manifest: /tmp/unified-limits-app-implementation.md and
/tmp/debug-capacity-owned-files.txt. Remaining repository-wide rows are explicit
in that report, including view-only excerpts and bootstrap alias provenance.

Root also changed source-only Compose/operator defaults to
CAPSTONE_NATIVE_MEMORY_LIMIT=2g, CAPSTONE_NATIVE_PIDS_LIMIT=512 and
CAPSTONE_NATIVE_TMP_SIZE=512m, with local.env.example documentation and quiet
Compose validation. These are external OS-enforced startup limits, distinct
from JSON processing budgets; debug cannot intercept a kernel OOM before it
happens. A future rebuild receipt must record effective deployed values. Current
deployment remains backend 785bb222 / native 1a2f5619 until that receipt.


## 2026-10-19 accepted decision: hard limits, soft thresholds and error recovery

Limits must explicitly declare whether they are hard or soft. A soft threshold
is an observation, warning or replanning trigger; it must not fail the whole
Attempt. Preserve explicit effective values and their application initialization
configuration. Do not fix a lifecycle error merely by inflating fixed seconds.
A transport request timeout or polling window is distinct from a task deadline.
A missed polling window does not prove the task stopped or permit duplicate work.

- Advisory diagnostics and local-check failures: record the actual error, impact
  and unresolved items; continue independent steps and allow honest limited delivery.
- Recoverable transient reads or idempotent receipt requests: resume the same
  request safely, preserving task identity, frozen input, prior work and receipts.
- Core blockers: stop the affected dependency and return usable partial products
  when their integrity and ownership remain valid. Do not claim blocked work passed.
- Hard permissions, identity, CAS and required persistence remain strict. Failure
  is fatal when the required contract cannot be met; do not weaken these checks
  to obtain a nominal completion.

This is an accepted error-policy requirement, not proof that every existing
limit or transport path already implements it. The 350.524 s reference is a
progress/investigation checkpoint, not a hard task timeout.


状态：实现契约补充。Work账本及复用前端已通过PR #48合入dev d86cc4ef；专业Work的生产Claim与资源固定已在本地应用分支b703e37b接通，尚未合入dev。独立ApplicationProfile快照、中性Claim、无模型正常发送、其余控制命令和持续执行仍待实现。延续现有Thread服务、事件账本和自主组织机制。参见[定稿与实现校准](../../reviews/2026-10-17-enterprise-design-alignment.md)。
本文件解决上一轮协议缺口，不新增业务指标、固定流程或通用执行前的任务编译。

2026-10-18补充（用户确认）：长程研究的任务寿命与通信状态必须分离。状态读取、启动回执、研究回执的短暂超时只能进入连接恢复，不能据此取消研究。重连核对原task_id、冻结请求和已提交修订，不重新执行任务或业务工具。只在用户停止、明确不可恢复错误或独立任务预算耗尽时终结；预算应显式、可核对，并保留恢复所需的上下文和制品。单次通信等待不是研究耗时上限。当前实现已补同一任务的通信恢复和幂等回执重放；跨进程丢失后的持续恢复、长程预算交互仍待验收。见[诊断与实测记录](../../reviews/2026-10-18-research-chain-repair.md)。

2026-10-18预算与错误补充（用户确认）：框架缺省预算必须允许应用配置覆盖，不能将框架常量当作所有任务的上限。生效值随准入请求冻结；超限及其他失败沿现有回答与事件链路持久化并如实送达前端。当前候选实现读取通用`CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS`（缺省600秒），企业研究可用`CAPSTONE_ENTERPRISE_RESEARCH_TIMEOUT_SECONDS`覆盖。进度使用确认游标分批传输，窗口容量不等于任务累计事件上限。失败回执新增`capstone-pi-task-result/2`，仅公开错误类别及阶段；继续读取旧版回执，不宣称旧版执行器能接管新版失败数据。跨执行器进程恢复仍是独立待验收能力。

## 1. 同一服务的新旧表示

现有客户端使用capstone-command/1、capstone-thread-snapshot/1及严格解析器。
它们要求模型上下文，不能直接接收无模型快照或未知字段。数据库加法迁移不等于wire兼容。

- 保留/api/v1/threads及其commands、events入口。请求头Capstone-Thread-Version选择1或2，
  缺省为1；响应回显版本，并使用Vary避免缓存混用。未知版本返回406，不修改任务。
  已有专业入口先用缺省v1，在成功响应可见回显后发送显式头，避免旧服务CORS白名单拒绝新增头。
  新Work入口显式请求2并要求响应回显2；不为探测重发写请求。新服务允许并暴露版本头。
- v2快照使用capstone-thread-snapshot/2；task_context含binding（thread_id/work_id/research_id）、goal_revision、snapshot_id、
  resource_refs及model_contexts列表，空列表合法。selected_model_context_id可空，不造默认模型。
  历史Run/Turn/Attempt、Thread游标、已有结果引用继续保留；专业投影由应用适配器解析。
- v2命令使用capstone-command/2，保留command_id、idempotency_key、thread_id、可选run_id、kind、payload。
  新增target（kind/id/expected_revision）。expected_revision是目标对象修订，不是Thread event_seq。
  v2只用对象CAS控制写冲突；流游标用于读取/补取，不因无关进展事件拒绝用户答复。
- v2回执沿用现有accepted/pending/rejected语义及accepted_event_seq，目标放target中；
  command.applied事件表示实际生效。语义候选schema中的applied状态不是wire回执枚举。
- 两版共用一个Thread event_seq。v2事件保留原外层身份，版本化payload增加work关联；
  从快照恢复或补取不重发命令。禁止为了旧客户端过滤事件而制造缺口或伪造序号。

Thread记录minimum_protocol_version。既有Thread保持1，新企业Thread为2。v2客户端可读取v1
并在应用适配器中展示旧记录；只有记录了显式Work关联的新任务才使用v2工作状态。
已有Thread第一次提交v2工作命令时，在事务中迁移最小版本并保存目标关联，不改旧证据。
若旧Attempt仍在执行，待其安全边界再迁移；迁移期间保留原命令回执，不启动第二个主Attempt。
35e014df切片对活跃Attempt或Case返回可处理拒绝，不自动安排延后迁移；完成后可显式重试。
鉴权后，已存命令的精确同键同载荷回查先于minimum_protocol_version门禁，返回原版本回执，
避免“v1提交成功但丢响应→其他客户端升级→原请求重试”丢失幂等恢复。
旧客户端的新写入或不兼容快照/事件读取返回409 protocol_upgrade_required，不返回空历史或假模型。
版本1客户端仍可访问未升级的历史Thread；版本2客户端可访问全部获准历史。

回退单位是经验证的前后端/协议组合。新任务数据不回滚删除；旧执行装配无法恢复的v2任务
保持原状态及成果，由支持v2的只读/恢复入口承接，不能声称旧客户端能完整接管。
这不要求维持两套组织循环；版本适配仅存在于应用输入输出边界。

## 2. 命令到现有控制面的映射

2026-10-17最新决定覆盖下方早期切片交互：新建任务即新会话，入口预选Profile，
发送通过一个原子命令接纳输入并接受真实执行；首次需要的Work由宿主在同事务建立。
不能由浏览器串联“保存成功→再启动”构造正常发送，也不向用户暴露第二启动步骤。
原子命令继续复用Thread账本、幂等键、事件游标和Attempt队列；具体wire随实现固定。
下方work_message/start_work记录已实现的内部接缝，不构成新应用的交互要求。

语义命令名在v2 wire使用下表snake_case名称，不直接传入v1的_identifier解析器。
workspace配置继续是资源控制入口，复用已有身份/幂等存储，不另建Work命令账本。

| 语义操作 | wire操作/归属 | 生效语义 |
| --- | --- | --- |
| message | work_message，Thread commands | 目标须明确为现有Work或new；新建Work由宿主分配身份，不猜文本相似度 |
| start | start_work，Thread commands | payload为空；对已有Work修订做CAS，固定本次目标和资源选择，原事务入队真实Attempt |
| goal.revise | revise_goal，Thread commands | CAS后保存新目标修订，边界应用并标记受影响依赖 |
| input.respond | respond_input，Thread commands | 保存答复、核对问题身份和目标版本，再按第3节继续 |
| pause/resume/cancel | pause_work/resume_work/cancel_work，Thread commands | 复用Attempt控制；pause/cancel接收不等于停稳 |
| action.resolve | resolve_action，Thread commands | 保存外部确认及来源，解开相关依赖；不直接重做副作用 |
| budget.increase | increase_budget，Thread commands | 验证主体权限与批准配置，修订预算；不默认恢复用户暂停的工作 |
| thread.rename/archive | 既有Thread管理操作的v2适配 | 改导航元数据，不取消工作或隐藏未决动作 |
| workspace.configure | workspace资源控制入口 | 对配置修订CAS；新增能力边界采用，撤销阻止相关新调用 |

命令幂等以现有主体/Thread/Idempotency-Key范围保存；同键同请求返回原回执，先于CAS。
不同载荷复用键被拒绝。Work/goal、Thread元数据、workspace配置各自使用对应修订，不能互用。
v1原命令保留旧语义；v2不靠send_ordinary/send_professional选择两个总组织循环。

### Work执行绑定切片

早期内部切片以`work_message`保存内容、`start_work`请求执行；新会话交互不使用这一两阶段流程。
刷新和读取不自动重复发送；正常输入统一改由上述原子输入执行命令接纳。
本片先连接已注册专业能力，内部适配既有自动路由和Attempt队列，不增加业务流程分支。
Work公开`latest_attempt_id`、`start_available`和`start_unavailable_reason`；可启动表示
当前资源及队列允许接收，不承诺Provider健康或任务结果。运行时失败沿既有事件及终结事务呈现。
无可用执行能力只保留任务与原因，不制造必然失败的占位Attempt。

接受启动后，回执target保留Work身份与本次turn_id/attempt_id。同一事务写入
`command.applied`的完整Work投影和既有Attempt接受事件；开始及终结事件携带对应Work身份和投影。
本片状态为ready/queued/running/completed/failed/cancelled/interrupted/blocked；
状态变更递增Work修订，只有目标变更才递增goal_revision。完成表示本次Attempt完成，
不能据此宣称全部业务结论已得到独立验证。完整暂停、输入等待和持续组织仍由Task 3实现。

启动接受时复制真实ModelContext中的enabled_profiles/selection_revision并持久化TaskContext。
Claim核对并消费同一快照；不增加另一份能力选择源。下一次显式启动可使用前次结果形成的
合法新模型修订，Work及研究身份不变。本片不声称已固定全部外部资源内容版本。

同片提供`cancel_work`（Work对象CAS，空payload），复用既有`attempt_cancel_requested`
及worker取消检查，不创建新的控制循环。宿主核对Work的latest_attempt_id就是当前Attempt；
取消其他Work不影响在运行的任务。接收后`cancel_requested=true`，状态仍为queued/running，
只有真实终结事务才清除请求并写入终态。界面沿用原停止组件，区分停止请求与停止完成。
重复请求使用原幂等身份；已排队但尚未领取时也不提前宣称停止完成。

Work输入完整性：宿主记录`consumed_message_count`，仅成功终结推进；启动接受、失败、取消
或失租不把尚未处理的补充标记为已消费。本次执行输入包含当前目标和全部未消费补充，
已完成轮次沿既有Work限定历史及研究状态恢复。超出既有单次输入边界时返回
`work_input_too_large`并保留原文，不抛服务器异常，不静默删除中间补充，也不把全部历史
永久拼入每次启动的输入。该计数是宿主恢复元数据，不是业务流程阶段。

## 3. 答复生效与继续执行

input_request记录request_id、work_id、goal_revision、问题来源、阻塞的依赖引用及状态。
问题可由用户资料不足或外部动作核对产生，不要求每个研究缺口都变成人工问题。

1. 接收答复时检查归属、问题仍开放、目标修订及资源引用；幂等重试返回原回执。
2. 在事务中保存答复。没有活跃Attempt时由Thread服务应用；有活跃Attempt时在安全边界应用。
   applied表示答复已成为任务上下文，不表示业务问题已被证明解决。
3. 格式/权限不合法只拒绝该命令并保留草稿；答复合法但资料仍不足则记录新观察，保留相关缺口。
4. waiting_input下合法答复生效即可转queued，按原单主Attempt、租约、授权和预算规则领取续接Attempt。
   不要求API先证明存在下一业务行动：恢复后的同一主会话理解答复，决定继续或重新等待。
   不在API中另开规划器，不设置资料齐全清单；合法答复仍不足时保存观察后按实际缺口再次等待。
5. paused下答复仅更新上下文并发applied，保持paused；用户resume后再排队。
   running下答复保持running；旧目标问题拒绝自动套用到新目标，返回修订冲突供重新关联。

新资料只解开实际依赖；已取消Work不因晚到答复复活。用户明确继续时创建新Attempt。
action.resolve只解除有来源支持的依赖，unknown关联及冲突行动在确认前保持隔离。
预算增加可使预算阻塞恢复，但不覆盖用户暂停/取消；是否恢复由原因与显式resume决定。

## 4. 检查来源及交付保证

复用获准资源注册和Action回执，不另建一个所有工具必须接入的检查平台。
检查调用与普通行动共用来源记录。宿主根据实际调用登记checker_ref（资源版本）、execution_ref、
input_refs、适用范围、结果和方法来源；模型提出检查但不能自签Authority或独立验证身份。

- 确定性只是执行方式。模型生成脚本的结果记录为自检，不能凭deterministic标签证明独立。
- 业务适用性由外部定义/专业Pack解释；应用只声明需要的保证及接受来源，不内置指标算法。
- 要求独立核验时，提供者声明独立方法及适用范围，宿主校验版本、执行身份和授权。
  来源声明及实际检查覆盖公开记录，不把注册行为本身当作业务正确性证明。
- 没有明确独立核验要求时，缺少独立检查器不阻断工作；交付标明已检查/未检查部分。
- 明确要求无法满足时，允许交付有用部分并保留未满足项，不把任务变为程序异常或无限重试。

检查回执与当前交付的目标/输入/产物版本绑定；过期只影响依赖该回执的声明。
伪造或越权回执拒绝接纳为依据，并返回可处理观察；必要答案/证据持久化失败仍不能宣称成功。

## 5. 最小实施验证

Task 2同时交付v2解析、版本协商、对象CAS及前端最小入口：旧专业Thread可读、无模型任务可建、
未支持版本不破坏历史、旧客户端访问升级Thread明确要求更新。
Task 3验证答复幂等、waiting自动排队、paused不自动启动、旧目标答复不串用及无关进展不触发CAS拒绝。
还需覆盖v1提交丢响应后升级再重试，以及无需预先判断可行行动就能领取答复续接Attempt。
Task 4验证自检不升级独立核验、过期检查仅影响相关交付，以及缺检查器时仍可提供有限成果。
发布前验证相同Thread只有一个主Attempt与事件账本，沿用既有专业业务回归，不以设计schema检查替代运行验证。
