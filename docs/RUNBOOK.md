# 运行操作指南

Capstone's current shipped application is `grid-static-analysis` for
pandapower static analysis. This runbook documents that application and its
established grid compatibility and evidence contracts.

## 前置条件

- Python 3.12 或更高版本与 `uv`
- Node.js 22.19 或更高版本与 `npm`

## 初始化

在仓库根目录执行：

```sh
make setup
make doctor
```

`make setup` 分别同步 grid 产品的 `grid-agent`、`grid-simulator`、PyPSA 行业耦合、容量规划与运行计算 Pack 及其建模 Pack 与 authority 依赖，并以两个包各自的 lock 执行 frozen `npm ci`。inventory 参考域由 `make test-inventory` 按需同步和验证。grid 包的源码 lock 将 owning Pi 包绑定为本地 `file:` 依赖；发行 gate 会把该依赖转换回可独立安装的精确 `0.1.0` tarball 依赖。`make doctor` 不发送模型请求。grid／参考包和 PyPSA 包因 pandas 主版本约束分别安装在不同 Python 环境。

## 包模式与安装验证

本仓库包含十三个 Python 发行包和两个 Pi npm 包；新增中性会话宿主 `capstone-agent` 和 PyPSA 应用包 `pypsa-agent`：

| 发行包 | 资源所有权 |
| --- | --- |
| `capability-agent-kernel` | 领域无关的 Profile、契约源、执行器、投影、authority、工具目录、指南、轨迹和组合接口 |
| `capstone-agent` | 中性持久会话、无头与交互式 CLI、本地 HTTP/SSE 服务 |
| `grid-simulator` | `gridctl`、已登记 pandapower 网络、确定性计算、结果数据集和证据 |
| `pandapower-domain-pack` | pandapower 静态分析 Profile、能力契约、系统策略、指南、资源定位和兼容适配器 |
| `grid-agent` | CLI、Provider/Pi 运行时、认证、连续分析、报告、工作台服务和 stdout 答案封装 |
| `pypsa-agent` | PyPSA 双绑定应用 Profile 与独立工作进程 |
| `inventory-reference-service` | `inventoryctl`、已登记只读 catalog、`inventory-capability/1.0` 与内容寻址业务工件 |
| `inventory-domain-pack` | 只依赖公共 Kernel SPI 与 reference service 的 inventory Profile、策略、指南、执行器、投影和 authority |
| `pypsa-model-authority` | 已登记模型、不可变修订、固定求解和当前运行证据 |
| `pypsa-network-modeling-domain-pack` | 已登记模型打开、单值和逐时派生、检查与验证 |
| `pypsa-power-operations-domain-pack` | 授权调度、启停、滚动储能、拥塞 OPF、故障集和 AC 校验 |
| `pypsa-capacity-planning-domain-pack` | 授权容量扩建、联合启停、多期、随机和近最优规划 |
| `pypsa-sector-coupling-domain-pack` | 授权电转氢、热泵、储能和多端口平衡 |
| `@capability-agent/pi-tools` | 通用 Pi 能力请求构造、描述符校验、相关性检查和模型请求捕获 |
| `@grid-static-analysis/pi-grid-tools` | 当前 grid 产品的 Pi 扩展入口，保留 `grid_*` 工具名与 `grid_guide_open` |

源码开发模式使用 `pyproject.toml` 与 `package.json` 中的本地 path 依赖。安装验证模式使用仓库外临时目录：先构建十三个 Python wheel 与两个 npm tarball，再安装到干净 venv/npm 项目并执行 smoke 检查，确保兼容导入不会依赖源码路径。

```sh
make test-packages
```

该门禁也会运行 package boundary、protected-path digest 和 npm tarball 成员检查，拒绝反向业务依赖、源码路径耦合、测试、fixture、缓存、仓库根文件、环境文件、source map、密钥相关路径和路径逃逸。它不改变外部兼容 CLI、Pi 工具名、`grid-capability/1.0`、v1.0.1 stdout/stderr 契约、`runs/` 证据布局或 simulator-owned truth 边界；`analysis-generic` 使用独立的组合输出契约。

## Inventory 参考域验证

Workstream C 提供一个只读、非 grid 的第二领域，用于验证框架实例化能力，不是当前 `grid-agent` CLI 的可切换产品模式。执行完整参考域门禁：

```sh
make test-inventory
make test-packages
```

`inventory-reference-service` 发布 `inventoryctl`，仅接受 `inventory-capability/1.0` 的 `catalog.open`、`asset.list`、`asset.get` 与 `stock.summary` 只读能力。`inventory-domain-pack` 通过公共 `DomainRuntimeProfile` 注入 contract source、executor、projector registry 和 current-run authority。通用 `@capability-agent/pi-tools` 从 runtime descriptor 生成并执行 `inventory_*` 工具；模型仍不会获得 shell、任意 Python、通用文件操作或原始业务对象。

inventory 事实只由 `inventoryctl` 生成，并以 `inventory-revision/context/result/evidence:sha256:*` 内容引用持久化。authority 使用 no-follow、同绑定校验拒绝跨 run、篡改、符号链接、引用类型错配与未关联证据。该参考域没有创建、更新、预留、调拨或删除操作。

完整 Profile 还提供端点准备、状态/输出验证、指南、答案准入和展示组件。`make test-inventory` 包含真实 authority 的两轮应用、报告降级和回放验收；`make test-packages` 在仓库外使用 wheel 安装的 `inventoryctl` 重复完整应用，不依赖源码树。`guide:overview`、`guide:capability-map` 和 `guide:evidence-and-recovery` 可返回确定性打包信息；无引用业务请求仍为 limited，谱系准入不验证自由文本数值语义。运行环境仅保留明确的运行时白名单，不向 authority 透传 Provider/业务环境变量。

