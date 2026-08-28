# 运行操作指南

## 前置条件

- Python 3.12 或更高版本与 `uv`
- Node.js 22.19 或更高版本与 `npm`

## 初始化

在仓库根目录执行：

```sh
make setup
make doctor
```

`make setup` 分别同步 `grid-agent`、`grid-simulator`、`capability-agent-kernel` 与 `pandapower-domain-pack` 的本地 path 依赖，并以两个包各自的 lock 执行 frozen `npm ci`。grid 包的源码 lock 将 owning Pi 包绑定为本地 `file:` 依赖；发行 gate 会把该依赖转换回可独立安装的精确 `0.1.0` tarball 依赖。`make doctor` 不发送模型请求。

## 包模式与安装验证

本仓库现在按四个 Python 发行包和两个 Pi npm 包组装：

| 发行包 | 资源所有权 |
| --- | --- |
| `capability-agent-kernel` | 领域无关的 Profile、契约源、执行器、投影、authority、工具目录、指南、轨迹和组合接口 |
| `grid-simulator` | `gridctl`、已登记 pandapower 网络、确定性计算、结果数据集和证据 |
| `pandapower-domain-pack` | pandapower 静态分析 Profile、能力契约、系统策略、指南、资源定位和兼容适配器 |
| `grid-agent` | CLI、Provider/Pi 运行时、认证、连续分析、报告、工作台服务和 stdout 答案封装 |
| `@capability-agent/pi-tools` | 通用 Pi 能力请求构造、描述符校验、相关性检查和模型请求捕获 |
| `@grid-static-analysis/pi-grid-tools` | 当前 grid 产品的 Pi 扩展入口，保留 `grid_*` 工具名与 `grid_guide_open` |

源码开发模式使用 `pyproject.toml` 与 `package.json` 中的本地 path 依赖。安装验证模式使用仓库外临时目录：先构建四个 Python wheel 与两个 npm tarball，再安装到干净 venv/npm 项目并执行 smoke 检查，确保兼容导入不会依赖源码路径。

```sh
make test-packages
```

该门禁也会运行 package boundary 检查并检查 npm tarball 成员，拒绝测试、fixture、缓存、仓库根文件、环境文件、source map、密钥相关路径和路径逃逸。它不改变外部 CLI、Pi 工具名、`grid-capability/1.0`、stdout/stderr 契约、`runs/` 证据布局或 simulator-owned truth 边界。

## 主路径：执行自然语言分析问题

评测和人工验证智能体的自然语言理解、实体识别与多次工具编排时，使用 `make run-llm`。这是产品主路径：Pi/LLM 负责理解请求并组合发布的 pandapower domain tools，`gridctl` 负责所有确定性计算与证据。

```sh
make run-llm QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
make run-llm QUESTION="对IEEE-39节点系统运行交流潮流，并输出有功网损;"
make run-llm QUESTION="筛选负载率最高的5条线路;"
```

该路径需要按下一节配置 provider/Pi。stdout 始终是一个 JSON 对象，仅含 `question_id` 与 `answer_output`；进度与工具轨迹写入 stderr，simulator-backed 问题的证据写入 `runs/<question_id>/`。

## 离线冒烟与回归路径

`make run` 是本地、非计费的确定性路径，只覆盖明确支持的离线知识与诊断请求。它用于安装后冒烟、离线回归和验证器，不承担开放自然语言理解或多步智能体编排。

```sh
make run QUESTION="母线电压正常运行范围是多少?"
make run QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
```

标准输出始终是一个 JSON 对象，仅含 `question_id` 与 `answer_output`。数值计算和模型事实通过独立的 `gridctl` JSONL 进程完成，仿真边界固定为 pandapower 3.4.0；运行证据写入当前目录的 `runs/<question_id>/`。纯信息回答不会创建运行目录，也不会声称仿真证据。

对 TASK 中的潮流、排序、N-1 与风险分析请求，人工验收应使用上面的 `make run-llm` 主路径，以验证模型实际完成理解与多次工具编排。

`runs/` 是操作者可检查的运行记录，已被 Git 忽略。`.grid-agent/` 只存放项目内部 Pi OAuth、托管 Pi runtime、会话状态等内部状态，同样被 Git 忽略。版本化运行配置位于 `configs/runtime/`，例如 `configs/runtime/pi-runtime.lock.json`。

