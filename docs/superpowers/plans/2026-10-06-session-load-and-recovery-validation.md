# User-use, session load and recovery validation

The user requests a demo that remains usable through repeated and concurrent
work. Two load cases alone do not meet this requirement. Choose and execute the
full user-use scope below without asking the user to design the checks.

## Execution order

1. Extend validation on the rebuilt local API, workers and App.
2. Fix any application defect locally, rebuild and verify before cloud changes.
3. Run remote integration validation on cloud-dev with matching source/runtime.
4. Demo promotion follows cloud-dev and human acceptance. Demo deployment
   acceptance exercises the deployed release; it does not repeat local work.

Demo source `c68f6e1` already passes deployment acceptance. Its four services,
real model query and both families' calculations, public cases, old reports and
evidence, refresh/drafts, small controls, mobile layout and idle cleanup pass.
Receipt: `runs/demo-promotion-20261006/acceptance.json`. Keep that demo unchanged
while the expanded local/cloud-dev validation runs.

## Required coverage

| Area | Scenario | Acceptance |
| --- | --- | --- |
| Entry and models | Root entry, New, model directory, model switch across both families | No token gate; selected model/family and diagram agree; history remains readable |
| Core work | Pandapower power flow, PyPSA dispatch plus AC check, registered multi-step cases | Current-run results and evidence pass lineage checks; projections, report and evidence read successfully |
| Repeated sessions | Twenty empty Threads, then ten distinct working Threads in sequence | Empty records reserve no worker; all work completes; memory/process counts do not rise without recovery |
| Concurrent work | Three simultaneous submissions across both families; inspect queueing and actual execution overlap | No lost/duplicated work or cross-Thread results; report latency, memory, CPU, contexts and queue depth |
| Capacity | Bounded increase after three, plus same-Thread overlapping commands and stream limits | Pressure is bounded or rejected clearly; active work survives; capacity returns after disconnect/completion |
| Long use | Reuse an owned Thread for follow-up work, switch/revisit models, read paginated earlier history | Correct model/revision; bounded initial history; paging preserves order and evidence; drafts survive refresh |
| Idempotency | Replay a write identity, conflicting replay, stale event cursor | One admitted Attempt; clear conflict; resync allows the next command |
| Cancellation and failure | Cancel queued/running owned work; exercise local interruption and timeout checks | Terminal state is clear; runtime and pinned resources release; subsequent work succeeds |
| Network and process recovery | Disconnect/reconnect the App; restart idle API/worker; interrupt only owned work locally | Durable history survives; streams recover; interrupted work is fenced; fresh work completes |
| Evidence isolation | Compare references between concurrent Threads and replay retained reports | No cross-run admission; prior report hashes unchanged; no user data deleted |
| Resource lifecycle | Warm baseline, active peaks, post-completion and post-idle samples with pages open | Separate retained contexts from baseline process memory; quantify residual growth and cleanup time |

## Measurement and release rules

Record source/image identity, role, timestamps, anonymous/file memory, CPU,
process counts, retained/active contexts, completion times and queue wait. Use
actual registered calculations for representative work; do not pass a fake
backend or count queued submissions as simultaneous execution. Keep Provider
credentials in existing protected state. Limit billed remote work to the
representative cases needed to verify local findings.

Start with three concurrent requests. Increase only when the measured resource
margin and completion behavior permit it. Record observed limits rather than
claiming an untested user capacity. Preserve existing databases, buckets, Threads
and reports. Any destructive fault injection stays local and targets only the
test-owned runtime. Report baseline memory as well as memory released after idle;
zero cached contexts does not mean zero server memory or zero cost.

Store bounded private receipts under `runs/session-use-validation-20261006/`.
Keep a result for each required row, including a specific remaining gap when a
scenario cannot be verified. The final summary must distinguish completed demo
deployment acceptance from the broader local/cloud-dev user-use acceptance.