`make validate` 使用当前保护配置 `configs/runtime/application-instantiation-protected-paths.json` 检查已提交路径摘要与工作树清洁性。历史 Workstream C closure 的保护记录保留为当时证明，不能替代当前发布基线。

## Capstone 统一客户端

`capstone-agent` 按受信任的 `application_id` 选择持久应用工作进程；pandapower 与 PyPSA 保持平行的 Domain Pack 和独立 Python 环境。中性宿主负责会话、指令、进度、已提交答案和证据读取，应用工作进程负责 Profile 装配及所选 authority。工作进程使用带会话 ID、序号和大小限制的 JSONL 协议；请求不能指定任意命令或路径，也不向模型开放进程、文件或原始网络操作。

```sh
make setup-capstone
make capstone-agent-run REQUEST=validation/client/pandapower-scripted-task.json
make capstone-agent-run REQUEST=validation/client/pandapower-analysis-task.json
make capstone-agent-run REQUEST=validation/client/pandapower-analysis-test.json
make capstone-agent-run REQUEST=validation/client/pypsa-regional-demo.json
make capstone-agent-run REQUEST=validation/client/pypsa-scigrid-demo.json
make capstone-agent-run REQUEST=validation/client/pypsa-ac-dc-demo.json
make capstone-agent-chat APPLICATION=pandapower-static-analysis MODE=scripted-demo CASE=pandapower-scripted-task
make capstone-agent-serve CAPSTONE_PORT=8766
```

`pandapower-analysis-task.json` 和 `pandapower-analysis-test.json` 分别对应 `validation/questions/task.md.txt` 与 `test.md.txt`，使用 `mode: "provider"` 调用项目配置的真实模型；两份题单分别为 9 条和 7 条。`pandapower-scripted-task.json` 是无需 Provider 凭据的三回合演示，运行 pandapower 正式 Profile、真实 `gridctl` 和当前运行证据。PyPSA 示例也使用无需 Provider 的三回合脚本演示。请求字段为 `schema`、`application_id`、`instructions`，演示模式另带 `mode: "scripted-demo"` 与已登记 `case_id`。脚本演示严格核对该案例的指令顺序。

直接在终端运行无头命令时，工具进度显示相对时间、状态和简短结果，最终只显示完成摘要及报告路径；当 stdout 被管道或程序捕获时，仍输出单个 `capstone-client-result/1.0` JSON 对象。交互命令在同一会话中逐条接收指令并立即显示答案、结果与证据数量，不展开长引用。完整报告位于 `runs/capstone-agent/<run-id>/output/report.md`，运行结束时会打印实际完整路径。JSON 结果的 `result.core.report_ref` 给出已登记的报告工件引用。脚本演示的回答由确定性模型替身产生，不应当作真实 LLM 的分析叙述。

HTTP 服务只监听 loopback，首次启动在忽略的 `.capstone-agent/` 状态中创建权限为 0600 的操作者令牌。App 以 `Authorization: Bearer <token>` 调用 `POST /api/v1/sessions` 创建会话，向 `/api/v1/sessions/{id}/turns` 逐条提交指令，以 `GET /api/v1/sessions/{id}/events?after=<sequence>` 接收可按序号恢复的 SSE。`POST /api/v1/sessions/{id}/close` 完成会话；`GET /api/v1/sessions/{id}/turns/{ordinal}`、`/result` 和 `/evidence?ref=<reference>` 分别读取已提交答案、最终组合结果及经当前运行 authority 验证的证据。状态接口返回安全的 `error_code`；服务最多保留 32 个会话，达到上限返回 429，重启后会话不会恢复。服务拒绝非本机 Host、跨源 Origin、无令牌和未登记案例。旧的 `make capstone-client REQUEST=...` 仍为兼容入口。

两个应用均登记了 `mode: "provider"` 的自由文本路径，复用已有 Kernel/Pi 运行机制；可选 `provider` 和 `model` 仍按原运行时配置解析。真实 Provider 请求可能计费，本轮未执行计费验收；本地脚本演示不调用它。中性宿主只路由两个显式应用，不进行动态插件发现。

## Hosted App and deployment

独立的 `packages/capstone-app/` 是公开演示操作台，当前只开放已登记的三轮脚本案例。顶部电力科学AI主题图展示专业框架与科学计算模型，图下短文介绍 CAPSTONE 的领域能力与运行机制。目录浏览和打开案例不调用 Provider；选择案例即显示登记模型全图。点击「执行指令 1」会创建会话并直接提交首条指令，后续可逐条提交，也可点击「自动完成」让同一会话按序提交剩余指令、等待每轮已提交答案并结束运行。「停止自动执行」只停止后续步骤，已接受的当前指令会正常完成。切换案例时，当前标签页保留各案例最近一次会话、完成步骤选择和仍在运行的自动流程；显式启动新运行只重置该案例。报告生成后显示在中栏分析流程底部；右栏查看运行状态与当前运行准入证据。演示登录成功后当前标签页只保存连接标志；刷新时重新向 API 领取演示凭证并恢复工作台，不持久化凭证。页面调用相同的 `/api/v1` 接口，不关心 API/worker 所在平台。报告与当前运行准入证据由 API 从私有工件存储读取，浏览器不直接访问 bucket 或本地运行目录。

