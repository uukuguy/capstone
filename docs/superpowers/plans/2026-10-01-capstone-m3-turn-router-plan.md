# Capstone M3 — Auditable Turn Routing and Generic Conversation

## Goal

让 `send_auto` 在 Capstone Harness 内完成可审计的意图路由，同时保留
Pi 的通用对话能力。普通对话默认可用，专业电网请求继续受工具目录、结果
admission、绑定和证据门控约束。

## Scope

1. 增加中立的 `TurnRouter` SPI、`TurnIntent`、`TurnPlan` 和
   `DecisionUnavailable`。Plan 只保存受限的 route、capability hint、模型
   Context 快照摘要和 revision，不保存原始 provider 上下文。
2. `send_ordinary` 与 `send_professional` 直接生成显式 Plan；`send_auto`
   通过可注入 Router 生成 Plan。分类只负责路由，能否执行与提交仍由现有
   Harness admission 硬门控决定。
3. 提交 `turn_plan_created`、`turn_route_selected` 和必要的
   `turn_route_fallback` 运行事件，再启动 Pi/DSH runtime。事件 payload 有限、
   可 JSON 回放；路由失败走安全的 ordinary fallback 或 typed failure。
4. 增加普通对话策略，默认开启。普通回答可在没有 Authority result/evidence
   的情况下以 `offline_information/limited` 完成，不创建电网证据；关闭策略
   时显式普通请求失败并留下可诊断终态。
5. 增加 `JevDecisionRouter` 的可选适配器和开关，默认关闭且不引入 Jev
   依赖。Jev 不可用或输出不可信时返回 `DecisionUnavailable`，由应用策略
   选择受限的 ordinary fallback；不会把原始输入或运行上下文发送到未知接口。
6. 保持 `capstone-agent` 为唯一应用根；Grid/PyPSA 仅通过应用注入 Router、
   runtime 和 Domain Pack admission。M3 不实现多 Run、WebSocket 或 UI 重做。

## Verification

- Router 单元测试：显式路由、auto 路由、Jev 开关、typed fallback、payload
  上限和 Context 摘要。
- Harness/worker 测试：Plan 事件先于 runtime 事件；普通回答不要求 evidence；
  专业回答仍然缺证据即失败；普通策略关闭时失败码稳定。
- Capstone package tests、边界检查、`make doctor`、`git diff --check`。
- API/worker 源码改变后执行 `make capstone-local-rebuild` 并检查 ready。
- M3 独立代码评审报告，按 Critical/High/Medium/Low 分类。

## Non-goals

- 不把 Pi skill/MCP/plugin 误当成电网 Domain Pack；实际 runtime materialization
  留在后续阶段，但保留注入 seam。
- 不在 M3 自动判断 Domain Pack 语义冲突，不增加逐工具开关。
- 不允许 model 自己声明 result/evidence admission，也不绕过当前运行绑定。
