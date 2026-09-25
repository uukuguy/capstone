# Capstone Agent Framework

[English](README.md) | 简体中文

Capstone 是一个能力优先的框架，用于在权威业务领域系统之上组装具备证据闭环的应用。

它将领域无关的 Kernel、可独立安装的 Domain Pack 和应用自有的兼容产品分离。模型只能组合受限的语义能力；已登记的权威服务始终拥有领域事实与当前运行证据。详见 [Capstone Agent Framework](docs/architecture/capstone-framework.md)。

## 框架架构

Capstone 将四个所有权层保持为相互独立：

```text
Application -> Domain Pack -> Kernel -> registered Authority
```

依赖只能向右流动。结果和证据引用通过显式契约返回，而不是反向导入或暴露原始对象。Application 拥有公共 CLI 或 UI 以及任何兼容投影；Domain Pack 拥有领域契约、策略、指南、执行、投影和当前运行领域状态；Kernel 拥有领域无关的组合与生命周期；已登记的 Authority 拥有基于来源或确定性产生的领域事实、结果、修订和证据。

源码导入、注入接口的运行调用和证据返回是不同的关系。Domain Pack 可以导入显式白名单内的 authority 协议／资源 API，但不能导入其原始实现；Kernel 不导入具体 authority。详见[三类关系图](docs/architecture/capstone-framework.md#imports-calls-and-evidence-are-different-relationships)。

## 添加应用

集成新应用时，先定义权威系统边界和带版本的语义协议；再通过公共 Kernel SPI 实现 Domain Pack；使用具备凭据作用域和公共渲染器的 `ApplicationProfile` 绑定该 Domain Pack；最后使用真实权威调用和当前运行证据链路证明无 Provider 验收。显式多 binding 装配支持在同一应用中组合独立领域，工具、状态、证据和输出均按命名空间隔离。应用可以针对指定来源、目标和用途授权只读引用交接；未授权共享仍被拒绝。Capstone 当前不提供动态发现或运行时领域选择。

## 框架保证

- 模型只能获得已发布、可执行、具有精确 schema 的语义工具，以及受限上下文、策略和指南。
- 领域事实和当前运行证据由 Authority 接纳和产生，而非模型、Kernel 或 Application。
- 通用结果保留 Kernel 所有的 `core` 以及 Domain Pack 所有的命名空间载荷；任何版本化公共兼容投影由 Application 拥有。
- 面向读者的事实性结论只能使用当前运行中已由 Authority 接纳的结果和证据引用。

完整的所有权、运行时、组合输出和当前运行证据协议以 [Capstone 框架架构](docs/architecture/capstone-framework.md) 为准。

上述保证验证引用完整性和当前运行谱系，不证明模型生成的每句话在语义上正确。确定性事实展示来自已验证的 Authority 结果；自由文本解释仍是模型输出。报告或观察器故障单独记录，不撤销已接纳的主答案；必需的证据和答案持久化失败仍会阻止相应操作成功。Capstone 面向能力包接入与 AI 业务验证，不以企业级服务性能为目标。

## 首个应用：电网静态分析

本仓库中的首个 Capstone 应用是 `grid-static-analysis`：`grid-agent`
用于对已登记电力系统网络执行具备证据闭环的静态分析。LLM 负责理解请求并组合项目定义的工具；`gridctl` 与固定版本的 pandapower 模拟器负责全部确定性网络计算。

`v1.0.1` 是声明的静态分析产品范围内的稳定版本。当前覆盖情况始终以可执行能力矩阵为准。

## 功能范围

- 发现已登记网络，并通过受控声明式接口创建模型。
- 派生不可变网络修订和分析场景。
- 执行拓扑、AC/DC/三相潮流、AC/DC 最优潮流、IEC 60909 短路、状态估计、诊断、故障分析、风险评估、网络等值和静态保护分析。
- 查询、聚合、比较和排序由模拟器管理的结果数据集。
- 在多步骤分析和连续报告中复用经过验证的上下文。
- 记录原生执行轨迹，并提供只读调查工作台。
- 将最终数值结论绑定到当前运行的结果和证据引用。

项目覆盖的是声明的 pandapower 静态分析产品范围，而不是 pandapower 的全部公开 API。时序/控制工作流、绘图、任意文件或数据库转换，以及未固定的外部求解器运行时不属于模型能力边界。详见[能力架构](docs/architecture/pandapower-capability-composition.md)和[可执行覆盖矩阵](configs/capabilities/pandapower-3.4.0-static-analysis.json)。

## 电网应用架构

```text
自然语言请求
      |
      v
grid-agent + Pi/LLM       意图理解、工具组合、上下文、答案封装
      |
      v  grid-capability/1.0
gridctl + grid-simulator  契约、登记模型、结果、证据
      |
      v
pandapower                确定性电力系统计算
      |
      v
runs/<question_id>/       操作者可见的当前运行证据
```

LLM 只能选择已登记的语义工具，不能获得 shell、任意 Python、原始 pandapower 对象、DataFrame 或通用文件系统访问权。所有数值和网络特定结论都必须跨越模拟器边界返回。

## 包组装

Capstone 通过 Kernel、能力传输、当前运行权威和应用组合这些可复用接缝来组装领域包。下方的 pandapower 包构成首个正式应用；`inventory-domain-pack` 仍是 conformance 基础设施，而非已选定的第二个生产领域。

仓库现在包含十一个可独立构建的 Python 发行包和两个 Pi npm 包。其中四个发行包组装 grid 产品，两个构成只读 inventory 参考域，另五个提供 PyPSA 模型权威、网络建模、运行计算、容量规划与行业耦合 Pack：

| 发行包 | 职责 |
| --- | --- |
| `capability-agent-kernel` | 领域无关的 manifest、contract、executor、projection、authority、tool-catalog、guide、trajectory 与 composition 接口 |
| `grid-simulator` | `gridctl`、已登记 pandapower 网络、确定性计算、结果数据集和模拟器证据 |
| `pandapower-domain-pack` | pandapower 静态分析领域 Profile、策略、指南、能力契约、资源所有权和兼容适配器 |
| `grid-agent` | CLI、Provider/Pi 运行时初始化、认证、连续分析、报告、工作台服务和最终 JSON 答案封装 |
| `inventory-reference-service` | `inventoryctl`、已登记只读目录、严格的 `inventory-capability/1.0` 和内容寻址 inventory 工件 |
| `inventory-domain-pack` | 仅基于公共内核 SPI 的 inventory Profile、策略、指南、契约、执行器、投影器和当前运行工件权威 |
| `pypsa-model-authority` | 已登记 PyPSA 模型目录、不可变修订、受限建模操作及当前运行结果和证据引用 |
| `pypsa-network-modeling-domain-pack` | 通过公共 Kernel SPI 提供 PyPSA 建模契约、策略、指南、执行、投影与权威准入 |
| `pypsa-power-operations-domain-pack` | 通过授权模型交接执行固定容量调度、机组启停、登记故障集调度和 AC 校验，保存目标绑定证据 |
| `pypsa-capacity-planning-domain-pack` | 通过授权模型交接执行登记的容量扩建、联合启停、多期、随机和近最优规划，并保存目标绑定证据 |
| `pypsa-sector-coupling-domain-pack` | 通过授权模型交接执行登记的电转氢、热泵、储能和多端口平衡，并保存目标绑定证据 |
| `@capability-agent/pi-tools` | 通用的描述符驱动 Pi 能力请求传输与请求捕获 |
| `@grid-static-analysis/pi-grid-tools` | 保留现有 `grid_*` 工具和指南行为的 grid 兼容 Pi 扩展包装 |

源码开发模式使用各包 manifest 中固定的本地 path 依赖。安装验证模式会构建十一个 Python wheel 与两个 npm tarball，在仓库外隔离安装并执行冒烟检查，确保不会从源码路径导入。grid／参考包和 PyPSA 包使用不同 Python 环境，因为两套已固定的仿真依赖要求不同的 pandas 主版本：

```sh
make test-packages
```

能力包作者可从 [Domain Pack 接入指南](docs/guides/domain-pack-onboarding.md) 开始，并运行
`make test-domain-pack-conformance` 验证 inventory SDK、固定 HTTP 与通用 Pi 参考用例。
HTTP adapter 仅用于测试；干净安装 smoke 会在 wheel 外复制它。

PyPSA 建模 Pack 提供已登记模型的打开、按类型修改负荷需求并派生修订，以及受限模型检查。独立的运行计算 Pack 提供固定容量调度、机组启停、登记故障集调度和调度后的 AC 校验。容量规划 Pack 提供登记的容量扩建、容量与启停联合优化、双投资期路径、双场景随机投资和近最优容量替代方案。行业耦合 Pack 提供登记的电转氢、热泵、氢储能、热储能和多端口 CHP 平衡；热储能流程使用登记的逐时 COP。精确工具见[建模目录](configs/capabilities/pypsa-1.3.0-modeling.json)、[运行计算目录](configs/capabilities/pypsa-1.3.0-power-operations.json)、[容量规划目录](configs/capabilities/pypsa-1.3.0-capacity-planning.json)与[行业耦合目录](configs/capabilities/pypsa-1.3.0-sector-coupling.json)。`make test-pypsa` 运行聚焦测试；干净 wheel 验证会把当前运行模型引用经应用授权交给真实目标 Pack。grid CLI 仍绑定 pandapower。

`make test` 是不使用 Provider 的单元门禁：分别运行十一个 Python 包、两个 Pi 包和 trajectory workbench。grid CLI E2E 保持为仅集成层的 `make test-e2e`。`make check-types` 使用锁定的 pyright 1.1.408，以 standard 模式和 Python 3.12 最低版本检查全部生产 `src` 树及 workbench；Kernel output 模型中 3 处局部 Pydantic schema 属性覆盖为保持既有公开 wire 契约的例外。`make check-fast` 组合边界、类型和单元测试；`make check-integration` 运行 E2E、实际构建 SDK 捕获冒烟（`make test-pi-capture-runtime`）与无 Provider 验证；`make check-release` 再加入干净包和源码安装检查。以上命令均不调用付费 Provider。

已配置的 GitHub Actions 会在 Linux/macOS、Python 3.12/3.14 与 Node 22.19.0 上运行 release 检查。这说明 CI 配置覆盖范围，不宣称远端工作流已经通过。

在其记录的 conformance 基线中，inventory 参考域复用通用 Pi transport 和 Kernel 组合路径，证明独立打包的只读业务权威可在不复制 `grid-agent` 的前提下实例化单领域框架。后续 Kernel 与 simulator 优化均由各自当前记录独立复审和保护；这项历史证明不宣称这些路径至今未变。当前发布的 `grid-agent` CLI 仍显式选择 pandapower Profile；inventory 仍是 conformance 基础设施，而不是第二个生产领域。

无 Provider 的[双 binding 验收](packages/inventory-domain-pack/tests/test_multi_binding_application.py)装配 pandapower 与 inventory，在两轮中调用两个真实 authority，提交各自拥有的 claims，并检查报告与 replay。托管 Pi 启动冒烟加载两个已发布的工具目录和指南，以及唯一一组 `agent_` 核心工具，无需调用 Provider。这些检查证明独立组合，不开放 binding 之间的领域模型或证据共享。

inventory Profile 现已提供完整应用所需的全部 SPI 组件。无 Provider 验收通过真实 `inventoryctl` 执行两轮上下文复用、准入答案、`core` + `domains.inventory`、报告隔离与回放；干净 wheel 测试在仓库外使用当前解释器安装的 console script 重复完整应用。这些检查证明运行装配和证据谱系，不证明自由文本解释的语义正确性。

外部 grid 兼容 CLI、Pi 工具名、`grid-capability/1.0` 协议、v1.0.1 双字段 stdout 封装、stderr 诊断、`runs/` 证据布局和模拟器事实所有权契约保持不变。显式的 `analysis-generic` 命令使用下文的组合输出契约。

## 通用应用路径

可复用的应用接缝按一个明确方向组装：

```text
ApplicationProfile -> AgentApplication -> DomainBinding -> Domain Pack
```

内核拥有框架 `core` 部分（运行身份、生命周期、状态、回合和审计元数据）。每个 Domain Pack 独立拥有自己的 `domains.<binding_id>` 部分及其语义载荷。通用入口保留两部分，并输出组合的 `capability-agent-output/1.0` 契约，例如：

```json
{"schema":"capability-agent-output/1.0","core":{...},"domains":{"grid":{...}}}
```

通用运行的完成状态反映已接受答案和必要上下文事务；报告或进度故障不会撤销它们。
pandapower 领域 schema 为 `pandapower-static-analysis-output/1.1`：报告不可用时引用为 null，
非空引用仍必须由当前运行接纳。展示故障可查看 `core.diagnostic_refs` 和
`core/diagnostics/<code>/diagnostic.json`；诊断存储失败时回退为安全 stderr 诊断。

运行正式内建的 pandapower 应用：

```sh
make application
```

如需显式指定指令文件、Provider 或模型，请使用 Makefile 覆盖参数；完整的运行、输出、计费和当前运行证据契约见 [Pandapower Static-Analysis Application](docs/PANDAPOWER-APPLICATION.md)。无 Provider 验收门禁会使用同一个已准备的 pandapower endpoint，通过真实语义 `gridctl` 调用：

```sh
make validate-application
```

`inventory-domain-pack` 仅用于 fixture/conformance 参考；它不是第二个生产 CLI 模式，也不表示已经选定了有用的第二领域智能体。C.1 已完成：两个 canonical v1.0.1 业务任务文件均已使用获得授权的 Provider 通过正式应用路径，显式兼容路径也保留了 v1.0.1 答案封装。正式操作流程见 [Pandapower Static-Analysis Application](docs/PANDAPOWER-APPLICATION.md)。

通用组合结果有意不同于显式的 v1.0.1 兼容投影。`run`、`analysis` 和 `report` 命令保留版本化适配器及其精确的双字段 stdout 对象（`question_id` 与 `answer_output`）；适配器渲染旧版封装前，内部丰富结果仍会先完成验证。

## 快速开始

前置条件为 Python 3.12+、Node.js 22.19+、`uv` 和 `npm`。Provider 支持的分析还需要配置相应的 LLM 凭据；离线冒烟检查不需要 Provider。

```sh
git clone https://github.com/uukuguy/grid-static-analysis.git
cd grid-static-analysis
make setup
make doctor
```

执行确定性离线冒烟检查：

```sh
make run QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
```

执行主要的自然语言代理路径：

```sh
cp .env.example .env
# 在 Git 忽略的 .env 文件中配置一个受支持的 Provider 凭据。
make install-pi
make run-llm QUESTION="对 IEEE-39 节点系统运行交流潮流，并报告有功网损。"
```

如需使用项目自有的 OpenAI Codex OAuth 而不是 API key，请先在 `.env` 中设置 `GRID_AGENT_LLM_PROVIDER=openai-codex`，再执行 `make auth-login`；该登录命令不会自动选择 Provider。也可以在单次调用中使用 `make run-llm PROVIDER=openai-codex QUESTION="..."` 指定 Provider。Provider 配置、认证优先级、运行时安装和失败诊断详见[运行操作指南](docs/RUNBOOK.md)。

## 主要工作流

| 目标 | 命令 |
| --- | --- |
| 检查运行环境 | `make doctor` |
| 离线确定性冒烟检查 | `make run QUESTION="..."` |
| LLM 驱动的单题分析 | `make run-llm QUESTION="..."` |
| 连续多题分析 | `make analysis INSTRUCTIONS=path/to/instructions.txt` |
| 连续分析兼容别名 | `make report INSTRUCTIONS=path/to/instructions.txt` |
| 正式 pandapower 应用 | `make application [INSTRUCTIONS=...]` |
| 通用登记应用 | `make analysis-generic APPLICATION=... INSTRUCTIONS=...` |
| 无 Provider 应用验收 | `make validate-application` |
| 构建并启动只读工作台 | `make trajectory PORT=8765` |

`grid-agent run` 向 stdout 精确写入一个 JSON 对象：

```json
{"question_id":"...","answer_output":"..."}
```

进度、诊断和工具事件只写入 stderr。连续分析同样只输出一个最终答案封装，其 `answer_output` 指向生成的报告。

## 结果、证据与工作台

模拟器支持的单题运行将 canonical 工件写入 `runs/<question_id>/core/` 和
`runs/<question_id>/domains/grid/`；应用发布字节保持的根 `events.jsonl`、
`tool-results/` 与 `evidence/` 兼容快照以保留旧路径。最终结论只能引用当前运行已经接纳的结果和证据。纯信息类离线回答不会创建仿真证据。

内部认证、托管 Pi 运行时、缓存和会话状态位于 Git 忽略的 `.grid-agent/` 目录；版本化运行配置位于 `configs/runtime/`。

启动本地只读轨迹工作台：

```sh
make trajectory PORT=8765
```

UI 和 API 默认位于 `http://127.0.0.1:8765`。工作台只投影已记录事实用于调查，不能修改运行记录，也不能替代模拟器事实。

## 验证

```sh
make doctor
make test
make test-e2e
make validate
make validate-application
make test-inventory
make test-packages
```

`make validate-provider PROVIDER=<id> [MODEL=<id>]` 是可选命令，需要显式凭据，并可能产生 Provider 费用。

## 仓库结构

| 路径 | 职责 |
| --- | --- |
| `packages/capability-agent-kernel/` | 领域无关 Python 内核契约、组合、工具、指南和轨迹原语 |
| `packages/grid-simulator/` | `gridctl`、登记模型、pandapower 执行、结果和证据 |
| `packages/pandapower-domain-pack/` | pandapower 领域 Profile、契约、策略、指南、资源和适配器 |
| `packages/grid-agent/` | CLI、Pi/LLM 运行时、上下文、报告、工作台服务和答案封装 |
| `packages/inventory-reference-service/` | 只读已登记 inventory 权威、协议、工件和 `inventoryctl` |
| `packages/inventory-domain-pack/` | 使用公共内核 SPI 与通用 Pi transport 的 inventory 参考 Domain Pack |
| `packages/pi-capability-tools/` | 通用描述符驱动 Pi 能力传输与请求捕获 |
| `packages/pi-grid-tools/` | grid 兼容 Pi 工具包装、指南和请求捕获 |
| `packages/trajectory-workbench/` | 只读 React/TypeScript 轨迹调查 UI |
| `configs/` | 版本化能力、策略、Provider 目录和运行配置 |
| `validation/` | 离线、脚本 Pi、语义和可选 Provider 验证套件 |
| `docs/` | 操作指南、架构、设计历史、计划和持久项目状态 |

## 文档索引

- [Capstone 框架架构](docs/architecture/capstone-framework.md) — 已实现的 Kernel、Domain Pack、应用、权威服务和证据边界。
- [运行操作指南](docs/RUNBOOK.md) — 初始化、认证、执行、证据与故障排查。
- [人工验证手册](docs/MANUAL-VALIDATION.md) — 可复现的人工验收流程。
- [能力注册与组合推理](docs/architecture/pandapower-capability-composition.md) — 能力范围和 LLM 工具编排边界。
- [分析上下文架构](docs/architecture/analysis-context.md) — 经过验证的多步骤上下文模型。
- [轨迹事件架构](docs/architecture/trajectory-events.md) — 权威原生执行时间线。
- [当前项目状态](docs/status/CURRENT-STATE.md) — 结构快照与实现入口。
- [仓库 Agent 契约](AGENTS.md) — 稳定的 Codex/Claude Code 规则与事实来源。

## 安全与贡献边界

凭据只能存放在环境变量或 Git 忽略的项目认证状态中，不能进入命令参数、提交文件、日志、模拟器环境或证据。新增模型能力必须可复用、由契约定义、经过白名单，并由已登记的权威服务执行；禁止逐题捷径和任意执行面。
