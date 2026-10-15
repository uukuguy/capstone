# Next-Session Handoff

> 2026-10-15，本次会话结束。

## TL;DR

- user-local 已发布，运行来源 b7e68dd；双架构和公开安装入口验收通过。
- 推进图、功能验收记录和版本目录已对齐。
- 下一步先验证用户自己的 LLM 和业务流程，再处理反馈。

## 当前状态

- PR #23、#24、#25 已正常合入 dev，Linux/macOS 检查通过。
- 交接核对时 dev 为 b47ce1e；运行版本仍为 b7e68dd，后续文档提交不改变运行来源。
- 根 dev 和保留的任务工作区 Git 干净；已合并任务分支均已关闭。
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

1. 用户使用自己的 Key 验证安装、历史数据和实际业务流程。
2. 记录问题对应的 Git、架构、操作和日志；不得暴露 Key。
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