API 启动时预热已登记案例的权威模型图，已认证的 `GET /api/v1/cases/{application_id}/{case_id}/diagram` 直接返回经过边界校验的完整底图，不创建运行或证据。运行中的 worker 仍从该次运行登记的 `gridctl` 或 PyPSA authority 读取完整元件和坐标，将底图与逐步骤图层分别写入持久事件；API 通过已认证的 `GET /api/v1/sessions/{id}/network?ordinal=N` 重建指定步骤的投影，并以当前运行视图覆盖案例预览。SciGRID-DE 使用模型地理坐标展示全部 585 个母线、852 条线路和 96 台变压器；IEEE-39 使用模型电气示意坐标展示 39 个母线、35 条线路和 11 台变压器。非电网步骤继续显示同一底图，图层数值回到中性；完成步骤可点击回看，执行任务时重新对焦。白底拓扑图支持拖动平移、Shift + 滚轮或按钮缩放、适配全图和回到任务；普通滚轮滚动页面。电气示意图用短母线符号，地理拓扑图用位置点；图例仅列实际存在的元件类型。线路负载率着色仅覆盖同修订、同本轮已准入的逐元件结果，并标明数值单位和局部覆盖率；缺失的元件保持中性色。没有可验证底图时显示不可用状态，不影响已提交答案。模型面对的 PyPSA `model.topology` 仍只返回至多 50 个母线；完整底图只供操作视图使用。

本地使用一个后端镜像的 `api`、`worker` 两个角色，以及 PostgreSQL 和兼容 S3 的 RustFS：

```sh
cp deploy/local.env.example deploy/local.env
# 编辑 Git 忽略的 deploy/local.env，替换全部示例值。
docker compose --env-file deploy/local.env config --quiet
docker compose --env-file deploy/local.env up --build -d
curl -fsS http://127.0.0.1:8767/health/ready
make setup-capstone-app
make capstone-app-dev
```

在浏览器打开 `http://127.0.0.1:5173`；本地 Compose 默认启用公开演示模式，登录框自动填入服务端提供的演示凭证，点击「连接工作台」即可。该凭证只允许已登记的脚本案例；Provider 模式仍需私有 `CAPSTONE_OPERATOR_TOKEN`。仅 API 端口绑定本机 loopback；数据库和 bucket 不发布主机端口。若 8767 已被占用，可设置 `CAPSTONE_API_PORT` 更改 Compose 的发布端口，同时设置 App 的 `VITE_API_ORIGIN` 为该 API 原点。`make build-capstone-app` 生成静态发布产物，`make test-capstone-app` 运行前端定向测试。

镜像从已锁定的 grid/PyPSA/Capstone Python 环境与 npm 依赖构建，并在构建期安装、逐项校验六个官方 PyPSA 模型资产；运行时不会从宿主复制 `.grid-agent/` 或下载模型。API/worker 的差别只在 `/app/deploy/entrypoint.sh` 的角色参数。会话、命令幂等键与事件序号位于 PostgreSQL；报告和受限证据投影位于私有工件存储。worker 中途退出后租约到期会标记运行中断，先前已提交的答案仍可读取。API 的 `/health/ready` 检查 PostgreSQL，依赖 bucket 的操作仍以实际读写结果为准。

云端部署说明分别位于 [Cloud Run + Vercel](../deploy/cloud-run/README.md) 和 [Railway + Vercel](../deploy/railway/README.md)。Cloud Run 使用服务加 worker pool、Cloud SQL 和 GCS；Railway 使用 Web 与后台 worker、PostgreSQL 和私有 S3 bucket。两个后端角色须使用同一镜像 digest 和同一账本/工件配置。Vercel 项目根目录为 `packages/capstone-app`；构建变量 `VITE_API_ORIGIN` 是所选 API 的公开 HTTPS 原点，绝不能设置操作员或 Provider 凭据。API 设置 `CAPSTONE_PUBLIC_DEMO=true` 时，演示凭证由服务端发放并自动填入登录框；关闭该开关后仍可用私有操作员令牌。`CAPSTONE_ALLOWED_HOSTS` 与 `CAPSTONE_ALLOWED_ORIGINS` 分别约束 API Host 和 App Origin；`PORT` 在服务角色启动时读取。云端数据库、bucket、密钥和域名须先准备好，实际部署另行授权。

## PyPSA 电网模型库与本地案例

PyPSA 1.3.0 的六个官方 Network 示例与 15 个项目模型一起登记在模型库中。官方 NetCDF 只通过操作者命令下载，逐项核对固定文件大小和 SHA-256，保存于 Git 忽略的 `.grid-agent/runtime/pypsa-models/`。若要使用只读容器目录，可设置 `CAPSTONE_PYPSA_MODEL_LIBRARY_DIR` 指向已安装且校验过的资产目录。缺失或被改动的资产不能被 `model.open` 使用；案例运行中不会联网下载。

```sh
make setup-pypsa
make list-pypsa-models
make install-pypsa-models
make list-pypsa-cases
make run-pypsa-case CASE=regional-demand-stress
make run-pypsa-case CASE=ac-dc-interconnection
make run-pypsa-case CASE=scigrid-dispatch
make run-pypsa-case CASE=regional-demand-stress DEMO=1
make run-pypsa-case CASE=scigrid-dispatch DEMO=1
make run-pypsa-case CASE=ac-dc-interconnection DEMO=1
```

案例清单位于 `validation/pypsa-cases/cases.json`。`runnable` 表示已登记并通过本地应用链路的流程；`catalog-only` 表示模型已入库但相应的规划、储能价值或跨部门分析仍缺受控能力。`validation/pypsa_cases.py` 使用确定性脚本 Provider 验证 `AgentApplication`、两个 Domain Pack、授权模型交接、PyPSA 求解器和当前运行证据。它不检验真实 LLM 的问题理解和工具选择，也不代替需凭据且可能计费的 Provider 验证。

