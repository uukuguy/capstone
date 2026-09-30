# Capstone 主线重新基线设计

**状态：** Approved for M0 baseline; implementation remains split into the
milestones below.

**日期：** 2026-10-01

**范围：** 统一 Capstone 应用、Capstone Harness、Thread/Run/Turn/Attempt、
当前电网模型、pandapower/PyPSA 运行时、普通对话、自动路由，以及 Web/TUI/CLI
共同使用的应用边界。

**依据：**

- [Capstone Framework](../../architecture/capstone-framework.md)
- [Architectural Decisions](../../status/DECISIONS.md)
- [Thread Web UI 主合同](2026-10-01-capstone-thread-web-ui-main-contract.md)
- [当前状态](../../status/CURRENT-STATE.md)

## 1. 重新基线的原因

Thread 的持久化协议、Attempt 生命周期、事件投影、严格恢复和 Web Composer
已经有可用基础。最近的工作先推进了 Web 表面，应用级装配却仍停留在历史
`grid-agent.hosted` 路径，造成了三个可见错误：

1. Hosted Thread 实际只注册 pandapower，前端的 PyPSA 选项无法代表真实后端能力。
2. `send_auto` 只是命令名称，还没有产生可审计的 `TurnPlan` 或执行真正的路由。
3. 运行时使用专业电网上下文，却没有 Capstone 应用级普通对话策略，导致普通
   问题被模型自行拒答。

本文件重新固定应用装配和执行边界。它不增加新的业务工具，也不继续修改 Web
视觉层；后续实现必须先恢复正确的应用主线，再继续增加 Composer 控件和 TUI
细节。

## 2. 不可变的产品和架构判断

### 2.1 唯一应用边界

`capstone-agent` 是 Capstone 的唯一应用级宿主，负责：

- public `capstone` CLI 的 `tui`、`chat` 和 headless `run` 模式；
- Thread API、SDK、Web 和 TUI 使用的应用装配；
- Provider 设置、应用策略、模型目录组合、Domain Pack/Profile 选择；
- Capstone Harness 的运行时选择和公共事件投影；
- 读者可见的应用输出和兼容投影。

`grid-agent` 只保留冻结的 pandapower 兼容命令和必要的正确性、安全性维护。
`pypsa-agent` 以及历史上的其他 `*-agent` 命名只表示迁移中的内部适配或注册
组件，不是并列的用户应用。

### 2.2 四层所有权

```text
Application -> Domain Pack -> Kernel -> registered Authority
```

- Application 选择模型、Profile、Provider、公共客户端和投影。
- Domain Pack 负责语义工具、策略、指南、执行、结果准入、证据投影和领域状态。
- Kernel 负责中性的组合、上下文、生命周期、事件、轨迹、重放和框架 `core`。
- Authority 负责注册模型、修订、确定性计算、结果数据集和证据。

Pi/DSH 是低层 Harness runtime，不拥有 Capstone 业务语义；模型也不能直接
访问 Authority 内部或原始网络对象。

### 2.3 Thread/Run/Turn/Attempt

v1 仍然是一个 Thread 一个 Run。Run 不因 Turn 完成、模型切换、Profile 选择或
Attempt 重试而关闭。

```text
Thread
└── Run
    ├── Turn 1
    │   ├── Attempt 1a
    │   └── Attempt 1b (retry)
    └── Turn 2
```

每个 Attempt 冻结：

- Model Context 身份和 Authority revision；
- Profile selection revision；
- 工具目录和运行时快照；
- Provider/model；
- trace level、runtime mode 和 fencing/lease 身份。

丢失 Attempt 不允许半恢复。没有完整的 runtime/session、事件序列、Context
hash、工具状态和 Authority 幂等连续性证明时，Attempt 必须变为
`interrupted`，重新执行只能创建新的 Attempt。

## 3. 目标应用装配

### 3.1 Capstone 应用根

新增的主装配概念属于 `capstone-agent`，建议实现为：

```text
build_capstone_application()
├── ModelAuthorityRegistry
│   ├── pandapower adapter
│   └── PyPSA adapter
├── ModelCapabilityProfileRegistry
├── DiagramProviderRegistry
├── TurnRouter configuration
├── Harness runtime registry
│   ├── Pi
│   └── DSH placeholder
└── ThreadApplicationAssembly
```

`grid-agent.hosted` 和 `grid-agent.hosted_worker` 不再拥有上述组装逻辑。迁移
完成后，它们只能调用 `build_capstone_application()` 并保留兼容入口；新的 Web、
CLI、TUI 和 API 代码不得反向依赖它们。

### 3.2 统一模型目录

Thread 只消费中性的 `ThreadModelDescriptor`，其来源由应用选择的 Authority
adapter 决定。一个有效模型记录至少包含：

```text
public model id
authority model reference
exact revision reference
implementation family
display name
diagram provider identity
```

