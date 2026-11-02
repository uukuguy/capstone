# Gateway argument diagnosis and execution labels

Observed thread: `thr_5bd702a75df2e3de832e`.
Attempt: `attempt_62f03f49855f2a37`. The user reported LLM 07.
Read-only event evidence is saved under `runs/gateway-arguments-20261031/`.

Events 123–126 show one composed call and its nested gateway call. The model sent
`scope: {object_ref: {...}}` to the published directory tool. Its schema accepts a
string or an object whose values are strings. The extra wrapper makes
`/scope/object_ref` an object, so the Capstone adapter rejected the arguments
before calling MCP. The two error rows describe this same failure. They are not
two gateway requests. No upstream request ID exists for that rejected call.

The model later supplied the flat reference and proceeded. No transport-name
mapping change or business-specific argument rewrite is needed. The framework
must not guess that an arbitrary object wrapper can be removed.

The adapter now returns bounded JSON Schema locations, rules, and types for
argument errors. It omits argument values. The relay and native wrapper preserve
these diagnostics and state that the rejected call was not executed. This uses
the admitted schema for any tool; no business name or route is encoded.

The App now uses the recorded purpose for the composed execution row and keeps
that label through completion or failure. This record already contains
`读取北京电网前5个变电站对象并查看返回字段`; the App previously hid it behind a generic
label. Older records with no purpose use `执行多步数据处理`.

Verification: 99 focused adapter/relay tests, 26 JavaScript gateway/composition
tests, and 145 App tests passed. TypeScript checks passed. Tests prove that a
nested type failure is rejected without an upstream call and that diagnostic
values exclude secret canaries. No CI or cloud deployment was started.

Canonical local rebuild passed. API and all workers use the same image
`4a9002eed974cdf6deec048e807a0263dc5004afa982ff3c389d5383027582d2`.
The scoped cleanup receipt is
`.capstone-agent/cache-maintenance-20261031-141041-53925.log`.
In the existing browser, the historical 131 ms row now reads
`读取北京电网前5个变电站对象并查看返回字段`. Its recorded failure remains visible;
displaying a clearer label does not rewrite the execution history.
