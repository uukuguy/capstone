# Capstone Agent Framework

简体中文 | [English](README.md) | [打开在线 Demo](https://capstone-app-production-975e.up.railway.app/)

**用智能体对话开展电网分析。**

Capstone 把自然语言指令、电网模型和分析结果放在同一个工作台中。你可以让智能体检查网络、执行计算，或继续追问某项结果。智能体选择已发布的领域工具，pandapower 和 PyPSA 提供模型事实与计算能力；计算结果及其证据随对话保留，便于查看与核查。

![当前 Capstone 智能体对话工作台：左侧 IEEE-39 拓扑图，右侧包含潮流结果的智能体回答](docs/images/capstone-agent-conversation.png)

## 从一句指令开始

打开[在线 Demo](https://capstone-app-production-975e.up.railway.app/)，或在本地运行 App。首页直接进入智能体对话。在**模型**菜单中选择已登记的电网模型，也可以通过自然语言打开模型，然后围绕它提出分析请求。

例如，分析 IEEE-39 时可以连续发送：

```text
有哪些 pandapower 的电网模型？
打开 ieee39 电网模型。
执行一次交流潮流，报告收敛状态和全网有功损耗。
基于刚才的结果，筛查负载率最高的三条线路。
查看这些线路的端点母线，以及支持回答的结果与证据。
```

在同一段对话中继续追问结果或细化分析。每条指令都绑定到一个模型上下文和运行。**新建对话**会创建独立的 Thread；保存其链接后，刷新页面仍能回到同一段对话。

智能体对话是主要入口。已登记案例保留为引导流程与验证样例；早期的案例库页面位于 `/old`。

## 可以分析什么

| 模型家族 | 当前对话提供的能力 |
| --- | --- |
| pandapower | 登记模型检查、母线与支路查询、拓扑、交流与直流潮流、网损、负载率、模型约束检查和 N−1 分析 |
| PyPSA | 登记模型检查与负荷派生、固定容量经济调度、机组启停、滚动储能调度、拥塞 OPF、登记故障集的安全调度，以及调度后的交流潮流校验 |

可用操作取决于选定模型和已发布的能力契约。完整拓扑不可用时，模型菜单会说明原因。准确的执行范围见 [pandapower 能力矩阵](configs/capabilities/pandapower-3.4.0-static-analysis.json)、[PyPSA 建模目录](configs/capabilities/pypsa-1.3.0-modeling.json)和 [PyPSA 运行计算目录](configs/capabilities/pypsa-1.3.0-power-operations.json)。

例如，选择 PyPSA 的 `two-bus` 模型，要求先做经济调度，再执行交流潮流校验：

![当前 Capstone PyPSA 智能体对话：左侧双母线拓扑，右侧经济调度与交流潮流校验结果](docs/images/capstone-pypsa-conversation.png)

这些截图来自在线 App 对已完成分析的回看。图中的数值属于对应运行，不是预设答案或性能基准。

## 从回答查看计算与证据

回答下方的操作可以打开该指令对应的电网图、查看已准入的结构化结果、读取证据，以及回看执行步骤。电网图支持平移、缩放和元件定位；标注使用模型名称，并带 `bus`、`line`、`trafo` 前缀，PyPSA 的 Link 使用 `link`。

数值图层只使用匹配模型修订和当前运行的已准入结果，缺失值保持中性。线路负载率色阶描述返回数值的分布；是否越限由约束评估判断。

模型事实和数值结论来自已登记的权威系统。模型目录等信息性回答不会创建计算证据。结果、报告和证据可以经 API 回看；浏览器只读取私有存储中的受限投影。

## 在本地运行

需要 Python 3.12+、`uv`、Docker Compose、Node.js 22.19+ 和 npm。首次检出仓库时执行：

```sh
git clone https://github.com/uukuguy/capstone.git
cd capstone
make setup
make install-pi
make install-pypsa-models
cp deploy/local.env.example deploy/local.env
```

编辑 Git 忽略的 `deploy/local.env`，替换数据库、存储、操作员和 Provider 的示例凭据。运行时选择项应与[共享宿主运行配置](configs/runtime/host-runtime-v1.json)一致。Provider 凭据仅保留在后端配置中；普通智能体对话使用已配置的 LLM，可能产生 Provider 费用。具体配置见[运行手册](docs/RUNBOOK.md#hosted-app-and-deployment)。

使用仓库统一入口启动 API、pandapower worker、PyPSA worker 和 App：

```sh
make capstone-local-rebuild
```

打开 `http://127.0.0.1:5173/`。本地 Compose 直接开放对话访问，无需浏览器令牌。重建入口检查依赖与服务就绪状态，确认 API 和两个 worker 使用同一镜像，并在需要时启动 Vite App。它复用本地已校验的 PyPSA 模型资产。修改 API、worker 或 App 源码后，再运行这一入口。

App 默认也监听局域网接口，同一网络中的手机可打开 `http://<电脑局域网 IP>:5173/`。设置 `CAPSTONE_APP_HOST=127.0.0.1` 可限制为本机访问。需要在前台查看 Vite 日志时，使用 `make capstone-app-dev`。

## 框架怎样支撑对话

```text
Application → Domain Pack → Kernel → registered Authority
```

| 层 | 负责什么 |
| --- | --- |
| Application | 选择模型家族、能力绑定和 Provider，提供对话、API、CLI 与答案视图 |
| Domain Pack | 拥有语义工具、契约、策略、指南、执行，以及结果与证据准入 |
| Kernel | 管理步骤、受限上下文、轨迹、工件和回放 |
| Authority | 访问登记模型，执行计算或查询来源事实，产生结果与证据 |

智能体只调用白名单中已发布且具有明确契约的语义工具。模型接口不开放原始 pandapower/PyPSA 对象、任意代码、shell 命令或通用文件访问。领域系统通过明确的结果和证据引用返回事实。Kernel 保持领域中立，其他应用也可以接入独立安装的 Domain Pack 和已登记权威系统。

仓库还包含 PyPSA 容量规划与行业耦合 Domain Pack；当前托管的 PyPSA 对话选择建模和运行计算能力。组合机制见[框架架构](docs/architecture/capstone-framework.md)，扩展方式见 [Domain Pack 接入指南](docs/guides/domain-pack-onboarding.md)。

## CLI 与兼容入口

CLI 可用于自动化和定向检查。完成安装后，可执行不调用 Provider 的 pandapower 查询：

```sh
make doctor
make run QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
```

需要 LLM 编排时，先按[运行手册](docs/RUNBOOK.md#llm-配置与-pi-rpc-路径)配置 CLI 的 Provider，再执行：

```sh
make run-llm QUESTION="对 IEEE-39 执行交流潮流，并报告有功损耗。"
```

`grid-agent` 保留为 pandapower 兼容 CLI，答案、报告和标准输出契约见 [pandapower 应用说明](docs/PANDAPOWER-APPLICATION.md)。统一的 `capstone-agent` CLI 和引导案例命令见[运行手册](docs/RUNBOOK.md#capstone-统一客户端)。确定性脚本样例用于离线验证，与普通 LLM 对话分开。

## 开发与部署

本地 Compose 加 Vite 用于日常迭代，cloud-dev 用于远端集成验证，demo 提供已验证的用户试用版本。cloud-dev 与 demo 分别使用自己的数据库、工件存储、凭据和公开域名。demo 晋级使用在 cloud-dev 验收过的同一源码版本或工件。

App 定向检查使用 `make test-capstone-app` 和 `make build-capstone-app`。仓库离线门禁为：

```sh
make doctor
make test
make test-e2e
make validate
```

Provider 验证是需要单独授权的检查。部署步骤和运行配置集中在操作文档中：

- [开发与发布生命周期](docs/architecture/capstone-development-lifecycle.md)
- [Railway 部署](deploy/railway/README.md)
- [Cloud Run + Vercel 部署](deploy/cloud-run/README.md)
- [运行手册](docs/RUNBOOK.md)
- [项目当前状态](docs/status/CURRENT-STATE.md)
