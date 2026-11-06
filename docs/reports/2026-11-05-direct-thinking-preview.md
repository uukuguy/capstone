# 三区 Thinking 直接推送试验

入口：http://192.168.72.66:5173/ 。源码
`073860ca543d9150c0ae7e8db9520e531b7a2bf4`，恢复引用
`refs/capstone/experiments/direct-thinking-20261105`。未合入dev，无CI，
.63、main、cloud和demo未更新。完整病态11节点任务由用户继续验证。

## 已部署内容

真实 Thinking 片段通过私有HTTP进入API，由原SSE连接推送。临时片段
不使用持久化序号。后台按5秒或16KiB UTF-8预算合并写入，最多64个
待写片段；语义事件和终态之前强制写完。工具、产品、最终答案与成功
状态仍以持久化为准。写入失败阻止正常成功并记录失败终态。批次ID
去重，刷新和重连以数据库为准。继续使用现有Thinking组件。

这是单API进程试验，默认关闭。三区开启CAPSTONE_THINKING_PREVIEW=1，
worker使用私有CAPSTONE_THINKING_PREVIEW_ORIGIN=http://api:8766。
发布端核对后台认证、活动租约、会话和工作空间。浏览器不接收租约或
凭据。并行片段无法准确归属时等待正式文本，避免放错位置。

理解工具请求JSON-schema constrained sampling（strict prefer）。生成契约
要求uses_selected_skill为布尔值，false保持原有“不使用”含义；Python
校验与引用边界保持原契约。提供方不支持时沿用SDK回退。尚未实施
上下文精简或新的推理预算策略。

## 验证

- 后台127项定向通过，11.60秒；生成与输入54项通过/6跳过，10.44秒。
- 前端106项、类型检查、生产构建通过。一项历史目的文案测试在原
  store/client基线也失败，单独排除，不宣称全部前端测试通过。
- 复审修正时间字段、UTF-8预算、路由元数据和发布中刷新屏障。
- 规范本地重建ready，API/worker同镜像32877cb1；doctor和缓存维护通过。
- 三区匿名私有发布返回401。两模型真实简短会话完成，刷新事件读取通过。
- Qwen真实帧通过现有组件重放：正式文本前出现真实片段，正式文本后
  即使仍传入旧临时片段也只显示一次。无已连接浏览器，视觉验收待用户。
- 原report.html、benchmark.csv、reproduce_results.csv重新下载，三份
  哈希与部署前一致；未重新审查数值结论。

| 简短会话 | 首个临时片段 | 首个正式Thinking | 临时批次/正式事件 | 整条任务耗时 |
| --- | --- | --- | --- | --- |
| Qwen，attempt_74dcc3b14ff69854 | 3.4461秒 | 6.9664秒 | 5/2，全部对应 | 31.2181秒 |
| dsv4，attempt_db08e027e1f8d731 | 无可显示文本 | 无可显示文本 | 0/0 | 52.8227秒 |

本次是简短解释流式显示与存储原理，不是病态11节点。公开理解阶段
为Qwen7.9751秒、dsv420.1510秒，不能与不同上下文的103.7/13.0秒直接
比较，也不代表固定提速。显示通道不减少模型生成或服务端排队。
原始帧和组件检查保留在`.capstone-agent/direct-thinking-20261105/`。

## 部署与恢复

API/worker同镜像：
`sha256:5acaa8e86bd950a165288a33f1a2a2d116682858d38d7cc1912830ec5b58864d`。
App：`sha256:9556e9cdc771c23cfc1c656712a2c1ac284d7be9197aae8a82a425e98261a162`，
脚本index-yrDmbrl1.js，同一源码，标签dky3-dev。Native保持cc50f8d8/
image2d13aca8；网关“三区研发”与数据卷保持原配置。

活动数为0后备份再切换。受保护的`private/backups/073860ca/`保存原环境、
Compose和PG备份；68bd1e07后台和22be9e5c App镜像保留。首次激活漏写
Compose项目名，只创建了错误项目前缀的三个候选容器，原服务仍运行。
核对标签后只移除这三个容器，明确使用`-p capstone-dky3-dev`完成切换；
没有删除卷或修改其他应用。回退须先检查活动任务，再恢复备份环境与
Compose并以明确项目名重建API/worker/App。没有数据库格式迁移。
