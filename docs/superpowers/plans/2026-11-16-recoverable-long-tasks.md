# Recoverable Long Tasks Implementation Plan

Goal: establish the complete recoverable long-task capability in the accepted
[design](../specs/2026-11-16-recoverable-long-task-design.md).
User approved the design on2026-11-16. Owner capstone-agent/capstone-harness;
branch feat/recoverable-long-tasks-20261116, destination dev. Implementation
uses the existing initialized historical-input-receipts worktree. Preserve
postmerge root control drafts. No CI approval is carried forward.

Architecture: retain the existing attempt ledger and native accepted receipts.
Introduce executor-local execution authority with an immutable generation and
monotonic expiry. Connect transport renewal to the live host attempt guard.
Keep recovery state and domain side effects explicit; no generic blind replay.

## Delivery and verification

- [ ] Execution authority and bounded native termination. Add a small
  `native_execution_authority.py` state machine, with deterministic fake-clock
  tests for expiry, generation mismatch, replay, delayed renewal and no revival.
  Extend `general_pi_server.py` and `pi_delegation.py` with protected admission
  and renewal. Reuse runner cancellation/process-tree cleanup. Check actual
  cleanup before terminal status. Test request identity and accepted receipt
  restoration. Renew only under `NodeControl.checkpoint` and the host ledger
  guard; reads never renew. Derive timing bounds from the existing30-second
  worker lease and measured transport/cleanup bounds, without granting stale
  host work indefinite executor authority.
- [ ] Durable recovery and safe continuation. Reuse accepted task receipt,
  immutable product grants, interrupted seals and historical delivery receipts.
  Test ambiguous submission, missing completion, executor/API/worker restart,
  new generation isolation and uncertain-effect reporting. Persist any missing
  binding before remote admission. Do not recreate a second task ledger.
- [ ] Whole-capability real acceptance. Canonical rebuild; isolated model task
  with saved intermediate product, worker SIGKILL, bounded automatic cleanup,
  exact historical read, new instruction, completed report and refresh.
  Exercise transient outage, cancellation and restart separately. Record
  observed cleanup, latency, bytes, version identity and repeat work. Update
  capability acceptance against every design criterion; incomplete criteria
  keep the user goal active. Focused local checks first; each CI needs approval.

Each delivery uses failing regression tests before implementation, focused
consumer tests afterward, an explicit owned-path commit and journal checkpoint.
Do not claim end-to-end acceptance from the isolated state-machine tests.
