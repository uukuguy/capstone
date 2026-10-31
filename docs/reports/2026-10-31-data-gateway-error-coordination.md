# 给 data-gateway：新疆10月消纳率会话协查

## 网关核对回复：修正待实例重载

后续实测：已重新初始化连接并先读取说明，再调用 discover_gateway、check_gateway_contract
和完整 describe_gateway_contract。三者发布时间一致，更新为
`2026-10-31T21:46:14.480376+08:00`，实例标识未变。
runtime.unknown_arguments 已声明未知顶层参数在处理前拒绝且不改写执行；
runtime.ambiguous_source 已声明外层复制失败子缺口并保留 query_index。
Capstone workspace 网关缓存 reload 成功。证据位于
`runs/gateway-publication-after-reload-20261031/`。这是契约验证，未重放业务查询。

以下为网关维护者提供的核对结果，尚未由 Capstone 重连验证。当前进程发布时间仍为
`2026-10-31T16:43:18.790290+08:00`。重载后只比较 `check_gateway_contract`
返回的实例标识和 `contract_updated_at`，变更后刷新后续任务契约；历史任务保持冻结。

- 请求 `28e25923db3c481696a4dc0f76470498` 同时匹配来源 `0021430000`、`0021990100`，各 696 行，均在同一张 2025 年表中。字典没有来源名称，不能据行数或编号代选。发现路径为 `list_object_metrics`（复制已有 object_ref，measurement_id=11032001），再用返回的 metric_ref 和原窗口调用 `discover_metric_sources`，确认来源后将 source_id 传入所选序列工具。这些名称只记录当次契约，不写入执行路由。
- 本次月缓存未命中，失败结果没有写入。缓存保存原始采样月份，键含请求 source_id、映射及其时区、对象、测点、库身份和数据文件身份。分辨率及统计量不在键中，与缓存原始采样的用途一致，不能据此认定缺陷。重载后外层 gap 将直接返回 ambiguous_data_source 及已有恢复说明。
- 请求 `244a32a501b04bed9f2b47eff8dd9ea6` 的计划为覆盖索引全表扫描加临时 B 树，在 sqlite 的 20 秒预算处中断。后续请求应按已发现对象和时间范围收窄，或动态选择已发布的序列/统计工具。不得原样重试或提高预算。
- 重载后 orderBy 将在执行前被拒绝，路径为 /orderBy，明确未执行，并建议唯一近似参数 order_by；合法名称来自 input_schema.properties。当前进程仍会忽略该额外字段。网关称其匹配规则判为编辑距离 1；Capstone 不复制或重新推导该匹配算法，不自动改写执行。

Capstone 尚待修复的独立问题：通用错误摘要需要展示失败子结果中的具体原因，不能只显示外层占位说明。网关将原因提升到外层不能代替客户端的通用修复。
本次仅更新核对结论，没有重放冻结任务或新疆业务查询。

## 新增协查：统计查询的数据源选择与缓存

入口：`http://127.0.0.1:18001/mcp`。实例：`3db5bb96-2c27-4d97-8584-346bc4a18656`。
以下依据已保存的调用记录分析，没有重放业务查询，也没有清理缓存。

### 204ms 的统计错误

工具：`query_database_series`。request_id：`28e25923db3c481696a4dc0f76470498`。

```json
{"mapping":"grid.minute","object_id":"0101430000","measurement_id":"11032001","start_time":"2025-06-15T00:00:00+08:00","end_time":"2025-08-16T00:00:00+08:00","resolution":"day","statistics":["max","mean","min"]}
```

外层 gaps 是 `query_error / See this subquery result for details`。
实际子错误位于 `data[0].result.gaps[0]`：

```json
{"reason":"ambiguous_data_source","message":"Multiple data sources match; select source_id explicitly","data_ref":"database.b40bf1bf6aff56af1942e2bf","scope":{}}
```

返回 `source_id:null`，`calculation.cache_mode="use"`，`cache_hits=0`。
目前可以确认数据源选择存在歧义，不能据此确认统计缓存故障，也不能排除数据源目录或元数据缓存过期。

请网关侧按该 request_id 核对：

