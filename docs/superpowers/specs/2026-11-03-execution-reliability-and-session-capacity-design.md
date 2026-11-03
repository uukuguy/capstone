# Execution reliability and session capacity

Status: user approved on 2026-11-03. Implementation and acceptance are tracked in
the [plan](../plans/2026-11-03-execution-reliability-and-session-capacity.md).

## Goal and evidence

Deliver two bounded improvements: reliable use of the existing observation and
reporting path, and concurrent independent native sessions with truthful waiting
state. Preserve the existing conversation UI and source/evidence boundaries.

The November 2 summer-chain audit found long-window expansion after narrow
success, expensive observation exploration, null-value failures and generated
script errors. It did not find identical parameters repeated upstream. A remote
gateway failure is not proof of an application defect.

Existing mechanisms already include tools.plan/batch, exact successful readonly
observation reuse, bounded inspect/read, tools.table validation, and capstone-report
--check-only. Reuse and test these mechanisms before introducing new ones.
See [observation pipeline](../../reports/2026-11-01-unified-observation-pipeline.md)
and [audit](../../reports/2026-11-02-intranet-summer-chain-audit.md).

The native entrypoint starts one serve_thread_attempts loop. That loop calls
run_pending_attempt synchronously, so one running attempt blocks the next claim.
The App already contains a queued label; accepted/started state propagation and
snapshot restoration require verification before changing presentation.

## Options and selected proposal

1. Extend the existing worker with bounded independent slots, retain the ledger
   as the only claim authority, and complete the existing processing path. This
   offers local reproducibility and a small deployment change. Recommended.
2. Run additional worker containers. This preserves the serial loop but makes
   capacity and shutdown depend on operator replica configuration. It still needs
   the same claim, isolation and UI verification.
3. Add a scheduling service or global result cache. This introduces new state,
   identity and recovery contracts without addressing the immediate defects.

Use option 1. Do not change per-task gateway concurrency to address long-window
timeouts. Model request pools remain optional and disabled by default.

## Package A: reliable observation-to-product execution

- Reproduce failures with bounded source fixtures at the actual adapter/native
  boundary. Verify the current code before selecting a patch.
- Validate the model-selected batch against current grants, frozen schemas,
  capacity and issued references before execution. Return usable diagnostics and
  existing observations. Code must not choose representative business objects,
  infer statistical coverage, or impose an initialization/first-tool sequence.
- Preserve exact successful readonly reuse, explicit refresh, failed-refresh
  invalidation, source identity and scope. Do not add cross-session caching or
  silently combine different windows. Polling actions must remain live.
- Make retained completed-call references and bounded inspect/read recovery
  usable after a processing or read-budget failure. Fix missing wiring or
  misleading recovery instructions only where reproduction proves a defect.
- Use existing table validation for missing fields, nullability and malformed
  values. Preserve source bytes and gaps; do not silently drop or coerce rows.
- Exercise report check-only with malformed tables, missing sources and layout
  failures. Correct its recovery receipt if needed. Models select appropriate
  validation from advertised capabilities; arbitrary scripts are not claimed
  validated by a report-spec check. Do not add a mandatory extra model review.
- Keep upstream timeout/service errors distinguishable from local processing
  failures. Do not automatically retry, enlarge budgets, or rewrite the whole task.

Acceptance: selected batch rejection makes zero upstream calls; processing repair
uses retained observations without new reads; explicit refresh and polling remain
correct; invalid data produces bounded diagnostics without a false product;
corrected data produces a downloadable product with exact source references.
Measure upstream calls, model rounds, first useful product time and total time.
Only comparable real tasks support a performance-improvement claim.

## Package B: bounded sessions and truthful waiting

- Add a validated positive native-worker slot setting. Keep the library default
  at 1 for compatibility; configure the local development candidate to 2 for
  acceptance. Document how an operator selects capacity for the later deployment.
- Claim at most one attempt per free slot, using the existing PostgreSQL lease
  and fencing rules. Do not claim work into an unbounded in-memory executor queue.
  Preserve accepted ordering, implementation-family selection and same-thread
  single-active-attempt guarantees across worker processes.
- Each attempt has separate lease renewal, cancellation, workspace, observations,
  resources and products. Review shared runtime-factory caches and cleanup locks
  before parallel use. Do not close a factory while any attempt still uses it.
- Release a slot only after its attempt runtime and subprocess cleanup completes.
  A failed/cancelled attempt must not terminate unrelated work. Stop taking new
  work on shutdown, and fence or finish active work through existing contracts.
- Project accepted and unleased work as waiting, and actual start as execution.
  Use durable events/snapshots for refresh recovery. Do not label waiting as model
  generation, invent a queue rank/ETA, or expose other users' task details.
- Reuse the existing composer, message and process components. Waiting remains
  cancellable, and cancellation must prevent later execution of that attempt.

Acceptance: with two slots and three independent sessions, two start before either
finishes and the third waits without a lease. Finish/cancel one and the next can
start after cleanup. A second worker cannot duplicate a claim; same-thread work
does not overlap. Cancelling a queued or running task leaves other tasks intact.
Refresh retains the correct waiting/running/terminal state and each task's files.

## Delivery and verification

Work from dev f7d40163 in an isolated implementation branch. Preserve the six
post-merge control snapshots and unrelated summer-audit file in the root checkout.
Deliver Package A and Package B as separate reviewable commits with focused tests.
Update the canonical execution worklist and version register, not a new ledger.

Run focused Python/Node/App checks, real PostgreSQL claim tests, and the canonical
local rebuild before real App trials. Use existing authorized model access for
two independent native tasks plus one waiting task, continuation and refresh.
Record exact source/images, timings, products and cleanup receipts. A missing
Provider or gateway is an explicit verification gap, not a passed test.

Research server is disconnected: no probes, remote deployment or remote business
acceptance. Do not update main, cloud-dev or demo. CI needs its own explicit
approval after a concrete candidate is ready; this design review does not grant CI.

## Deferred

Distributed global fairness/quotas, provider-wide concurrency, queue ETA, automatic
query-window subdivision, new research UI and enterprise research-mode delivery
are separate work. Do not promise these through the two-slot worker change.
