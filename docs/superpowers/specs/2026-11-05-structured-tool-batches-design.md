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

Test direct batches, whole-list rejection, duplicate IDs, input ambiguity, ordered
results despite out-of-order completion, partial and transport failure, observation
reuse, a dependent second stage, shared program capacity, unknown/write exclusion,
and cancellation with no leaked slots. Run existing composition and direct consumer
checks. Rebuild local-dev with the canonical command and preserve its private state.
Validate a bounded real-model task; distinguish scheduler checks from model adoption.
No intranet access, cloud/demo changes, CI, push or merge.
