# Capstone M6 Harness 收敛与 Case 执行设计

**日期：** 2026-10-02
**状态：** Approved design for implementation planning
**范围：** Harness 内部收敛、应用层 Case 执行抽象、顺序批处理实现、交互投影和兼容层门禁

## 1. 目标

M6 将 `capstone-agent` 的 Harness 变成唯一的新应用编排入口，并把用户可见的
Case 从旧 App 的隐式批处理升级为可恢复、可审计的应用层 CaseExecution。

M6 只实现顺序执行策略 `sequential_batch`，但不把 Case 等同于 Batch，避免后续
交互式、审批式、分支式案例被当前实现锁死。

## 2. 架构边界

```text
Capstone application
  ├── CaseCatalog -> CaseDefinition
  ├── CaseExecutionService
  │    └── CaseExecutionStrategy
  │         └── SequentialBatchExecutor (M6)
  ├── CapstoneHarness
  │    ├── Thread / Run / Turn / Attempt orchestration
  │    ├── ControlResolver / CommandExecutor
  │    ├── HarnessPiClient
  │    └── HarnessDSHClient (unavailable shell)
  └── ThreadSnapshot / EventPage projections

grid-agent / pypsa-agent
  └── transition adapters
       ├── Authority and Domain Pack assembly
       ├── model catalog / runtime factory
       └── legacy compatibility entry points
```

### 2.1 所有权规则

- `capstone-agent` 拥有 Case catalog、CaseExecution、策略选择、批处理推进和应用投影。
- Harness 拥有 Thread、Run、Turn、Attempt、命令生命周期、运行时事件归一化和恢复语义。
- Domain Pack 拥有语义工具、策略、结果投影和结果/证据 admission。
- Authority 拥有模型、revision、计算、结果数据集和证据。
- Case 不属于 Kernel、Domain Pack 或 Authority；它们只看到普通 Turn、Attempt 和已 admission 的结果。
- `grid-agent` / `pypsa-agent` 不再拥有新 Case、Thread、TUI、Profile 选择或运行时切换能力。

### 2.2 包拆分策略

M6 先在 `capstone-agent` distribution 内完成 Harness 和 CaseExecution 收敛，
不立即拆出独立 `capstone-harness` distribution。公共接口和依赖方向稳定后再评估拆包，
避免过早拆包造成循环依赖和迁移噪声。

## 3. 概念模型

### 3.1 CaseDefinition

CaseDefinition 是应用层用户可见的案例定义，包含：

- `case_id`
- `case_version`
- `display_name`
- `description`
- 可接受的模型/实现族约束
- 有序 `CaseStepDefinition` 列表
- 每步的用户可读标题、指令文本和稳定摘要

CaseDefinition 在执行开始时由 CaseCatalog 读取并冻结为 `case_revision`；后续目录更新
不会修改已创建的执行。

### 3.2 CaseExecution

CaseExecution 是一次案例执行实例，不是新的运行时或事实来源。它绑定：

- `case_execution_id`
- `thread_id`、`run_id`
- `case_id`、`case_version`、`case_revision`
- `strategy_id`、`strategy_version`
- 创建时的 `model_context_id`、模型 revision 和 `selection_revision`
- 当前步骤、步骤状态、时间和错误信息

M6 的策略为：

```text
strategy_id = sequential_batch
strategy_version = 1
```

公共身份使用 `case_execution_id`。`batch_id` 只允许作为顺序批处理策略的内部别名或
兼容投影，不能成为 Thread 核心身份。

### 3.3 CaseStep

每个 CaseStep 绑定一个普通 Turn，并记录：

- `ordinal`
- 指令摘要
- `turn_id`
- `latest_attempt_id`
- 当前状态
- 最终回答引用、result refs、evidence refs
- 运行时长和错误码

一个步骤最多有一个活跃 Attempt。重试使用原 Turn 创建新 Attempt，失败 Attempt 永不覆盖。

## 4. 执行策略和恢复

### 4.1 SequentialBatchExecutor

`SequentialBatchExecutor` 是 M6 唯一的 `CaseExecutionStrategy`：

1. 冻结 CaseDefinition、ModelContext 和 Profile selection。
2. 创建 CaseExecution 和第一个 Turn。
3. 等待当前步骤的 Attempt 进入终态。
4. 只有步骤成功提交后才创建下一步 Turn。
5. 所有步骤成功后提交 `case_execution_completed`。

