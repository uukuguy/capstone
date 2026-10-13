# Pi研究状态链路验证

来源：feat/autonomous-agent，提交7df7180；基于dev4f15cfc。
日期：2026-10-12。状态：基础链路通过，App与业务验收未完成。

## 实际覆盖

- Kernel持久账本是提交依据；客户端消息不等于提交成功。
- 研究工具使用宿主生成的契约，不接受路径、运行或Attempt身份参数。
- 更新回执绑定请求摘要和宿主身份；取消后未知结果可只读查证，不重复写入。
- 已确认提交而视图暂不可读时，保留提交事实，并阻止旧视图进入下一次模型请求。
- 有界上下文标明截断和总量；详情分页取得。研究判断不产生Authority证据。
- 实际锁定Pi SDK使用离线可控模型传输。测试执行工具、Kernel提交、后续请求、真实压缩、会话关闭及重新打开。
- 实际请求缺少最新研究视图时，Pi进程停止；不返回正式回答。

受管Pi来源：b79e4cc834970cca69daebffab7df1da7d1e52c4，版本0.84.4。
测试无需Provider凭据或网络模型调用。它验证运行机制，不验证LLM自主解题质量。

## 检查结果

| 检查 | 结果 |
| --- | --- |
| Python3.12完整Kernel测试 | 609通过 |
| 全仓Python类型检查 | 0错误、0警告 |
| Pi工具测试 | 60通过 |
| 最终修正后重跑实际Pi集成 | 2通过，1.82秒 |
| JavaScript语法检查、git diff --check | 通过 |

新增故障测试先复现：已提交但视图旧时误报research_receipt_unreadable。
修正后返回research_view_not_ready，同时保留committed回执；后续请求检查仍阻止续推。
客户端等待轮询20ms，宿主RPC服务轮询25ms；这是调度参数，不是用户请求耗时承诺。

命令（在实施worktree内）：

```sh
UV_PYTHON=3.12 uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
UV_PYTHON=3.12 uv run --project packages/grid-agent pyright
npm test --prefix packages/pi-capability-tools
npm run check --prefix packages/pi-capability-tools
UV_PYTHON=3.12 uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/runtime/test_pi_research_integration.py -q
git diff --check
```

## 尚未验证

App实际Attempt生命周期和Authority引用准入尚未接线；未完成三个业务指令、正式回答和前端四视图验收。
未合入dev、未部署。独立审查代理因模型配置错误无法启动；本次为源码自审与自动检查，不记录独立审查通过。

## 后续App适配与故障交付

3e471d0：按宿主注册的CoreToolCatalog检查内核工具来源，不把研究读写算作领域调用。
携带物理结果、证据或领域绑定的内核事件被拒绝，正常领域核验保留。
120项相关检查通过（178.51秒），含实际Authority的模型切换、潮流和结果复用；
该耗时为测试套件耗时，不是一次用户请求耗时。4项警告来自pandapower变压器旧数据字段。

3f2f111：已经由应用/领域准入为limited的正式回答，不再被专业路线替换为capability_required。
执行交付结束与业务受限状态分别保留；未新增结果或证据。
98项后端检查通过（10.46秒），65项App组件检查通过（6.24秒），Python类型检查通过。
前端检查覆盖受限回答、此前回答和工具记录保留。

用户要求故障后仍须恢复或交付有用结果，已进入设计与优先计划。
本次只修通受限回答路径；运行异常后的智能体恢复、失败终态的已验证部分结果/证据交付仍未完成。

## Task-goal browser check

The real App component rendered controlled research events. The goal stayed on its own task,
started collapsed, and expanded through a browser click. Bounds checks passed at1440px and390px.
The detail uses11px text.68 component tests and TypeScript checks passed.
This is not live API, Provider, model-switch, or three-case business acceptance. Source remains uncommitted.
# Large result delivery — 95ddebf

The saved island run reproduced a display-capacity failure: three admitted projections
totaled more than64KiB. Their Authority references passed verification. The application
then rejected the whole answer before terminal delivery. This is a framework defect.

Large result projections now use bounded `result_projection_part` ledger events and a
terminal `result_projection_manifest`. Both commit in the same transaction. Small
results keep their existing inline format. Full projection data remains in the snapshot;
event and Attempt-record pages retain every part. The App reassembles only complete,
same-Attempt parts named by the admitted terminal manifest. Verified partial data can
also accompany a failed task. Calculations and Authority evidence are unchanged.

Verification:68 backend Harness/projection/HTTP checks;19 actual PostgreSQL checks,
including injected write-failure rollback and restart;68 App projection/protocol checks;
Python and App types passed. The real saved island results replayed into a failed terminal
with all3 result refs,4 evidence refs and two128-row tables. Largest event5126bytes.
Browser checks at1440/390px showed3 cards/256 rows and no page overflow.
The browser replay first found duplicate InMemory event sequence numbers; the sequence
update was fixed and added to regression assertions before the final browser pass.

Local receipts: worktree `runs/autonomous-live/deepseek-island-1791807782/admission-replay.json`,
`delivery-replay.json` and `runs/autonomous-ui/delivery-browser.log`. These are saved
data replays, not a new Provider run or HTTP/browser business acceptance.
No merge or deployment. Multi-run snapshot growth and on-demand full Authority dataset
access remain integration work; transport parts preserve the bounded projection, not an
assertion that every raw Authority table is already exposed through the App.