1. 哪些 source_id 同时匹配？它们是替代数据源、按时间分区的数据源，还是重复注册？请提供现有发现工具的调用参数，供客户端取得合法候选及选择依据。
2. 统计缓存键是否包含已解析的数据源身份和影响结果的版本、时间区间、时区、分辨率、统计参数？来源改变或目录更新时，旧缓存是否仍被复用？这是待查项，不是已确认故障。
3. 是否缓存过来源歧义或失败结果？若是，失效条件是什么？本次 cache_hits=0 的统计范围是否包含来源解析或元数据缓存？
4. 请将具体子错误及恢复方法传到外层 gaps 或已有 agent_guidance，避免外层只有“看子查询详情”。来源不唯一时，不要求网关猜选，也不要求新增语义注册。

Capstone 侧同样有展示缺陷：摘要只取了外层错误，漏掉子错误。客户端需通用地展开失败子结果，保留 request_id；不按本工具名添加特例。

### 20s 数据库超时

工具：`execute_data_query`。request_id：`244a32a501b04bed9f2b47eff8dd9ea6`。

```json
{"request":{"table":"SG_DATACENTER.SG_CON_PWRGRID_H1_MEA_2024","columns":["t.MEAS_TYPE"],"filters":[{"field":"t.MEAS_TYPE","op":"eq","value":"11032001"}],"group_by":["t.MEAS_TYPE"],"aggregates":[{"op":"count","field":"*","as":"n"},{"op":"count_distinct","field":"t.ID","as":"ids"},{"op":"min","field":"t.CREATE_TIME","as":"t0"},{"op":"max","field":"t.CREATE_TIME","as":"t1"}],"limit":5}}
```

网关返回 `query_timeout`，driver 为 sqlite，source_instance 为 local-business-copy。
该请求没有时间范围，含 count_distinct；limit=5 不限制聚合前的扫描量。
请检查生成 SQL、执行计划、索引使用和数据库时间预算。统计缓存是否相关需结合网关记录判断。
Capstone 没有触发传输超时；调用方也需依据计划收窄查询，不应原样重试或直接提高预算。

## 追加协作请求：未知参数要返回可纠正的诊断

用户已确认：希望参数错误返回具体原因和最可能的纠正方法。当前回复中
“orderBy 会被丢掉，其余参数继续执行”仍可能造成请求意图被改变。
请在执行前识别这类未知参数并返回富诊断，不静默丢弃、不自行改写后执行。
这不要求新增业务语义注册体系，也不要求增加错误名称别名。

具体例子：调用当次发布的记录读取工具时，把 `order_by` 写成 `orderBy`。
请指出 `/orderBy`、原错误名称、合法参数名来自该工具 inputSchema.properties，
并明确 `executed:false`。保留现有唯一建议条件：大小写不同，或编辑距离恰好为1且只有一个候选。
`orderBy` 若不符合该条件，就给合法参数来源，不强称它唯一对应 `order_by`。
多个候选时说明没有唯一改法，保留候选给客户端选择。表名和字段名同样由网关权威核对，
只因目录搜索不完整而没找到时，不能断言不存在。

可沿用现有 gaps 及 scope，不增加新的入口。下面只是客户端已支持的最小诊断形状示例，
实际字段以双方确认的输出契约为准：

```json
{"status":"error","gaps":[{"reason":"unknown_argument","message":"未知参数 orderBy",
"scope":{"path":"/orderBy","rejected_value":"orderBy",
"legal_values_source":"inputSchema.properties","suggestion":"请核对该工具原契约的合法参数名；没有满足条件的唯一改法时不自动更名",
"executed":false}}],"provenance":{"request_id":"example-request"}}
```

Capstone 本次补齐 gap/scope 中执行状态、拒绝值、合法值来源和纠正建议的展示。
建议只是诊断，不表示已经改写执行。已发出的任务和数据观察继续冻结；不为验证该示例
重放新疆查询。此请求尚未发送到外部服务。

## 网关回复与重新连接核对（18:48）

已读取网关修正回复，重新连接并阅读初始化说明，随后调用发现、轻量检查及完整契约入口。
本次 `contract_updated_at` 为 `2026-10-31T16:43:18.790290+08:00`，与旧发布时间不同；
发现、检查、完整契约三处一致。检查 request_id：`d599cd654e0f4bb4b1dfbbf318abc5ba`。
57项发布工具的 selection 有效：business35、provider_global11、provider_fallback6、gateway5；
只有一家主提供方，无扩展提供方。原始返回保存在忽略目录
`runs/gateway-publication-20261031-164318/`。

