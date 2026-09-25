# Domain Pack 接入模板与 conformance 入口

本指南把已运行的 inventory 参考实现整理为新只读 Domain Pack 的起点。新领域仍需单独发行包、自己的注册 authority 和 Application 绑定；不能把业务语义放进 Kernel，也不能把 inventory 的事实或状态当成新领域实现。框架边界见[架构合同](../architecture/capstone-framework.md)。

## 从哪些文件开始

| 作者需要提供的内容 | 可复制的参考位置 | 验证重点 |
| --- | --- | --- |
| 独立包、精确的 Kernel/authority 依赖 | [inventory pyproject](../../packages/inventory-domain-pack/pyproject.toml) | wheel 可单独构建，资源装入 wheel。 |
| 版本化语义操作和字段 schema | [capabilities](../../packages/inventory-domain-pack/src/inventory_domain/resources/capabilities/) | 模型只见业务参数；没有 URL、令牌、可执行文件或任意代码参数。 |
| Pack manifest、公开 Profile 和装配 | [profile.py](../../packages/inventory-domain-pack/src/inventory_domain/profile.py) | 公开 Kernel SPI 注入组件；Application 显式选择一个或多个独立 binding。 |
| 领域策略、指南和资源定位 | [resources](../../packages/inventory-domain-pack/src/inventory_domain/resources/) | 指南与工具清单发布一致，离线说明不伪造事实引用。 |
| executor 和可信 provisioner | [execution.py](../../packages/inventory-domain-pack/src/inventory_domain/execution.py)、[provisioning.py](../../packages/inventory-domain-pack/src/inventory_domain/provisioning.py) | authority 地址、超时和凭据由装配固定；异常有稳定错误类别。 |
| current-run authority、投影、状态、输出 | [authority.py](../../packages/inventory-domain-pack/src/inventory_domain/authority.py)、[projection.py](../../packages/inventory-domain-pack/src/inventory_domain/projection.py)、[state.py](../../packages/inventory-domain-pack/src/inventory_domain/state.py)、[output.py](../../packages/inventory-domain-pack/src/inventory_domain/output.py) | result/evidence 属于本轮、可离线验证；`core` 仍归 Kernel。 |
| Application 级回归 | [SDK conformance](../../packages/inventory-domain-pack/tests/test_application_conformance.py) | 两轮真实 authority 调用、提交、报告故障和 replay。 |

### SDK authority 示例

inventory 的生产参考路径通过 `InventoryRuntimeProvisioner` 固定 `inventoryctl`，由 `InventoryctlExecutor` 请求已注册 authority。[SDK conformance](../../packages/inventory-domain-pack/tests/test_application_conformance.py)只脚本化模型决策，业务调用仍走真实 `inventoryctl`，并验证两轮应用及当前运行证据。复制此模式时，替换领域合同、authority 和业务投影；不要复制 grid 的兼容输出封装。

### 显式多 binding 装配

同一 `ApplicationProfile.domains` 可以显式选择多个 `DomainBinding`。每个 binding 需要唯一 ID、工具前缀、独立工作目录和凭据作用域，并分别注册自己的 authority。运行时 `capability-agent-runtime/1.1` 发布所有已选领域的工具目录和指南，核心 `agent_` 工具仅发布一组；原单 binding `1.0` 格式继续兼容。

[双 binding 验收](../../packages/inventory-domain-pack/tests/test_multi_binding_application.py)提供 pandapower 与 inventory 的两轮真实 authority 示例：第一轮打开各自上下文并读取结果，第二轮复用各自上下文再次调用 authority，随后检查独立 claims、`domains.grid` / `domains.inventory`、报告和 replay。显式 claims 通过真实 `TurnController.submit` 提交；测试中的薄控制器子类只把脚本决策接入该接口，应用的 Provider 接口仍返回读者文本。[Pi 启动冒烟](../../packages/pi-capability-tools/test/domain-tools.test.mjs)使用托管 SDK 和默认通用扩展验证两个已发布目录、指南和唯一核心工具组，不调用 Provider。

