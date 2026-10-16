# 新建对话耗时

## 基准和第一批修订

cloud-demo 浏览器新建到输入框可用：22.024秒；创建请求19.161秒。
6d229e0缓存已验证的运行能力目录，并合并模型打开与概况读取。
上线后两次完整新建为27.614秒和14.051秒。仍未解决主要阻塞。

## 第二批修订 bd2a200

API原先在每次创建时同步重新导出基础图，阻塞事件循环。
现在按注册模型及修订缓存基础图，返回独立副本，不复用任务图层或计算状态。
缓存按16 MiB预算淘汰，出现内存压力时释放；失败不缓存。
服务就绪前预热默认图和worker能力目录。可选图预热失败不阻止API启动。
创建操作在线程池运行，保留原持久化和准备协议。

39项缓存/HTTP/目录检查、5项worker预热/模型概况检查及类型检查通过。
独立源码复审APPROVE，不能替代上线计时。
规范本地重建：66f6377a4482，端口5173/8767，原数据保留。
本地两次完整POST创建：1.570秒、2.117秒。未调用LLM。
记录：runs/demo-n1-debug/new-thread-local-bd2a200.json。

## 发布状态

bd2a200四角色已SUCCESS。稳定后浏览器新建7.393/8.062秒，POST4.798/6.018秒。
滚动更新期间的13.952/7.010秒不作为稳定基准。
3注册用例9轮、报告和证据回放通过；原Thread恢复通过，无Provider调用。
local-demo同源ready，镜像7f63f52d71c4，端口15173/18767，数据保留。
验收标签：demo-20261014-0744-bd2a200。创建请求剩余5–6秒，尚未完全消除云端额外开销。
cloud-dev保持原版本。数据库、对象存储、凭据和端口不变。
N−1输入膨胀、工具引用错误和收尾耗时另见执行差异审计，尚未完成优化。

## 07d618a：定位新建响应等待

源码对照：73b6c07把worker模型能力准备加入创建请求等待；ed2524f创建后直接返回。
07d618a在201响应发送后启动原有预热，首条任务通过同一owner锁等待并复用。
本地创建POST0.145/0.025秒；基础图0.480/0.668毫秒，PG连接3.942/4.972毫秒，写入102.754/13.898毫秒。
本地模型能力准备1428.893/2813.274毫秒；后者包含两个并发创建时的等待，不能解释为独立单次准备耗时。
云端POST0.698/0.447秒，服务端91.597/36.009毫秒。浏览器整页新建2.794/2.512秒；实际点击新建2.085/2.718秒。
云端细分日志读取返回Problem processing request，没有取得模型准备各段数据；不得编造云端细分。
部署已更新到07d618a，发布验收、独立demo标签和local-demo同步仍未完成。
证据：runs/demo-n1-debug/new-thread-cloud-07d618a-api.json、new-thread-timing-cloud-07d618a.log、new-thread-click-cloud-07d618a.log、new-thread-local-07d618a-phases.json。

## 2026-10-14 后续发布核对

同一07d618a部署的三个注册用例共九轮、报告及证据回放通过，无Provider调用。
后台工作台准备最终为ready；原Thread thr_f5c1ce9f1f662f398ea8的历史回答、
IEEE39结果图和可用输入框在实际cloud-demo页面恢复，浏览器本轮无错误。
API、App和两个worker仍为交接中的四个SUCCESS部署，没有重新部署。
部署元数据已读取四个镜像摘要；各角色独立构建，摘要不同本身不能认证源码一致。
SSH读取运行收据失败，因为当前账户没有注册SSH公钥。
筛选后的API日志显示同一启动契约10a77f73e48e，但不包含源码工件摘要。
故精确运行工件核对尚未完成；没有新建demo验收标签，也未更新local-demo。
cloud-dev、现有端口、数据库和存储均未改动。

收据：runs/demo-n1-debug/demo-07d618a-acceptance.json、
demo-07d618a-role-identity.json、demo-07d618a-deployment-source.json、
demo-07d618a-runtime-identity.json、demo-07d618a-filtered-runtime.log。
浏览器截图：output/playwright/demo-07d618a-original-thread.png。

## 后续发布身份核对

临时验证公钥注册成功，SSH认证后返回平台控制入口说明，未返回所选容器的运行回执。服务文件下载断开，按API域名发起的SFTP也被拒绝；临时注册密钥已删除。没有新建部署或修改数据库、存储、Provider配置。
PR #18双平台检查均失败：Linux工具说明断言本地复现，macOS流式报告计时检查本地独立运行通过。失败仍保留，不能据此声称合并门禁通过。
用户指定顺序为：两个demo完成后先通过门禁合入dev，再从dev推进剩余业务链与交互验收。

## 2b6ae7b：可核对的运行身份候选

启动日志增加与容器文件相同的无秘密运行回执，供各角色的契约、源码与安装工件摘要核对。针对性59项检查通过；既有来源文案断言按通用契约修正，流式预算测试使用确定时钟覆盖持续输出超过单次空闲预算的情形。
规范local-dev重建ready，三个后端共享镜像2d50788075d7。529个安装源码文件与精确提交逐角色一致，回执源码及安装工件摘要一致，App显示2b6ae7b且dirty=false。原数据保留。
双平台PR检查38554449840、显式完整发布检查38554987581及本地make check-pr进行中。cloud-demo两worker候选构建中，尚未宣告云端验收；cloud-dev和local-demo不变。
本地收据：runs/demo-n1-debug/2b6ae7b-local-runtime-receipts.json及2b6ae7b-local-source-verification.json。

候选四角色已SUCCESS，三后端回执契约/源码与本地一致，云安装工件摘要一致。三注册用例九轮及报告、证据回放通过，零Provider调用。实际浏览器恢复原Thread回答、39母线/46支路图和可用Composer，控制台零错误。
历史回答图操作按钮的自动点击曾被footer拦截，保留为后续交互检查项；图的实际恢复与按钮点按验收分开记录。
用户最新基线原则：此部署只算未合入候选验证。先合入dev，再以同一dev合并提交正式发布两个demo；2b6ae7b不创建正式demo标签。
云收据：runs/demo-n1-debug/2b6ae7b-cloud-runtime-receipts.json、2b6ae7b-runtime-alignment.json、demo-2b6ae7b-acceptance.json。截图：output/playwright/demo-2b6ae7b-original-thread.png。
