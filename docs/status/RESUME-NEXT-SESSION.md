# Live Session Checkpoint

> Updated: 2026-09-30 10:24 CST. **Session remains active — not a final handoff.**

## TL;DR

- `capstone-thread/1` persists immutable Turn + Attempt targets with strict
  model/revision/context fencing, normalized Harness events, leases, terminal
  commits, and SSE recovery.
- `capstone-agent` remains neutral about Domain Packs, Authorities, Pi, and
  DSH. Hosted API/CLI consume injected catalog/runtime assembly only; legacy
  Case App remains the default.
- `capstone-model-capability-spi` provides exact descriptors/selections,
  trusted sealed registry resolution, and closeable handles.
- `ModelCapabilityContextOwner` now prepares exact selected handles and
  contribution adapters atomically for a Run-owned immutable Context. Attempts
  borrow the Context; retries reuse it; drift, missing adapters, preparation
  failure, and cleanup failure fail closed.
- `PreparedApplicationPiRuntimeFactory` passes the prepared Context to an
  application-owned Pi session factory. Session stop does not release Run
  resources.
- `grid-agent` and `pypsa-agent` now expose explicit migration registration
  hooks for their existing complete Application Profiles. These hooks are not
  called by their default compatibility/application paths.

## Current implementation

- `packages/capstone-agent/src/capstone_agent/thread_protocol.py` — strict
  Thread snapshots, optional exact Profile selections, event pages, receipts.
- `packages/capstone-agent/src/capstone_agent/thread_service.py` — in-memory
  and Postgres stores, command admission, Attempt claims, leases, snapshots.
- `packages/capstone-agent/src/capstone_agent/model_capability.py` — Capstone
  model/family/default selection above the neutral SPI.
- `packages/capstone-agent/src/capstone_agent/model_capability_context.py` —
  Run-owned prepared Context, contribution bridge, rollback and cleanup.
- `packages/capstone-agent/src/capstone_agent/thread_application.py` —
  injected Authority/Pi assembly and paired prepared-session runtime factory.
- `packages/capstone-agent/src/capstone_agent/kernel_capability_preparation.py`
  — Kernel public `prepare_application` bridge, independent workspace,
  Authority model binding, revision gate, and endpoint cleanup.
- `packages/grid-agent/src/grid_agent/application/thread_capabilities.py` —
  explicit pandapower migration registration.
- `packages/pypsa-agent/src/pypsa_agent/thread_capabilities.py` — explicit
  PyPSA migration registration.

## Verification

- Capstone Python suite: 185 passed, 27 skipped.
- Model Capability SPI: 13 passed.
- Grid application tests: 43 passed; PyPSA tests: 17 passed.
- Focused Context/Thread application tests: 18 passed; bridge coverage then
  raised the Context tests to 13 focused cases.
- `python tools/check_package_boundaries.py` — passed.
- `git diff --check` — passed.
- Commits: `4d1d274` prepared Context lifecycle; `dcace18` legacy Profile
  capability registration hooks; `a11fbb0` paired prepared assembly;
  `f89e0f4` real Kernel/Authority preparation bridge.

## Immediate next action

1. Bind the prepared Kernel contribution into one explicit Pi session builder;
   it must consume the prepared tool catalog and Authority endpoint before Pi
   starts, and expose no raw objects to Thread/Web.
2. Add one opt-in end-to-end Thread worker composition root, keeping the
   default compatibility CLI and Web Case route unchanged until an end-to-end
   Thread run proves model, tool, result, and evidence admission.
3. Add public tool provenance and control-command execution only after this
   runtime path has a real selected Domain Pack and Authority.

## Recovery constraints

- Never map legacy sessions into Thread snapshots by inventing model revision,
  grid page, evidence, or prepared handles.
- Never expose native Pi/DSH events directly to Web/TUI clients.
- A contribution is process-local and never persisted; Thread stores exact
  Profile references only.
- Never claim an Attempt completed if terminal persistence failed; stale leases
  must be interrupted before a clean retry.
- Preserve unrelated unstaged `.gitignore` addition `.codegraph/`.
