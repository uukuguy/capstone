# 固定 HTTP authority 接入实验

日期：2026-09-22。依据：[深度优化方案](2026-09-22-capstone-deep-optimization-proposal.md) B 阶段与[框架边界](../architecture/capstone-framework.md)。本实验只使用本机 loopback 服务、脚本模型和测试凭据；HTTP adapter 位于 inventory Pack 的测试树，不进入发布 wheel。

## 结论

现有 Pack 的 provisioner、executor 与 current-run authority 注入点足以让脚本模型通过已发布的 inventory 语义工具访问固定 HTTP 服务。两轮应用、结果/证据准入、报告及离线 replay 无需修改 Kernel 业务代码。干净安装测试将测试 adapter 复制到隔离目录，在六个已安装 wheel 上完成调用；这证明公开 Pack 装配可复用，尚不证明默认 Pi/JavaScript transport 能直接连接 HTTP。

HTTP 连接参数、操作和凭据由可信装配固定；模型只传已声明的业务参数。服务端使用注册的 `warehouse-a` 目录作为事实来源。测试凭据只由 `CredentialScope` 的 lease 注入 executor；workspace JSON、结果、receipt、公开 metadata 和渲染输出均不含凭据值。

## 验证矩阵

| 情形 | 预期与观察 |
| --- | --- |
| 两轮正常调用 | `catalog.open`、分页 `asset.list`、`stock.summary` 均经真实 loopback HTTP；两轮提交，current-run result/evidence 准入，snapshot 与 replay 相同。 |
| 401、403、429 | adapter 返回各自固定错误码；失败操作不发布完整 result。 |
| 超时、schema 漂移、第二页失败、分页期间版本变化 | adapter 分别返回固定错误码；不发布完整 result。 |
| 第二轮 HTTP 429 | 应用保留首轮已提交引用，第二轮以无新 result/evidence 的 limited 回答继续完成；通用 credential screening 对模型只暴露 `capability_transport_failed`。 |
| 重复读取 | 相同业务值和版本，仍有不同观测时间/请求 ID，因此 result 引用不同。 |
| receipt 篡改 | 持久化文档即使重新按内容寻址，离线 authority 仍拒绝响应摘要不符的 result。 |
| 报告发布失败 | 两轮主答案保持已提交，故障只形成诊断。 |
| 干净安装 | 六个 wheel 的现有 smoke、HTTP adapter smoke 和 npm 包边界检查通过。 |

实验模块 562 行，其中包含 loopback 服务、HTTP executor、receipt 校验与 provisioner；测试 174 行（12 项）。这些是端到端实验代码量，不是新 Pack 的生产代码量或接入人时。未记录可重复的接入工时，因此不估算“接入时间”。Kernel 业务文件改动数为 **0**。

主目录门禁已通过：`make doctor`、`make test`（inventory 131 项）、`make test-e2e`（37 项）、`make validate`（发布能力覆盖 24/24）、`make check-types`（Pyright 0 错误）、`make check-package-boundaries`、`make validate-application`、`make test-packages`。未运行需凭据和可能付费的 Provider 验证。

## receipt 保证范围

receipt 记录 authority ID、语义操作、合同版本、每页请求 ID 和观测时间、目录版本、页数、完整标志以及**经过 schema 校验和规范化的页数据摘要**。它和结果一起按内容寻址持久化，离线准入复算摘要并核对结果、目录版本及末页计数。

该摘要证明本地保存的规范化页与结果一致，不是原始 HTTP 响应字节的签名，也不是远端服务的密码学证明。测试服务使用稳定目录版本；真实服务若没有服务端快照或强一致分页承诺，即使各页声称相同版本，也不能据此证明跨页同时性。接入真实 API 时，Pack 必须声明其快照/版本语义，并按该语义决定是否允许组合页结果。

## 后续接口决定

1. **C 阶段**：把现有 inventory conformance 整理为 Pack 作者可运行的入口和可复制的最小装配示例；提供 SDK authority 和固定 HTTP adapter 两条示例路径。模板须说明哪些组件由作者实现、哪些由 Kernel 复用，避免复制 562 行实验服务。
2. **D 阶段**：默认 Pi 工具仍使用 executable descriptor 和 JavaScript subprocess。若需要交付正式 HTTP Pack，先为模型 transport 明确受控 HTTP adapter 的装配合同与错误映射，再决定是否改公共 SPI。现有 credential screening 将原始 adapter 错误统一映射为 `capability_transport_failed`；细分 401/403/429 的读者诊断需经过脱敏和稳定合同设计。
3. 保留当前行为：不向模型开放 URL、令牌、通用 HTTP、任意文件或 subprocess。只有已声明的只读/幂等语义操作才可考虑重试；本实验没有自动重试。

实验未使用真实外部服务、Provider 凭据或付费模型，也没有验证远端授权策略、TLS、服务端限流窗口和真实网络时效。
