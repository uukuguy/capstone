# Next-Session Handoff

> Updated: 2026-09-29 12:00 CST end of session.

## TL;DR

- 已将本地、cloud-dev、用户试用三阶段研发与发布架构写入
  `docs/architecture/capstone-development-lifecycle.md`。
- `AGENTS.md` 已加入强制隔离、同修订晋级、凭据和验证要求；README 已移除研发内部细节。
- Railway cloud-dev 的 API、worker、App 按同一源码修订部署并通过健康检查；用户试用环境保持独立。
- 当前工作树干净，`main` 已同步 `origin/main`。

## Where things stand

- 最新提交：
  - `a0f994c` — journal project state refresh
  - `6728960` — refresh structural project state
  - `7f63add` — record lifecycle architecture
  - `cdf6057` — codify development release lanes
  - `2e300db` — record cloud-dev deployment
- 文档验证通过：`make doctor`、链接检查、`git diff --check`、`CLAUDE.md` 符号链接检查。
- Railway cloud-dev API `/health/ready` 和 App `/health` 返回 `200`。
- cloud-dev 尚未配置独立 `DEEPSEEK_API_KEY`，因此 Provider 云端验证仍需单独授权和配置。
- 用户试用环境不跟随普通开发推送；本地 App 继续承担高频迭代。

## What this session delivered

- 新增研发与发布生命周期规范文档。
- 在 `AGENTS.md` 中固化三阶段架构和不可绕过的核心要求。
- 清理中英文 README，保留用户需要的部署入口。
- 刷新 `CURRENT-STATE.md`，记录架构边界和规范文档索引。

## Next steps

1. 如需云端 Provider 验证，在 Railway cloud-dev 的受保护变量中配置独立 Provider key。
2. 运行一个 Provider 案例，比较本地与 cloud-dev 的分步耗时、报告和证据回放。
3. 后续发布只能按“本地门禁 → cloud-dev 验证 → 精确修订晋级”的流程执行。
4. 新功能开发前先阅读 `AGENTS.md` 和研发生命周期文档。

## Don't go down these paths again

- 不把研发内部架构和 cloud-dev 细节写回面向用户的 README。
- 不让 cloud-dev 与用户试用共享数据库、bucket、凭据、域名或运行数据。
- 不用普通开发推送直接更新用户试用环境。
- 不用旧 Compose 镜像代表当前源码进行远程验证。
- 未配置独立 Provider key 时，不宣称云端 Provider 验证已通过。

## Ready-to-paste commands / configs

```sh
git status --short --branch
make capstone-local-rebuild
make doctor
curl -fsS https://capstone-api-production-bb72.up.railway.app/health/ready
curl -fsS https://capstone-app-production-83ef.up.railway.app/health
```
