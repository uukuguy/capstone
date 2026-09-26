# Recovery Baton

> Updated: 2026-09-26 23:58 CST. Operator App implementation is complete locally; this is a session handoff.

## Delivered

- 用户已批准的专业 Capstone 操作 App、持久 API/worker、PostgreSQL 账本与私有工件存储已集成到 `main`。App 首版仅提供单人内部使用和已登记三轮脚本案例；浏览不会调用 Provider。
- 单一后端镜像以 `api` 或 `worker` 角色启动；本地 `compose.yaml`、Cloud Run 服务/worker pool 模板、Railway 服务配置说明和 Vercel 静态 App 配置已提交。镜像构建期安装 Pi 与六个经哈希校验的 PyPSA 模型资产；不复制本地凭据或忽略状态。
- 最终镜像 ID `sha256:699e9dc5dbd9a879b81e70069b0c4ff229ae01c5586d3173ef6eb7b74e30e749`，本地约 3.0 GB。镜像内 `gridctl` 可执行、六模型校验通过，`deploy/local.env` 不存在。
- 本地 Compose API `http://127.0.0.1:8767` 与 Vite App `http://127.0.0.1:5173` 当前运行；`/health/ready` 通过。Compose API/worker 对 pandapower、PyPSA 各完成 3/3，报告和证据可读。桌面/390px 浏览器流程完成，控制台无错误、窄屏无横向溢出。
- 聚焦后端测试 11 项、工件测试 4 项、App 测试 5 项及生产构建通过；`make doctor`、Compose 解析、部署脚本语法、双语文档本地链接、`CLAUDE.md` 相对符号链接及 `git diff --check` 通过。按用户要求未重复全量 `make test` / `make test-e2e` / `make validate`，未运行计费 Provider 验证或云部署。

## Next authorized work, if requested

1. 用户提供云项目、域名、PostgreSQL/GCS 或 Railway bucket、Secret Manager/服务权限后，按 `deploy/cloud-run/README.md` 或 `deploy/railway/README.md` 审核并执行真实部署；Vercel 项目根目录为 `packages/capstone-app`。
2. 真实 Provider 七题路径仍需用户明确授权凭据与可能产生的费用后再验收。

## Preserve

- `.codex/config.toml` 是用户原有暂存改动，不属于本任务。不要提交或重置。
- `deploy/local.env`、`.grid-agent/`、`.capstone-agent/`、`runs/` 和容器卷均含本地运行状态；不要为清洁 Git 删除。
- 本地测试容器 `capstone-ledger-test`（PostgreSQL 127.0.0.1:32768）与 `capstone-objects-test`（RustFS 127.0.0.1:32769）仍在运行，与 Compose 服务隔离。
- 使用 `docker compose --env-file deploy/local.env ps` 检查服务；该 env 文件已被 Git 忽略，不要在日志或命令输出中打印凭据。
