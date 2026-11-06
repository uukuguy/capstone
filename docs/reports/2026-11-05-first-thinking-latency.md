# First Thinking latency: local-dev trial

Candidate: `7387ef7f77c6d390fdb434cb3e4d6ff1951375e8`, recovery ref
`refs/capstone/fixes/first-thinking-latency-20261105`.
It includes private timing experiment13e60841, based on configuration255c8855
and runtime367374aa. The user subsequently authorized local-dev deployment.
Local-dev now runs7387; both intranet stages remain at their last confirmed367
with overlay255. No intranet probe or activation was performed while disconnected.
The local trial below does not accept intranet dsv4 first-Thinking performance.

## Evidence

The prior successful63 ordinary trial completed in8.0752s, with first preview
at6.1726s. Its event arrival times are coarse: several ledger events arrived
together. They must not be read as precise execution boundaries. Source timestamps
show about137ms between command persistence and worker start in that trial.

Restricted read-only measurements inside the63 worker found PostgreSQL connection
setup25–33ms and an in-connection SELECT1 about1.1–1.4ms. Seven preparation
connections can explain roughly0.2s, not all6.2s. A snapshot method was safely
rejected by the read-only transaction because it performs expiry/title maintenance;
it was not retried and no data were changed. No connection pool was introduced.

Actual capability property reads also trigger gateway publication HTTP requests.
One executor_binding used2 GETs and163.874ms; one no-model general_resources used
3 GETs and148.668ms. These are one-sample operation measurements, not universal
latency promises. They support removing duplicate publication reads.

## Implemented changes

The native host records fixed private timing phases: task start, resources ready,
launch request, actual Popen completion, first Provider request start, response
headers, first bytes, first nonempty Thinking/text and host task finish. The first
Provider exchange is kept separate from later calls. Request start is an application
boundary, not proof that a socket has sent bytes.

Records contain task identity, monotonic durations and bounded numeric sizes only.
They never enter the ledger, model context or App. They contain no URL, credentials,
prompt or output text. Default stderr emission was tested without logger setup;
diagnostic failures cannot fail execution. Closing is atomic and timer state is
removed on revoke, including workspace failures and cancellation.

Capability preparation now captures publication once within each binding and
passes that snapshot to the preparer. The real executor identity, resource
readiness and contracts are still checked. The next binding reads again. There
is no cross-task cache. Regression checks reduce2/3 reads to1 and prove refresh,
copy isolation, invalid-publication rejection and old-interface compatibility.

Timing/build checks:304 passed,35 skipped in27.46s. Binding/direct-consumer checks:
93 passed,22 skipped in5.00s. Both units passed independent review. Source commits
used temporary indexes and preserved the normal index and unrelated work. No CI.

## Earlier interrupted real trial and deployment state

Local diagnostic13e trial attempt_45f5a8064e6c932b, thread
thr_05c6701d3a3d64183443, ended interrupted. No Provider response headers were
recorded, so it provides no successful first-token latency. The subsequent network
unavailability report prevents valid end-to-end comparison. It is not a passing
performance test and is not automatically repeated.

The private timing did record request size:141962 wire bytes,53 tools,90157 bytes
of canonicalized tool schemas and49896 bytes of system messages. Those sizes are
facts about this failed request, not proof of the cause of normal6.2s latency.
Future profiling can examine avoidable full-schema loading while keeping all
authorized capability summaries visible. No such behavior change is accepted here.

At the offline checkpoint, both intranet stages remained runtime367374aa with overlay255c8855.13e images and
Apps were prepared remotely but never activated. Local runtime and fixed-source
App were restored to the verified367374aa using retained exact images; all roles
are healthy and share the expected backend image. Stage data were preserved and
the local ledger was backed up before restoration. No user task was cancelled.

The later local-only authorization and validation are recorded below. Resume
intranet validation with one bounded ordinary test after connectivity returns. Use candidate
7387, actual native timings, HTTP acknowledgment and browser observations; then
decide the next optimization from measured phases. Align allthree runtime sources
only after required validation. Do not treat prepared images as deployed.

Safe receipts: `.capstone-agent/first-thinking-20261105/` (ignored), including
database-readonly-summary.json, gateway-publication-readonly.json and
local-ordinary/native-timing-offline.json. Structural/deployment status is in
[the version register](../status/VERSION-CONTROL.md).

## Authorized local-dev deployment and real verification

Local API, all workers and native now use7387ef7f. The API/worker image is
sha256:7d271fe53f849b39fa42aa044b4d94ea6cd4ad3d4951d4bfc42a7f6308364fd2;
native is sha256:f15c3a80e6387c05f1a6bdaaffe5616c0d2e22cb97ac4b7cd049e7bce65c61c5.
The fixed-source Vite App reports full7387/local-dev, PID66644, same-origin proxy.
Canonical rebuild, App typecheck/build,1788-file source audit and readiness passed.
Fresh idle guards and protected environment/ledger backups preceded activation.
The private environment file is unchanged; no user task was cancelled.

Real attempt_2a6ef4a6b2183f1c, threadthr_0a7f4188890105fbcfd3, selected the
unchanged local default commercial-deepseek-flash and returned你好. Submit to
terminal took3.1359s; HTTP acknowledgment took0.1637s. There was one execution LLM,
zero understanding events and zero tool calls. Browser display and refresh replay
passed. This model supplied no Thinking: zero preview/durable Thinking events and
no first_thinking timing. No artificial Thinking was inserted.

| Native timing phase | Milliseconds since native task start |
| --- | ---: |
| Resources configured | 59.403 |
| Process launch requested | 64.612 |
| Process spawned | 70.391 |
| Provider request started | 556.693 |
| Response headers | 965.836 |
| First response bytes | 976.483 |
| First text | 1843.916 |
| Native task finished | 1969.532 |

Process-spawn to request-start took486.302ms; request-start to headers409.143ms;
request-start to first text1287.223ms. These are successful local commercial-model
measurements. They must not be compared directly with the prior intranet dsv4
6.1726s first-Thinking sample. Client terminal time also includes admission,
worker orchestration, persistence and event delivery outside the native span.

A separate read-only operation inside the running local worker confirmed one
publication GET for executor_binding (23.89ms GET,39.566ms operation). This proves
the deployed call-count change, not a cross-host latency improvement. It made no
model request and changed no task state.

Local receipts: `.capstone-agent/local-latency-20261105/`; runtime screenshot:
`output/playwright/local-latency-7387-answer.png` (ignored). Intranet deployment and
the target dsv4 Thinking latency remain pending connectivity.
