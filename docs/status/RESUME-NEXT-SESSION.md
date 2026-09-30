# Live Session Checkpoint

> Updated: 2026-09-30 12:31 CST. **Session remains active — not a final handoff.**

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
  hooks for their existing complete Application Profiles. Both provide opt-in
  Thread composition roots over the shared prepared Kernel/Pi bridge in
  `capstone-agent`; the concrete Pi RPC builder writes a bounded runtime
  descriptor and closes the trace on session stop without starting Pi during
  assembly.

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
- `packages/capstone-agent/src/capstone_agent/kernel_pi_session.py` — shared
  prepared Kernel profile validation, Pi RPC runtime descriptor/session
  construction, and per-binding result/evidence admission aggregation.
- `packages/grid-agent/src/grid_agent/application/thread_capabilities.py` —
  explicit pandapower migration registration and opt-in Thread composition
  root over the shared bridge.
- `packages/pypsa-agent/src/pypsa_agent/thread_capabilities.py` — explicit
  PyPSA migration registration and opt-in Thread composition root over the
  shared bridge.
- `packages/capstone-agent/src/capstone_agent/harness.py` — bounded tool
  capability, binding, projector, result, and evidence provenance for UI
  diagnostics; professional/tool attempts now require an application-owned
  `AdmittedAttemptAnswer` before terminal completion.
- `cancel_live_attempt` is a durable control command: it targets the live
  Attempt, emits a request event, and becomes `attempt_cancelled` at a Harness
  heartbeat safe point. `retry_new_attempt` creates a fresh immutable Attempt
  in the predecessor's logical Turn from an interrupted, failed, or cancelled
  predecessor after model-context fencing; it never resumes or mutates the
  predecessor.
- Profile controls (`enable_profile`, `disable_profile`, and
  `replace_selection`) now validate against the exact application capability
  catalog, persist `selection_change_pending`, and activate the staged set at
  the next new Turn boundary. The active Model Context keeps its identity and
  advances `selection_revision`; the prepared Context owner keys resources by
  that revision.

## Verification

- Capstone Python suite: 195 passed, 27 skipped.
- Model Capability SPI: 13 passed.
- Grid Thread capability tests: 5 passed; PyPSA package tests: 19 passed,
  including a professional Attempt with admitted result/evidence refs;
  Harness/Thread application tests:
  17 passed; Capstone suite: 189 passed, 27 skipped. The full Grid suite
  reached 874 passed but
  exposed two unrelated
  failures in checked-in schema drift and a provider-backed offline answer.
- Focused Context/Thread application tests: 18 passed; bridge coverage then
  raised the Context tests to 13 focused cases.
- `python tools/check_package_boundaries.py` — passed.
- `git diff --check` — passed.
- Changed-file pyright — 0 errors.
- Cross-package Thread regression is green after the shared bridge move.
- Commits: `4d1d274` prepared Context lifecycle; `dcace18` legacy Profile
  capability registration hooks; `a11fbb0` paired prepared assembly;
  `f89e0f4` real Kernel/Authority preparation bridge; `afe9805` opt-in
  pandapower Thread Pi session builder seam; `d02c8fb` concrete Pi RPC
  descriptor/session builder; `45abb24` bounded Harness provenance;
  `afc932e` provider-free Thread worker fixture; `1eecfa1` application
  result/evidence admission gate; `0690078` per-binding admission ownership;
  `5d6d569` shared prepared Kernel/Pi assembly and explicit PyPSA Thread root;
  `aac8fbd` PyPSA Profile shared-worker fixture; `4209d8d` PyPSA admission
  lineage worker fixture.

## Immediate next action

1. Connect selection activation to the application preparation lifecycle:
   prepare the replacement profile contribution set before retiring the old
   revision, and expose preparation failure as a durable bounded control
   outcome while preserving the old effective selection.

## Recovery constraints

- Never map legacy sessions into Thread snapshots by inventing model revision,
  grid page, evidence, or prepared handles.
- Never expose native Pi/DSH events directly to Web/TUI clients.
- A contribution is process-local and never persisted; Thread stores exact
  Profile references only.
- Never claim an Attempt completed if terminal persistence failed; stale leases
  must be interrupted before a clean retry.
- Preserve unrelated unstaged `.gitignore` addition `.codegraph/`.
