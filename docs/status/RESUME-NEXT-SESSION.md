# Next-Session Handoff

> Updated: 2026-09-28 03:58 CST. Final handoff after the current session.

## TL;DR

- 已将底层工具失败记录做成 Kernel 通用机制，pandapower 与 PyPSA 报告共用同一套失败提取和格式化逻辑。
- 工具失败会保存 `error_code`、`error_message`，报告显示直接失败原因；当前实际观察到的失败案例是 PyPSA 的 grid-dispatch。
- 相关聚焦测试全部通过；根目录全量测试受现有跨包环境问题影响，不能作为本次改动门禁。

## What this session delivered

- `packages/capability-agent-kernel/src/capability_agent/application/projector.py`
  - `tool.failed` 诊断保存结构化错误码和错误原因。
- `packages/capability-agent-kernel/src/capability_agent/application/reporting.py`
  - 新增通用 `ToolFailure`、`extract_tool_failures`、`format_tool_failure`。
- `packages/pypsa-agent/src/pypsa_agent/reporting.py`
  - PyPSA 报告轨迹显示统一失败原因。
- `packages/grid-agent/src/grid_agent/compat/v1_0_1_report.py`
  - pandapower 报告把同一失败诊断投影为执行限制。
- 新增 Kernel、PyPSA、pandapower 回归测试。

## Verification

- Kernel projector/reporting：18 passed
- PyPSA reporting：3 passed
- pandapower report adapter：2 passed
- `git diff --check`：passed
- 根目录全量 pytest 未通过，原因是现有环境缺少依赖、跨包同名测试收集冲突，以及 grid-agent 第三方 conftest 缺少 `timeout` 选项。

## Next steps

1. 重新运行 grid-dispatch，确认新报告出现具体失败码和直接原因。
2. 检查报告中是否只显示实际失败的工具，不给成功案例增加空诊断。
3. 如确认无误，再按部署流程同步云端。

## Ruled out

- 不在 PyPSA 或 pandapower 报告里硬编码某个错误码。
- 不为两类 Domain Pack 各维护一套失败报告逻辑。
- 不把历史运行记录强行回写；旧记录没有保存结构化错误详情，只能新运行生效。

## Working tree

- 当前工作树包含本轮及此前用户要求的多项未提交修改；不要重置或清理无关路径。
- 本轮新增/修改的失败诊断相关文件见上方清单。
