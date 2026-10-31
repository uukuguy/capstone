# 新疆10月消纳率会话：逐条工具错误分析

分析对象：`thr_d4f80602b2954e7b107e`，执行 `attempt_cc63f76830bcf82d`。
原始问题：`新疆10月份整体消纳率情况”+"画一条曲线”。`
本次仅读取已保存记录，没有重放业务请求、重建服务或启动 CI。

## 结论

共有 7 条失败工具结束记录，分为以下情况。没有发现本次失败由工具名映射错误引起。
网关成功识别了五次业务工具调用，并返回了可关联的 request_id。

| 序号 | 位置 | 工具和输入 | 完整错误与判断 |
| --- | --- | --- | --- |
| 1 | LLM 06，事件 96 | `agent_tool_load` 一次选择 7 个工具 | `Tool activation count capacity exceeded`。Capstone 容量拒绝。两个常驻网关入口也占容量，2+7=9，超过当前上限 8；输入 schema 却允许 names 最多 8 个，错误又没有告诉模型剩余容量。不是工具名称未映射。后续事件 111 改选 3 个工具继续执行。 |
| 2 | LLM 15，事件 384 | `describe_data_table`，`table=SG_DATACENTER.SG_CON_PWRGRID_S_WIND` | `Unknown or ambiguous table; use discovered schema.table`。模型改写了已发现标识：目录中实际是 `SG_DATACENTER.SG_CON_PWRGRID_S_DWIND`，少了 `D`。属于调用参数错误。 |
| 3 | LLM 15，事件 386 | `describe_data_table`，`table=SG_DATACENTER.SG_CON_PWRGRID_S_SOLAR` | 同上。目录实际是 `SG_DATACENTER.SG_CON_PWRGRID_S_DSOLAR`，同样少了 `D`。属于调用参数错误。 |
| 4 | LLM 22，事件 836 | `describe_source_table`，`table=SG_DATACENTER.SG_CON_PWRGRID_H_CE_RESULT_2021` | `Unknown or ambiguous source table; use discovered schema.table`。表标识确实来自目录，但该条目标明 `declared_only`、`physical_registered=false`、`readable=false`，其 next_actions 指向 `describe_data_table`，模型却选了原始物理表结构工具。属于入口选择错误；不能据此说该表名不存在。 |
| 5 | LLM 22，事件 837 | `describe_source_table`，`table=SG_DATACENTER.SG_CON_PWRGRID_H_CE_RESULT_2025` | 同上。后续 `describe_data_table` 成功返回该表声明结构，进一步排除了表名映射问题。网关“Unknown or ambiguous”把声明存在与物理不可读混为一句，诊断需要更明确。 |
| 6 | LLM 32，事件 1488 | `query_source_records`，见下方原参数 | `Unknown source field`。最可疑的是 `order_by[0]="-DATE"`：后续使用 `DATE`、`STAT_TYPE` 成功，所选字段及 ID 过滤也成功。当前返回没有错误参数路径，不能把具体字段的推断冒充网关确认；请网关按 request_id 确认。 |
| 7 | LLM 35，事件 1629 | `agent_tools_execute` 内调用 `saveContext` | `Unknown observation reference`。模型把 `datasets:[{name:'rows',value:rows}]` 交给保存接口；接口要求每个 dataset 提供已观察调用的 `call` 和可选 `pointer`。缺失 call 后直接查 undefined，产生不明确错误。属于 Capstone 内部组合程序参数错误及诊断不足。此前网关读取已成功，不能把整步视为没有执行。 |

第 6 条的实际参数：

```json
{"table":"SG_DATACENTER.SG_CON_PWRGRID_H_STA_QUA_2025","columns":["DATE","STAT_TYPE","INTEGRAL_VALUE"],"filters":{"ID":"0101650000"},"order_by":["-DATE","STAT_TYPE"],"limit":10}
```

第 7 条保存失败之前，已成功读取 989 行，`next_offset=null`，request_id
`394b595042d24e0bba8aa9ffc5205dd4`。读取结果在私有观察记录中仍存在。
应恢复已有观察引用再保存，不能为了修复保存错误重复执行整段程序。

## 为什么界面看不懂

完整响应已经保存在执行宿主的 observation 中，并没有丢失。
但 `progress.py` 对长失败响应仅保留开头 100 字符和末尾 497 字符，中间用省略号拼接。
这既截掉了 `gaps[].message`，也让嵌套 MCP JSON 不再是合法 JSON。
`threadFeedback.ts` 再尝试解析这段不完整 JSON，失败后只能显示
“工具返回错误；请展开原始诊断查看详情”。

因此，仅改前端 JSON 解析不能完整解决：后端必须在截断前提取结构化错误摘要、错误码、
参数位置和 request_id；原文继续由受控诊断入口按需读取。提取要覆盖通用 MCP 包装，
不能按业务工具名称写分支。不得把未受控的原始业务载荷直接投到界面。

## Capstone 后续修复范围

1. 统一错误投影：从完整结果提取诊断，再做长度限制和保护信息过滤；界面直接显示原因和 request_id。
2. 工具加载容量：公布实际常驻数量、可选容量和本次请求数量；输入约束与执行规则一致。
   保持有界菜单，不靠扩大预算掩盖问题，也不为某几个业务工具加例外。
3. 保存上下文：在使用 dataset.call 前校验来源引用，明确指出缺失的字段路径。
   不接受模型提供的数组自动升级为观察证据；保留已完成读取的恢复信息。
4. 已返回的 table_ref、next_actions 和工具契约应原样使用；不要在源码内添加电网表名或工具路由。

后续实施：用户确认方案后，已实现默认256/可配置1024工具容量、集中搜索/契约预算、
tools.follow(ref,pointer)原样复制成功观察中的动作、保存来源引用校验与已完成调用恢复信息，
以及在完整响应上提取错误原因/参数位置/request_id。上述原始诊断结论保留。
相关本地检查100项及前端类型检查通过；五份真实错误均验证得到可读摘要。
本地运行环境与浏览器验证另记；未启动CI。通用业务标识合法值仍依赖网关契约，
不能宣称所有字符串参数都能在本地确定验证。

## 业务结果的边界

本次生成的是缺口核查报告和 CSV，没有消纳率曲线。
目录的 declared_only 和查询无记录都是有效业务结果，不是这 7 次工具失败的同义词。
最终答复中“0 条已接入记录”比 declared_only 的证据更强：后者只证明不可读，
不能证明真实业务总记录数为零。其声明的“合计仅31行”也需要区分每表行数，不能直接沿用。
用户没有指定年份；实际运行额外探索多个年份，不应把它当成用户已经确认的分析范围。

## 原始证据

忽略目录 `runs/latest-tool-audit-20261031/`：

- `snapshot.json`：会话快照。
- `attempt_cc63f76830bcf82d.json`：1945 条事件、39 次模型响应。
- `failed-observations.json`：五次网关错误的完整保存响应及观察元数据。
- `decoded-observations.json`：66 份观察的解包结果，含发现、目录、后续成功读取。
- `source-metadata.json`：观察来源与调用关联。

该目录含业务查询结果，只用于本地受控诊断，不作为公开附件提交。
网关协查稿见同目录文档 `2026-10-31-data-gateway-error-coordination.md`。
