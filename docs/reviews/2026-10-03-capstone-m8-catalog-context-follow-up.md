# Capstone M8 联邦目录上下文修复复审

日期：2026-10-03
范围：M8 独立复审后的 PyPSA 可见性缺陷修复

## 问题

统一 Thread API 已经暴露 pandapower 与 PyPSA 的联邦模型目录，但 family worker
创建 Pi 会话时只注入当前 Domain Pack 的目录和策略。当前模型为 pandapower 时，
模型会把“当前 worker 没有 PyPSA 工具”误答成“系统没有 PyPSA 模型”。这违反了
应用级目录与执行族隔离的边界。

## 修复

- `AttemptClaim` 携带有界、不可变复制的 application-owned catalog metadata。
- 统一 Thread 应用把联邦目录注入 API 与两个 family worker 的 Thread service。
- Pi 会话策略增加全族注册模型清单，并明确：跨族模型可以被说明，但必须先切换
  模型后才能执行该族工具。
- pandapower/PyPSA worker 仍分别只领取自己的 `implementation_family` Attempt，
  没有获得对方 Authority 或工具的执行权限。
- 兼容 hosted 入口只有显式开启 `CAPSTONE_FEDERATED_CATALOG_CONTEXT=true` 才
  加载联邦目录；当前本地统一 Compose 默认开启。

## 验证

- Capstone Agent focused：`49 passed`（Thread service、Kernel Pi policy、统一
  application、worker 与 catalog）。
- Ruff、Pyright、`git diff --check`：通过。
- 当前源 `make capstone-local-rebuild`：通过；API、pandapower worker、PyPSA
  worker、PostgreSQL 均 healthy。
- 运行时 `/api/v1/threads/{id}/catalog`：22 个模型，包含 `pandapower` 与
  `pypsa`，其中 21 个为 PyPSA 模型。
- `make test-e2e`：grid `39 passed`，registered worker `3 passed`。

## 结论

修复通过。应用级可见性与 family-specific 执行权限重新分离：询问可用模型时不再
错误声称没有 PyPSA；实际计算仍要求用户先选择或切换到 PyPSA 模型。