多 binding 组合本身不授予跨领域共享权限。`DataSharingPolicy` 继续默认拒绝；应用可以通过 `ReferenceGrant` 明确写入来源、目标、引用类型、用途和目标能力族。可信应用代码先请来源 authority 核验当前运行修订，再把内容寻址交接凭证记录到可回放上下文，目标 authority 准入后才执行目标能力。模型参数不能选择 grant 或 authority 地址。[PyPSA Operations 安装冒烟](../../packages/pypsa-power-operations-domain-pack/tests/installed_smoke.py)、[容量规划安装冒烟](../../packages/pypsa-capacity-planning-domain-pack/tests/installed_smoke.py)与[行业耦合安装冒烟](../../packages/pypsa-sector-coupling-domain-pack/tests/installed_smoke.py)各自使用真实建模与目标 Pack 两个 binding 验证授权交接、目标求解和独立证据；[基础接收者冒烟](../../packages/pypsa-network-modeling-domain-pack/tests/installed_smoke.py)继续覆盖通用只读路径。交接不共享原始模型、状态或 evidence。`grid-agent` CLI 继续显式选择 pandapower，保持两字段兼容输出。

### 固定 HTTP authority 示例

[HTTP 实验 adapter](../../packages/inventory-domain-pack/tests/http_authority_experiment.py)展示同一 Profile 如何替换 provisioner、executor 和 authority factory。连接目标由可信装配固定，令牌通过 binding credential lease 注入；分页完整性和版本检查在 Pack/authority 内完成，规范化响应页写入可离线核验的 receipt。[HTTP 应用回归](../../packages/inventory-domain-pack/tests/test_http_authority_experiment.py)覆盖两轮、401/403/429、超时、schema 漂移、部分分页、版本变化、重复读取、凭据泄露、报告失败和 replay。

HTTP 示例留在测试树，不随 wheel 交付。默认 Pi/JavaScript 工具仍使用 executable descriptor；脚本模型的 HTTP 成功不能宣称真实 Pi 的 HTTP 通道已接通。接真实 API 前，应先规定服务端版本/快照语义、鉴权、TLS、权限、限流和脱敏错误合同。详见[实验结论](../reviews/2026-09-22-http-authority-experiment.md)。

## 可重复的开发者入口

在仓库根目录运行：

```sh
make test-domain-pack-conformance
make test-packages
```

第一个命令固定运行 inventory 的 SDK、HTTP 和通用 Pi conformance，并检查包边界；它是参考包的稳定入口。新 Pack 应在自己的测试树提供相同级别的两轮应用、故障和 replay 验证，并将对应目标加入工程门禁。第二个命令从干净 wheel/npm 安装检验已发布接口；HTTP adapter 会作为**测试文件**复制到隔离 smoke 目录，不会进入发布产物。

兼容性信息的机器源是各包的 `pyproject.toml`、npm package manifest 和锁文件；`make test-packages` 会实际构建、安装和执行 smoke。先保留精确依赖，积累多版本安装矩阵证据后再考虑放宽范围，避免另存一份会漂移的版本清单。

## 最小验收合同

1. 新 Pack 能独立构建和安装，Kernel 不新增领域词汇或业务导入。
2. 未发布的 authority 操作不会变成模型工具；模型不能控制端点、命令或凭据。
3. 两轮有状态调用的结果和证据属于当前 run，第二轮能复用允许的上下文；replay 与已提交答案一致。
4. 凭据不进入参数、stdout、报告、工件或公开 metadata；远端失败不产生可准入的完整结果。
5. 报告和评价失败保留已提交主答案；真正的引用或提交错误仍失败。
6. 用干净安装验证包内资源、公开 SPI 和应用装配，记录 Provider 与真实外部服务验证的独立范围。
