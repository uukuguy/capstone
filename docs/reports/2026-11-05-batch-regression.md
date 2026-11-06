# 真实任务串行与调用错误复查

用户反馈4ba17891后仍大量串行、调用错误多。本轮先核对真实会话，未重跑原任务。

## 已确认问题

最新迎峰度夏任务attempt_1579b781f690006a，共186次工具开始、42次错误结束：
29网关、7组合程序、6bash。114次源记录查询全局最大并发4，但后续59调用组和
31调用组最大并发均1。小批次并发已工作，独立对象/年份的分页链仍外层串行。
链内游标分页确有依赖，不能把全部页随意并发。

组合程序出现full_result变量未定义、tools.saveContext不存在、超过有界读取预算。
程序按r.tool选择批次结果，但宿主之前未稳定提供该字段。这些属于Capstone问题。
本轮不把病态算例的analysis_non_converged误算成普通工具契约错误。

## 修正

来源984131e388244ee4cf24e1d13c2af4a41f87ede4，父4ba17891，
refs/capstone/fixes/batch-regression-20261105。

- tools.map有界执行独立异步链，返回输入顺序的映射值；每条链可等待自己的游标。
  mapper失败后不领取新项，排空运行项后报错，已有观察引用保留。
- 新结果、复用和跳过结果提供宿主确定的tool身份，源数据不能覆盖它。
- tools.saveContext/loadContext与原全局函数同源；不放宽datasets数组及引用验证。
- tools.help提供准确helper契约，说明full_result必须是实际返回的字面引用对象。
  不发明隐式变量，不自动改写模型JavaScript，也不声称能保证所有模型选对并发。

4项回归先失败后通过；55Node检查、20Python检查/1环境跳过通过。
新测试覆盖6条链每链3页、实际并发4、游标顺序、身份防覆盖、helper保存恢复与失败排空。

## 网关协查

本机网关发行包37文件、grid_database文件0，find_spec返回None，实际工具返回
No module named grid_database。其他internal_error待owner按request_id核对。
没有改动网关的脏工作区、配置、容器或数据。

用户明确授权通知；通过Orca现有工作区邮箱发送msg_0c13593879cc，并标工作区未读。
已入队，尚未确认读取；legacy终端邮箱会在终端关闭后失效，报告保留在仓库。
协查单：[运行缺包与request_id](2026-11-05-data-gateway-runtime-assist.md)。

## 部署与验证状态

规范本地重建完成，1313项运行输入与候选一致。API/所有worker/native/App均为984131e3，
全角色healthy，私有Env完整比较保持。API/worker同镜像cb6678d6，native200f8447。
固定源码Vite PID91545，页面local-dev、dirty=false。规范及最终定向清理完成。

真实commercial-deepseek-flash任务attempt_f5928ad4d535dc30，
thread thr_c422f7057df29e71949f，完成40.9591秒。6条独立对象/年份查询链，每链2页，
实际12次query_source_records最大并发4，查询区间1.5998秒；六条实际游标序列均0、1。
本轮工具错误0。chains-check.csv已保存并从正式下载接口读取：203字节、12行，
六链各2行，状态ok且returned_rows均1，SHA256：
ef937e12fa477c9a4d36660f04613c4ae0a7757719351d115d4c0901b7fce359。
浏览器来源/文件链接及刷新恢复通过。这证明有界多链分页路径可用，
不代表模型必然使用tools.map，也不代表原114次任务全部错误或性能已接受。
网关缺包协查仍未收到回复，不声明29次网关错误已修复。
doctor、18本地链接、相对符号链接和diff检查通过。控制图23:12快照已在1920px
核对，dev HEAD与本地来源分开、4ba→984实际祖先边存在、无横向溢出。
独立复审未取得，不计复审通过。源码与回执通过本地恢复引用保留，正常索引未动。
私有备份及试验回执：.capstone-agent/batch-regression-20261105/。
未联系63/66、未改local-demo/cloud/demo、无CI/push/merge。
