# Tool execution lifecycle and bounded queues

Status: accepted in conversation on 2026-11-08. Implementation pending.

## Contract

All tool paths use neutral identities and lifecycle observations. No scheduling
decision depends on tool, provider or business names. The application selects
versioned capacity; execution owners enforce it. Default capacity is eight.
Independent calls enter a rolling queue, not a barrier between waves of eight.
Resource conflicts use published effects and owner-scoped resource identities;
unknown mutation safety must not become assumed read safety.

Record submission, queue admission, lease acquisition, execution start, execution
end and lease release. Cancellation request is distinct from confirmed termination.
Release capacity only after the underlying execution has stopped. Correlate task,
call, parent/batch and owner identities. Use monotonic durations within each owner;
wall timestamps locate events but do not prove cross-host clock agreement.
Records contain policy version, limit, scope and provenance, never credentials.
Reuse and skipped work are distinct from new source execution.

The Authority owns process start/exit observations. General host invocation events
cannot assert Authority execution. Failed or missing telemetry stays unknown.
Persist execution receipts through existing event/artifact paths, not a second ledger.

## Presentation

Connect all calls admitted by one model response as one batch. The connector means
batch membership, not simultaneous execution. Show batch item count separately
from queue capacity and observed peak. Single-call queue and execution durations
come from recorded owner nodes. Batch elapsed is submission to last completion;
never sum overlapping durations. Legacy records retain invocation duration and
report actual execution concurrency as unknown. Do not manufacture historical nodes.

## Acceptance

Sixteen independent synthetic calls reach eight active calls and immediately refill
on completion. Mixed entry paths sharing a budget cannot exceed it. Conflict,
failure, cancellation, queued cancellation and real process exit retain accounting.
Owner receipts survive refresh and match actual subprocess execution. UI groups
all sixteen and distinguishes recorded execution from legacy invocation timing.
Validate focused tests, then local rebuild, real model/tool products and restoration.
CI requires separate approval. Dev integration and graph alignment remain distinct
from local implementation and verification.