三个 `runnable` 条目各带 `introduction` 结构化字段，供 App 展示案例摘要、业务问题、PyPSA 框架支持、智能体交互变化、专业与框架价值、解读边界。`introduction.markdown` 指向同目录下的完整介绍：[区域负荷增长](../validation/pypsa-cases/introductions/regional-demand-stress.md)、[SciGRID-DE 调度](../validation/pypsa-cases/introductions/scigrid-dispatch.md)、[AC/DC 互联核查](../validation/pypsa-cases/introductions/ac-dc-interconnection.md)。介绍是静态案例说明，不含某次求解的数值结论；App 应从该次运行的展示 JSON 读取实际结果与证据。当前交互为选择已登记案例、由确定性脚本走完语义能力流程，尚未验收开放式 LLM 自主规划。

每个介绍另有 `current_user_input` 与按顺序排列的 `demo_instructions`。默认 `run-pypsa-case` 仍把案例清单中的单条固定 `question` 交给应用；`DEMO=1` 则在同一次 `ApplicationRequest.questions` 中提交三条登记指令，复用同一模型修订与应用运行。也可用 `INSTRUCTIONS=path` 提交每行一条指令的文本文件；脚本仅接受与该案例登记列表完全一致的内容。三个案例已在本地用确定性 Provider 完成多回合验收，展示 JSON 的 `turns` 按序提供指令、已提交答案及逐回合结果/证据引用；区域负荷比较还给出两次求解各自的结果引用。`pypsa-agent` 已登记正式双绑定 Application Profile；`capstone-agent` 逐条提交指令并返回本轮答案与证据。真实 LLM 对这些指令的理解与工具选择尚未验收。

每次 `run-pypsa-case` 的 stdout 为案例展示 JSON；完整副本写入 `runs/pypsa-cases/<run_id>/presentation.json`。其中包含模型来源与校验值、逐回合答案、情景、求解状态、带单位说明的目标或比较、受限拓扑、可追溯的答案/结果/证据引用。SciGRID-DE 只提供前 50 个母线及它们之间的分支预览，并明确给出省略数量。拓扑本身不代表求解后的潮流覆盖层；线路高负载列表来自独立的调度结果。官方示例的数据与假设需要结合原项目说明解释，不能用作运行许可。可参阅[模型库与案例设计](superpowers/specs/2026-09-26-pypsa-model-library-and-business-cases-design.md)。

## 主路径：执行自然语言分析问题

评测和人工验证智能体的自然语言理解、实体识别与多次工具编排时，使用 `make run-llm`。这是产品主路径：Pi/LLM 负责理解请求并组合发布的 pandapower domain tools，`gridctl` 负责所有确定性计算与证据。

```sh
make run-llm QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
make run-llm QUESTION="对IEEE-39节点系统运行交流潮流，并输出有功网损;"
make run-llm QUESTION="筛选负载率最高的5条线路;"
```

该路径需要按下一节配置 provider/Pi。stdout 始终是一个 JSON 对象，仅含 `question_id` 与 `answer_output`；进度与工具轨迹写入 stderr。每个创建 workspace 的单题运行都通过 `AgentApplication` 和 turn controller 提交，公开文本只从已提交且 admission-bound 的答案读取，而不是 Pi 文本或渲染结果。

## 离线冒烟与回归路径

`make run` 是本地、非计费的确定性路径，只覆盖明确支持的离线知识与诊断请求。它用于安装后冒烟、离线回归和验证器，不承担开放自然语言理解或多步智能体编排。

```sh
make run QUESTION="母线电压正常运行范围是多少?"
make run QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
```

标准输出始终是一个 JSON 对象，仅含 `question_id` 与 `answer_output`。数值计算和模型事实通过独立的 `gridctl` JSONL 进程完成，仿真边界固定为 pandapower 3.4.0；运行证据写入当前目录的 `runs/<question_id>/`。纯信息回答不会创建运行目录，也不会声称仿真证据。

对 TASK 中的潮流、排序、N-1 与风险分析请求，人工验收应使用上面的 `make run-llm` 主路径，以验证模型实际完成理解与多次工具编排。

`runs/` 是操作者可检查的运行记录，已被 Git 忽略。`.grid-agent/` 只存放项目内部 Pi OAuth、托管 Pi runtime、会话状态等内部状态，同样被 Git 忽略。版本化运行配置位于 `configs/runtime/`，例如 `configs/runtime/pi-runtime.lock.json`。

当前锁定 Pi 0.84.4。2026-09-05 对托管源码和两个扩展的三份 frozen lock 执行 npm audit，六项严重度/总计均为零，漏洞列表为空；真实构建 SDK 的通用/grid 捕获成功与拒绝路径也已验证。精确版本、源码、补丁、三份锁与依赖图、审计摘要和捕获结果记录在 [`configs/runtime/pi-security-remediation-v1.json`](../configs/runtime/pi-security-remediation-v1.json)。这是一份特定时间、特定依赖状态的验证记录，不保证未来没有新增 advisory，也不代替完整发布验收。

旧 Pi 0.80.6 的 2 个 High 和 2 个 Moderate 风险仍按原文保存在 [历史例外](../configs/runtime/pi-security-risk-exception-v1.json)，其 2026-09-30 到期日不变；不得将新版本审计结果写成旧版本漏洞已经消失。`make check-runtime-risk` 默认只做本地验证：新版本须匹配 remediation 绑定及实际安装图，旧版本继续受原例外与到期门约束，未知版本拒绝。审计不会在默认门禁中自动联网执行；release 操作者仍须复核可信 registry/audit 信息。

`make install-pi` 遇到含旧补丁或其他本地修改的托管源码时，会将整个目录保留为 `.grid-agent/runtime/pi/source-preserved-<id>` 后重新安装，不删除旧源码或认证状态。新安装未完成时不启用 active marker。`make test-pi-capture-runtime` 使用真实已构建 SDK 与两套扩展、仅替换模型传输端，离线验证先持久化再调用及捕获失败阻断；它已纳入 `check-integration` / `check-release`。

