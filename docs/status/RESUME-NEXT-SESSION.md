# Next-Session Handoff

> Updated: 2026-09-28 08:26 CST. Final handoff after the current session.

## TL;DR

- 本轮产品变更已整理提交；产品代码与测试已到 `a41a44e`，交接文件的本地提交已到 `d4f2152`，`origin/main` 仍在 `a41a44e`。
- 五个案例入口、Provider/LLM 配置、统一报告诊断、过程摘要、案例概览、拓扑图和缩放显示已统一到当前实现。
- 下一次如继续验证，优先在 5173 启动最新 App，跑一个 PyPSA Provider 案例确认网页链路和报告。

## Where things stand

- 主产品提交：
  - `52ee54e feat: unify provider case execution and reporting`
  - `88e3795 test: align network view headings`
  - 日志提交：`35e38c2`、`a41a44e`
- 验证结果：
  - App：60 项通过
  - Kernel：562 项通过
  - Capstone Agent：87 项通过，22 项跳过
  - Grid 聚焦测试：3 项通过
  - PyPSA 聚焦测试：9 项通过
  - `git diff --check`：通过
- 根目录跨包全量 pytest 仍受现有环境问题影响，包括第三方 `timeout` 选项、跨包同名测试收集和缺失依赖；不作为本轮产品回归结论。
- 工作树只剩 `?? .codex/`。该本地配置按原约定保留，未提交、未删除。
- `.debug-ops/` 和 `output/` 已加入忽略，磁盘内容保留。

## What this session delivered

- Provider 案例入口统一：
  - Makefile 增加五个案例命令，全部走真实 Provider/LLM 路径。
  - App 创建会话使用 `mode: provider`。
  - `deepseek` / `deepseek-flash` 从配置注入，缺配置时尽早失败。
- 统一报告与诊断：
  - Kernel 保存工具失败的结构化错误码和直接原因。
  - pandapower 与 PyPSA 报告共用失败提取和格式化机制。
  - PyPSA 新增正式报告壳层，过程摘要与正式回答分开。
- App 与过程展示：
  - 步骤摘要、步骤执行时间、刷新恢复和断开重连接口已接入。
  - 案例概览支持短值同行、长值分行，并保留底部分隔线。
- 拓扑图：
  - PyPSA 保留权威地理坐标，使用电气元件图例。
  - 缩放时线路保持细线，母线和空心变压器符号保持可读。
  - 共址母线做确定性展开，变压器保持在线路中点。
- 版本整理：
  - 新增 Provider 案例请求文件、锁文件、报告测试和运行时测试。
  - 本地产物目录不再污染 Git 状态。

## Next steps

1. 启动 `http://127.0.0.1:5173/` 的最新 App，验证 PyPSA AC/DC、SciGRID-DE 或区域负荷案例。
2. 至少重新跑一个 Provider 案例，确认网页总时长、每步时长、过程摘要和正式报告一致。
3. 如需要完全清空 Git 状态，再单独决定 `.codex/config.toml` 是继续保留本地还是纳入版本控制。

## Don't go down these paths again

- 不恢复“生成电气示意图”切换；PyPSA 当前应保持地理拓扑加电气元件图例。
- 不给变压器增加额外垂直偏移；共址母线展开后，变压器应严格位于支路中点。
- 不为 pandapower 和 PyPSA 维护两套工具失败报告逻辑。
- 不把根目录跨包 pytest 的环境收集错误当作本轮功能回归。

## Ready-to-paste commands

```sh
make capstone-app-dev
npm test --prefix packages/capstone-app
make capstone-agent-pypsa-regional
make capstone-agent-pypsa-scigrid
make capstone-agent-pypsa-ac-dc
```

Provider 配置使用 `CAPSTONE_PUBLIC_PROVIDER=deepseek`、
`CAPSTONE_PUBLIC_MODEL=deepseek-flash`，不要依赖隐藏默认模型。
