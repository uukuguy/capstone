# Live Session Checkpoint

> Updated: 2026-10-15 12:45. **Session remains active — not a final handoff.**

## TL;DR

- user-local 已发布，运行来源 b7e68dd；双架构和公开安装入口验收通过。
- 推进图、功能验收记录和版本目录已对齐。
- 用户内网无法下载公网文件；当前实施AMD64离线包，默认PROVIDER=openai，优先OPENAI_BASE_URL/OPENAI_MODEL/OPENAI_API_KEY。
- 工作区为.worktrees/dev-trial-deployment，分支feat/user-local-offline；Provider40b338d及离线导入6b74397已实现，172项及67项专项通过，零Provider调用。
- 最新产品修订75af46a；7930c07目录保留修订及独立审查通过。PR #27已转正式；CI38680987676的macOS缺Docker导致新增Compose测试失败，75af46a补依赖声明，有Docker8项通过，无Docker路径5通过1跳过。等待推送后双平台重检。本地check-pr、E2E39+3及make validate全部通过。
- 候选源码6b74397639e4c10b75bb90855c9dab863024da04镜像及离线包已生成；.capstone-agent/accept_offline.py在29373/项目capstone-user-nkfgc84h验收，安装、三案例九轮/回放、浏览器、重启/重复安装、缺Key/地址保留服务与配置/卷保留全部通过，报告证据哈希一致。候选已停止且保留数据。该候选不含7930c07目录保留修订。
- 最终包须在PR正常合入后按实际dev合并SHA重建及完整验收。不可将6b74397候选标作最终包；不调用真实Provider。7930c07精确上下文已准备，尚未构建。

## 当前状态

- PR #23、#24、#25 已正常合入 dev，Linux/macOS 检查通过。
- 交接核对时 dev 为 b47ce1e；运行版本仍为 b7e68dd，后续文档提交不改变运行来源。
- 根dev为1d0b280；离线任务工作区有进行中的实现与控制记录，未合入或发布。
- local-dev：b7e68dd；local-demo/cloud-demo：faa6af9；cloud-dev：24d9a32。
- 未操作用户现有 ~/capstone 安装；其实际版本需在用户升级后重新核对。

## 本次交付

- 一条命令安装并启动，默认 ~/capstone、端口19173。
- 无参数安装最新已发布版本；支持指定 Git，错误参数列出版本。
- capstone.sh 管理安装、版本查看、启动、切换、状态、日志和停止。
- 版本共享数据；兼容性和配置检查先于停止当前服务。
- ARM64 原生 Linux 容器及 AMD64 模拟 Linux 容器通过案例、
  报告证据回放、重启、浏览器、匿名拉取及升级/回退检查。
- 验收未调用 Provider；用户 LLM/业务与 Windows/WSL2 尚未验证。

## 下一步

1. 等待PR双平台门禁；正常合入dev后用.capstone-agent/build_offline_final.py <merge-SHA>构建AMD64最终归档，运行accept_offline.py及浏览器检查。交付归档预定存放根工作区runs/user-local-offline/。按仓库规范重建local-dev，demo/cloud不变。
2. 用户已确认PROVIDER=openai可用；本轮仅合成Key和脚本验证，不调用真实Provider。交付不含用户Key。
3. 先处理试用反馈，再按规范工作清单推进自主智能体剩余缺口。
   Research R1 不自动作为下一任务。

## 恢复约束

- 不重跑发布脚本，不移动或复用已有发布标签。
- 不因文档提交推进 dev HEAD 而重建或重标记运行版本。
- 保留用户安装、var、认证状态、数据卷及无关工作区。
- 新数据格式的兼容与迁移由开发发布流程验证。

## 入口与证据

启动环境设置 DEEPSEEK_API_KEY 后执行：

curl -fsSL https://raw.githubusercontent.com/uukuguy/capstone/dev/deploy/dev-trial/install.sh | sh

公开版本：user-local-b7e68dd、user-local-7832134。
版本目录：docs/status/USER-LOCAL-VERSIONS.tsv。
工作清单：docs/superpowers/plans/2026-10-07-capstone-conversation-completion.md。
详细收据：.worktrees/dev-trial-deployment/.capstone-agent/
下的 user-local-final-closeout.json、user-local-final-acceptance.json
及对应平台验收日志。
