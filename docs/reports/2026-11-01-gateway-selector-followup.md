# 网关契约选择器协查

入口：`http://127.0.0.1:18001/mcp`。
实例：`3db5bb96-2c27-4d97-8584-346bc4a18656`。

空会话 `thr_a78bd119eb081018e2d9`，执行
`attempt_f27ce0c18e08e7aa`，只要求读取实例、提供方和契约时间并保存 JSON。
模型调用 `describe_gateway_contract`，参数为：

```json
{"concept":"gateway contract check"}
```

网关原始返回为：

```json
{"content":[{"text":"Error executing tool describe_gateway_contract: Unknown registered concept","type":"text"}],"isError":true}
```

该返回没有 `request_id`，不能提供不存在的关联标识。Capstone 调用 ID 是
`call_01_l7X88qCibhsiPeztIt654600`。原始执行记录保存在
`runs/lightweight-direct-reference-20261101/records.json`。

这里首先是模型使用了未发现的自由文本。客户端不应把它猜成某个概念，也不应保存固定概念列表。
重新连接后，发现结果确实有 `data.concepts[].id`；但参数契约中的 `concept`
只有字符串类型，没有枚举，也没有说明合法值来自该路径。已发布的输入契约允许该字符串，
因此通用 schema 预检不能据此判定它无效。

请做两项小范围改进：

1. 在该参数说明中指出合法值来源；若列表适合放入契约，可由网关动态发布枚举，客户端现有通用预检即可使用。
2. 未知概念错误补充参数路径、拒绝值、合法值来源、真实执行状态和 request_id。
   不需要增加新语义注册系统，也不要替用户自动改写调用。

本轮重连已读初始化说明、发现、轻量检查及该工具契约。三处完整发布时间一致：
`2026-11-01T16:34:18.989104+08:00`。证据保存在
`runs/lightweight-normalized-reference-20261101/gateway/`。
该工具契约读取的 request_id 为 `fbb64999251944ec9ace92762d52ca89`，
它仅关联本轮读取，不能代替上面错误调用缺失的 request_id。

此说明已准备，未通过外部消息工具发送。未重放业务请求，也未修改历史冻结快照。
