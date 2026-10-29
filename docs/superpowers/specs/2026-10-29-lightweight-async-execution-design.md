# Lightweight asynchronous execution

User accepted the overall optimization on 2026-10-29. Implementation continues
without another approval gate. This record covers interactive first drafts,
not certified reports or automatic DR activation.

## Observed problem

The completed summer-study run used77 model requests and102 tool calls in384.959s.
Discovery/data used62 requests and181.647 model seconds.22 shell calls inspected
saved JSON; those calls are not all assumed unnecessary. Analysis/report used14
requests and141.999 model seconds. Files were visible only after finalization,
although a PPT was saved at69 and its primary manifest checked at76.

## Delivery and ownership

1. Capture completed tool writes asynchronously, coalescing overlapping capture
requests. Use the existing safe file collector, immutable bytes and host-owned
task/attempt checks. Publish admitted versions while execution is running.
Failure or cancellation does not remove earlier usable versions. A primary
manifest identifies a delivery candidate, not correctness or user acceptance.
2. Improve generic bounded tool previews so common field/row inspection can be
done without repeated whole-result reads. Preserve original source bytes and
identity. Existing `agent_tools_execute` batches independent gateway calls and
performs dependent transformations against exact observed values. No forced
business workflow or province-specific query logic is introduced.
3. Add an application-selected asynchronous LLM pool. Initial jobs are bounded
text analysis requests using explicit supplied observations and returned dependency
results. They share the selected protected model runtime, but not mutable model
conversation state. They have no tools, file or business-authority grants.
Gateway parallelism remains with the admitted composition tool. This is not DR.
4. The verified native report helper accepts `capstone-presentation/1` content
JSON through `capstone-report --spec slides.json --output slides.pptx`. It reuses
fixed layouts, continuation pages, bounded CSV tables and embedded PNG/JPEG;
facts and numerical calculations remain with the caller and registered sources.
The original HTML path stays compatible. Do not silently remove semantic checks
or assume every script correction wasteful.

## Pool contract

User clarified the runtime boundary: every business lightweight ModelRuntime
request enters a single instruction-owned request dispatcher. The parent does
not need to select a special tool to activate that dispatcher. Independent SDK
sessions share its concurrency limit; requests within one conversation depend
on the previous returned request. The optional text-analysis submission tools
declare additional independent contexts and dependencies; they are not the
only route into the pool. A pool does not invent decisions that depend on unseen
model output. Session title maintenance remains outside this business dispatcher.

Request publication: `capstone-model-request-pool/1`, concurrency2, lifetime
budget256 requests,120s actual execution deadline. The separate whole-task
budget is unchanged. Semantic analysis jobs do not charge time spent waiting
inside the request dispatcher against a second execution timer. An aborted
consumer is not transport cleanup: its semantic attempt stays reserved until
the actual provider stream and result drain. Known never-started cancellations
leave the queue immediately; explicit subsequent work may then proceed.

The process viewer keeps queued/dependency calls at the bottom. Actual start
moves a request into the execution trace and expands it; returns advance the
normal chain. Model timing excludes queue and dependency waiting. Actual event
intervals establish parallelism; parallel tools do not imply parallel LLM calls.
Same-chain retries remain separately observable and cannot overlap an uncertain
predecessor. Unknown ownership is displayed rather than guessed by timestamps.
Once the parent SDK prompt has settled and no executable frontier remains, the
host waits for real pool results instead of issuing model calls to poll status.
Bounded collection waits do not themselves classify a business failure.

Readable product versions in the active instruction open and update the right
pane without requiring a late primary manifest. Selecting a current-instruction
CSV does not stop following its later report. Historical selections and explicit
grid browsing retain priority; the next instruction resets follow state. Stable
host path plus digest suppresses same-byte terminal reclassification jumps.

Submit atomically validates unique IDs and dependency DAGs. Ready calls start
within the host concurrency limit. Submission returns immediately. The parent
can perform independent work, consume actual finished results, append work and
wait only when no independent work remains. Collection waits are bounded and
report current state rather than inventing a result or retrying.

States distinguish queued, waiting dependencies, running, cancelling and terminal
completed/failed/cancelled/blocked. Queue age is not execution time. A per-call
deadline begins on actual start; the parent task's absolute budget is separate.
A deadline requests cancellation, keeps the concurrency slot and prevents duplicate
attempt keys until cleanup is confirmed. An expected business gap is a returned
observation, not global failure. No automatic retry occurs. A caller must change
inputs or justify a new attempt after the old one is known terminal. Parent exit
and cancellation request child cancellation and drain cleanup before disposal.

Child usage/timing events are subordinate observations under the parent task;
they never imply DR activation or Authority evidence. Returned text is bounded,
and absent/failed output stays explicit. A final parent answer cannot silently
abandon unresolved jobs.

## Acceptance

Focused tests prove immutable v1/v2 publication before parent completion, retained
versions after failure, dependency ordering, bounded concurrency, cancellation
slot retention, deadline/queue distinction, no duplicate uncertain attempts and
model context isolation. Real local validation uses the canonical rebuild and
Vivaldi existing tab with new test conversations. Measure first usable artifact,
first primary candidate, final artifact, model count, uncached/cache-read tokens,
response sum and total time. Do not call a single stochastic speed difference
an accepted improvement. No sibling gateway changes or internal resource probes.