Executor 只能调用公开 Thread service/command 接口，不得直接调用 Pi、DSH、Domain Pack、
Authority、WorkerSession 或 ledger 私有写入方法。

### 4.2 状态

```text
created -> running -> waiting_step -> completed
                         │
                         ├── blocked
                         └── cancelled
blocked -> running       # 仅在显式重试成功或安全推进恢复后
```

- `blocked` 表示当前步骤失败、外部中断或恢复连续性不足，未执行的步骤不会自动推进。
- 用户显式执行 `cancel_case_execution` 后进入终态 `cancelled`，不把用户停止伪装成失败。
- Worker lease 丢失、事件连续性破坏或 Attempt 运行时死亡时，立即进入 `blocked`。
- M6 不实现 Attempt 内恢复；恢复只能通过新 Attempt 重试。
- 已完成步骤的答案、结果和证据保持可读，但失败步骤的部分输出不进入下一步上下文。
- CaseExecution 取消后为终态，不自动继续。
- CaseExecution 失败不会关闭 Run；Run 仍可接受新的普通 Turn 或新的 CaseExecution。

### 4.3 上下文锁定

CaseExecution 创建时固定 ModelContext、模型 revision 和 Profile selection revision。
执行期间模型切换和 Profile 选择命令返回 `case_context_locked`，不隐式延迟、不静默生效。
用户必须取消/完成当前 Case 后再切换上下文。这样保证同一 Case 的步骤在一致模型和能力集合上执行。

## 5. 公共命令和事件

### 5.1 命令

所有命令进入现有 `CommandEnvelope`，使用 expected event sequence 和 idempotency key。

#### `start_case_execution`

```json
{
  "case_id": "...",
  "case_version": "...",
  "strategy_id": "sequential_batch",
  "expected_event_seq": 12,
  "idempotency_key": "..."
}
```

服务端校验 CaseCatalog、Thread/Run 状态和当前 ModelContext，成功后创建 CaseExecution。

#### `retry_case_step`

```json
{
  "case_execution_id": "...",
  "step_ordinal": 2,
  "failed_attempt_id": "...",
  "expected_event_seq": 31,
  "idempotency_key": "..."
}
```

只允许重试当前阻塞步骤，且必须匹配其失败/取消/中断 Attempt。

命令会原子地创建新的不可变 Attempt 并重新执行当前步骤；旧 Attempt 和事件保持不变。
新 Attempt 成功后由策略继续推进，失败则再次进入 `blocked`。

#### `cancel_case_execution`

运行中只设置当前 Attempt 的取消请求；不删除已完成步骤，不把取消显示成失败。

#### `resume_case_execution`

只用于编排器在当前步骤已经由新 Attempt 成功提交、但在创建下一步骤前发生安全中断的
执行。服务端必须验证当前步骤的成功 Attempt、事件连续性和固定上下文，再继续创建下一
步骤；它不会恢复旧 Attempt，也不会从任意中间状态猜测恢复点。

### 5.2 事件

事件进入同一个有序 Thread event ledger：

```text
case_execution_created
case_execution_started
case_step_started
case_step_completed
case_execution_blocked
case_retry_created
case_execution_cancelled
case_execution_completed
```

每个事件需要携带适用的：

```text
case_execution_id
case_id / case_revision
strategy_id / strategy_version
step_ordinal
turn_id / attempt_id
model_context_id / selection_revision
```

事件不携带 raw Authority objects、DataFrames、Provider secrets、隐藏推理或无限文本。

## 6. 应用级交互投影

M6 把“功能实现与用户交互显示一起设计”作为硬约束。每个重要应用概念必须同时定义：

- 生命周期状态；
- 当前可执行动作；
- 禁用原因；
- 关联模型/Run/Turn/Attempt/Profile/证据边界；
- 默认显示内容和详情内容；
- 失败、重试、重连或重新开始方式。

### 6.1 Case 交互

空闲时显示案例名称、版本、步骤数、当前模型和“开始案例”。

运行时在对话区附近显示紧凑进度：

```text
案例执行中 · 1 / 3
✓ 打开 IEEE-39 模型
● 执行交流潮流       运行中 12.4s
○ 按线路负载率排序
```

阻塞时将错误和动作附在具体步骤下：

```text
步骤 2 未完成 · 运行被中断
已保留步骤 1 的回答和证据。
[重试此步骤] [停止案例]
```

完成时显示“案例已完成 · N / N 步 · 总运行时长”，并提供案例过程查看入口。
取消时显示“案例已停止 · 已完成 N / M 步”，不伪装为失败，也不自动恢复。

