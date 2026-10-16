# 企业执行协议：迁移、命令生效与检查来源

状态：实现契约补充。2d3f86c6接入现有服务的v1版本协商；v2及其迁移仍待实现。延续现有Thread服务、事件账本和自主组织机制。
本文件解决上一轮协议缺口，不新增业务指标、固定流程或通用执行前的任务编译。

## 1. 同一服务的新旧表示

现有客户端使用capstone-command/1、capstone-thread-snapshot/1及严格解析器。
它们要求模型上下文，不能直接接收无模型快照或未知字段。数据库加法迁移不等于wire兼容。

- 保留/api/v1/threads及其commands、events入口。请求头Capstone-Thread-Version选择1或2，
  缺省为1；响应回显版本，并使用Vary避免缓存混用。未知版本返回406，不修改任务。
  过渡期仅声明已实现的1，2仍返回406。浏览器先用缺省v1，在成功响应可见回显后发送显式头，
  避免旧服务CORS白名单拒绝新增头；不为探测重发写请求。新服务允许并暴露版本头。
- v2快照使用capstone-thread-snapshot/2；task_context含work_id、goal_revision、snapshot_id、
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
鉴权后，已存命令的精确同键同载荷回查先于minimum_protocol_version门禁，返回原版本回执，
避免“v1提交成功但丢响应→其他客户端升级→原请求重试”丢失幂等恢复。
旧客户端的新写入或不兼容快照/事件读取返回409 protocol_upgrade_required，不返回空历史或假模型。
版本1客户端仍可访问未升级的历史Thread；版本2客户端可访问全部获准历史。

回退单位是经验证的前后端/协议组合。新任务数据不回滚删除；旧执行装配无法恢复的v2任务
保持原状态及成果，由支持v2的只读/恢复入口承接，不能声称旧客户端能完整接管。
这不要求维持两套组织循环；版本适配仅存在于应用输入输出边界。

## 2. 命令到现有控制面的映射

语义命令名在v2 wire使用下表snake_case名称，不直接传入v1的_identifier解析器。
workspace配置继续是资源控制入口，复用已有身份/幂等存储，不另建Work命令账本。

| 语义操作 | wire操作/归属 | 生效语义 |
| --- | --- | --- |
| message | work_message，Thread commands | 目标须明确为现有Work或new；新建Work由宿主分配身份，不猜文本相似度 |
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
