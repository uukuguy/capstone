# 给 data-gateway：新疆10月消纳率会话协查

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