模型目录必须满足：

- 默认模型为 pandapower IEEE-39；
- pandapower 与 PyPSA 模型可以同时注册；
- 解析模型时返回精确 revision，不允许隐式 latest；
- 不把 raw pandapowerNet 或 PyPSA Network 放入 Thread snapshot；
- 模型切换准备失败时保留原 Context；
- 模型切换成功后创建新的 Model Context，旧结果和工具不自动成为当前能力；
- 真实 Authority 模型身份必须来自注册目录，不能继续用 UI 虚构的 `pypsa39`。

当前 PyPSA Authority 已有 `regional-six-bus`、`two-bus`、
`pypsa-example/scigrid_de` 等真实注册模型。Thread 对外使用的 ID 形式必须
在实现 M1 时统一确定，并同时解决现有安全标识校验对 `/` 的限制；不能用一个
不存在的模型名称掩盖这个问题。

### 3.3 Profile 和 Domain Pack 选择

模型解析得到 implementation family 后，Capstone Model Capability Catalog
解析兼容的 Profile。Profile 选择遵守：

- 精确版本和受信注册；
- 用户选择 Profile/Domain Pack，不能选择单个工具；
- 语义重叠不自动判定，工具调用必须显示来源和版本；
- 空 Profile 选择有效，表示普通对话、模型发现或上下文操作；
- 专业电网结论、工具调用、结果和证据必须有适用的启用 Profile；
- selection revision 在 Turn 边界生效，运行中的 Attempt 不被悄悄改变。

一个 Model Context 可以对应多个 Domain Pack，但每个 Pack 保留自己的执行、
Authority、结果和证据所有权。跨 Pack 数据必须经过显式、类型化、可重放的
application grant。

## 4. Capstone Harness 边界

当前代码中的 `capstone_agent.harness`、Thread worker 和 Thread service 已经
实现了部分 Harness 责任。后续应按以下逻辑边界收敛；是否拆成独立 distribution
属于后续工程决策，不改变职责。

### 4.1 Harness 拥有

- Attempt 运行和终态提交；
- Pi/DSH runtime client 的替换接口；
- 原生事件到 Capstone public event 的归一化；
- bounded progress、tool provenance、answer/result/evidence projection；
- cancellation、lease、fencing、retry 和严格恢复；
- TurnRouter/TurnPlan 的调用和路由事件；
- 所有客户端消费的公共事件 Envelope。

### 4.2 Harness 不拥有

- pandapower 或 PyPSA 语义工具；
- Authority 原始对象和凭据；
- Domain Pack 的结果准入实现；
- UI 自己解释出的模型、拓扑或数值；
- Pi/DSH 原生事件的直接外透。

`HarnessPiClient` 是生产 Pi 适配器，`HarnessDSHClient` 是预留空壳。二者对
Thread 暴露同一个 Harness runtime 协议；切换发生在 Harness runtime 与
Capstone Harness 之间，而不是让 Web/TUI 直接连接 Pi/DSH。

## 5. 普通对话和自动路由

### 5.1 普通对话默认打开

Capstone 应用配置必须提供：

```text
ordinary_conversation_enabled = true
```

普通对话默认使用当前 Provider 的通用知识能力，但：

- 不创建 Authority 结果或证据；
- 不把普通问题强行解释成电网问题；
- 没有实时来源时，对新闻、行情等实时问题明确说明数据边界；
- 不因当前 Model Context 是电网模型而拒绝所有非电网问题；
- 普通回答仍然经过正常的 Attempt、事件、时长和错误投影。

实时搜索若未来需要，必须作为受控的 Application/Domain capability 注册，不能
通过任意 URL、shell 或模型自由联网实现。

### 5.2 TurnRouter 和 TurnPlan

`send_auto` 必须进入 Harness 的 `TurnRouter`，而不是只改变命令字符串。路由
产物为最小可审计 `TurnPlan`：

```text
route
confidence (bounded)
capability hints
model context snapshot
source
plan revision
```

分类只负责路由。它永远不能授权工具、结果、证据或最终声明；这些仍由工具目录、
Domain Pack admission 和 current-run binding 硬门控决定。

路由错误必须可以：

- 重规划；
- 进入普通回答；
- 返回 `capability_required`；
- 保留可重放的 route/replan/hard-gate 事件。

### 5.3 Jev

Jev 是可插拔实验路由器，不进入 Kernel，也不进入 Model Capability SPI。部署模式：

```text
off | heuristic | jev_shadow | jev_active
```

默认 `off`。Run 快照记录模式、schema 和模型。Jev 失败必须使用 typed
`DecisionUnavailable`，并按 explicit ordinary/professional/unspecified 三类
走安全降级。Jev payload 只允许经过清洗的指令摘要、模式和上下文摘要，不包含 raw
network、tool/evidence data、secret、path、完整 transcript 或 hidden reasoning。