实际进入应用或连续分析运行时，CLI 在 stderr 输出 `model request capture: <status>`，不改变 stdout 答案封装。`enabled` 表示本次运行已配置完整捕获通道，`disabled` 表示没有配置通道，`unavailable` 表示使用注入的模型 transport 或在运行准备失败时无法声明捕获状态。Python/JS descriptor 均会预先拒绝不完整的通道组合。`enabled` 只说明配置，须检查当前 run 的 request 工件才能确认某次模型请求已被持久化。当前默认入口矩阵如下：

| 入口 | 默认状态 | 原因 |
| --- | --- | --- |
| `analysis` / `report` | `enabled` | 原生轨迹捕获及提交确认通道由连续分析装配。 |
| `analysis-generic` | `disabled` | 默认通用 Application 尚未配置 canonical request capture。 |
| `run` 的模型路径 | `disabled` | 单题兼容入口复用通用 Application。 |
| 注入脚本模型的测试装配 | `unavailable` | 没有可观察的真实 Pi 请求捕获配置。 |

`ApplicationOutcome.model_request_capture_status` 和 `AnalysisOutcome.model_request_capture_status` 向程序调用方提供同一诊断。真实捕获失败继续由现有 Pi/轨迹完整性路径阻断；诊断字段本身不作为证据，也不改变答案成功条件。

## 连续分析报告

需要按顺序执行 TASK 指令集并生成可复核报告时，使用 `make analysis`：

```sh
make analysis
make analysis INSTRUCTIONS=validation/questions/task.md.txt
```

`grid-agent analysis --instructions PATH` 会在一个 Pi/LLM 进程中执行整个指令文件；后续指令可以复用同一分析目录中已验证的上下文、结果和证据。stdout 只输出一个最终 `AnswerEnvelope`，其中 `question_id` 是 `analysis-<UTC timestamp>`，`answer_output` 是项目相对报告路径，例如 `runs/analysis-20260814T120000Z/report.md`。进度、工具事件、检查点和诊断全部写入 stderr。

每次分析的输入副本、逐回合答案、上下文账本、上下文快照、证据、trace 和最终报告都保存在同一个 `runs/<analysis_id>/` 目录中；逐回合答案写入 `output/answers.jsonl`，不会流式写到 stdout。该迁移不支持独立 `--output`/`--report-path`、resume、命名 session 或 session 切换。

`make report` 和 `grid-agent report --questions PATH` 是兼容别名，委托同一个连续分析路径；它们不再启动每题一个 `grid-agent run` 子进程。

## 通用应用实例化路径

正式内建 pandapower 应用的入口是：

```sh
make application
```

它沿着 `ApplicationProfile -> AgentApplication -> DomainBinding -> Domain Pack`
组装运行时。Kernel 负责组合结果的 `core`（运行身份、生命周期、回合、审计和引用），Domain Pack 负责 `domains.<binding_id>` 的领域载荷；通用 stdout 结果遵循 `capability-agent-output/1.0`，不会把领域字段误当成所有应用共同的答案字段：

```json
{"schema":"capability-agent-output/1.0","core":{...},"domains":{"grid":{...}}}
```

通用运行的答案完成与报告发布分开判定。报告/进度派生故障不会撤销已接受答案；
最终报告不可用时 `core.report_ref` 与领域 `report_artifact_ref` 为 null。
领域 schema 显式升级为 `pandapower-static-analysis-output/1.1`，core schema 不变；
非空报告引用仍须通过当前运行接纳。查看 `core.diagnostic_refs` 及
`runs/<run_id>/core/diagnostics/<code>/diagnostic.json`，若诊断工件也无法保存则检查
stderr 固定诊断。不要把没有接纳引用的报告检查点当作可信最终报告；必要答案、
证据和上下文完成事务失败仍会使运行失败。

运行后应在 `runs/<run_id>/` 检查当前运行结果/证据 lineage、上下文快照与 replay、答案审计、工具轨迹和已接纳的报告工件。`make application` 是需要 Provider 的正式产品入口；Provider 凭据只保存在环境变量或项目拥有的 ignored 认证状态中，不写入命令参数、提交文件、日志或工件。完整参数、输出契约、兼容边界和当前运行证据检查见 [Pandapower Static-Analysis Application](PANDAPOWER-APPLICATION.md)。

Task 10 的无 Provider 验收用确定性的 scripted model transport 调用同一份已准备 pandapower endpoint，再由真实语义 `gridctl` 执行工具调用。它覆盖 `validation/application/` 中的两个脚本案例，并检查当前运行引用、上下文复用、答案审计、报告摘要/接纳、replay equality 和 `core` + `domains.grid` 输出：

```sh
make validate-application
```

该门禁是应用 wiring 与安全边界的可复现验收，不等同于 Provider-backed 业务运行。C.1 已完成：`validation/questions/task.md.txt` 与 `validation/questions/test.md.txt` 均已通过获得授权的 Provider 在 `analysis-generic` 路径完成，并通过当前运行证据、答案、报告和 replay 审计；显式 v1.0.1 compatibility 路径也已通过。`inventory-domain-pack` 仍只用于 fixture/conformance 参考，不是生产 CLI 的第二领域模式。

第一领域完整应用的 Provider-backed 复现、当前运行证据审计，以及无 Provider 门禁的组合方式统一记录在 [Pandapower Static-Analysis Application](PANDAPOWER-APPLICATION.md)。

`run`、`analysis` 和 `report` 是显式的 v1.0.1 兼容路径，仍由兼容适配器输出 stdout 中精确的 `question_id` 与 `answer_output` 两个字段；通用入口的组合 `core` 与 `domains` 结果不会被误称为这两个字段。

## 本地轨迹工作台

