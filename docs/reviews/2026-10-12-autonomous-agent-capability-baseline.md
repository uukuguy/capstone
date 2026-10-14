# 自主研究首期基线盘点

日期：2026-10-12。本记录包含静态源码/契约盘点和隔离Authority实测，不是智能体端到端验收报告。

## 来源

- 根dev：4f15cfc；产品恢复来源：6ff7094。后续设计文档在工作区，未进入部署。
- 受管Pi源码HEAD：b79e4cc834970cca69daebffab7df1da7d1e52c4，与运行锁一致。
- 能力来源：[发布矩阵](../../configs/capabilities/pandapower-3.4.0-static-analysis.json)。
- 原始失败来源：[部署业务样本记录](2026-10-11-deployment-answer-samples.md)。历史记录不作为当前通过凭据。

## 已确认与尚待实证

| 范围 | 已确认的静态事实 | 尚待实证/完成 |
| --- | --- | --- |
| 研究上下文 | Pi context转换先于模型请求捕获；异常可被扩展runner捕获 | 必需版本检查、压缩/恢复后的实际输入 |
| 研究提交 | RPC等待循环可处理宿主请求；现有回执只确认轨迹留档 | 独立研究更新处理器、持久去重、取消/恢复 |
| 轻量入口 | KernelPiSessionBuilder要求prepared profiles，普通分支也在该检查之后 | 资源分层，准备耗时实测；不能只删除分类器 |
| 知识方法 | 已有版本绑定的guide资源读取及精确工具目录 | 首请求有界摘要、重复读取控制；方法正文不等于初始化已懒加载 |
| OPF | opf.ac/opf.dc和完整持久结果查询已发布 | IEEE39实际收敛、全线路/节点覆盖、价格单位和成本来源 |
| N-1与缓解 | 支路N-1、不可变修订、OPF、越限检查、比较已发布 | 故障集覆盖、优化建模、目标、控制量及逐方案AC回验 |
| 双线路停运 | revision.derive支持有序事务补丁；拓扑能力已发布 | line149/line59真实对象、停运前后分量与供电状态 |
| 短路 | IEC60909操作已发布 | mv_oberrhein所需参数、供电条件、设备额定值及适用范围 |
| 电压稳定性 | 当前矩阵未列独立稳定性能力 | 明确所求稳定性量与可用方法；不能以稳态电压合格替代 |
| 全量结果 | result.dataset.query有offset/limit和总量/下一页字段 | Thread到App的受控页访问与覆盖显示 |

本次盘点已运行一次隔离OPF；未运行N-1、短路或真实Provider请求。
“多个原子能力已发布”仅说明存在组合基础，不能证明整个研究任务必然可完成。

## 隔离Authority实测

只经公开gridctl request调用，未导入原始pandapower对象，未修改部署模型或用户数据。
17次调用的输入、输出、身份和耗时保存在本地忽略路径runs/autonomous-design-baseline/receipts.json；
对应Authority工作区位于同目录authority。该回执不自动成为产品当前对话的已准入证据。

- IEEE39打开成功：39母线、35线路、11变压器。
- opf.ac默认选项成功，converged=true；result_ref为
  result:sha256:3c063913f1390b46be1c94e23a2eff88593a4aeaa0822f0ded3ad11fcbbb894f。
- 从该结果取得35/35条线路loading_percent及39/39个节点lam_p，两次查询next_offset均为空。
- analysis.run CLI调用墙钟1.308秒，包含进程启动；不是纯求解器耗时，也不是智能体端到端耗时。
- lam_p schema的unit为null。数值列存在不等于货币单位已明确；必须追溯成本数据及单位来源，不得自行标为元/MWh。
- mv_oberrhein打开成功：179母线、181线路、2变压器。
- 线路59为Line 59，端点45→34；线路149为Line 149，端点79→64；均在运。
  这些为表索引，不是已证实的用户编号解释策略。
- 在同一派生修订同时停运59/149后，topology.components.get返回连通分量由2增至4。
  派生修订为revision:sha256:5edbac0e5c38a0423d2178ccb74331624b0cf568d3f665ec5a9ef5f8b3ebc1f6。
  这证明拓扑进一步分裂，不证明新增分量可维持带电孤岛运行。
- 两个外部电网源的rx_max、rx_min、s_sc_max_mva、s_sc_min_mva均为空。
  至少已发现短路输入缺口；不能擅自填入默认短路容量后冒充原模型结论。

本次结果证明公开计算/查询基础可用，未证明主智能体组织、正式回答质量、约束回验或完整复杂业务通过。

## 保留的整体回归样本

1. 当前模型概况及可做分析：检查事实来源、相关性和耗时，不应无故运行仿真。
2. 执行交流潮流：使用已打开模型，呈现已算出的有效结果，不无端要求对象列表。
3. 沿用潮流结果列负载率最高三条线路：复用适用结果，不重新计算潮流。
4. line7跳闸后线路重载：通用对象识别、派生场景及真实约束判断。
5. 母线31负荷变为1.3倍：通用对象识别、派生场景及新修订结果准入。
6. 全部发电设备N-1：理解机组范围，检查可用能力组合；不偷偷替换为支路N-1。
7. 中文连续对话：正式回答不混入英文执行前缀，中间进展与最终消息分离。
8. 三条新业务问题：原文保留在实施计划所引用设计中；分别检查完整性和真实证据。

样本允许语义改写，不用关键词命中判定产品正确性。客观验收使用实际工具事件、
模型/结果修订、全量行数、引用准入及执行次数；语言质量与业务充分性另行检查。

## 性能记录

每例记录源提交、模型/能力版本、冷或热、总耗时、准备、首次模型响应、首工具、
Authority累计耗时、结果查询、正式回答阶段与重复调用原因。
累计工具耗时不冒充墙钟耗时；复杂问题不套用简单问答时限。
普通概况曾约10秒是历史比较目标，不是本轮实测值。
出现明显增加时查阶段差异，不能靠缩短回答或省略必要验证换取通过。

## Confirmed derived-context admission defect

Using the saved real mv_oberrhein double-outage Authority artifacts, verify_context passed and
its parent_context_ref matched the bound opening context. The current Application verifier
rejected the successful child-context event with `tool identity does not match the bound model context`.
Reproduction: implementation worktree `runs/autonomous-admission/probe.py`, Python3.12.
This proves a strict-context admission defect; it is not a live agent task result.
The repair must validate Authority-owned ancestry, preserve the immutable original binding,
and reject unrelated models/contexts. Do not remove revision checks or trust model-written lineage.
Result projections also pass expected_model_revision and require review before claiming the repair complete.

## Derived flow integration check

Real isolated IEEE39 load scaling, AC flow, artifact admission, Domain result projection and Thread
terminal validation passed in9.59s. Child model revision is retained. Test:
`test_thread_capabilities.py::test_real_derived_powerflow_reaches_thread_result_projection`.
No model Provider, HTTP API, or browser used. Actual derived network view remains to be connected;
wrong-revision frontend overlay guards must stay in place. Changes are uncommitted.
