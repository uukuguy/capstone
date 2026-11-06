# 内网默认模型改为dsv4

63内网联调和三区研发的新会话默认模型改为dsv4，注册profile为
intranet-dsv4-18804，地址http://192.168.72.69:18804/v1。
本地默认commercial-deepseek-flash保持。所有已注册模型继续可选；
既有明确选择与冻结profile身份不因默认值改变而被覆盖。

三套环境全角色同步源码
`bfb16344242658ffeeaf8ee8c1f5dcfdcf7bd82c`，恢复引用
refs/capstone/fixes/default-dsv4-20261105。该源码在f34bb4d3上只改应用的
内网默认profile、对应回归与部署说明，不改模型定义、凭据或领域权限。

| 环境 | API/worker摘要前缀 | Native摘要前缀 | App构建 |
| --- | --- | --- | --- |
| 本地联调 | 7abbf1e5 | 0c25ecb5 | 固定源码Vite；生产构建index-bY0zX88l.js留存 |
| 63内网联调 | 34b2e04a | 43fbc924 | index-SA4f70Kv.js |
| 三区研发 | df3b64ef | 002e4daa | index-akFfGCb3.js |

## 验证

- 默认值回归先出现2项失败，修正后137项定向通过/9跳过，1.15秒；覆盖
  profile目录、冻结选择、理解/执行模型解析、输入和主机运行契约。
- 两套内网公开input-catalog默认均为intranet-dsv4-18804；本地仍为原默认。
- 两次真实请求均不传llm_profile_id：63的attempt_adb583b42311e8f6和三区的
  attempt_5c2adb643f9b4bc0均完成。持久化的提交profile均为18804，理解引擎
  engine_identity.model均为dsv4，刷新恢复通过。耗时51.1102/49.9256秒是
  简短对话全流程记录，不作为模型固定速度或原病态算例提速证据。
- 三套App分别从同一源码构建；类型、生产构建、完整版本、环境标签和
  同源API均通过。API/worker同镜像，三套运行角色OCI标签均为完整bfb源码。
- 本地规范重建使用支持的CAPSTONE_START_APP=0，随后单独验证固定App构建。
  首次默认重建因静态preview没有Vite开发用的__capstone-build接口而停在
  App环境检查；已通过支持的跳过开发服务器选项完成重建，不算产品回归。
- 网关、认证状态、数据卷保持各自独立；63旧数据关键表与备份哈希一致，
  新增验证会话另计。此前同源码基底的真实工具、文件下载与Thinking回归保留。

切换前均确认无未结束任务；未取消任何新任务。63/三区受保护备份分别在
各服务器private/backups/default-dsv4-bfb16344/，本地备份在忽略运行目录。
本地App改以固定源码Vite开发模式运行，避免生产模式把local-dev显示成
user-local。原始生产构建保留在apps/local-dev/；当前固定源位于
.capstone-agent/default-dsv4-20261105/local/dev-app/，源码与bfb归档一致。
生成的生产环境receipt另存；Git发现边界仅对子进程生效，防止归档误继承
外层工作树HEAD。版本来自归档build-revision.txt，环境为local-dev。
app-fixed-source.pid/log位于local/；该入口不会反映工作树修改。恢复高频
工作树Vite前须先停止它。浏览器确认local-dev/bfb及原默认模型，两个内网
页面均显示bfb及18804/dsv4。三套运行源码与实际dev HEAD6c55e6ee分开记录。

日志、真实帧、模型证明、构建摘要均在.capstone-agent/default-dsv4-20261105/。
无CI、push或合并，main/cloud/demo保持原来源。