面向日常操作的界面说明、排障和 API 示例见 [轨迹工作台操作手册](TRAJECTORY-WORKBENCH-OPERATOR-GUIDE.md)。

已存在的原生或兼容 v0.2 分析目录可通过只绑定回环接口的服务检查：

```sh
make trajectory PORT=8765
# 等价：grid-agent trajectory serve --host 127.0.0.1 --port 8765 --runs-root runs
```

`make trajectory` 每次都会先构建并打包 workbench 静态资源，再在 `http://127.0.0.1:8765` 提供同源 UI 与只读 API。只需要更新静态资源时使用 `make build-workbench`；首次安装或重装依赖使用 `make setup-workbench`。生产资源随 `grid-agent` wheel 一起发布，服务启动时会验证 `index.html`、`assets/app.js` 和 `assets/app.css` 都存在；缺失时会清晰失败并提示运行 `make build-workbench`。浏览器的非 `/api/` 客户端路由返回 SPA 入口，`/api/*` 永远保持 JSON API 响应（包括 404）。

首版只接受 `127.0.0.1`、`::1` 或 `localhost`；例如 `0.0.0.0` 和局域网地址会在启动前被拒绝。该操作是服务命令，不产生答案 JSON；启动和故障诊断只写 stderr，使用 Ctrl-C 停止。

服务仅提供 GET：`/api/runs`、`/api/runs/{analysis_id}`、`/api/runs/{analysis_id}/business`、`/api/runs/{analysis_id}/agent`、`/api/runs/{analysis_id}/context?at_sequence=N` 与 `/api/runs/{analysis_id}/artifacts/{artifact_ref}`。工件必须已在投影索引登记并在读取时重新校验摘要；任意路径、Pi 原始 sidecar、符号链接逃逸和未知引用都会被拒绝。响应固定为不可执行数据类型，并包含 CSP、`nosniff`、拒绝 frame、`no-referrer` 和 `no-store`；服务没有 CORS、写入路由或实时流。

## LLM 配置与 Pi RPC 路径

配置写在仓库根目录的 `.env`：它已被 Git 忽略。先复制模板，再只填写一个实际使用的密钥：

```sh
cp .env.example .env
# 编辑 .env：例如保留 GRID_AGENT_LLM_PROVIDER=openai，填写 OPENAI_API_KEY=...
```

可选的非密钥参数也写在 `.env`：`GRID_AGENT_LLM_MODEL`、`GRID_AGENT_LLM_BASE_URL`、`GRID_AGENT_LLM_TIMEOUT_SECONDS` 与 `GRID_AGENT_LLM_MAX_RETRIES`。后两项分别是单次 provider 请求的秒数和重试次数（`0` 禁用重试）；每次 `make run-llm` 都会写入项目私有的 Pi `settings.json`，同时作用于 Pi 的 HTTP 空闲时限、SDK 请求时限和自动重试。命令行参数优先于 `.env`，进程环境变量优先于 `.env`。支持的 provider 与默认密钥变量为：`openai`/`OPENAI_API_KEY`、`openrouter`/`OPENROUTER_API_KEY`、`deepseek`/`DEEPSEEK_API_KEY`、`minimax`/`MINIMAX_API_KEY`。`openai-codex` 使用 Pi OAuth，而不是 API key。

