# Structured tool batches

User approved the design on 2026-11-05: submit explicit independent calls,
let the host schedule them, and retain programs for observation processing.

## Contract

Extend `agent_tools_execute` with an alternative `calls` input. Each item has
a unique `id`, an admitted `tool`, and exact `arguments`. `calls` and
`program`/`tools` are mutually exclusive. Keep the existing program contract.
The host derives selected tools from the call list and uses the existing whole
batch preflight, capacity reservation, invocation, retention and observation refs.
No generated user program is needed. Return items in input order with their IDs.
Preflight failure invokes nothing. An individual execution failure does not discard
other results, imply rollback, or trigger a retry. Transport failure has unknown
upstream execution status; do not label it unexecuted.

Dependencies cross explicit stages: discover, submit known independent calls,
then inspect and submit dependent work. No JavaScript rewriting, business keyword
routing, mandatory first discovery action, additional planning LLM, or general DAG.
Prefer a contract-supported range or aggregate over unnecessary fragmented reads.

## Scheduling and scope

Use a cancellation-aware FIFO scheduler shared by all invocations of one
composition instance. This instance belongs to one native task session and one
frozen gateway catalog. Its maximum is the existing policy concurrency (4).
Retain each program's lower concurrency bound. Published read-only, non-destructive
tools may overlap. Unknown or mutating tools take an exclusive slot; model claims
and tool names cannot establish safety. Calls outside composition and separate
native processes are not covered by this session scheduler. Cross-task gateway
capacity is owned by the gateway/relay, not a process-local semaphore.

Cancellation removes queued entries and aborts active invocation signals. Keep
leases until invocation settles. No new retries, adaptive concurrency or cache
freshness changes. Preserve successful issued references and existing evidence rules.
Record index and queue/start/end timing in composition receipts without source data.

## Verification

## Real-task correction (2026-11-05)

The bounded two-call trial did not establish adoption for independent paginated
chains. Actual attempt1579b781 had114query calls: an early9-call group overlapped4,
but later59-call and31-call groups overlapped1. Individual page cursors depend on
prior responses; separate objects/windows do not necessarily depend on one another.

Add `tools.map(items,async mapper,{concurrency?})` in the isolated program worker.
It returns mapped values in input order, defaults to the validated program limit,
and preserves the host scheduler. Each mapper may await its own cursor chain.
On mapper failure, stop claiming new items, drain active mappers, then throw;
successful observation refs remain available in the normal completed-call receipt.
This does not rewrite arbitrary user JavaScript or certify semantic independence.

Return the host-resolved registered `tool` identity on all call/reuse outcomes.
Source payloads must not override it. Alias tools.saveContext/loadContext to the
existing globals, without weakening dataset/reference validation. tools.help()
publishes exact helper signatures, including the datasets array and literal issued
full_result object contract. No implicit full_result variable is introduced.

Real task also revealed a separate local gateway installation missing grid_database.
Owner received an authorized assistance notification and request IDs. Do not modify
their dirty checkout or runtime. Gateway internal errors are not all attributed to
one cause until owner checks the original exceptions.

Test direct batches, whole-list rejection, duplicate IDs, input ambiguity, ordered
results despite out-of-order completion, partial and transport failure, observation
reuse, a dependent second stage, shared program capacity, unknown/write exclusion,
and cancellation with no leaked slots. Run existing composition and direct consumer
checks. Rebuild local-dev with the canonical command and preserve its private state.
Validate a bounded real-model task; distinguish scheduler checks from model adoption.
No intranet access, cloud/demo changes, CI, push or merge.
