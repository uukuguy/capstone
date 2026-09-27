# Capstone Agent Framework

简体中文 | [English](README.md)

Capstone 让智能体组织分析任务，让专业系统负责计算，并把每一步的结果和证据留在同一次运行中。应用可以据此展示结论、回看过程，也能追查结论来自哪个模型和哪次计算。

电网分析是仓库中的第一批应用：pandapower 负责静态电网计算，PyPSA 负责已登记的建模、运行和规划能力。框架本身不绑定电力行业；接入其他领域时，由独立的 Domain Pack 定义可用能力和权威系统边界。

![Capstone 电网分析工作台：案例库、IEEE-39 拓扑图和当前运行状态](docs/images/capstone-workbench.png)

## 从工作台看起

[操作 App](packages/capstone-app/) 提供五个已登记案例：两个 IEEE-39 静态分析案例，以及区域负荷、SciGRID-DE 调度和 AC/DC 互联三个 PyPSA 案例。打开案例即可查看完整模型图；运行时可以逐步执行，也可以自动完成三条指令。

电网图会随步骤定位到相关元件。已完成的步骤可点选回看；图中的数值着色只使用本轮已接纳的计算结果。每轮结束后，报告显示在分析过程下方，右侧可查看运行状态和证据。

![IEEE-39 当前运行的电网拓扑图与线路负载率图层](docs/images/capstone-grid-topology.png)

公开工作台使用已登记的脚本案例，不调用付费 LLM Provider。自然语言工具编排有单独的 CLI 路径和凭据配置，见[运行手册](docs/RUNBOOK.md)。

## Capstone 怎样工作

```text
Application → Domain Pack → Kernel → registered Authority
```

| 部分 | 负责什么 |
| --- | --- |
| Application | 选择领域能力，提供 App 或 CLI，呈现答案和报告 |
| Domain Pack | 定义领域工具、契约、策略、指南，以及结果和证据的准入规则 |
| Kernel | 管理运行、步骤、受限上下文、轨迹、工件和回放 |
| Authority | 访问登记模型，执行计算或查询，产生可信的结果与证据 |

智能体只能调用已发布的语义工具。它不能直接拿到 pandapower 对象、PyPSA 内部状态、任意命令或文件访问权。数值和网络结论来自相应的权威系统，并通过明确的结果、证据引用返回应用。Kernel 保持领域中立；一个应用可以显式组合多个 Domain Pack，但领域状态和凭据仍各自隔离。

完整的所有权与数据流见[框架架构](docs/architecture/capstone-framework.md)。想接入新领域，可从 [Domain Pack 接入指南](docs/guides/domain-pack-onboarding.md)开始。

## 在本地打开工作台

需要 Docker Compose、Node.js 22.19+ 和 npm。先创建本地环境文件，把其中的示例密钥换成本地值：

```sh
cp deploy/local.env.example deploy/local.env
docker compose --env-file deploy/local.env config --quiet
docker compose --env-file deploy/local.env up --build -d
make setup-capstone-app
make capstone-app-dev
```

打开 `http://127.0.0.1:5173/`。本地演示凭证由 API 发放，页面直接进入工作台；不需要手动填写访问令牌。报告和证据保存在私有工件存储中，浏览器只通过 API 读取受限内容。更多端口、凭据和故障排查说明见[运行手册](docs/RUNBOOK.md#hosted-app-and-deployment)。

## 使用 CLI

CLI 开发需要 Python 3.12+、`uv`、Node.js 22.19+ 和 npm。以下命令安装依赖并运行不调用 Provider 的检查：

```sh
make setup
make doctor
make run QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
```

统一的无 Provider 三步案例也可从命令行运行：

```sh
make capstone-agent-run REQUEST=validation/client/pandapower-scripted-task.json
make capstone-agent-run REQUEST=validation/client/pypsa-regional-demo.json
```

`grid-agent` 是 pandapower 应用的兼容 CLI。其 `run`、`analysis` 和 `report` 命令在标准输出中只写一个包含 `question_id` 与 `answer_output` 的 JSON 对象；进度和诊断走标准错误输出。需要 LLM 的自然语言分析使用 `make run-llm`，先按[运行手册](docs/RUNBOOK.md)配置 Provider 与 Pi。凭据不能写进命令参数或提交到仓库。

## 部署与开发

本地 Compose、Cloud Run 和 Railway 使用同一套 API 契约和同一后端镜像；镜像按角色启动 API 或 worker。两者共享 PostgreSQL 运行账本和私有工件存储。静态 App 可部署在 Railway 或 Vercel，通过 `VITE_API_ORIGIN` 连接公开 API；这个构建变量只放 API 地址，不放密钥。

- [Railway 部署说明](deploy/railway/README.md)
- [Cloud Run + Vercel 部署说明](deploy/cloud-run/README.md)
- [完整运行手册](docs/RUNBOOK.md)

前端定向检查使用 `make test-capstone-app` 和 `make build-capstone-app`。完整离线门禁包括 `make test`、`make test-e2e` 与 `make validate`；Provider 验证单独授权，可能计费。

## 进一步阅读

- [Capstone 框架架构](docs/architecture/capstone-framework.md)：四层所有权、组合输出、当前运行证据
- [pandapower 能力架构](docs/architecture/pandapower-capability-composition.md)与[可执行能力矩阵](configs/capabilities/pandapower-3.4.0-static-analysis.json)
- [Pandapower 应用说明](docs/PANDAPOWER-APPLICATION.md)：兼容 CLI、报告和证据契约
- [项目当前状态](docs/status/CURRENT-STATE.md)：实现进度与已知边界