已通过 Capstone `/api/v1/workspace/gateways/reload` 重连当前选定的本地联调实例，状态 connected，
实例标识未变。代码刷新按实例和 contract_updated_at 比较，不比较发现与错误指导中范围不同的
contract_revision。新目录用于后续授权；旧任务绑定的目录采用独立深拷贝。未修改任务
`work_a94339a8ac07f50f7a6f`，未重放新疆查询，也没有执行任何业务工具。

网关已解释原拒绝点：排序前导减号无效；年度结果表只有声明、没有可读物理表；
风光表名少写字符，目录返回才是标识来源。错误诊断现说明路径、拒绝值、合法值来源和
executed:false；唯一建议不表示自动改写执行。额外参数仍可能被输入契约忽略，不能依赖猜名。
这些是本次实例的协查结论，不转成固定业务名称或路由规则。

消纳率业务仍未完成：年份没有确认，记录也未证明存在指定年份、新疆范围内可读的十月序列
或可核对的分子分母。工具发布或声明结构不表示数据可用。原协查问题不再归因为网关工具名映射。
以下为当时发出的协查请求，保留为历史记录；网关错误拒绝行为本次未重新触发验证。

入口：`http://127.0.0.1:18001/mcp`。
实例：`3db5bb96-2c27-4d97-8584-346bc4a18656`。
当次发现的 contract_updated_at：`2026-10-31T13:19:56.304991+08:00`。
当次发现的 contract_revision：`120ece51f46b0787a1b27ef0d718ace78b89a6c8231b002b1f41354d9c85cf3a`。
五次错误中 provenance.agent_guidance.contract_revision 则为
`432ded43ce94e3eedd67f594a5224b044250541a949e7815a934201864e0c992`。
请说明这两个字段是否属于不同版本范围；目前不能仅凭不同哈希认定运行期间发生了契约变更。
这是对保存记录的协查，本次没有重放业务查询，不用当前新契约替换当次快照。

业务问题：“新疆10月份整体消纳率情况，画一条曲线”。用户未指定年份。
任务 `work_a94339a8ac07f50f7a6f`，执行 `attempt_cc63f76830bcf82d`，
trace_id `eb818a13d1ed9fda271dcb2b00080689`。

当次只有主提供方“电科院达梦数据库”（`grid-default`），没有扩展提供方。
Capstone 有工具加载容量、上下文保存和错误展示问题，由 Capstone 自行修复。
没有证据表明本次存在网关工具名映射故障。

## 请确认的具体情况

### 调用方确定校验需要的最小说明

Capstone 会统一校验工具身份、参数结构和观察引用，并支持原样执行当次返回的动作。
以下示例仅用于说明问题，不会把表名和工具名写进长期执行逻辑。

- 表目录已经给出 `SG_DATACENTER.SG_CON_PWRGRID_S_DWIND` 及其 next_actions。
  Capstone 应引用并复制这个动作的 tool/arguments，避免模型重新拼成 `_S_WIND`。
  对需要自行组合的请求，请明确参数的合法值从哪份发现结果取得；若范围小且固定，
  直接在 inputSchema 给 enum。搜索结果不完整时不能当作全量白名单。
- `columns`、`filters` 和 `order_by` 中的字符串涉及源字段。
  请在契约中明确字段合法值的结构发现入口，以及 order_by 是否只接受原字段名。
  例如 `order_by[0]="-DATE"` 不合法时，返回路径 `/order_by/0` 和实际拒绝原因，
  若允许另一种排序表示，给出符合当前 inputSchema 的具体示例；不需要新增排序工具。
- declared_only 的目录结果已给 `describe_data_table` 动作。
  请在物理表工具说明中明确不接受仅声明项；拒绝时返回“无物理连接/不可读”而非泛称未知表。
  如希望 Capstone 在调用前判定，应提供可机读前置约束，不能要求 Capstone 从工具名猜路由。
- 错误继续使用已有 gaps/provenance。请尽可能提供字段位置、拒绝原因、合法值来源和
  是否已执行/可否修正后调用；缺少信息时保持未知，不用额外通用语义注册层。

