# Recoverable long-task execution

Status: user-approved design, 2026-11-16; not implementation acceptance.
Owner: capstone-agent / capstone-harness. Destination: dev through scoped PRs.

## Outcome

A long task can cross instructions and process failures while retaining its
admitted inputs, saved products and actual execution history. Recovery starts
from a durable boundary with explicit authority. It must not silently repeat
an external effect, adopt late work from an expired owner, or declare success
because the task process disappeared.

The application remains the presentation and admission owner. Harness owns
neutral execution state and fencing. Domain Packs and registered Authorities
retain semantic actions, facts and evidence. No domain tool routing enters
the recovery mechanism.

## Current evidence and gaps

Dev 44abf3c5 includes PR120. CI43806396571 passed on macOS. Real worker loss
proved stale-lease rejection and retained-product recovery; the native task
continued after its parent worker died. Manual cancellation was test cleanup.
See [the measured report](../../reviews/2026-11-15-worker-loss-product-recovery.md).

`thread_worker.py` binds a live attempt guard. `native_conversation.py` derives
an execution owner from the lease. `general_pi_server.py` has task cancellation,
but parent process death removes the caller that would request it. Polling
task state is observation, not proof of continued execution authority.
Current historical files and delivery receipts support a new instruction;
they do not establish an automatic mid-tool checkpoint or exactly-once effects.

Further source inspection: `GeneralPiHost.submit` already writes an accepted
receipt before starting its execution thread. Re-admission checks the exact
request hash. After restart, a saved terminal result is reused; an accepted
request without a result returns an explicit unknown-outcome failure without
repeating work, retaining captured artifacts. Reuse this protection instead of
creating another admission ledger. Extend and verify its relationship to the
new execution generation and host recovery state. Existing regression coverage
includes `test_service_restart_replays_receipt_without_repeating_work` in
`test_general_pi_server.py`; this source inspection alone is not a fresh test
or real executor-restart acceptance.

Local baseline check, 2026-11-16: Python3.12 focused selection in
`test_general_pi_server.py` passed 13 cases in0.72seconds. It covers retained
terminal receipt replay without repeating work, terminal receipt persistence
failure, and usage/failure receipt restoration after host reconstruction.
These tests reconstruct the host with controlled runners; they do not prove
native process-tree termination, real container restart or automatic recovery.

## Options

1. Recommended: executor-local renewable execution authority, combined with
   durable host recovery records. The executor can stop work even when its
   caller disappears. Host recovery can explain and reconcile that stop.
2. Host-only orphan reconciliation: simpler, but an unavailable host or ledger
   leaves native work running. Useful as reconciliation, insufficient alone.
3. Live process/session reattachment: retains more transient state, but needs
   durable executor ownership, restart support and effect reconciliation first.
   It is not the first recovery contract.

## Execution authority

Bind each native task to one immutable attempt and execution generation.
The host obtains renewal authority only from a currently valid ledger lease.
Use a distinct protected executor capability; do not expose the ledger token
to native tools, model context, browser, logs or products.

The executor uses its own monotonic deadline. A validated renewal extends it;
status reads and event acknowledgements do not. A short transport outage can
recover before expiry; after expiry the generation cannot be revived. A new
attempt gets a new generation. Repeated admission of the same exact request
is idempotent; changed identity is rejected.

On expiry, reject new tool/child/model starts, request cancellation, and confirm
local process-tree termination within a configured grace period. Keep status
as stopping or unknown until cleanup is observed. Late events and products
cannot cross the host's existing attempt fence. Cancellation of a provider
request does not claim that remote computation or billing has stopped.
The implementation plan must derive renewal and stop bounds from the actual
ledger timing, with delayed/reordered renewals tested against those bounds.

## Durable recovery boundary

Keep immutable admitted input versions, accepted product descriptors, tool call
identities and terminal receipts. Recovery records distinguish completed,
interrupted and uncertain actions. Persist executor binding before relying on
remote admission; reconcile ambiguous admission by the same immutable identity.

After failure, seal captured products incomplete and retain their bytes. Start
a distinct attempt using the existing explicit continuation contract and fresh
grants. Restore accepted context from durable references under a bounded model
budget; do not replay the full raw trajectory into the model.

Automatically resume only work whose contract establishes safe retry or whose
completion is verified. For an uncertain external effect, first query its
owning Authority or surface the unresolved action. A generic harness must not
invent idempotence or rerun an arbitrary tool. Mid-tool memory restoration and
automatic repetition of all interrupted work are not implied by this design.

## Acceptance for the whole capability

- A multi-stage real task saves intermediate work, receives a later instruction,
  and completes using the actual preserved inputs/products and their versions.
- Worker SIGKILL expires authority and stops the native process tree within the
  measured bound; the old generation cannot renew, write or affect a new task.
- Short transport loss recovers within the valid window without duplicate work;
  expiry remains terminal even if delayed messages later arrive.
- API, worker and executor restarts each produce an honest recovered state;
  uncertain admission and lost completion receipts are reconciled explicitly.
- Cancellation reaches actual local cleanup, including children. New tasks do
  not reuse old authority. Recovery never adopts a late old result implicitly.
- Side-effect uncertainty is visible and never triggers an unproved replay.
- Refresh restores the existing conversation, execution state, intermediate
  products and continued attempt. Evidence is independently readable and hashed.
- Long context and large resources use bounded references and on-demand reads;
  no full-file payload or unbounded history is required for recovery.

Use deterministic memory/PostgreSQL/transport tests plus real isolated model
and worker-failure trials. Record stop latency, repeat work, exact input/output
identity and cleanup state. Offline fixtures alone cannot accept this goal.
CI requires separate per-run approval. Cloud/demo acceptance remains separate.

## Delivery

First establish execution ownership and bounded termination, including executor
restart and ambiguous admission behavior. Then establish durable recovery
selection and safe retry decisions. Finally exercise the complete multi-stage
task across failure and continuation. These are delivery boundaries within one
capability goal; none alone closes the user goal.
