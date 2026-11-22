# Capstone 执行连续性审查

审查日期为 2026-11-23，CST。源码是 `dev` 提交 `6898d487` 加本地工作区改动。
运行证据来自 local-dev，App 端口 5174，API 与三类 worker 共用镜像
`9eea3d68b01f`。源码观察和运行观察分别列出。Mission 计划省略字段的修复
已进入工作区，尚未进入该运行镜像。

审查覆盖普通 Instruction、会话 Goal、Mission 及其子会话的主要接纳、派发、
复盘、恢复和交付路径。运行观察为 PostgreSQL 只读核对和此前保存的回执。
本次不修改产品行为，不重放用户工作，不把静态审查当作端到端验收。

## 共同链路

| 优先级 | 路径 | 当前行为 | 需要处理 |
| --- | --- | --- | --- |
| P0 | Pi 接纳结果未知 | 接纳 POST 断开时缺少可证明的接纳结果。恢复状态读取把运行中、无终态和读取异常汇成 `unknown`。该 Attempt 保留运行占位，原会话的后续执行和 Mission 复盘可能无法接纳。 | 保存可核对的接纳状态与原请求身份。仅在证明原请求未接纳时恢复，沿用原身份。仍无法判定时显示具体状态，继续其他已准入工作。 |
| P1 | Worker 维护任务互相阻塞 | 一次维护循环顺序运行租约核对、Control、原生恢复、Mission 复盘和 Goal。前项抛错会跳过后项。在单槽和多槽路径上，维护异常也会跳过该轮正常领取。Goal 复盘有进展时，布尔短路会跳过同轮 Goal 初始规划。 | 分离各维护任务异常边界。每类任务使用独立、可追查的诊断，保留并行领取。停止重复尝试相同的确定性失败。 |
| P1 | 路由和执行准备 | 模型路由超时、能力上下文准备失败或执行器初始化失败会把当前 Attempt 结算为失败。只有配置支持的路径才回滚待应用的模型选择。 | 区分可重试准备与不可用能力。保持原指令和已冻结输入，记录受影响步骤，提供安全的原请求恢复路径。 |
| P1 | 输入冻结 | 一个不可读的默认会话材料会拒绝整条提交。一批显式成果、附件或 Authority 来源的冻结也有整批失败路径。Goal 隐式历史成果已经支持逐项记录并继续。 | 区分显式必需输入和自动带入的历史内容。自动带入项逐项记录。显式必需输入失效时，保留指令和可用资源，说明哪项工作依赖它。 |
| P1 | 恢复期成果交付 | 已有终态的原生结果在恢复时逐项保存文件。一个文件传输异常会退出本次恢复块，其他文件和正式答复不能在该次恢复中独立结算。 | 复用正常交付的逐文件结果，保留已保存制品，单独重试失败项。正式答复或强制证据持久化失败时不能宣告交付成功。 |

