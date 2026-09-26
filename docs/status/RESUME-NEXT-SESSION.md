# Live Session Checkpoint

> Updated: 2026-09-26 17:48 CST. Live checkpoint after model-policy and observability fixes on `main`.

## TL;DR

- 六个 PyPSA 1.3.0 `pypsa.examples` 官方 Network 已加入模型库并在本机校验安装，连同原有 15 个项目模型共 21 个登记模型；六个官方资产均已打开并完成限定范围的结构检查。
- 三个本地案例已通过：区域负荷增长双情景、SciGRID-DE 调度、AC/DC 拓扑检查。它们使用确定性脚本 Provider 验证完整应用和本轮证据链；开放式 LLM 规划、容器与前端仍待后续工作。
- 三个可运行案例已有双格式专业介绍：案例清单提供 App 可读的结构化字段，独立 Markdown 说明业务问题、PyPSA 框架支持、智能体交互变化、价值和结论边界。
- 新的中性 `capstone-agent` 通过同一持久会话接口支持无头、交互式和 loopback HTTP/SSE。pandapower 与 PyPSA 各有已登记的独立工作进程；`grid-agent` 保留原有兼容入口。
- 两个应用的 Provider 路径已装配，实际计费 Provider 调用尚未验收。三个 PyPSA 案例及 pandapower 样例均已通过新无头入口的三回合执行；真实 pandapower HTTP 会话、逐轮答案和权威验证证据已验收。
- DeepSeek 的旧静态模型白名单已移除，仓库本地 `.env` 中的 `deepseek-flash` 通过离线配置预检；`make analysis` 在配置失败时不再留下空运行目录。新宿主显示工具事件与报告检查点路径，通用报告列出结果和证据引用。

## Where things stand

- `main` 已提交多模式设计 `f4c47ff`、实施计划 `4a2c870`、Kernel 流式回合 `fb66927`、中性工作进程协议 `f324dbc`、HTTP/SSE 适配器 `a1f9d91`，以及完成两个应用接入的 `93cf39a`。
- 本轮重新通过 `make doctor`、`make test`、`make test-e2e`（37 项）、`make validate`（24/24）、`make test-packages`、`make check-types`、文档链接与符号链接检查。主检出的实际离线 `grid-agent run` stdout 仍是单个 `question_id` / `answer_output` JSON 对象。
- 六个官方模型资产重新核对为已安装；SciGRID-DE 案例重新完成求解并生成本轮答案、结果及证据引用。
- 案例介绍变更通过聚焦测试 3/3、`make test`、`make test-e2e` 37/37、`make validate` 24/24、`make doctor`、结构化/Markdown 一致性及本地链接检查。
- 三回合实现通过 PyPSA 聚焦测试 5/5、三个案例本地演示、`make test`、`make test-e2e` 37/37、`make validate` 24/24、`make doctor` 与链接/符号链接检查；Makefile 演示入口 stdout 为可直接解析的 JSON。
- 统一客户端通过聚焦测试 11/11、pandapower 与 PyPSA 的实际三回合样例、`make doctor`、`make test`、`make test-e2e` 37/37、`make validate` 24/24、链接与符号链接检查；未调用可能计费的 Provider 路径。
- 流式进度修复通过客户端聚焦测试 15/15、PyPSA 案例 7/7、实际双应用流式检查、`make doctor`、`make test`、`make test-e2e` 37/37、`make validate` 24/24 和文档链接/符号链接检查。进度输出失败不再阻断案例答案。
- 工作区仍有用户已暂存的 `.codex/config.toml`；不要把它混入任务提交。
- 新宿主依赖 `packages/capstone-agent/.venv`、`packages/pypsa-agent/.venv` 两个忽略的本地环境；`make setup-capstone` 可重建。最终 `make doctor`、`make test`、`make test-e2e`（grid 38/38、Capstone 3/3）、`make validate`（24/24）、`make test-packages` 和 `make check-types` 均已通过。
- 本轮配置/进度/报告修复提交为 `f8c4657`；`make doctor`、单元测试各目标、`make test-e2e`（grid 38/38、Capstone 3/3）、`make validate`（24/24）、`make check-types`、文档链接与符号链接检查通过。真实 DeepSeek 请求未执行，因此 `make analysis` 尚未做计费路径复验。
- `.worktrees/pypsa-operations` 留有忽略的本地运行环境，不要为了清理而删除。
- 官方 NetCDF 保存在忽略的 `.grid-agent/runtime/pypsa-models/`，运行证据和展示 JSON 保存在忽略的 `runs/pypsa-cases/<run_id>/`。这些本地资产与用户数据都不要为了清理工作区而删除。