DeepSeek 模型名以其[官方模型列表](https://api-docs.deepseek.com/api/list-models/)为准；项目只校验非空模型名，不维护 DeepSeek 模型白名单。当前官方模型列表包含 `deepseek-flash` 与 `deepseek-v4-pro`。Pi 对尚未收录的显式模型名使用自定义模型 ID，最终是否可用由 DeepSeek API 验证。

Pi 运行时按以下顺序发现：`GRID_AGENT_PI_COMMAND`、项目托管版本、`PATH` 中的 `pi`。因此 Pi 已在 `PATH` 时无需配置 `GRID_AGENT_PI_COMMAND`；否则可在 `.env` 设置该绝对路径，或在仓库根目录执行 `make install-pi` 安装本项目锁定版本到 `.grid-agent/runtime/pi`。模型密钥会仅在启动 Pi 子进程时通过环境变量传递，不写入 `.grid-agent/auth/pi` 的配置文件或命令行。

当 `GRID_AGENT_LLM_PROVIDER=openai-codex` 时，不填写 API key。先从已经登录的本地 Pi 导入 OAuth 凭证，或登录到项目自己的 Pi OAuth 配置：

```sh
make auth-import-pi
# 若尚未有本地 Pi 登录态：先 make install-pi，再 make auth-login
```

```sh
# 默认读取 .env 中的 GRID_AGENT_LLM_PROVIDER
make run-llm QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"

# 临时覆盖 .env 中的 provider
make run-llm PROVIDER=deepseek QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
```

`make run` 始终是本地、非计费的离线 gridctl 路径；`make run-llm` 才会调用配置的 LLM，并把受控的 `gridctl` 放入 Pi 的受限 PATH。Pi 只暴露项目生成的 `grid_*` domain tools 和 `grid_guide_open`；不会启用通用 shell/read/write/edit 内置工具。模型完成必要工具使用后返回普通面向读者的最终文本；每个创建 workspace 的单题运行与连续 `analysis` 都由 `grid-agent` 控制器确定性绑定当前回合的结果/证据引用并完成答案提交。

`make run-llm` 的 stdout 仍只输出最终 JSON；实时进度写到 stderr，包括运行耗时、provider/model、生效的超时与重试参数、输入与输出前 200 字摘要、Pi 工具事件、重试事件，以及超过 10 秒无事件时的等待提示。密钥字段会被隐藏。单题在线 `run` 的 stdout 只投影已提交、admission-bound 的 reader text；其 canonical workspace 保留 `core/events.jsonl`、domain 工具结果与 evidence，并在 `turns/<turn_id>/` 写入 `answer-draft.json`、`answer.json` 和 admission sidecar。

若日志出现 `401 ... authentication_error`，表示当前 provider 的 API key 无效、过期或与所选 provider 不匹配；更新 `.env` 中对应的密钥后重新运行。该错误不会重试。若出现 `Request timed out`，先确认日志首行的超时和重试参数，再检查 provider 服务状态或提高 `GRID_AGENT_LLM_TIMEOUT_SECONDS`。单题运行原始事件应从 `runs/<question_id>/core/events.jsonl` 检查；根目录 `events.jsonl` 仅在兼容快照成功发布后可用。创建 workspace 或事件日志前发生的故障可能没有日志文件，此时使用 stderr 诊断。

### 启动阶段领域运行时故障

`grid-agent run` 和连续 `analysis` 在模型执行前会物化内建 pandapower Profile。以下故障沿用当前 stderr 诊断和 stdout 错误 envelope 行为；其中发生在 Profile、合同、指南、策略或 `environment.describe` 阶段的错误不会启动模型执行：

| 故障类型 | 常见含义 |
| --- | --- |
| invalid Profile/manifest | `DomainManifest` 字段非法，或 manifest 声明的资源、协议、工具前缀与运行环境不兼容 |
| protocol mismatch from `environment.describe` | `gridctl` 返回的 `protocol` 或 `protocol_version` 与 Profile 声明不一致 |
| missing capability contract root | Profile 指向的 capability contract 目录不存在、为空或包含无法解析的合同 |
| missing guide or system policy resource | `guide_root` 或 `system_policy_path` 缺失，导致 Pi 工具指南或系统策略无法物化 |
| existing gridctl transport errors | `gridctl` 无法启动、超时、stdout 不是单条匹配请求的 JSON 协议响应，或返回 typed simulator error |
| evidence-integrity errors | 当前运行结果、证据、authority 或 lineage 未通过现有内容引用校验，不能被跨回合复用或绑定到答案 |

当前没有领域选择命令；CLI 固定选择内建 pandapower 静态分析 Profile。需要切换领域时必须先经过后续 Workstream 的设计和命令契约变更。

## Skill 与工具边界

Pi 只能访问项目发布的 grid domain tools 和 `grid_guide_open`。工具描述由发布的 capability 契约生成；`skills/grid-static-analysis/` 说明如何组合不可变模型、完整网络/结果数据集、分析和证据。模型不得在回答正文中暴露内部 result/evidence/context/asset/constraint/path/nonce 标识；运行时根据当前回合已消费和已产生的 lineage 提交答案。

当前发布面覆盖 60 个注册网络、声明式创建与不可变修订、全静态表访问、拓扑、AC/DC/三相潮流、AC/DC OPF、IEC 60909、状态估计、诊断、AC/DC N-1、模型约束越限、风险排序、电网等值和静态保护。`configs/capabilities/pandapower-3.4.0-static-analysis.json` 是范围矩阵，`environment.describe` 是运行时权威；动态仿真、时序控制、任意文件导入、任意 Python/I/O 和未固定的外部求解器仍是明确排除项。

## 证据检查

每个 simulator-backed 单题 `run` 使用 canonical workspace；兼容根路径是应用发布的物理快照：

- `runs/<question_id>/core/events.jsonl`：canonical Kernel 事件 trace；根 `events.jsonl` 是字节保持兼容副本。
- `runs/<question_id>/domains/grid/tool-results/`：canonical domain 结果；根 `tool-results/` 是兼容副本。
- `runs/<question_id>/domains/grid/evidence/`：canonical 当前运行证据；根 `evidence/` 是兼容副本。

根兼容副本不是 authority 输入，也不会创造证据。兼容发布失败会使 CLI 非零，但不会删除已提交的 canonical 答案；已经发布的完整兼容子树或私有暂存可保留用于诊断。

连续 `analysis` 额外写入 controller-owned 答案工件：`runs/<analysis_id>/turns/NNN/answer-draft.json` 是控制器根据当前回合最终文本和已消费/已产生 lineage 生成的提交草稿，`turns/NNN/answer.json` 是已接受的答案 envelope，`output/answers.jsonl` 汇总逐回合已接受答案。

在线运行不要求模型使用答案持久化工具。单题 `run` 与连续 `analysis` 都由控制器写入 `answer_output`、`result_refs` 和 `claim_evidence_refs`，并验证这些引用确实来自当前运行和当前回合 lineage。验证器不从 `answer_output` 文本中解析引用。`result_refs` 用来声明直接支撑最终结论的主结果，分析证据中已经关联的结果也会被自动定位、校验其当前运行归属和上下文一致性。拓扑事实可使用空 `result_refs`；AC、排序和 N-1 等结果型结论必须有当前运行的主结果或与其相连的分析证据。

连续分析的 stderr 应显示分析工具调用和一次正常模型完成；trace 不应包含模型发起的 `grid_submit_answer` 调用。若任一必需回合失败，运行状态为 `failed`、CLI 退出码为 `1`，且 `report.md` 必须在回答占位符之后保留该回合已经成功返回的可观察轨迹与工具结果摘要。

最终答案只能引用当前运行中实际存在的 `evidence:sha256:*` 或 `result:sha256:*`。迁移和清理不会删除用户主工作树中的既有 `var/` 数据；本分支只使用新的 ignored `runs/` 和 `.grid-agent/` 布局。

保证范围：引用准入证明当前运行谱系和内容完整性，不逐句验证模型自由文本。确定性事实展示应回到已验证的 authority 结果核对。报告/观察器失败通过独立诊断体现，不撤销已接纳的主答案；排查时分别检查主答案和报告状态，不把报告缺失等同于业务计算失败。必需的证据、答案和上下文提交失败不按展示故障降级。

## 验证

需要逐项人工核验命令、stdout 边界、结构化工具轨迹和证据引用时，请使用 [人工验证手册](MANUAL-VALIDATION.md)。该手册只使用本 Makefile 发布的入口。

```sh
make test
make test-e2e
make validate
make validate-application
make test-inventory
make test-packages
```

`make test` 是完整离线单元入口：分别运行十三个 Python 包、两个 Pi 包、workbench 与 verification-target 自检；其中 grid-agent 单元命令显式排除 E2E，`make test-e2e` 保持为离线命令行和脚本化 Pi → gridctl 的集成层。`make test-inventory` 运行 reference service、Domain Pack 和 unchanged generic Pi transport，避免在 domain 子目标重复 transport 测试。`make test-pypsa` 聚焦 PyPSA authority、建模、运行计算、容量规划和行业耦合 Pack。`make test-packages` 构建并安装干净发行工件，验证十三个 Python distribution 与两个 Pi npm 包的源码路径隔离和兼容入口。`make setup` 同步 agent/simulator/Capstone/PyPSA/tools/workbench；inventory 测试通过各自 `uv run` 按需创建环境。

`make check-types` 使用锁定的 pyright 1.1.408，standard 模式、Python 3.12 最低版本，覆盖全部生产 `src` 树，并运行 workbench check。Kernel `output.py` 保留 3 个局部 Pydantic schema-attribute override，以维持现有公开 wire 属性；这不是整包忽略。`make check-fast` 为边界、类型和单元层，`make check-integration` 为 E2E 与两项 provider-free validation，`make check-release` 再加入 package 与 source-setup 检查。所有这些 gate 不调用 provider 或使用付费凭据。

仓库已配置 GitHub Actions：Linux/macOS × Python 3.12/3.14，Node 22.19.0，依次执行 setup、install-pi、doctor 和 `check-release`。这是配置说明，尚不代表远端 CI 已验证通过。

`make validate` 运行三层 deterministic validation：offline `task-required`、scripted-Pi `static-analysis-core`，以及绑定 `docs/test_script/测试题目答案.jsonl` 的 `static-analysis-full` 语义验收。报告分别写入 ignored `runs/validation-offline.json`、`runs/validation-scripted.json` 与 `runs/validation-static-analysis-full.json`；能力矩阵不足 100% 也会失败。语义验收比较真实工具结果事件和标准答案，不比较润色后的答案文字。
`make validate-application` 是独立的 provider-free generic application gate，报告写入 `runs/validation-application-instantiation.json`；它验证第一领域 pandapower 的完整 Profile/Binding/Domain Pack 实例化，不选择或宣称第二个生产领域。

`make check-protected-paths` 和 `make validate` 使用当前 C.1 repository gate：`configs/runtime/application-instantiation-protected-paths.json`。该运行时策略固定保护不可变的 acceptance 输入和 simulator truth boundary：`configs/capabilities/pandapower-3.4.0-static-analysis.json`、`packages/grid-simulator`、`packages/inventory-domain-pack`、`packages/inventory-reference-service`、`validation/questions/task.md.txt` 与 `validation/questions/test.md.txt`。每项 digest 均来自该路径的已提交 `HEAD:<path>` Git 对象；gate 同时拒绝这些路径的 working-tree 变更。

该 C.1 策略刻意不保护将在已批准后续任务中变更的 `packages/capability-agent-kernel`、`packages/pi-capability-tools`、`packages/trajectory-workbench`、`packages/grid-agent` 和 `packages/pandapower-domain-pack`。这不会改写 Workstream C 的历史证据：`docs/status/climb/config.yaml` 继续以其记录的 source revision 与 protected-path baseline 证明当时的 closure。

Workstream C 的最终本地 release closure 必须从已提交且干净的 release-source revision 运行：

```sh
tools/climb/cycle.sh C-H005
```

该入口不接受 gate 或 command 覆盖。它按 `docs/status/climb/config.yaml` 中受固定 allowlist 校验的顺序，现场执行 inventory reference authority、Domain Pack SPI、通用 Pi transport、authority lineage、发行工件、`make doctor`、`make test`、`make test-e2e` 和 `make validate` 共九个门。策略文件本身、精确命令、权重、前置图、protected-path baseline 和 release pathspec 都进入 policy/source tree digest；每个门前后都重新检查 clean revision、tree digest 和 policy digest。只读 closure 链记录命令、rc、stdout/stderr digest 和完整输出 digest，最终 100 分不读取 carry-forward receipt。

`tools/climb/gate-receipt.py <gate-key>` 仍可为同一 revision 生成内容寻址的机械记录。其 mode-0600 HMAC 只用于发现意外损坏；密钥和验证器对同一 OS 用户可见，因此它不是独立信任根，也不能证明同一用户无法重签。release closure 会现场重跑全部门，不以这些 HMAC receipt 代替执行。该本地链只证明本次本机命令的可复核执行，不宣称具有 CI/外部签名者的跨主体不可伪造性。

可选 provider validation 会产生真实模型调用，必须显式给出 provider 且环境中已有对应凭证：

```sh
make validate-provider PROVIDER=openai MODEL=gpt-5.5
# 可覆盖验证集；默认 static-analysis-full
make validate-provider PROVIDER=openai MODEL=gpt-5.5 VALIDATION_SUITE=task-required
```

报告写入 `runs/validation-provider.json`，分别记录编排完成度、语义正确性、证据和工具调用效率；效率预算是诊断分，不会覆盖正确的主结果或阻断分析入口。报告记录 provider/model、trace、延迟以及可用的 token/cost 元数据，不写入密钥。
