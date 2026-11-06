# 给 data-gateway：查询超时协助

Capstone 最近一次业务探查里，`data_gateway_execute_data_query` 连续多次被网关自己停掉。请按下面的 request_id 核对执行计划和可收窄的索引键。Capstone 没有重放这些查询。

会话 `thr_90863d57149cbd24c4b1`。记录时间以库内 `occurred_at` 为准，约 18:22–18:23。相邻两次失败大约相隔 20 秒，所以这是网关的查询时间预算，不是 Capstone 的 HTTP 读取上限（当前为 1800 秒）。

## 请协助的失败

工具：`execute_data_query`。外层原文：

`Database query exceeded the time budget; inspect prepare_data_query and narrow indexed keys/time range；code=query_timeout`

已见到的 request_id：

- `a020ed9f9360462b9c43ea0924e35810`
- `27fc142e73554d8e9b5296a669888b53`
- `1c3d6e1fe3f34258a96ec92ef1c44c0b`
- `ed61e4ae75504aa99952eb5d041631f2`
- `4986657ebadc41b6aa733b3f14199e0e`
- `dec3674dc19e4d079c366d47b47e17c3`
- `3c839a8f97b544baa1d32a60ea708116`

触发它们的组合程序对 `SG_DATACENTER.SG_CON_PWRGRID_H1_MEA_2024`、`_2025`、`_2026` 各做一次无时间条件的聚合。其中 2024 年的请求体是：

```json
{"request":{"table":"SG_DATACENTER.SG_CON_PWRGRID_H1_MEA_2024","columns":[],"aggregates":[{"op":"count","field":"t.ID","as":"n"},{"op":"min","field":"t.CREATE_TIME","as":"mn"},{"op":"max","field":"t.CREATE_TIME","as":"mx"}],"limit":5}}
```

`limit: 5` 不能限制聚合前的扫描。请求没有时间范围，也没有其他索引键。

请按这些 request_id 回复：

1. 实际时间预算、生成的 SQL、执行计划，以及是在扫描中被取消，还是执行前就拒绝。
2. 这组年表里，做 count / min / max 时必须带上的索引列或时间谓词。请给出一个能在预算内完成的请求例子，不要只重复 “narrow indexed keys”。
3. 失败的 gap 里请直接带上可用的字段名、建议的时间切分，以及 `executed` 是 true 还是 false。调用方不应猜表结构，也不应原样重试。
4. 不把提高时间预算当作唯一办法。全表聚合会继续超时。

Capstone 侧目前只做了这些：相同参数连续资源失败 3 次后，不再发这一次完全相同的请求。模型改了年份或条件后仍会发出同类全表聚合。执行链没有改写 SQL，也没有另开一轮网关诊断。

## 不要和这件事混在一起

同一会话里还有 3 次 `Selected observation exceeds the read budget`，`maximum_bytes` 为 32768。这是 Capstone 组合程序读取已保存观测的输出上限，不是网关查询超时。

例子：

- `program-call:ca49e8db-c237-4f9c-adbd-4bcba09c6397:1`，指针 `/data`。恢复建议是 inspect，不需要再访问网关。
- `program-call:643d0f0f-4fd2-4eb1-af70-e09018a58cf3:1`，指针 `/data/columns`，建议页 `offset=0, limit=22`。恢复建议是按页 read，不需要再访问网关。

这两次不要求网关重放。若后续成功查询的结果体本身过大，默认返回一页并给出 `next_offset` 会减少调用方整份读取。这是另一项，不替代上面的超时核对。

## 网关回复，Capstone 已接入

`query_timeout` 的 gap 现在带 `scope`。`scope.executed` 为 true，语句已提交并在 20 秒扫描预算处取消。`scope.retry_same_request` 为 false。`scope.fields` 依次是 `ID`、`MEAS_TYPE`、`DATASOURCE_ID`、`CREATE_TIME`。必须先等值约束 `t.ID`，然后才可以等值约束 `MEAS_TYPE`、`DATASOURCE_ID`。`CREATE_TIME` 只能在这之后做一天或一条序列的左闭右开范围。只写时间范围不能走索引，`limit` 也不限制聚合前的扫描。时间预算没有提高。

上述 7 个 request_id 都是这条路径，外层约 20013–20017 毫秒。2024 年表计划是 `SCAN t USING COVERING INDEX idx_tool_t_7d77e85354ddab9ec75d3adef2d9860f`。2026 年这张表不在本机联调快照里。

下一次同类超时会带 `scope.suggested_request`。2024 年已核对的例子是 `t.ID = 0101110000`，`t.MEAS_TYPE = 11012001`，`t.DATASOURCE_ID = 0021110000`，`t.CREATE_TIME` 从 `2024-01-01 00:00:00.000000` 到 `2024-01-02 00:00:00.000000`，预算内完成，`n = 24`。同一组键去掉时间、聚合全年也在预算内，`n = 8784`。

Capstone 现在对 `scope.retry_same_request === false` 的请求不再发第二次完全相同的调用，并把 `scope.fields` 与 `scope.suggested_request` 留在返回里。模型提示改为按这些字段收窄，不要求提高时间预算。