## What this session delivered

- 增加官方模型清单、校验安装器、不可变来源修订、受限拓扑能力与大型调度摘要。
- 增加七个业务案例清单与可展示的当前运行结果结构；三个案例已本地运行，储能/HVDC、容量结构、随机投资和碳系统四个案例仍明确标为仅入库。
- 增加 Makefile 入口、双语 README、运行指南、设计与计划文档；主检出所有支持门禁通过。具体见 `docs/superpowers/plans/2026-09-26-pypsa-model-library-and-cases.md`。
- `validation/pypsa-cases/cases.json` 的三个可运行条目现带结构化介绍；对应全文在 `validation/pypsa-cases/introductions/`，并由测试检查双格式一致。
- 每例增加 `current_user_input`、`demo_instructions` 与 `demo_workflow`；`DEMO=1` 或精确匹配的指令文件可在一个本地应用运行中提交三回合。AC/DC 输出按 `Line`/`Link` 组件及端点母线 carrier 说明结构。
- `tools/capstone_client.py` 用闭合请求契约选择受信任的应用工作进程，`validation/client/` 提供两个无 Provider 的样例。pandapower 脚本样例使用正式应用 Profile 和 `gridctl`，PyPSA 样例复用当前案例运行器；统一封装保留各自领域结果。
- 客户端和两个脚本工作进程的 `capstone-client-progress/1.0` 事件经 stderr 实时输出；PyPSA 调度事件在实际求解前发出，事件不携带工具参数或计算结果。
- `capstone-agent` 新增 `run`、`chat` 和 `serve`，共享持久会话及有界 JSONL 协议。两个应用工作进程逐轮提交答案，HTTP/SSE 可按序号读取事件和本轮 authority 验证的结果/证据；脚本演示工作进程过滤 Provider 密钥环境变量。
- 中性工作进程把已有的语义工具事件与报告检查点转为带脱敏的进度消息；最终通用报告纳入本轮证据引用。脚本演示的答案仍是模型替身文本；PyPSA 通用报告尚没有 pandapower 原生连续分析报告的逐回合专业叙述。
- 已保存的官方案例结果可查看 `runs/pypsa-cases/pypsa-case-7959da36a5044753/presentation.json`（SciGRID-DE）与 `runs/pypsa-cases/pypsa-case-544d2329350449c0/presentation.json`（AC/DC）。区域负荷案例的自动验收见 `validation/test_pypsa_cases.py`。

## Next steps

1. 后续 Web 页面消费服务端的运行、逐回合答案和证据接口；本地服务目前依赖仓库工作区与各应用的独立 Python 环境。若要求与 pandapower 原生报告同等深度，需要在中性报告层按逐回合已验证轨迹组织内容，并让 PyPSA Pack 提供业务叙述。
2. 四个仅入库案例只有取得受控验收后才升级为可运行；真实计费 Provider 路径需另行授权验收。
3. 用户已暂存的 `.codex/config.toml` 属于独立工作，保持原状。

## Ruled-out paths and boundaries

- 不把 PyPSA 领域语义放进 Kernel，不跨包共享内部状态，不让兼容投影成为框架统一输出要求。
- 不自行启动 C.2 动态选择/发现或 Workstream D 企业动作治理；它们仍是独立的后续决策。
- 不运行可能计费的 `make validate-provider`，除非用户明确授权。
- grid/reference 与 PyPSA 的固定 pandas 版本不兼容，使用各自的 Python 环境。
- `pypsa.examples` 六个 Network 是本轮“官方模型全集”的明确范围；PyPSA-Eur 等独立项目数据未入库。`model.validate` 仅检查已列明的母线引用、时间序列与形状规则，不能代替各规划或潮流形式的可行性判断。
- 静态案例介绍不包含某次运行的数值结果；App 的数值和网络结论须来自该次运行已准入的结果与证据。

## Ready-to-paste commands

```sh
git status --short
git log -5 --oneline
make doctor
make list-pypsa-models
make list-pypsa-cases
make capstone-client REQUEST=validation/client/pandapower-scripted-task.json
make capstone-client REQUEST=validation/client/pypsa-regional-demo.json
make capstone-agent-run REQUEST=validation/client/pypsa-regional-demo.json
make capstone-agent-chat APPLICATION=pandapower-static-analysis MODE=scripted-demo CASE=pandapower-scripted-task
make capstone-agent-serve CAPSTONE_PORT=8766
make run-pypsa-case CASE=scigrid-dispatch
make run-pypsa-case CASE=regional-demand-stress
```
