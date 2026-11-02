# General-chat latency diagnosis

The user reported 7.4 and 23.7 seconds in thread
`thr_254148d15ca3e60ded63`. These are the original attempts, not new model runs.

| Measurement | Three-sentence explanation | Meeting-note task |
| --- | ---: | ---: |
| Attempt | `attempt_c6149155a140ce81` | `attempt_35ec91ffe1e82adf` |
| Total | 7.398 s | 23.740 s |
| First text after start | 2.590 s | 6.552 s |
| First to last text event | 4.719 s | 17.080 s |
| Last text to completion | 0.089 s | 0.108 s |
| Tool execution interval union | none | 0.246 s |
| Text chunks | 141 | 484 |
| Median gap between chunks | 30.244 ms | 32.398 ms |

The second task read the note, listed its private workspace, and checked two
weekdays. Those tools do not explain most of the delay. Preparation and completion
are also small. Both attempts used general-chat and deepseek-flash; neither entered
the enterprise-research Pack.

## Confirmed framework cost

`delegated_runtime.py` emits a metadata-only `runtime_event` and an
`assistant_process_delta` for each text chunk. Each event is saved in a separate
PostgreSQL transaction. The native callback and its caller both run
`NodeControl.checkpoint`. The heartbeat callback calls `Harness._renew_lease`, which
renews the lease and queries cancellation. This adds two renewals and two
cancellation reads for each chunk, although `AttemptLeaseRenewal` also renews the
lease independently in the background.

A replay ran inside the actual local native-worker image against the same local
PostgreSQL service, using a unique isolated schema. It called the real service
methods and replayed the original chunk counts. It did not call a Provider or
modify the original threads. The temporary schema was removed in `finally`.

| Replay | 141 chunks | 484 chunks |
| --- | ---: | ---: |
| Two event writes per chunk only | 1.586 s | 5.499 s |
| Two writes plus both checkpoint paths | 4.140 s | 14.843 s |
| Event writes in checkpoint replay | 282 | 968 |
| Lease renewals in checkpoint replay | 282 | 968 |
| Cancellation reads in checkpoint replay | 282 | 968 |

For 484 chunks, measured method time was 5.751 s for event writes, 5.214 s for
renewals and 3.873 s for cancellation reads. This demonstrates material serial
framework overhead without any model generation. It is not an exact attribution
of the historical 23.740 seconds: this replay uses current code and isolated
tables, and original model generation could overlap event delivery. Do not subtract
the replay duration from the original total and label the remainder model time.
The original telemetry does not separate Provider generation from transport
backpressure.

## Next implementation boundary

Reduce duplicate delta metadata and coalesce very small text chunks while retaining
ordered recoverable text, tool outcomes, errors and final answers. Avoid renewing
the lease on every token; keep background renewal, lease-loss checks and prompt
user cancellation. Measure native generation, event queue blocking, persistence and
frontend receipt separately. Test cancellation, replay and terminal flushing before
claiming a speed improvement. Short research timeouts do not solve this problem.

The diagnosis and replay are complete. No latency optimization has been deployed.
The local image remains `18f11b7062e0`. Safe replay source and result are retained in
the root output directory `outputs/shared-step-acceptance/` as
`chat-ledger-timing.py` and `chat-ledger-timing.json`; the script reads its database
connection from the environment and contains no credential.

## Implementation candidate

The continuation implements the measured fix in the existing native execution
path. Background `AttemptLeaseRenewal` remains responsible for renewing the owned
lease. Dense heartbeat callbacks check local lease-loss state every time, and
query cancellation at most once per 100 ms while execution is active. The
initial explicit lease renewal and terminal cancellation checks remain.

The native host coalesces diagnostic text before assigning transport event IDs.
The first text is published immediately. Later text is published at size/time
thresholds on incoming chunks, before non-text events, and when the runner returns
or fails. A cancelled runner does not publish new buffered text. Event-page
acknowledgement is unchanged: the receiver still saves each assigned event before
acknowledging it. Coalescing in the receiving callback was rejected during review
because it could acknowledge text that had not been saved yet.

