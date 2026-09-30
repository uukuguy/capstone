# Live Session Checkpoint

> Updated: 2026-09-30 10:50 CST. **Session remains active — not a final handoff.**

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
  hooks for their existing complete Application Profiles. `grid-agent` also
  provides an opt-in Thread assembly and validates prepared Kernel tool paths
  and Authority endpoints before handing control to a Pi session builder. Its
  concrete Pi RPC builder writes a bounded runtime descriptor and closes the
  trace on session stop without starting Pi during assembly.

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
- `packages/capstone-agent/src/capstone_agent/harness.py` — bounded tool
  capability, binding, projector, result, and evidence provenance for UI
  diagnostics.

## Verification

- Capstone Python suite: 185 passed, 27 skipped.
- Model Capability SPI: 13 passed.
- Grid Thread capability tests: 5 passed; Harness tests: 6 passed; selected
  application tests: 7 passed. The full Grid suite reached 874 passed but
  exposed two unrelated
  failures in checked-in schema drift and a provider-backed offline answer.
- Focused Context/Thread application tests: 18 passed; bridge coverage then
  raised the Context tests to 13 focused cases.
- `python tools/check_package_boundaries.py` — passed.
- `git diff --check` — passed.
- Commits: `4d1d274` prepared Context lifecycle; `dcace18` legacy Profile
  capability registration hooks; `a11fbb0` paired prepared assembly;
  `f89e0f4` real Kernel/Authority preparation bridge; `afe9805` opt-in
  pandapower Thread Pi session builder seam; `d02c8fb` concrete Pi RPC
  descriptor/session builder; `45abb24` bounded Harness provenance;
  `afc932e` provider-free Thread worker fixture.

## Immediate next action

1. Add an application-owned Thread turn admission contract: tool results and
   evidence refs must be validated against the current prepared Authority
   context before `attempt_completed` is persisted.
2. Add the corresponding explicit PyPSA composition hook, keeping its model
   identifiers and authority binder application-owned.
3. Add public control-command execution only after result/evidence admission
   and current-run binding are enforced.

## Recovery constraints

- Never map legacy sessions into Thread snapshots by inventing model revision,
  grid page, evidence, or prepared handles.
- Never expose native Pi/DSH events directly to Web/TUI clients.
- A contribution is process-local and never persisted; Thread stores exact
  Profile references only.
- Never claim an Attempt completed if terminal persistence failed; stale leases
  must be interrupted before a clean retry.
- Preserve unrelated unstaged `.gitignore` addition `.codegraph/`.
