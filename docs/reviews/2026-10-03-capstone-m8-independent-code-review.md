# Capstone M8 独立代码评审

日期：2026-10-03
范围：M8 统一 Thread 应用（联邦目录、双族 worker、上下文重开、Compose、本地 Web 投影）

## 初审结论

初审为 `REQUEST CHANGES`。发现的问题已按阻断级别处理：

- 兼容 hosted 默认值被 M8 错误改成联邦应用；已恢复 `pandapower` 默认，`capstone` 保持显式 opt-in。
- 显式重开原先复用了 `model_context_activated`；现使用独立 `model_context_reopened` 事件，内存/PostgreSQL 回放、回滚和 Web 投影均识别两类事件。
- 重开命令现在必须携带模型 ID 与有界的 fresh-context reason，并在 pending/activation 事件中保留。
- worker application/family 组合不再由 Compose 独立配置；worker 入口按 adapter 固定注入对应 family。
- 联邦 API 支持显式配置的 worker health 探测；目录标记不可用族，Thread 创建和模型切换在 worker 不可用时拒绝。
- exporter 只继承非敏感的模型库配置；输出写入有界临时文件，联邦目录和 PyPSA 模型数量均有上限。
- exporter 文档的 family 必须匹配固定 exporter 槽位；两个 catalog exporter 的重复 `__main__` guard 已删除。
- worker `/health` 现在可检查 session/thread scheduler 的存活状态。

## 验证证据

- M8 Python focused suite：`72 passed`（包含 family availability、explicit reopen、联邦目录/exporter、HTTP projection、worker wake）。
- Capstone App：TypeScript check 通过，Vitest `159 passed`。
- M8 owned Python Pyright：`0 errors`；Ruff：通过。
- `tools/tests/test_deploy_entrypoint.py`：`3 passed`。
- `bash tools/test_local_rebuild.sh`：通过。
- `make test-e2e`：grid E2E `39 passed`；registered worker E2E `3 passed`。
- `make doctor`：通过；实际联邦 catalog smoke 为 `22 models`, default `ieee39`，`regional-six-bus` 路由到 `pypsa`。
- `git diff --check`：通过。
- 当前本地 Compose：API、pandapower worker、PyPSA worker、PostgreSQL 均 healthy；`/health/ready` 返回 ready，Vite App 返回 HTTP 200。
- PostgreSQL family leasing：独立临时 PostgreSQL 验证 `10 passed`，确认 pandapower/PyPSA worker 只领取匹配族的 Attempt。

## 结论

M8 在 demo-stage 范围内通过独立复审。云端 Railway 仍保持单族兼容部署；联邦双 worker 尚未宣称为云端发布拓扑。后续 M9 进入 PyPSA 结果投影与专业 Web 展示前，应继续沿用每阶段独立评审门禁。

## 复审后默认值决策

用户确认统一模式已具备默认资格后，本地 Compose 与 `deploy/local.env.example`
将 `CAPSTONE_HOSTED_APPLICATION` 默认设为 `capstone`。Railway 示例继续显式设置
`pandapower`，因为当前云端仍是单 worker 拓扑。默认值切换后的当前源重建、API
readiness、双 worker 健康检查和完整 E2E 再次通过：grid `39 passed`，registered
worker `3 passed`。
