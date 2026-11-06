# 三套联调环境同版本

本回执记录16:35的f34bb4d3对齐。随后内网默认模型改为dsv4，三套同步
bfb16344；当前版本见[默认模型更新](2026-11-05-default-dsv4.md)。

用户指定后续优先在63内网联调工作，并要求三区研发、内网联调、本地联调
使用同一版本。三套现已统一到源码
`f34bb4d3525df29d6acb1ee1e4ca71c45a718f3a`，包含单次理解、冻结模型选择、
Thinking直接推送与显示节奏/任务归属修正。

| 环境 | 入口 | API/worker镜像摘要前缀 | Native摘要前缀 | App |
| --- | --- | --- | --- | --- |
| 本地联调local-dev | http://localhost:5173/ | 8ecdd56c | 91ca997b | index-EER1YESG.js |
| 63内网联调intranet-dev | http://192.168.72.63:5173/ | 53a42476 | 17f6e7f7 | index-CC6_2hyT.js |
| 三区研发dky3-dev | http://192.168.72.66:5173/ | c8414ced | 37180666 | index-CDPJYwrQ.js |

各环境API、worker、native的OCI源码标签和App嵌入版本均为完整f34bb4d3
源码。每套API/worker镜像一致。镜像摘要按平台、构建层和App环境分别记录；
网关、凭据、Origin、数据卷和运行数据继续各自独立，没有跨环境复制认证状态。
dev HEAD仍6c55e6ee；部署源由恢复引用保存，没有移动分支或启动CI。

## 验证

- App三种环境分别从同一git archive构建，类型与生产构建通过；同源API、
  完整源码版本、环境标识及静态包SHA256均核对。三套公开就绪检查通过。
- 本地1213个运行源码/配置文件与该源码逐字节一致。三套native逐个核对
  已打包Python与资源文件，Git符号链接按目标内容校验，全部一致。
- 后台与原生角色健康。三个环境开启相同Thinking推送开关。
- 63旧threads、attempts、events、session_artifacts与切换前备份哈希一致。
  新增验证会话之后另存回执，不把它误算为数据丢失或回滚。
- 63真实Qwen任务attempt_ab1d3791a5acd772完成，123推送批次对应7条正式
  Thinking；首次推送4.0418秒、首条正式6.3675秒，总50.6026秒。
  工具实际创建version-check.txt，下载9字节内容为f34bb4d3加换行，SHA256
  c4b042162e669cdb5cdac177f7081ec8d76c495bcff80eaf1ec61dc094fbb631；刷新恢复通过。
- 63既有网关仍selected configured、connected、contract_available=true；
  受保护配置哈希未变。电科院MCP可连通是用户给定前提，本轮未读取或修改
  业务数据，也未将普通文件验证当作电科院业务验收。
- 三区和本地复用此前同源码真实模型、工具、产品与Thinking验证。
  本轮只补齐源码身份/App构建，没有重复执行病态算例。

## 本地运行与恢复

本地此前完成规范重建。实际运行源码已逐字节校验，本轮为镜像补齐准确的
源码标签和image-source.txt。App以同一源码的local-dev生产构建做固定版本
联调，使用Vite preview保留同源API代理，端口5173保持。
这条固定版本入口不会自动展示工作树后续修改；恢复高频开发时需停止该
preview，再使用原make capstone-app-dev启动工作树Vite，并明确记录新候选差异。
preview PID和旧进程命令保存在忽略的local运行目录。

切换均先确认没有未结束任务，再备份。63与三区备份位于各自的
private/backups/version-align-f34bb4d3/，本地备份位于
.capstone-agent/version-align-20261105/local/backup/；旧镜像保留，无数据库迁移。
63曾因sudo不允许docker-compose独立命令而暂停启动，改用已授权的
sudo docker compose后完成，未绕过权限或删除数据。

完整回执、摘要、源码审计和App构建记录位于
.capstone-agent/version-align-20261105/。没有更新main/cloud/demo，没有CI、push或合并。
