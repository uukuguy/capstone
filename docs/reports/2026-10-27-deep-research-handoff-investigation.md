# Deep Research handoff investigation

Status: bounded calculation path verified. Large-report acceptance and the observed parent-request stall remain open.

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

## Transport-only live comparison and control reduction

Transport fix0fffe239 was rebuilt as imagec0226499f93e9c201581a23f201fb5238e993fc61172ff608ad759d72c6ffc48. Vivaldi trial `attempt_b00880d6422c9d88` in thread `thr_22c47d471965dc8d5c60` repeated the same question. Its two record calls took0.437s and0.689s. This supports reduced receipt delay, but is not a controlled total-latency result: model planning differed.

The same trial made repeated overview calls and two unavailable bash calls from the planner. Summary execution finished at12:54:27.376. The outstanding parent action started at12:54:11.690 and produced no further main-chain event before manual cancellation at12:57:35.892. The attempt is cancelled, not passed. The ledger alone does not prove a continuation-wakeup failure; do not conflate this stall with the confirmed event-drain defect.

6b08e322 removes model registration turns for validated advisory returns: settlement, record and diagnostic assessment use one atomic checkpoint. Declared dependents can start immediately; missing checks retain limited status, and foreign refs cannot be admitted.31eb8fb5 makes advisory overview requests wait for an actionable return, with cancellation, rather than repeatedly returning unchanged state.117 controller tests and14 pinned SDK cases pass. Canonical rebuild for31eb8fb5 passed with imagef44f5ca9c762aa78e9748f1da0557db8371c4b286ea8407337f49973f55445e6 and scoped cleanup. A new Vivaldi comparison is pending.

## Successful automatic-registration trial and discovery contract failure

Trial `attempt_bb279f4dfb2c31a1` / `thr_b9e0c2c19255f0a11ee8` completed13:12:19.160–13:13:28.304 (69.144s), compared with the earlier92s sample. The model paths differ; this is observational, not a controlled benchmark. Company B ended13:12:40.541 and its registered success appeared in event148 at13:12:40.767, without a planner record call. The comparison child ended13:13:07.510 and its registered success appeared in event226 at13:13:07.720. The final parent tail was20.794s. The visible answer and saved CSV contain the expected simulated metrics.

Company A still needed an explicit limited record after an association failure. A reducer rejection exposed missing admitted observation content; fe2dd666 now retains the actual submission receipt alongside supplied support, so unknown support does not erase a saved producer statement. It remains an unverified claim and cannot make an unsupported check pass.5d9b40c2 permits one advisory finish call with the model's whole-goal review, removing the need for a separate assessment model turn.5d8e92f2 distinguishes saved returns from registered results in the UI.133 runtime/return tests,14 SDK cases,180 App tests and TypeScript passed.

The combined build passed canonical readiness and scoped cleanup as imagea439c731df75a5955d3ccef5362a7ad03f1464866646342aa2f8bbb480a6a3ec. Its next Vivaldi trial `attempt_0fbba5e903defbb0` / `thr_8ec05c90864392f53980` failed13:25:41.449, before analysis completion. The private failure receipt records `observation_source_invalid`. Events86–90 identify a child call to `agent_tool_search`; the SDK exposed this granted discovery tool but the host observation allowlist omitted it. This is a contract defect, not evidence of combined-finish failure.

The host fix admits only the two application-granted discovery tools (`agent_tool_search`, `agent_tool_load`) for an exact bound child call. Existing task/source identity and receipt checks remain in place; unknown tool names and missing grants fail. A real-host regression reproduced both failures before the fix.87 host/progress tests pass in3.42s with localhost proxy bypass. Initial test execution had two localhost HTTP502 failures caused by inherited proxy settings; those passed with NO_PROXY. Rebuild and real trial for this discovery fix remain pending.

## Final bounded trial

7513fc34 passed canonical local rebuild and scoped cleanup, imagefc72fe1ab67bca182a82a3bf7eeab829821fcc80040daf68c7244379c3d1f74c. The same question was submitted in a new Vivaldi conversation after the browser restarted; existing window137137 and existing Capstone tab were reused.

Attempt `attempt_340b0038e1a828cb`, thread `thr_f5d01cc73278b64e9631`, completed13:57:00.180–13:57:43.606,43.426s. No failed tool calls, correction calls, polling calls or explicit node record/assessment calls occurred. Parent tools were plan and combined finish only; the visible process records9 total tool calls and4 parent model requests.

| Boundary | Time | Measured delay |
| --- | --- | --- |
| Company B child ends → registered success |13:57:16.115 →13:57:16.295|0.180s|
| Company A child ends → registered success |13:57:16.599 →13:57:16.774|0.175s|
| Last company child ends → summary starts |13:57:16.599 →13:57:16.983|0.384s|
| Summary child ends → registered success |13:57:33.050 →13:57:33.237|0.187s|
| Combined finish call |13:57:38.630–13:57:39.066|0.436s|
| Summary child ends → final answer |13:57:33.050 →13:57:43.606|10.556s|

Vivaldi shows the correct simulated calculation table and retained limitations. Each task shows registered status, and return submission timing is clearly named. Evidence is saved under root `outputs/research-control-20261027/` as screenshot and accessibility text. The prose heading “利润同向” is inaccurate although the following numeric comparison is correct; this is a non-blocking generated-text issue and was not made a new retry gate.

The observed total decreased92s →69s →43.426s across successful samples. These are different model trajectories, not a statistically controlled benchmark. This validates the bounded calculation path; the original large report and provider-stall behavior still need separate measurement. The older versioned policy prose should be aligned through a new publication in later policy work, even though this trial correctly used the updated runtime contracts.
