# Capstone Control 与自主 Agent 设计

状态：用户已同意分层方向、会话内目标能力、两种协作模式，并确认组件名
`capstone-control`。用户随后已确认本书面设计；未实现、未验收。
所有者：capstone-control / capstone-agent / capstone-harness / capstone-app。
交付目标：dev；当前仅设计研究，不声明存在实现分支、PR 或部署。

## 1. 能力目标与边界

用户交付一个目标后，Agent 能在授权和预算内自主推进。长期工作可跨会话与
进程重启保留进度，等待事件后接续，并通过明确的成果与验收条件交付。

| 组件 | 所有权 | 不拥有的职责 |
| --- | --- | --- |
| capstone-app | 最终应用、工作空间、业务配置、用户授权与接受入口 | 推理循环、浏览器内持久调度 |
| capstone-control | 长期 Goal、Task、委托、任务板、触发、预算分配、接续和验收状态 | Agent 内部工具选择、专业事实 |
| capstone-agent | Thread、Work、上下文、独立可用的会话目标模式 | 跨 Agent 的共享任务状态 |
| capstone-harness | 单次 Attempt 的执行、事件、执行权限检查和回执 | 长期目标是否达成的最终判断 |

这是运行职责划分；Application → Domain Pack → Kernel → registered Authority
的业务所有权边界不变。Control 提供可复用的应用编排服务，由应用选择业务绑定、
权限与验收策略；Kernel 不新增电网业务语义。初期可共用后端进程和 PostgreSQL，
独立模块和数据所有权不要求立即部署独立服务。

## 2. 当前实现与命名兼容

源码基线：Capstone 4834ebe3；LoopX cac86bb。静态分析不等于运行验收。
当前 `thread_work.py` 保存 `works[].goal`、`goal_revision`、`revision` 和
`latest_attempt_id`；`TaskContext.goal_revision` 绑定目标版本。
`WorkBinding` 包含 thread_id/work_id/research_id，没有长期 goal_id。
普通会话也使用 Work，因此 goal 文本不证明已有自动目标接续能力。
`CapstoneHarness.run_attempt` 执行一次已领取的 Attempt。

新契约使用 Work objective 表达会话内目标，Goal 专指 Control 长期目标。
首期保留旧快照与旧字段读取；不批量重写历史数据。新旧命名转换应在版本化
协议边界确定性完成，不能依靠模型解释。若同一输入含冲突别名，明确拒绝。
现有 Work.status 不被静默赋予新含义；自动目标模式新增独立生命周期投影。

## 3. Agent 会话内目标模式

普通消息保持单次指令语义。显式 `/goal` 或等价结构化命令启用目标模式；
命令只是交互入口，核心能力可通过 API 使用，不依赖 App 或 Control 存在。

目标模式记录 objective、objective_revision、执行模式、状态、进度、待办摘要、
版本化成果引用、阻塞原因和预算。建议状态：ready、running、waiting、paused、
completed、failed、cancelled。状态 completed 表示委托交付通过执行侧检查，
不代表用户最终接受，也不自动关闭 Control Goal。

一次 Attempt 结束后，Agent 根据结构化进度提案及已保存成果决定下一步。
模型负责业务判断和下一步建议；代码检查身份、版本、预算、权限和状态转换。
允许继续、等待、完成或报告失败；缺少有效进度回执不得默认完成或无限重试。
等待释放执行资源，保存明确等待条件；预算耗尽进入 paused 并记录原因。
首次启用必须有有限的 Attempt 数和执行期限；额外 token/cost 限额仅在可可靠
计量时启用，不把未知消耗算作零。重试和失败执行仍计入相应预算。

自动接续在持久化边界安排新 Attempt，使用 operation_id、前驱 attempt_id 和
目标版本防止重复排队。沿用 Thread 当前单活动 Attempt 约束。用户新指令优先：
有执行时先中断或排队，在安全边界应用修改；旧版本完成事件不能推进新目标。
暂停与取消都阻止新执行；取消不删除成果。目标修改保留历史版本及原执行输入。

重启只从已保存的边界恢复，不承诺模型内存或任意工具调用的中点恢复。
外部副作用结果未知时沿用现有 unknown-outcome 保护，不自动重做。
现有故障恢复规则不能因开启 `/goal` 而放宽。

## 4. Control 与 Agent 的委托契约

长期 Goal 包含稳定身份、版本、目标、验收条件、预算和生命周期。
Task 是可分配工作单元，保存依赖、交付要求和协作权限。
ExecutionBinding 显式连接 goal_id、goal_revision、task_id、task_revision、
agent_id、thread_id、work_id 与委托代次；通过身份关联，不用目标文本匹配。
独立 Agent Work 无需任何 Control 身份。

拟定协议 `capstone-agent-delegation/1`：

