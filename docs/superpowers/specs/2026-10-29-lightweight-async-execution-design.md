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
4. Reuse report and calculation mechanisms where actual errors warrant changes.
Do not silently remove semantic checks or assume every script correction wasteful.

## Pool contract

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
