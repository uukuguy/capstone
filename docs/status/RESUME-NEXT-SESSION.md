# Next-Session Handoff

> Updated: 2026-11-05 end of session.

## TL;DR

- 本地执行过程与成果栏有一批未提交界面和收口改动。`dev` 仍是 `6c55e6ee`。不要提交这棵混杂工作树。
- 理解超时单独说明，时限仍是 120 秒。指令结束时，仍在运行的文件收成 `incomplete`，失败的对话输入关闭。
- 全屏右栏时「浏览产物」自动收起；收起后长指令只显示一行。并行细线只连接真正同时在跑的调用。

## Where things stand

- 分支 `dev`，HEAD `6c55e6ee`，与上次交接的提交点相同。工作树大量已改和未跟踪文件，其中包含本次之前的排版、内网和网关改动。
- 本次为收口重建过本地 API 与 worker。重建时迎峰度夏 `attempt_24d228a08c5fa95b` 被中断，原因 `lease_expired`（worker 于 19:43:38 换掉，19:45:57 记下中断）。要继续须重新发送该指令。
- 内网、cloud-dev、cloud-demo、main 本次没有部署。不要启动 CI。

## What this session delivered

- 理解超时文案与错误码 `intent_deadline_exceeded`。120 秒保留：已完成理解 17 次，中位 9.4 秒，最慢 56.3 秒。`thread_worker.py`。
- 指令结束收口：仍为 `running` 的捕获再记一版 `source_status=incomplete`；对话失败、取消、中断时关闭本条输入，原文留作明确重试。`thread_service.py`、`native_artifact_projection.py`、`thread_work.py`、`continuation_resources.py`、`thread_materials.py`。
- LLM 标题显示简明说明；工具行不再重复这句话。`agent_tools_execute` 显示真实工具名，不用固定别名「执行多步数据处理」。`ProcessCallTrace.tsx`、`CapstoneAssistantThread.tsx`。
- 并行分组改为必须整组同时重叠。一次最多约 4 路，不再把 59 项串成一条细线。
- 执行过程底部的「进度登记未更新」已去掉。
- 全屏右栏时「浏览产物」自动收起；收起时长指令一行。`ThreadWorkspace.tsx`、`resourceFullscreen.ts`、`ThreadProductsWorkspace.tsx`、`threadProducts.css`。
- 数据网关重联：左栏「数据网关」里点「刷新所有网关连接」。不要走「添加网关」或 Skills/MCP 新建。

## Next steps (immediate, action-level)

1. 刷新本地页面，核对全屏收起、一行指令、并行分组和工具行名称。不要为这次界面改动再重建 API。
2. 若要继续迎峰度夏，重新发送该指令。被中断的 Attempt 不会自动接着跑。
3. 用户明确要求之前，不要提交、不要 CI、不要动内网和云环境。提交时把本次文件与更早的未提交改动分开。

## Don't go down these paths again (ruled out)

- 不要把「执行多步数据处理」当作每次调用的说明。那是 `agent_tools_execute` 的固定别名。
- 不要用传递重叠把一整串调用画成一组。并发上限是 4。
- 不要把理解超时写成「未能开始执行」或「运行准备未完成」。
- 不要把 120 秒理解时限再加长。超时是因为没有交出决策。
- 不要在执行过程里再显示「进度登记未更新」。
- 重联数据网关不要新建 MCP，也不要重新安装。
- 不要把本次重建当成用户取消。那次中断是租约过期。

## Ready-to-paste commands / configs

```sh
curl --noproxy '*' -fsS http://127.0.0.1:8767/health/ready
```

本地成果栏是 Vite。界面改动刷新页面即可。后端收口已经在上次 `make capstone-local-rebuild` 的镜像里。不要为纯前端改动再重建。