源码：[Pi 接纳与恢复](../../packages/capstone-agent/src/capstone_agent/pi_delegation.py#L1087)、
[终态观察](../../packages/capstone-agent/src/capstone_agent/native_owner_recovery.py#L74)、
[数据库恢复检查](../../packages/capstone-agent/src/capstone_agent/thread_service.py#L5575)、
[Worker 维护](../../packages/capstone-agent/src/capstone_agent/thread_worker.py#L329)、
[多槽领取](../../packages/capstone-agent/src/capstone_agent/thread_worker_capacity.py#L36)、
[执行准备](../../packages/capstone-agent/src/capstone_agent/thread_worker.py#L157)、
[输入冻结](../../packages/capstone-agent/src/capstone_agent/thread_materials.py#L268)、
[显式成果选择](../../packages/capstone-agent/src/capstone_agent/thread_products.py#L365)、
[恢复交付](../../packages/capstone-agent/src/capstone_agent/native_owner_recovery.py#L45)。

## Instruction

| 优先级 | 路径 | 当前行为 | 需要处理 |
| --- | --- | --- | --- |
| P1 | 执行中的追加 | 当前队列仅支持文字。附件、上下文选择、成果引用或技能会让整条追加在前端返回，草稿保留，后端没有后续接纳记录。 | 把带资料或授权要求的追加保存为下一条独立指令。到执行边界时按其原资源范围接纳。 |
| P1 | 追加队列容量 | 队列按当前 Attempt 计数，包含已撤回项。容量满或执行器没有队列协议时拒绝追加，没有跨 Attempt 的等待入口。 | 保留容量边界和幂等台账。达到本轮上限时持久保存新指令，按后续可用容量接纳。 |
| P1 | 原生文件交付异常 | 正常原生执行的一个文件异常会先记录诊断，其他兄弟文件仍可能保存。最后重新抛出首个异常，正式回复结算可能随之失败。网络传输失败另有重试路径。 | 分别结算各文件，明确本轮可交付内容及缺项。按已注册交付要求判断哪项会影响整体结果。 |

源码：[追加入口](../../packages/capstone-app/src/ThreadWorkAdapter.tsx#L560)、
[队列接纳](../../packages/capstone-agent/src/capstone_agent/instruction_queue.py#L12)、
[原生文件收尾](../../packages/capstone-agent/src/capstone_agent/delegated_runtime.py#L547)、
[逐文件保存](../../packages/capstone-agent/src/capstone_agent/delegated_runtime.py#L653)。

## Goal

| 优先级 | 路径 | 当前行为 | 需要处理 |
| --- | --- | --- | --- |
| P0 | 续接命令拒绝 | 调度器只计数已接纳回执。被拒的续接仍是 `ready`，原身份持久重复，可以长期显示等待执行。 | 将拒绝原因附到待执行步骤。可恢复时按新证据或新修订恢复。保持原请求幂等，避免同一失败循环。 |
| P0 | 复盘异常 | 复盘调用直接抛异常会提交空提案，然后暂停 Goal。已保存的下一步也停住。对模型返回了无效格式或引用的修复回退，未覆盖通信或执行异常。 | 分离复盘诊断和步骤调度。已经准入的后续独立步骤可继续。依赖复盘判断的步骤保留待核验状态。 |
| P1 | 初始规划失败 | Provider 超时、暂态故障和两次模型提案都无效最终都进入规划失败暂停。 | 区分暂态和确定性故障。有限重试暂态问题，保留用户目标和计划诊断。 |
| P1 | 单步终态 | 单步执行失败、失联后中断、取消或缺少回执会暂停整个 Goal。当前路径未判定后续步骤是否依赖该步。最后一次复盘反复格式失败可直接形成部分交付，未判断还有无补救工作。 | 保存失败步骤和可用成果。由 Goal 决策识别独立工作和补救工作。区分用户停止和内部故障。 |
| P2 | 预算与期限 | 预算或期限耗尽后保留待执行步骤。旧 Goal 不能用原预算直接继续。当前候选会检查初始及替换计划容量，不能处理所有旧版已超预算计划。 | 提前说明剩余预算和不适配的步骤。保留原期限和用户授权。为有权限的预算调整提供续接入口。 |

源码：[续接扫描](../../packages/capstone-agent/src/capstone_agent/goal_continuation.py#L5)、
[复盘扫描](../../packages/capstone-agent/src/capstone_agent/session_goal_plan.py#L419)、
[复盘接纳](../../packages/capstone-agent/src/capstone_agent/thread_work.py#L408)、
[初始规划](../../packages/capstone-agent/src/capstone_agent/session_goal_plan.py#L309)、
[单步终态](../../packages/capstone-agent/src/capstone_agent/thread_work.py#L184)、
[结算与预算](../../packages/capstone-agent/src/capstone_agent/goal_receipts.py#L154)。

## Mission

| 优先级 | 路径 | 当前行为 | 需要处理 |
| --- | --- | --- | --- |
| P0 | 计划就绪与资源接纳 | 就绪命令检查所有任务的执行绑定与设备。如果某一项不可接纳，健康独立任务也不能派发。计划编辑还可能因一个任务的设备引用错误整体拒绝。当前工作区已修复省略空依赖和重复条件的问题，资源接纳仍是整批。 | 分别记录任务的接纳结果和依赖状态。派发已准入且依赖满足的任务。阻止受影响项使用无效授权。 |
| P0 | 组织者复盘接纳 | 主会话仍被 Attempt 占用或绑定未就绪时，复盘保持待处理。错误有时只有 worker 日志。复盘失败、确认不可接纳、超预算或超期可设置组织者暂停。独立子任务可能随之停住。 | 可见地记录待处理原因和下次恢复条件。复盘可用性不得阻塞已经准入的独立任务。记录已持久化的前驱事实。 |
| P1 | 子任务失败与核验 | 子任务失败、未知或取消可先暂停 Mission，再排入复盘。缺少必需回执或文件时交付仍保存，但子任务标为失败。核验异常由同一 Mission 的外层捕获，可能跳过后续独立核验和派发。 | 隔离每个 Task 的交付核验。保留可用制品和具体失败原因。相应依赖继续等待有效回执，独立任务继续。 |
| P1 | 部分结算 | 没有当前可派发项时允许保存部分交付并暂停组织者。一个可修复的失败任务可能被当成结算条件。 | 结算前区分可补救、等待依赖及确实无可执行工作三种情况。保留当前计划版本和逐条件证据。 |
| P2 | 同会话多轮计划 | Mission 直办只能绑定一个单轮 Task，主会话内缺少由 Mission 持续驱动 Goal 多轮的路径。启动组织阶段复用普通 Instruction 界面。 | 区分组织、主会话多轮执行和委派执行。展示当前阶段，保持 Mission 主目标、决策和最终交付。 |

源码：[计划就绪](../../packages/capstone-control/src/capstone_control/mission.py#L129)、
[计划编辑和部分结算](../../packages/capstone-control/src/capstone_control/mission.py#L318)、
[复盘扫描](../../packages/capstone-agent/src/capstone_agent/mission_continuation.py#L326)、
[组织者状态](../../packages/capstone-control/src/capstone_control/mission_reviews.py#L137)、
[子任务结算](../../packages/capstone-control/src/capstone_control/service.py#L275)、
[交付核验与派发](../../packages/capstone-agent/src/capstone_agent/control_host.py#L174)。

## 运行证据

- 截至 00:46 的近 12 小时采样，Thread 命令表有 2 条
  `product_context_unavailable` 拒绝，来自同一会话。此前对该 Goal 的 11 个
  成果引用做了只读回放，新绑定器全部解析成功。
- 同一采样的两条原生 Attempt 各记录 38 次 `unknown` 恢复检查，仍占用
  各自会话的运行位置。76 条记录对应 2 个 Attempt。
- 最近两个用户 Mission 各创建一条组织 Attempt，随后收到取消请求。
  一条计划保存因缺少 `depends_on` 被工具校验拒绝，另一条未保存计划。
  两个 Mission 的派发数均为零。其中的取消记录可以证明收到取消命令，
  不足以说明是谁发起取消。
- 已验收的混合 Mission 保存了两类子任务、四项已满足条件和三份字节已核对
  的制品。它证明该路径可以完成，不能覆盖所有失败和重试组合。
  [验收会话](http://127.0.0.1:5174/enterprise?workspace=enterprise&thread=thr_b4c4ebd2bfd4e3b349c1)

计数只覆盖当前本机库和采样时段。工具参数错误可能发生在命令建立之前，
因此不一定出现在 Thread 命令表。

## 回归验收

1. 模拟 Pi 运送接纳回执前断开，分别核对已接纳、明确未接纳和未知状态。原身份只有一份有效执行。并行会话继续，原会话可见具体状态。
2. 一条指令带两个独立材料，其中一个读取失败。有效材料仍可用，引用失败有对应记录。必需材料缺失时，依赖它的工作保持待处理。
3. 在 Goal 的第 1 步后注入复盘网络错误以及确定性续接拒绝。已接纳的独立步骤继续，重复拒绝停止刷记录，界面能说明未推进的原因。
4. 一个 Mission 同时有可运行的 Instruction 子任务、Goal 子任务和不可接纳的 Task。独立项能运行，缺失授权和依赖仅影响相关项。
5. 在交付核验和 worker 维护中各注入一个异常。兄弟文件、其他 Task 和其他 Thread 保有自己的结果和推进机会。
6. 验证显式停止、权限校验、工作版本、原始字节摘要及 Authority 回执继续生效。没有必要证据时，保留未满足状态和可访问的已保存结果。

本次验收项均为后续回归。现有混合 Mission 验收与只读采样只证明上文列出的真实行为。