另外，请确认同一次会话 discover 与错误 guidance 的 contract_revision 为不同哈希的原因：
若一个是网关总体、一个是工具或说明版本，请明确各自范围及客户端能否比较。

1. `query_source_records` 报未知字段，却没有指出哪个参数中的哪个字段。

请求参数：

```json
{"table":"SG_DATACENTER.SG_CON_PWRGRID_H_STA_QUA_2025","columns":["DATE","STAT_TYPE","INTEGRAL_VALUE"],"filters":{"ID":"0101650000"},"order_by":["-DATE","STAT_TYPE"],"limit":10}
```

request_id：`b5ca919633c74e5192be4bcde2b4b074`，时间 `2026-10-31T15:44:38.340204+08:00`。
原始业务响应为 `status=error,data=null`，gaps：

```json
[{"reason":"invalid_arguments","message":"Unknown source field","data_ref":null,"scope":{}}]
```

后续用 `order_by:["DATE","STAT_TYPE"]` 成功读取了同一对象同一表。
请确认拒绝点是否是 `order_by[0]="-DATE"`，并明确返回字段路径、拒绝值及契约允许的排序形式。
若不支持倒序，说明不支持即可；不需要新增排序语义注册机制。

2. 声明表与物理表不可读的错误可否区分。

```json
{"tool":"describe_source_table","arguments":{"table":"SG_DATACENTER.SG_CON_PWRGRID_H_CE_RESULT_2021"},"request_id":"4540b44e640a49bfa050541658081afb"}
```

```json
{"tool":"describe_source_table","arguments":{"table":"SG_DATACENTER.SG_CON_PWRGRID_H_CE_RESULT_2025"},"request_id":"c0fff84ae8c74c43966ee4c4d286a923"}
```

时间分别为 `15:43:36.148132`、`15:43:36.149161`（+08:00）。两次 gaps 都是：

```json
[{"reason":"invalid_arguments","message":"Unknown or ambiguous source table; use discovered schema.table","data_ref":null,"scope":{}}]
```

当次目录确实发布了上述 table_ref，但同时标记 `declared_only`、`physical_registered=false`、
`readable=false`，next_actions 指向 `describe_data_table`。
Capstone 模型没有遵守这个下一步工具，入口选错；后续正确工具能返回声明结构。
请确认当前拒绝符合设计，并考虑直接指出“只有声明结构、没有可读物理表”，附已有声明结构读取动作。
不要求让不可读表变成可读，也不要求新增业务路由。

3. 供关联排除的两次错误，不要求网关兼容错误表名。

```json
{"tool":"describe_data_table","arguments":{"table":"SG_DATACENTER.SG_CON_PWRGRID_S_WIND"},"request_id":"9d61dbda0e154f908884b78c4755ca3e"}
```

```json
{"tool":"describe_data_table","arguments":{"table":"SG_DATACENTER.SG_CON_PWRGRID_S_SOLAR"},"request_id":"485d0fafa7d64cecaac96ed3712dd20c"}
```

两次 gaps 均为 `invalid_arguments / Unknown or ambiguous table; use discovered schema.table`。
目录实际给的是 `SG_CON_PWRGRID_S_DWIND`、`SG_CON_PWRGRID_S_DSOLAR`；模型自行遗漏了 `D`。
这是调用方错误，请勿新增别名掩盖。

## 业务可执行性

本次最终只得到数据缺口报告，没有画出曲线。
当次目录中的新能源消纳结果年度表、月度评价表为 declared_only；运行记录也未找到目标十月的可用序列。
如需完成业务，请说明哪个已开通提供方及发现路径能够取得指定年份、新疆范围的消纳率或其可核验分子分母。
若当前实例未接入这些数据，明确告知缺少哪类接入即可；工具已发布和声明表存在不能当作已有数据。
分析年份仍需由用户确认，Capstone 不应默认把多个年份查询当作口径已确认。

当次 `discover_gateway` 原文与五次完整错误已保存在 Capstone 本地受控证据目录。
最小定位文件为 `runs/latest-tool-audit-20261031/discover_gateway-original.json`、
`discover_gateway-decoded.json` 和 `gateway-coordination-errors.json`。
可提供给网关维护者的最小附件应仅包含该次发现、相关目录条目和错误响应，
不要携带连接令牌、完整会话数据或无关查询结果。