研发演示阶段使用 FakeDecisionRouter 和协议 fixture，不要求 Jev 凭据或标注数据集。
数据集验证属于将来的 promotion gate，不能阻塞基础 Thread 开发。

## 6. Web、TUI、CLI 共用表面

三种表面必须只通过同一公共语义工作：

```text
ThreadSnapshot + EventPage + CommandEnvelope
```

### Web

- 继续使用 `CapstoneThreadClient`；
- assistant-ui 只负责消息生命周期、Composer 和渲染骨架；
- 结果、证据、工具来源和模型状态只来自 typed public projection；
- Composer 当前保持单一自动路由输入；
- 后续的模型、Profile、trace、停止和重试控制使用 compact controls，不恢复
  大块“普通对话/专业分析”页签。

### TUI

- Textual 是 v1 缺省 TUI；
- 左侧当前模型图区，右侧 Thread 对话区；
- 每个不同 Grid Model identity 只有一个分页；
- 当前模型切换时自动切换当前分页；
- TGP 探测和降级只存在于 TUI 层；
- TUI 不复制 Authority、Domain Pack 或 Pi 内部逻辑。

### CLI

- `capstone` 是公共命令；默认进入 TUI；
- `chat`、`tui`、headless `run` 共用 Thread/Harness 语义；
- `run` 默认一个最终 JSON，`--events` 才输出 JSONL 事件；
- `grid-agent` 的旧 stdout 合同继续作为兼容适配器存在。

## 7. 电网模型图区

电网图区属于当前 Model Context 的 presentation projection，不属于案例本身。

```text
active_model_context
  -> model identity/revision
  -> registered diagram provider
  -> bounded NetworkDiagram projection
```

要求：

- Thread 创建时默认准备 IEEE-39 页面；
- 一个 Thread 中每个 distinct Grid Model identity 一个页面；
- 页面不因普通对话或案例批处理创建；
- 模型切换成功后新模型页面成为当前页；
- 历史页只读，不改变当前 Context 或执行；
- PyPSA 页面只能由 PyPSA Authority projection 提供，不能显示 pandapower 图；
- 前端不得把某个 `case_id` 伪装成模型图来源。

## 8. 运行顺序

### M0 — 主线重新基线（本文件）

冻结上述边界，清理状态文档中把 `grid-agent.hosted` 当作主入口的描述。

### M1 — Capstone 应用根

把 hosted API/Worker 的主装配移动到 `capstone-agent`，让 `grid-agent.hosted`
只作为兼容 shim，并建立统一注册入口和 boundary tests。

### M2 — 真实模型与运行时分派

实现复合 Model Authority Catalog、真实 PyPSA 模型身份、Profile 解析、按
implementation family 的 Pi/Authority runtime dispatch，以及模型绑定图区。

### M3 — 普通对话与 TurnRouter

加入普通对话应用策略、TurnPlan、router events、Jev 开关和安全降级。默认普通
对话开启，Jev 默认关闭。

### M4 — Web/TUI 控件

在 M1–M3 稳定后继续 Composer compact controls、Profile/模型菜单、trace/stop/
retry 操作和一模型一分页的真实客户端投影。

### M5 — 统一验证

使用真实 pandapower scripted instructions、真实 PyPSA registered model、普通
问题、模型切换、Profile selection、失败/取消/重试/重连和 Web/TUI 双客户端完成
验收；最后执行本地 rebuild 和完整适用 gates。

## 9. 明确不做

- 不在 `grid-agent.hosted` 上继续堆新应用能力；
- 不把 `pypsa-agent` 改造成第二个用户应用；
- 不用 `pypsa39` 这类虚构模型身份掩盖真实目录；
- 不把普通对话做成一个 Domain Pack；
- 不用模型分类结果绕过工具和证据硬门控；
- 不在 UI 层直接连接 Pi/DSH；
- 不在本阶段实现多 Run；
- 不继续增加与主线架构无关的视觉细节。

## 10. 验收标准

M0 设计完成后的最低验收标准：

1. 所有新实现入口都能明确回答“属于 `capstone-agent`、Harness、Domain Pack
   还是 Authority”。
2. `grid-agent.hosted` 被明确标记为迁移兼容入口，而不是主架构入口。
3. pandapower 与 PyPSA 的模型目录、Profile、runtime 和图区边界互不混淆。
4. 普通对话默认开启，且不会要求领域证据；专业回答仍需要硬门控。
5. `send_auto`、Jev、TurnPlan 和普通策略的职责清楚，未把 UI 模式按钮当成路由实现。
6. Web、TUI、CLI 只共享公共 Thread/Harness 协议，不复制领域执行逻辑。
7. 后续实现可以按 M1–M5 顺序独立验收，不需要再次重新解释产品架构。

