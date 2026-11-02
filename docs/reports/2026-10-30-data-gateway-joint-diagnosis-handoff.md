# 本地研发网关：迎峰度夏联合诊断交接

## 定位标识

- 网关：本地研发，18003；instance_id `9afa2e62-3914-47a9-aa71-c6e13be743d9`。
- Capstone thread：`thr_dfa20d8487ecbbe8476a`。
- MCP diagnostics task_id：`work_149d0f91d0ea5114164e`。
- MCP diagnostics run_id：`attempt_6505bb3d4c888bdb`。
- trace_id：`773e57ee7295b7428ca0a44dc23dcb17`。
- 此run_id是执行轮次身份，与Thread账本的会话级run_dfa…不同；请按上述MCP字段检索。

用户授权Capstone同机协助只读检查日志；网关内部修复由data-gateway负责。部署后用这些关联身份交换诊断回执，不依赖共享文件系统。

## 已观察事实

完整研究969.479923秒，81次模型响应、244次工具开始事件。两次模型通信错误分别约300.130342秒和15.643366秒。长异常段HTTP200、982字节、无正常结束标记；随后模型继续执行。这些时间不能归因网关。模型响应区间累计764.752秒，其中正常响应约448.98秒；累计值不等于依赖关键路径。

按指定task/run筛选网关持久日志得到790事件、395个span，起止各395条。外层真实调用163次：132只读SQL、11表枚举、10表描述、6目录检索、其余4项发现调用。内层tool.execute与database.read是嵌套阶段，不应重复计作调用。全部关联到同一trace。

外层完成区间累计192121.7毫秒；tool.execute累计192019.8毫秒；70条database.read累计1255.87毫秒。调用可能并行，累计值不等于墙钟关键路径，不能把三个累计相加。数据库阶段目前覆盖不全，不能据此断言SQL数据库只用了1.26秒。

外层状态150ok、8partial、4error、1unavailable；错误码8次sql_result_truncated、2次invalid_arguments、2次query_timeout、1次source_capability_not_configured。partial/unavailable需按契约解释，不一律当失败。

## 请data-gateway专项细查

### P1：慢SQL实际时间花在哪里

| request_id | 外层耗时ms | 结果 |
|---|---:|---|
| 4a63ad2e39ac472482a24a65c0339244 | 20051.886 | query_timeout |
| a3298df11f69438bb812fb292ae54a56 | 20027.737 | query_timeout |
| 05a653999cbe439ab156d32b5c3231f3 | 17350.477 | ok |
| 9be4cb37b5f44357a1be37b97feefc8c | 16428.756 | ok |
| ddb9290b4d6b4842a8bc7a7ab4f7aa30 | 4986.635 | ok |
| 34641a7bfe08445090195426312cb48c | 4884.853 | ok |

请检查执行/取回/类型转换、连接与锁等待、扫描范围及可用索引；仅对已证实瓶颈提出修复。现有database.read阶段主要落在目录查询，需说明上述SQL为何没有对应阶段，是否需要覆盖该执行分支。不要先提高超时掩盖问题。

### P1：阶段状态语义

两个query_timeout外层error，但对应tool.execute内层为ok、error_code为空。请确认ok是“正常返回了业务错误包”还是“业务成功”；若仅表示调用函数返回，需明确区分执行状态与业务结果，避免诊断用户误读。并检查invalid_arguments与unavailable是否有同类情况。

### P2：契约是否足以避免重复原始SQL探索

本轮132次SQL、8次结果截断、2次参数无效。请按上述request记录核对参数错误反馈是否提供可操作的字段/类型约束，以及结果是否标注完整性和合法后续操作。结合本轮实际数据范围评估新发布的时序/统计语义工具是否已清楚说明适用对象、指标、时间、单位与限制。不要为“迎峰度夏”写死流程或新建特例工具；Capstone也要承担工具选择与重复探索的优化。

### P2：数据质量语义

请确认量测字段文本类型、缺测哨兵、统计聚合口径与省份覆盖的自描述是否准确。不能根据同比>15%就认定数据错误：本轮模型据此剔除5省，是Capstone研究方法问题；请仅提供真实质量标记与来源证据，不替模型背书。台风台区字段也需避免被解释为登陆/因果影响。

## Capstone承担的工作

模型流异常和恢复展示；减少重复发现/SQL与脚本试制；修正无依据排除省份；跨年曲线按同月日对齐；逐页验证PPT图片和图表。15页PPTX/CSV交付完成不等于研究质量接受。网关身份兼容修复已验证，界面恢复“本地研发”。

## 请返回的核验回执

对每项给出request_id、确认的阶段和耗时、根因或证据不足、是否需要修复、具体变更及复测方法。明确区分已观察、推断和待查。不要用跨机墙钟直接相减，也不要把嵌套span累计当任务总时长。

## 证据

应用分页事件、产物及摘要：忽略目录`runs/correlated-summer-20261030/`。本次筛选的网关元数据副本`gateway-diagnostic-metadata.json`与`gateway-spans.csv`仅用于诊断，不含认证或SQL正文；原始网关持久记录仍归data-gateway拥有。文档可独立交接，不要求对方读取Capstone的本机文件。

## 新阶段发布后的修订轮

同task_id work_149d0f91d0ea5114164e，新run_id attempt_a9448a3ec9f219b8。449.186478秒，42模型响应、11次网关调用（9SQL、2表枚举），无query_timeout。复用旧数据的修订任务，不能与完整首次研究直接比较性能。阶段记录已出现sql.plan/execute/fetch和fetch行数；一次sql_invalid_query的内外层均error。请重点核验以下两个慢请求，各阶段如下，勿相加嵌套外层。

cd5c7226a7134be4bba14f18b1742d1d [{"stage": "sql.plan", "elapsed_ms": 0.296, "status": "ok", "error_code": null, "row_count": null}, {"stage": "sql.execute", "elapsed_ms": 7471.532, "status": "ok", "error_code": null, "row_count": null}, {"stage": "sql.fetch", "elapsed_ms": 0.068, "status": "ok", "error_code": null, "row_count": 1}, {"stage": "tool.execute", "elapsed_ms": 7490.77, "status": "ok", "error_code": null, "row_count": null}, {"stage": null, "elapsed_ms": 7491.219, "status": "ok", "error_code": null, "row_count": null}]

e90baff504474987bcaa2d887a70d9d6 [{"stage": "sql.plan", "elapsed_ms": 0.153, "status": "ok", "error_code": null, "row_count": null}, {"stage": "sql.execute", "elapsed_ms": 7241.11, "status": "ok", "error_code": null, "row_count": null}, {"stage": "sql.fetch", "elapsed_ms": 0.118, "status": "ok", "error_code": null, "row_count": 1}, {"stage": "tool.execute", "elapsed_ms": 7262.172, "status": "ok", "error_code": null, "row_count": null}, {"stage": null, "elapsed_ms": 7263.004, "status": "ok", "error_code": null, "row_count": null}]

应用产物自述：16页修订PPTX及258条核心指标；已纠正按涨幅剔除与跨年横轴。视觉验收仍待独立核查，不能以模型自述代替。新增网关元数据样本在runs/correlated-summer-20261030/gateway-revision-diagnostic-metadata.json。