- Delegate：operation_id、Task 版本、objective、交付要求、上下文引用、权限与预算。
- Observe：有序进度事件、Attempt 身份、已保存产品、阻塞和预算消耗。
- Steer/Pause/Cancel：带预期版本与幂等键的控制命令及确认回执。
- Deliver：委托身份、完成类型、成果及证据引用、未决事项、验证记录与消耗。

这些是逻辑操作名，不在本设计中虚构已存在的 HTTP 路由。
重复操作返回原回执；同一 operation_id 不同内容被拒绝。
Control 通过公开 Agent 契约接入，不改写 Thread/Attempt 内部账本。
每个 Work 只存在一个自动续行所有者：Agent 管会话内继续，Control 管委托
生命周期。Control 不在尚有活动委托时重复发起另一条“继续”。

Agent 自主选择工具和局部计划，同时接受预算、撤销、租约和权限约束。
Control 能观察进度与阻塞，无须等到最终完成才获知状态。
Control 验收 Task 后组织后继工作；Goal 达标、Agent 完成、用户接受分别记录。
需要用户最终接受的成果绑定具体产品版本，不能由模型文本代替。

## 5. 跨会话接续与触发

Goal 独立于 Thread；同一目标可复用会话，也可为新阶段创建新会话。
新会话只接收有界上下文包：目标版本、已完成事项、未决问题、产品引用、
来源、授权与剩余预算。原始资源按需读取，不复制全量聊天或大文件内容。
旧结果作为历史引用传递；当前运行证据仍须经应用与 Domain Pack 显式准入。

事件和计时器先写持久 inbox，由幂等消费安排委托；浏览器关闭不影响调度。
触发去重使用来源事件身份。周期监控产生独立检查任务，不能让已关闭 Goal
在无明确策略时重新运行。通知与正式成果分开，外发通过持久发送记录去重。

## 6. 集中委托与公共任务板

两种模式共用同一套 Task 契约和状态。集中模式指定执行 Agent；任务板模式
允许 Agent 按能力和授权选择就绪任务，并通过服务原子领取。
任务板按 workspace/Goal 授权范围共享，不是所有 Agent 的全局可写空间。

领取检查任务版本、依赖、领取资格、占用与写入范围；保存 owner、lease_epoch、
有效期和操作回执。Task 租约管理分配权，Attempt 租约管理执行权，两者以委托
代次关联。过期执行者不能提交当前结果。重新分配前必须处理旧执行的撤销或
副作用未知状态，不能仅因 Task 租约超时就并行重做。

Agent 可提出新任务、拆分、依赖调整和成果评审；是否直接提交由显式授权决定。
任务完成提交产品引用，由约定验收流程解除依赖。成果不可变版本支持并行读；
冲突修改应生成分支版本并显式合并。消息用于沟通，任务状态和成果回执才是事实源。
不共享隐藏推理记录、宿主凭据、原始 Authority 对象或未授权业务状态。

## 7. 分阶段交付与验收

| 阶段 | 可独立使用的成果 | 验收边界 |
| --- | --- | --- |
| A：Agent 自主目标 | 无 Control 也能执行 `/goal`，保留普通聊天 | 真实模型多次推进、成果交付、暂停恢复、预算停止、改目标、刷新及重启恢复 |
| B：Control 委托闭环 | 一个持久 Goal 组织多个阶段，通过公开接口委托 Agent | 新会话接续、版本绑定、成果回交、撤销、幂等与用户接受 |
| C：公共任务板 | 多 Agent 可领取独立工作并交付依赖成果 | 并发领取唯一性、租约失效防旧提交、写冲突、依赖和部分失败恢复 |
| D：持续运行 | 事件/计时器驱动接续与通知 | 重复事件、离线等待、重启后触发、无效唤醒抑制、预算与通知去重 |

A 是首个实施候选，B/C/D 保留为依赖路线，不同时启动。
每阶段使用真实模型、工具与保存产品验收；离线测试验证确定性状态与并发边界，
不能代替真实路径。只运行改动及直接消费者的本地检查。CI 每次仍需单独批准。
App 复用现有会话与企业工作空间，不新建简化聊天界面；前端接受须检查真实截图。

## 8. 源码依据与设计选择

LoopX `turn_driver/driver.py` 分开会话身份和执行结算身份；`codex_cli.py`
直接使用 exec/resume，因此 Control 不应强制要求下层先进入某种原生 `/goal`。
Capstone Agent 可同时支持单次执行和目标模式，委托明确选择其一。
LoopX `loop_controller.ts` 校验前驱回执与预算；`acceptance_authority.ts`
限定可信验收；`team_plan_authority.ts` 和 `task_lease_acquire_decision.ts`
提供团队任务提交与领取冲突机制。借鉴契约，不引入第二份 LoopX 状态账本。

本设计选择独立 Control，而非将长期控制堆入 App 或 Harness。组件名已获用户
确认，包目录与部署拆分随实施计划确定。详细设计已获确认，先制定 A 的可执行计划；
其余阶段在前置契约验证后分别细化，避免过早冻结全部分布式接口。
