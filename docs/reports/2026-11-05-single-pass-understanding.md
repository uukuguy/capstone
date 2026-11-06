# Understanding latency measurement correction

The earlier16.346s Qwen and5.734s dsv4 figures measured a direct recognizer probe.
They did not measure the full session understanding stage. Presenting them as
representative session latency was incorrect. That probe also used different
saved inputs. Keep these measurements separate.

## Actual session timeline

The public event boundary is runtime_action started/response_completed with
response_intent理解当前指令. The user observations match the saved event times:

| Model | Attempt | Low RPC | Medium RPC | Public stage |
| --- | --- | --- | --- | --- |
| Qwen | attempt_dfe4e186900276bb | 27.186770s | 75.681403s | 103.719499s |
| dsv4 | attempt_6c5f76e1424e5dd7 | 6.613836s | 5.509077s | 13.047829s |

Maximum consumed-frame queue delay stayed below0.18s. The earlier approximately
99-second event-processing backlog is absent in these traces. The remaining
stage latency is mainly two serial model calls,not the previous write backlog.

The first pass stripped history and objects and used low reasoning. Its valid
business decision was discarded by _settled_without_business;the planner then
ran the complete request at medium reasoning. This made the direct one-call
probe an especially poor proxy for real UI latency.

## Single-pass repair

Source:`68bd1e07e6ce0a054128b2935222f27e3f339b63`,retained at
`refs/capstone/fixes/single-pass-intent-20261105`,on App/source snapshot22be9e5c.
It changes intent_runtime.py and its unscoped intent tests only.

The production planner now sends the complete frozen request once. History,
objects,capabilities,selection,skill and truncation metadata are retained.
Ordinary submissions use low reasoning. Explicit professional/deep/selected
resource controls retain medium reasoning. A business label no longer triggers
another recognition call. Saved valid decisions still replay without a new call.
The120-second deadline,output schema,permission checks and Authority boundaries
are unchanged. Obsolete brief-pass helpers were removed.

The regression first failed on duplicate recognition. Direct consumers passed
142 tests;the final parameterized unscoped suite passed20 tests,including both
explicit depth choices and exact equality with the full frozen request. Canonical
local rebuild59ef3de4,doctor and whitespace checks passed;scoped cleanup completed.

## Complete planner validation,not browser latency

A candidate container ran native_runtime_factory.plan_intent with the production
PostgresThreadService,event sink,freeze callbacks,cancellation checks and actual
model selection. Inputs used the user's saved instruction/history/catalog. Data
was isolated in capstone_intent_pipeline_20261105. The check stopped before any
business runtime/tool execution;it did not replay the complete calculation task.

| Model | Complete planning seconds | Recognizer invocations | Messages | Objects | Thinking writes |
| --- | --- | --- | --- | --- | --- |
| dsv4 | 23.165 | 1 low | 8 | 81 | 0 |
| Qwen | 38.140 | 1 low | 0 | 81 | 25 |

These are complete planner measurements,not UI wall times. They are independent
model responses under live load. dsv4 was slower here than the user's13s old-path
sample. The measurements prove one recognizer invocation and preserved context;they do
not establish a guaranteed speedup for either model. Real session acceptance
must use the same public event boundary,model,context and recorded load. Do not
substitute16.3/5.7 or these candidate values for a new user's session timing.

### Additional trace audit:recognition is not an HTTP model-request count

The Qwen single recognizer invocation actually contains two model responses.
The first tool arguments added an invalid top-level capability_refs string;
the next response removed that field. Its logged output totals2611+551 tokens,
with input9718 then12890. dsv4 returned one response,input11686/output440.
The one-pass fix removes application-level repeated recognition;it does not
guarantee a single provider completion when the SDK repairs invalid arguments.

In the older user-observed two-pass run,Qwen output totaled2354+6759=9113 tokens;
dsv4 totaled392+314=706. Output work is therefore a direct supported explanation
for much of the timing difference. These records do not prove a hardware speed
advantage,identical reasoning budgets or identical server scheduling.

Further optimization candidates are constrained structured generation,removal of
redundant context encoding and an explicitly verified understanding-role budget.
They are not deployed changes. An offline SDK probe can enable strict generation,
but transforms optional uses_selected_skill into boolean-or-null while the
application accepts boolean only. Align that contract before any service test;
do not relax validation or silently drop malformed fields. This audit made no
additional model calls or production configuration changes.

## Deployment

The user's attempt_b48693c4e846cb7e was running during preparation. Candidate
validation used a separate container without replacing the worker. Activation
waited until the main ledger had zero running attempts,then saved the database
dump and prior environment under private/backups/68bd1e07.

三区 now runs backend68bd1e07. API and worker both use
`sha256:f875656f924327d0c268a562488bdd3e89875b6a0d6792ce0eff3a5b8d884206`.
App22be9e5c/image992ea422 and native executorcc50f8d8/image2d13aca8 were retained.
All four roles and readiness passed. Default gateway三区研发 and all user data
remain. The .63/main/cloud stages were not changed. No CI,merge or acceptance
tag ran. The normal Git index and unrelated work remain untouched.

Evidence:.capstone-agent/intent-backpressure-20261105/single-pass-*.log and
single-pass-receipt.json;server worker volume
/app/runs/operator-single-pass-20261105/receipt.json. Browser visual verification
is unavailable;no frontend behavior changed in this follow-up.