The single-goal/direct adapter saves the actual text event without a second
metadata-only event. Multi-goal handling, tool events, failure reasons, admitted
final answers and Authority boundaries keep their existing contracts. The new
buffer source is copied to the isolated image and included in its identity hash.

Initial focused regressions failed for the existing duplicate events and dense
heartbeat renewals. After the changes, 168 backend/worker/bridge checks passed,
with one PostgreSQL-configured variant skipped, and 109 executor/delegation/resource
checks passed. Two HTTP tests initially reached the local proxy and returned 502;
they passed with localhost excluded from proxy use. An added child-failure test
initially assumed the fake multi-goal fixture must produce an attempt failure;
the fixture permits a limited answer, so the check now verifies the actual failed
child receipt and complete ordered text instead. Real native-conversation failure
checks remain in the suite. Doctor and diff checks passed. Local rebuild and
actual UI timing, cancellation and refresh acceptance are pending.

## Local acceptance

Canonical rebuild passed with API and workers on image
`sha256:ae5797e27d5eae1c3d31b7a177d90b1757b26b619bdad42a096feeb60021a993`.
Log: `/tmp/capstone-stream-latency-rebuild.log`. No cloud/demo deployment or dev
merge occurred.

The actual App created a new general-chat thread
`thr_735831197558604a28d0`. It submitted the exact original first instruction,
then uploaded the same original meeting-note file through the file chooser and
submitted the exact original second instruction. Both attempts completed with
deepseek/deepseek-flash, the same Provider/model IDs as before.

| Measurement | First before | First after | Second before | Second after |
| --- | ---: | ---: | ---: | ---: |
| Total seconds | 7.398 | 4.255 | 23.740 | 10.584 |
| First text event seconds | 2.590 | 2.912 | 6.552 | 7.956 |
| Text stream window seconds | 4.719 | 1.262 | 17.080 | 2.519 |
| Text events | 141 | 23 | 484 | 44 |
| Duplicate text metadata events | 141 | 0 | 484 | 0 |
| Answer characters | 233 | 324 | 834 | 920 |

After attempts: `attempt_ed219dff8baf0054` and `attempt_fe194fd983a0df5b`.
The second task had four actual tool calls. Both saved text streams concatenate
exactly to their committed final answers, with no loss or duplicated text. Browser
refresh retained both answers and the source attachment. Output length and model
sampling differ; this is one real before/after pair, not a controlled estimate of
a stable percentage improvement. First-text waiting did not improve. The measured
improvement is in serial stream handling; further Provider/round-trip/first-text
work remains open.

An additional ordinary task was stopped from the actual UI while generating.
Attempt `attempt_4716f26acda4f9c8` reached `attempt_cancelled` 223.256 ms after
`attempt_cancel_requested`. Child cancellation was confirmed. The answer is the
explicit stop notice, not partial generated content. The current step has
`finish_reason=interrupted`; no successful finalization step was invented. Refresh
retained the cancelled state and prior answers. No active test task remains.

The updated no-Provider replay used the real Harness, text buffer and service
methods in an isolated PostgreSQL schema. For both original chunk counts it
completed in about 0.060 s with two text events, two lease renewals and three
cancellation reads. Ordered text and final answers were complete. This is a burst
replay without model pacing or HTTP transport, not a predicted user response time.
The first replay fixture reused a run ID between its own two threads and failed
the uniqueness constraint; distinct run IDs fixed that fixture. Temporary schemas
were removed. The script and measurements are retained with the earlier replay.

Final checks: 168 backend/worker/bridge tests passed (one PostgreSQL variant
skipped), 109 executor/delegation/resource tests passed, and 60 App replay/progress
tests passed. Doctor and diff checks passed. Root durable measurements are in
`outputs/shared-step-acceptance/chat-latency-comparison.json`,
`chat-ledger-optimized.py`, `chat-ledger-optimized.json` and `chat-stop-check.json`.
