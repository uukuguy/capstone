# Understanding timeout and model selection repair

Fix source:`cc50f8d8766170341fd6f6b35d922e1237552459`,retained at
`refs/capstone/fixes/intent-backpressure-20261105`. It depends on snapshotc4466005
and changes nine task-owned implementation/test files. Dev remains6c55e6ee;
the normal index and unrelated mixed work were preserved. No CI or merge ran.

The fix is deployed to dky3-dev at http://192.168.72.66:5173/.
App sourcec4466005 and default gateway三区研发 remain unchanged. The .63 deployment,
main and cloud stages were not updated in this repair.

## Findings

Yesterday's .63 successes used the older6c55e6ee path. It did not run the new
independent model understanding gate before native execution. Thus the older
success and current failure are not a same-version network comparison.

The two三区 failed attempts were attempt_f7dd7a3f45478a4f and
attempt_c8f1a237a0606269. Both had Qwen recognition identity,although the second
submission froze dsv4. The recognizer was constructed from the startup default;
it did not read the frozen model selection for each attempt.

| Failure | Qwen-selected attempt | dsv4-selected attempt |
| --- | --- | --- |
| Actual understanding model | Qwen | Qwen |
| Thinking ledger rows | 1826 | 1818 |
| Mean characters per row | 4.9 | 4.8 |
| Maximum consumed-frame queue delay | 98.805s | 98.875s |
| Consumed-frame native receive span | 20.154s | 20.075s |
| Understanding outcome | 120s timeout | 120s timeout |

The receive span describes frames consumed before timeout,not proof that the
entire model response finished in20 seconds. The approximately99-second backlog
is direct evidence of local event-processing delay. Raw thinking callbacks
synchronously reached the durable event sink one fragment at a time. Each
thinking notification also passed the intent cancellation/lease checkpoint.

Execution has a related pressure source. The older Qwen benchmark wrote11258
thinking rows during about55 minutes; dsv4 wrote5909 process-text rows during
about24 minutes. The executor already had a text buffer,but its50ms interval
still allowed frequent writes. These counts show risk;they do not establish
what fraction of either complete business task was database time.

## Repair

Understanding and execution share the bounded TextDeltaBuffer. It retains text
up to4096 characters and coalesces arrivals over a1-second interval. The first
display fragment remains prompt; explicit phase/tool/decision/end boundaries
flush remaining text. Understanding heartbeats also flush due text. The public
event size stays within the existing4096-character contract. This is bounded
coalescing,not an unbounded pool or a new asynchronous browser transport.

Failed durable writes still raise. Pending text is retained after failure and
final cleanup does not silently retry the failed callback. Final answers,tool
results,artifacts and terminal events keep their existing durability/order rules.
The understanding deadline remains120 seconds.

Native recognizer creation now receives each attempt's frozen llm_selection.
The registered profile is validated before model resolution. An explicit
recognition-role override still has precedence. Engine identity records the
actual selected model; older frozen attempts are not silently rewritten.

## Verification

106 focused tests passed. Execution-side direct consumers:97 passed,1 skipped.
The final failure-buffer refinement passed five focused checks. Red tests first
reproduced per-fragment writes,failed-buffer loss,and ignored frozen selection.
Doctor,whitespace checks and canonical local rebuild passed. Final local
API/worker image585d98a9 matches the final stream_progress.py hash. Scoped local
cache maintenance completed.

The original saved instruction inputs were checked with real models using a
separate diagnostic PostgreSQL database,capstone_intent_probe_20261105. Each
notification used a fresh connection,transaction,row lock,event insert and
sequence update. No business executor or Authority calculation was invoked.

| Real understanding check | Qwen | dsv4 |
| --- | --- | --- |
| Selected/actual model | Qwen/Qwen | dsv4/dsv4 |
| Total seconds | 16.346 | 5.734 |
| Thinking writes | 10 | 0 |
| Thinking write seconds | 0.232 | 0 |
| Maximum queue delay seconds | 0.028158 | 0.001381 |
| Decision | valid,returned | valid,returned |

These are independent real responses,not a fixed performance guarantee. Both
produced executable decisions without required clarification. Full benchmark
execution was deliberately not started.

Two new public API task checks also completed and restored their saved snapshots:

- Qwen:threadthr_74c418717b55e9c60a18,attempt_853cd84d1614160f,about28.8s,7 thinking events.
- dsv4:threadthr_df74236e75797ccaf8aa,attempt_2694b9326a59fa84,about27.4s,0 thinking events.

The ledger confirms selection and engine identity match for both. The first
verification script required exact event-sequence equality after completion;
asynchronous title events advanced the sequence. Recovery verified monotonic
sequence and the saved answer instead,without rerunning that Qwen task.

## Deployment and recovery

| Role | Exact image SHA-256 |
| --- | --- |
| API and worker | `a6ee8475f549ea24fd69d3e528e8c4f463ce5c567d4dd4a99d21f3f219ac204b` |
| Native executor | `2d13aca8b5ec471e5a96ab0b1374208beee7fd7a8668b00ccfe56787aef5b8a7` |

Zero user attempts were running at activation. The database dump and previous
runtime.env are retained under private/backups/cc50f8d8. Old images,all volumes,
gateway configuration and user history remain. Both backend roles use the same
image;the source-bound catalog was rebaked and build-cache ownership restored.
The health endpoint and all affected containers are healthy.

Evidence:.capstone-agent/intent-backpressure-20261105/ and
runs/intent-backpressure-20261105/. Server understanding receipt:
/app/runs/operator-intent-check-20261105/receipt.json in the worker volume.
No acceptance tag or full benchmark acceptance is claimed. No browser visual
acceptance is claimed for the control graph because no browser is connected.

## Deferred design

Direct browser display with asynchronous batched durability was discussed.
It is not implemented here. A future design must define provisional display,
sequence/reconnect recovery,durable watermarks and mandatory flush barriers
before terminal success. Required answers,products and Authority evidence must
not be acknowledged as saved before their required persistence completes.