当前 Pi 0.80.6 依赖树仍有 2 个 High 和 2 个 Moderate 已知漏洞；它们没有被修复，也不能表述为已消失。临时受理记录是 [`configs/runtime/pi-security-risk-exception-v1.json`](../configs/runtime/pi-security-risk-exception-v1.json)，绝对到期日为 2026-09-30，列出了 provider HTTP/解析攻击面、缓解措施、责任人和升级触发条件。`make check-runtime-risk` 会确定性检查 Pi pin、两个 npm lock 中的脆弱版本、实际 `node_modules` 安装图与 lock 的逐包版本一致性、基线计数和到期日；任一漂移或到期都使 gate 失败。该本地门不声称发现锁版本后来新增的 advisory；release 操作者仍须复核可信 registry/audit 信息。目标仍是验证并升级到安全的 Pi >=0.84.3，而不是续期来替代升级。

## 连续分析报告

需要按顺序执行 TASK 指令集并生成可复核报告时，使用 `make analysis`：

```sh
make analysis
make analysis INSTRUCTIONS=validation/questions/task.md.txt
```

`grid-agent analysis --instructions PATH` 会在一个 Pi/LLM 进程中执行整个指令文件；后续指令可以复用同一分析目录中已验证的上下文、结果和证据。stdout 只输出一个最终 `AnswerEnvelope`，其中 `question_id` 是 `analysis-<UTC timestamp>`，`answer_output` 是项目相对报告路径，例如 `runs/analysis-20260814T120000Z/report.md`。进度、工具事件、检查点和诊断全部写入 stderr。

每次分析的输入副本、逐回合答案、上下文账本、上下文快照、证据、trace 和最终报告都保存在同一个 `runs/<analysis_id>/` 目录中；逐回合答案写入 `output/answers.jsonl`，不会流式写到 stdout。该迁移不支持独立 `--output`/`--report-path`、resume、命名 session 或 session 切换。

`make report` 和 `grid-agent report --questions PATH` 是兼容别名，委托同一个连续分析路径；它们不再启动每题一个 `grid-agent run` 子进程。

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

DeepSeek 官方 OpenAI API 的 V4 model 参数为 `deepseek-v4-flash` 或 `deepseek-v4-pro`，不要填发行日期后缀；项目会在启动 Pi 前拒绝其他 DeepSeek model id。

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

`make run` 始终是本地、非计费的离线 gridctl 路径；`make run-llm` 才会调用配置的 LLM，并把受控的 `gridctl` 放入 Pi 的受限 PATH。Pi 只暴露项目生成的 `grid_*` domain tools 和 `grid_guide_open`；不会启用通用 shell/read/write/edit 内置工具。模型完成必要工具使用后返回普通面向读者的最终文本；单题在线 `run` 直接发布 stdout envelope，连续 `analysis` 再由 `grid-agent` 控制器确定性绑定当前回合的结果/证据引用并完成答案持久化。

`make run-llm` 的 stdout 仍只输出最终 JSON；实时进度写到 stderr，包括运行耗时、provider/model、生效的超时与重试参数、输入与输出前 200 字摘要、Pi 工具事件、重试事件，以及超过 10 秒无事件时的等待提示。密钥字段会被隐藏。单题在线 `run` 只把模型返回的普通最终文本放入 stdout envelope，并保留 `events.jsonl`、工具结果和 evidence；它不会写入 `answer-draft.json`，也不会写入带 controller-bound lineage 的 `answer.json`。

若日志出现 `401 ... authentication_error`，表示当前 provider 的 API key 无效、过期或与所选 provider 不匹配；更新 `.env` 中对应的密钥后重新运行。该错误不会重试。若出现 `Request timed out`，先确认日志首行的超时和重试参数，再检查 provider 服务状态或提高 `GRID_AGENT_LLM_TIMEOUT_SECONDS`；运行原始事件保存在 `runs/<question_id>/events.jsonl`，可用于进一步诊断。

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

每个 simulator-backed 单题 `run` 可检查：

- `runs/<question_id>/events.jsonl`：Pi 事件、工具调用和结果 trace。
- `runs/<question_id>/tool-results/`：工具侧结果暂存目录。
- `runs/<question_id>/evidence/`：当前运行的 context、model、network-fact、analysis 和 result 证据。

连续 `analysis` 额外写入 controller-owned 答案工件：`runs/<analysis_id>/turns/NNN/answer-draft.json` 是控制器根据当前回合最终文本和已消费/已产生 lineage 生成的提交草稿，`turns/NNN/answer.json` 是已接受的答案 envelope，`output/answers.jsonl` 汇总逐回合已接受答案。

