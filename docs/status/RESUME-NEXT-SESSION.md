# Next-Session Handoff

> Updated: 2026-09-29 09:45 CST.

## TL;DR

- 已完成 Provider 案例上下文前置和当前步骤严格边界，避免模型提前执行后续步骤。
- 已修复 PyPSA Provider 案例使用错误变量导致的 `RuntimeError`；SciGRID-DE 三步真实运行已完成。
- 本地 API/Worker 与云端 API/Worker 均已重新部署并通过健康检查。

## Where things stand

- 最新提交：
  - `96c14db build: refresh packaged trajectory workbench`
  - `348159e fix: close PyPSA model download before sync`
  - `2c0f4df test: clarify registered capability inputs`
  - `673fa2d feat: align local rebuild and public demo configuration`
  - `e82a26b fix: bind PyPSA provider case context`
- 本地验证：
  - pandapower Provider 运行从 48.5 秒降至 29.3 秒。
  - `make capstone-agent-pypsa-scigrid` 已完成三步。
  - PyPSA 测试 16 项通过。
  - 本地 API/Worker 使用同一镜像摘要运行，`/health/ready` 正常。
- 云端验证：
  - Railway API、Worker 最新部署均成功。
  - API `/health/ready` 正常，App 返回 200。
  - 云端目录接口可用。
  - 尚未做完整云端 Provider 性能对比。
- 工作树：
  - 历史遗留改动已按功能拆分提交；`.codex/` 保留本机并已加入忽略。
  - `deploy/local-model-assets/*.nc` 保留在忽略目录中，构建时由本地模型库校验并复制。
  - 状态文件将在本次整理结束时一并提交。

## What this session delivered

- Kernel 新增应用级 prompt decorator。
- Provider 登记案例注入：
  - application/case/model 标识；
  - 当前步骤能力；
  - 当前步骤边界；
  - 禁止未来步骤泄漏；
  - 已知模型时禁止重复目录发现。
- pandapower 与 PyPSA Worker 共用同一套案例上下文机制。
- 修复 PyPSA provider 分支把 `provider_case` 错写成 `case` 的变量错误。
- 增加注册 SciGRID-DE Provider 预检回归测试。
- 本地和云端重新部署。
- 历史遗留工作树已按功能拆分为配置、能力描述、PyPSA 下载修复和工作台构建四个提交。

## Next steps

1. 在本地 App 中验证 PyPSA SciGRID-DE、区域负荷和 AC/DC 案例的网页链路。
2. 如需性能对比，再单独运行一次云端 Provider 案例，记录云端与本地每步耗时。
3. 后续提交前只暂存任务所属文件，并保持 `.codex/` 与本地模型资产在忽略目录中。

## Don't go down these paths again

- 不在 PyPSA Provider 分支复用 scripted 分支的 `case` 变量。
- 不让 Provider 案例通过全量模型目录发现已登记模型。
- 不把未来步骤文本或预期答案注入当前步骤 prompt。
- 不把 Railway 不兼容的通用 cache mount 语法重新加入共享 Dockerfile。
- 不将当前云端延迟直接归因于报告接口；主要成本仍需通过 Provider 分步日志测量。

## Ready-to-paste commands / configs

```sh
make capstone-local-rebuild
make capstone-agent-pypsa-scigrid
make capstone-agent-pypsa-regional
make capstone-agent-pypsa-ac-dc
curl -fsS http://127.0.0.1:8767/health/ready
curl -fsS https://capstone-api-production-ec73.up.railway.app/health/ready
```

Provider 配置：

```text
CAPSTONE_PUBLIC_PROVIDER=deepseek
CAPSTONE_PUBLIC_MODEL=deepseek-flash
```
