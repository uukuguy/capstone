# Live Session Checkpoint

> Updated: 2026-08-29 23:52 CST. **Session remains active — not a final handoff.**

## TL;DR

- Workstream C 已在 main 完成 C-H001、C-H002、C-H003，分别确认 authority service、Domain Pack SPI 与 unchanged generic Pi transport。
- 两个新分发包已建立：inventory-reference-service 与 inventory-domain-pack。
- 下一动作：实现 C-H004 的 no-follow current-run authority admission 与 lineage 红队测试。

## Where things stand

- climb 已确认 25 + 20 + 15 三门，最终 100 分由 C-H005 固定策略 closure 汇总。
- reference service 11 tests、Domain Pack 8 tests 通过；两个 wheel 均能构建。
- generic Pi 真实注册并执行 inventory tools，未修改 capability-agent-kernel、pi-capability-tools 或 trajectory-workbench。
- 当前 main 比 origin/main 领先 10 个提交。

## In-flight work

1. 用 failing tests 覆盖 valid admission、foreign run、tamper、symlink、kind mismatch 与 unlinked evidence。
2. 替换 InventoryArtifactAuthority 的 C-H002 临时占位实现。
3. 在干净 revision 上执行 C-H004 climb cycle。

## Boundaries

- Inventory 保持只读；Domain facts 只能来自 inventoryctl 的 current-run artifacts。
- 不修改 protected framework paths；不引入动态发现、写治理或多域路由。
- 不运行 provider validation。
- 不遗留临时 worktree 或 feature branch。

## Immediate next action

```sh
uv run --project packages/inventory-domain-pack pytest packages/inventory-domain-pack/tests/test_authority.py -q
```