内部 ID 和 `strategy_id` 默认隐藏；诊断详情可查看。不可用动作显示为禁用并说明原因，
不能通过消失按钮制造未知状态。

### 6.2 全局应用概念投影要求

`ThreadSnapshot` / `EventPage` 的投影必须能表达：

| 概念 | 必须表达的交互语义 |
| --- | --- |
| Thread | 连接、重同步、当前 Run |
| Run | 是否接受新 Turn、是否关闭、runtime mode |
| ModelContext | 当前模型、revision、切换状态 |
| Profile selection | 已启用、待生效、锁定原因、来源 |
| Turn | 指令、路由、回答状态 |
| Attempt | 状态、耗时、重试动作 |
| Tool | 名称、来源包、阶段、结果状态 |
| CaseExecution | 步骤、进度、阻塞原因、动作 |
| Result/Evidence | 提交状态、来源 Run/Attempt、查看范围 |

客户端可以自由排版，但不能根据内部 ID、事件顺序或错误码自行猜测用户文案和按钮。

## 7. 扩展 SPI

应用层定义两个协议：

```python
class CaseDefinition(Protocol):
    case_id: str
    case_version: str
    display_name: str
    model_constraints: object
    steps: tuple[CaseStepDefinition, ...]

class CaseExecutionStrategy(Protocol):
    strategy_id: str
    strategy_version: str

    def create_execution(
        self, definition: CaseDefinition, context: PinnedCaseContext,
    ) -> CaseExecution: ...

    def advance(
        self, execution: CaseExecution, terminal_step: StepOutcome,
    ) -> StrategyDecision: ...
```

M6 的 `SequentialBatchExecutor` 提供固定顺序、单活跃步骤和显式阻塞/恢复语义。
不实现通用 DAG、循环调度、并行步骤或调度器。

未来策略可以包括：

- `interactive_checkpoint`；
- `approval_gated`；
- `branching_workflow`；
- `replay_evaluation`。

这些策略共享 CaseDefinition、CaseExecution、Thread/Turn/Attempt 和事件账本，不改变
Thread 核心身份模型。

## 8. 兼容层硬门禁

`grid-agent` / `pypsa-agent` 可以提供 assembly、模型目录、runtime factory、旧 CLI 和旧
worker，但禁止：

- 定义 CaseExecution、BatchExecutor 或新的 Thread 状态；
- 直接调用 Harness runtime；
- 直接写 Thread ledger；
- 增加模型切换、Profile 选择、TUI 或 Web 编排；
- 通过私有模块绕过 Capstone 公共应用接口。

边界检查必须确认：

1. 新 Case/Harness 实现只存在于 `capstone-agent`；
2. 兼容包只提供 assembly 和历史入口；
3. CaseExecution 的创建和推进只能由 Capstone application service 完成；
4. 删除兼容包后，Case、Thread 和 Harness 核心代码不需要移动或重写。

## 9. M6 非目标

- 不实现多 Run、Run 分支或跨 Run 比较；
- 不实现真实 DSH runtime；
- 不实现 WebSocket 人在回路控制；
- 不实现通用 workflow/DAG engine；
- 不重做现有三栏 Case App；
- 不把 Case 事实、结果或证据移入 Kernel；
- 不为兼容层增加新业务功能；
- 不在本阶段完成最终 TUI/TGP 客户端。

## 10. 验收定义

M6 只有同时满足以下条件才算完成：

1. `capstone-agent` 提供 CaseDefinition、CaseExecution 和 Strategy 接口；
2. `SequentialBatchExecutor` 能按步骤创建 Turn，并等待当前 Attempt 提交后再推进；
3. 失败、取消、中断进入阻塞/终态，重试创建新 Attempt，历史事件不变；
4. ModelContext 和 Profile selection 在 CaseExecution 中固定，切换被明确拒绝；
5. 所有 Case 命令具备幂等、期望序列校验和稳定 receipt；
6. ThreadSnapshot/EventPage 能表达案例进度、动作、阻塞原因和关联上下文；
7. Web/TUI/CLI 至少有一个公共投影回归套件验证相同状态语义；
8. 兼容层边界断言阻止新 Case/Harness 实现外泄；
9. 现有兼容 stdout、Authority admission、当前 Run 证据约束和全部既有 release 门禁保持通过；
10. M6 独立代码评审完成，Important/Critical findings 清零。