在线运行不要求模型使用答案持久化工具。单题 `run` 中，模型返回普通最终文本后直接形成 stdout envelope；连续 `analysis` 中，控制器再写入 `answer_output`、`result_refs` 和 `claim_evidence_refs`，并验证这些引用确实来自当前分析目录和当前回合 lineage。验证器不从 `answer_output` 文本中解析引用。`result_refs` 用来声明直接支撑最终结论的主结果，分析证据中已经关联的结果也会被自动定位、校验其当前运行归属和上下文一致性。拓扑事实可使用空 `result_refs`；AC、排序和 N-1 等结果型结论必须有当前运行的主结果或与其相连的分析证据。

连续分析的 stderr 应显示分析工具调用和一次正常模型完成；trace 不应包含模型发起的 `grid_submit_answer` 调用。若任一必需回合失败，运行状态为 `failed`、CLI 退出码为 `1`，且 `report.md` 必须在回答占位符之后保留该回合已经成功返回的可观察轨迹与工具结果摘要。

最终答案只能引用当前运行中实际存在的 `evidence:sha256:*` 或 `result:sha256:*`。迁移和清理不会删除用户主工作树中的既有 `var/` 数据；本分支只使用新的 ignored `runs/` 和 `.grid-agent/` 布局。

## 验证

需要逐项人工核验命令、stdout 边界、结构化工具轨迹和证据引用时，请使用 [人工验证手册](MANUAL-VALIDATION.md)。该手册只使用本 Makefile 发布的入口。

```sh
make test
make test-e2e
make validate
make test-packages
```

`make test` 运行 agent、pandapower simulator 和 Node 扩展测试；`make test-e2e` 运行离线命令行样例及脚本化 Pi → gridctl 路径。`make test-packages` 构建并安装干净发行工件，验证四个 Python distribution 与两个 Pi npm 包的源码路径隔离和兼容入口。
`make validate` 运行三层 deterministic validation：offline `task-required`、scripted-Pi `static-analysis-core`，以及绑定 `docs/test_script/测试题目答案.jsonl` 的 `static-analysis-full` 语义验收。报告分别写入 ignored `runs/validation-offline.json`、`runs/validation-scripted.json` 与 `runs/validation-static-analysis-full.json`；能力矩阵不足 100% 也会失败。语义验收比较真实工具结果事件和标准答案，不比较润色后的答案文字。

Workstream B 的最终本地 release closure 必须从已提交且干净的 release-source revision 运行：

```sh
tools/climb/cycle.sh B-H005
```

该入口不接受 gate 或 command 覆盖。它按 `docs/status/climb/config.yaml` 中受固定 allowlist 校验的顺序，现场执行 kernel、Domain Pack、通用 Pi、应用边界、发行工件、`make doctor`、`make test`、`make test-e2e` 和 focused `make validate` 共九个门。策略文件本身、精确命令、权重、前置图和 release pathspec 都进入 policy/source tree digest；每个门前后都重新检查 clean revision、tree digest 和 policy digest。只读 closure 链记录命令、rc、stdout/stderr digest 和完整输出 digest，最终 100 分不读取 carry-forward receipt。

`tools/climb/gate-receipt.py <gate-key>` 仍可为同一 revision 生成内容寻址的机械记录。其 mode-0600 HMAC 只用于发现意外损坏；密钥和验证器对同一 OS 用户可见，因此它不是独立信任根，也不能证明同一用户无法重签。release closure 会现场重跑全部门，不以这些 HMAC receipt 代替执行。该本地链只证明本次本机命令的可复核执行，不宣称具有 CI/外部签名者的跨主体不可伪造性。

可选 provider validation 会产生真实模型调用，必须显式给出 provider 且环境中已有对应凭证：

```sh
make validate-provider PROVIDER=openai MODEL=gpt-5.5
# 可覆盖验证集；默认 static-analysis-full
make validate-provider PROVIDER=openai MODEL=gpt-5.5 VALIDATION_SUITE=task-required
```

报告写入 `runs/validation-provider.json`，分别记录编排完成度、语义正确性、证据和工具调用效率；效率预算是诊断分，不会覆盖正确的主结果或阻断分析入口。报告记录 provider/model、trace、延迟以及可用的 token/cost 元数据，不写入密钥。
