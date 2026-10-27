# Deep Research handoff investigation

Status: active. No claim that all handoff latency is resolved.

## Real observation

Source: local PostgreSQL event ledger, attempt `attempt_d52ae75e269018d8`, thread `thr_5b5621f93b94fb538c66`. Times below are Asia/Shanghai on2026-10-27.

| Boundary | Time | Evidence |
| --- | --- | --- |
| Original continuation accepted after capacity fix |12:00:05.041|event3170|
| Final analysis child ended |12:03:05.995|event3709,n2_channel|
| Main record call |12:03:23.618–12:03:29.786|events3777–3781,6.168s|
| Next main record call |12:03:33.664–12:03:46.353|events3795–3800,12.689s|
| Revision rejected |12:04:09.103|event3918: result input missing declared producer dependency|
| Corrected revision |12:04:21.536–12:04:34.989|events3939–3944,13.453s|
| Report child started |12:04:35.186|event3946;89.191s after final analysis child|
| Long report model response |12:06:35.247|event4012,response_ms103782,output26685 tokens|
| Return rejected |12:07:51.162|event4105,invalid check,0.398ms tool execution|
| Return rejected again |12:08:00.912|event4110,invalid check,0.185ms tool execution|
| Return saved |12:08:09.681|event4115|
| Report child ended |12:08:12.953|child terminal event|
| Repair child started |12:08:59.496|n6_report_fix|
| Parent execution failed |12:09:48.589|event4462,native_continuation_no_progress|

The89.191s gap is control and model work, not numerical analysis. The104s response is report generation, not result transport. Invalid return checks add two model correction turns. The later no-progress failure is a separate defect; do not describe the whole delay as network waiting.

## Fixes and verification

-702d6c5a: a checkpoint pulse could resume continuation without actionable parent work. The wait now rechecks its predicate. A regression first reproduced premature wakeup;107 controller tests pass.
-64e33e75: advisory enterprise checks with malformed numbers/status/explanations become explicit limitations and missing checks remain not_run. Valid outputs stay available. Strict mode still rejects the same malformed return. Ownership, file path, result identity and version checks stay strict.
- Public task-return projection carries bounded, sanitized recorded limitations. UI shows handoff status, wall-clock interval and failure count outside folded task details, with recorded limitations available to inspect.
-123 JavaScript runtime tests,23 public-event tests,5 pinned-SDK structured-return cases,179 App tests and TypeScript passed. These tests are scoped, not full release acceptance.

## Remaining measurements

- Canonical local rebuild for64e33e75 passed, including matching API/worker image and scoped cache cleanup. The Vivaldi real-model trial completed; see below. The later event-drain fix still needs a rebuild and live measurement.
- Attribute the6–13s record/revise calls among protected reads, state serialization, CAS writes and public-event publication before changing persistence.
- Do not silently relax producer dependency or cross-version reference checks. Host derivation from admitted inputs may remove redundant declarations, but requires a separate reviewed change.
- Full report/repair usefulness and visual graph readability remain separate acceptance items.

## Small real-model trial and event backlog

Vivaldi submitted a new conversation with two independent simulated company calculations, followed by a short comparison. Thread `thr_5a8b701431950552a440`, attempt `attempt_10974869a39ee7f8` completed from12:39:50 to12:41:22 (92s). The visible answer has correct profits20/30 and30/20万元, margins20%/25% and20%/14.81%, and states that the data is simulated. No no-progress failure occurred.

The two initial children finished by12:40:09. One returned association could not be verified. The parent made two exact-reference inspection calls, then scheduled a text recalculation instead of using the supported values with a recorded limitation. Comparison finished at12:41:00; record, assess, finish and final response took another22s. This is an unresolved source of extra model turns, not evidence of a calculation bottleneck.

The HTTP executor previously processed the entire public event page before polling and acknowledging research requests. A deterministic regression simulates20 events with100ms durable publication each. Before the fix, the receipt is acknowledged only after event20. The fix services the protected research bridge between events once250ms has elapsed. It preserves event order, cursor checks, source validation and replay behavior. This proves a starvation path; its share of the live6–13s calls still requires measurement.

Scoped verification:137 transport/bridge tests passed,1 skipped,37.03s. The receipt-backlog test failed on the original code and passed after the change. Lost admission/bootstrap/acknowledgment response and terminal replay cases remain green.
