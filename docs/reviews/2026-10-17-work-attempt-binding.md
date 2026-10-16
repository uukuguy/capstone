# Work与生产执行绑定

状态：实现、产品检查和本地入口验收完成，起点dev885b2c14。local-dev运行a8b4e578；双平台CI及dev合入待完成。

## 范围与复用

本片将已保存Work接入既有Attempt队列、worker租约、执行事件和结果投影。
`start_work`沿用同一Thread命令入口、对象修订与幂等回执；不建立第二套调度器。
`cancel_work`复用既有取消事件和worker停止检查，界面保留停止入口，真实终态前不显示已停止。
已有专业资源的任务先接入现有生产执行器。无模型任务继续保存和恢复，
在真实native执行能力接入前不伪造模型、Attempt或成果。

前端沿用既定企业布局与成熟对话组件，将Work状态并入现有ThreadProjectionStore，
共用事件序列、断线补取、待确认命令及结果恢复。现有专业会话可显式进入任务工作台；
读取保留原协议，创建Work才升级，不因查看界面迁移历史。

## 固定范围与研究归属

启动时固定目标、WorkBinding及当前合法ModelContext。
能力选择沿用唯一的enabled_profiles与selection_revision，生产Claim恢复并消费快照。
此项是既有版本化Profile引用的固定，不代表全部外部资源内容和配置版本已冻结。
前次执行产生的合法模型修订可在下一次显式启动时重新绑定，Work及研究身份保持不变。

Work研究独立于其他Work和历史模型研究；保留原历史路径，不按相同模型或相似文字合并。
`enterprise-research`和`grid-analysis`的新应用组合注册、持续Pi组织及完整成果工作台
仍按所属任务推进，本片不以已有专业Profile别名代替它们。

## 验收清单

- [x] 内存与真实PostgreSQL：入队、重启、租约隔离、终结状态与同键重试。
- [x] 停止请求沿原worker生效；错误Work隔离，重复请求与终结竞态可恢复。
- [x] 生产Claim消费固定选择；同Work研究恢复、不同Work及旧研究隔离。
- [x] 前端共享状态流、真实结果恢复、跨会话响应与草稿隔离、无模型明确不可执行（注入执行事件回归）。
- [x] 旧专业入口回归，独立评审，规范本地重建与实际浏览器观察。
- [ ] 适用双平台CI、正常PR合入dev、精确来源与推进图同步。

## 早期评审发现与修复

- 失租中断路径未同步Work，可能使任务一直显示运行中并禁止再次启动。
- 既有同模型历史回退可能将其他Work或旧专业任务的指令、答案和结果引入新Work。
- 较长的已保存目标或累积消息可能超出RoutingInput边界，启动时抛出未处理异常。

三类问题已修复，后端独立复审通过：所有宿主中断路径同步Work；历史、结果引用和冻结的
会话上下文按Work过滤；本轮完整补充沿既有输入边界接入，成功后才推进消费计数。
停止请求不受启动准备及worker健康条件阻断，沿原控制链到真实终态。
复审记录：`/tmp/work-attempt-backend-review.md`。整体验收仍等待前端复审、集成门禁及运行检查。

前端早期评审发现历史窗口缺少归属边界时，未知Attempt可能显示到其他Work。
实现已加入全部Work最近Attempt映射及未知归属隔离提示。停止回执丢失但终态先到时，
保留原请求核对入口，不让待确认命令锁死任务。前端独立复审通过；26项聚焦测试、
242项共享组件/状态回归及TypeScript通过。记录：`/tmp/work-attempt-ui-review.md`。

后端追加核对待生效的模型与能力选择：Work启动必须沿原激活边界固定本次选择，
不能误用旧配置。实现复用原激活机制，拒绝启动不提交选择或事件；内存及PostgreSQL
正反例及最终独立复核已通过；前后端评审无未关闭问题。

## 聚焦验证

- 真实隔离PostgreSQL执行测试33项通过；涵盖启动、重启、失租、选择绑定、研究接入、
  跨Work隔离、输入消费、取消及待生效资源选择。
- 相关后端离线回归193项通过、12项数据库用例在该次运行跳过；数据库路径另按上项实测。
- 前端执行与恢复聚焦26项、已有共享交互回归242项通过；入口标题修正后7项入口测试通过。
- TypeScript、Python类型检查、包边界、App构建和diff检查通过。

日志：`/tmp/capstone-work-binding-execution-final.log`、`/tmp/capstone-work-binding-focused-final.log`、
`/tmp/capstone-work-binding-types-final.log`、`/tmp/work-attempt-app-build.log`。
产品门禁首轮日志为`/tmp/work-attempt-check-pr.log`。专业分析938项、仿真244项已通过；
App全量552项通过。研究尺寸测试改用真实Claim；回环代理排除后23项通过。
本机Provider环境影响部署测试的校验顺序，后续检查移除继承的Provider/Model配置。
修复后全后端1465项通过、2项跳过；其余产品门禁全部通过：部署工具207项、
Kernel642项、专业Domain Pack143项，以及通用工具、库存、PyPSA、成果工作台和注册worker。
这是按原`make check-pr`目标分段完成的产品检查，不是完整发布验收。
日志：`/tmp/work-attempt-backend-final.log`、`/tmp/work-attempt-remaining-clean-env.log`。

集成检查发现既有租约在历史读取前开始计时，慢读取可能耗尽1秒租约。
`a8b4e578`将准备、校验及账本写入放在最终租约写入前，保持事务原子性与严格过期拒绝。
两类慢历史读取回归先失败再通过；真实PostgreSQL及Work回归58项、类型检查通过，
独立评审通过。记录：`/tmp/capstone-work-lease-fix-report.md`、`/tmp/work-lease-review.md`。

本片未获Provider调用授权；离线测试不得记录为真实业务质量验收。
main、cloud-dev、demo与用户交付版本不在本片部署范围。

## 本地运行与界面

`a8b4e578`规范重建ready；API及双worker各1153文件匹配，镜像
`sha256:6aa4d1901cdcb4532ffee12af651ca5c5c03cde875f0f8da3d30238083994e8e`。
App构建身份相同；收据`runs/work-attempt-binding/local-identity.json`。

新专业Thread `thr_ff5128f155a022d6e65a`读取任务工作台时仍为v1，首次保存才升级v2。
Work `work_9e5baab14671da22c2c3`补充后revision2、goal_revision1，两条消息刷新后保留，
事件序列不因刷新增长；真实资源下开始按钮可用，但未点击。所有Attempt引用为空。
已有无模型Work仍可恢复资料，并明确显示暂不可开始。旧专业拓扑和会话入口可读。
390px页面无横向溢出，输入区和导航可用；最终浏览器console无错误或警告。

截图：`output/playwright/work-attempt-work-ready-desktop.png`、
`output/playwright/work-attempt-work-restored-mobile.png`。
