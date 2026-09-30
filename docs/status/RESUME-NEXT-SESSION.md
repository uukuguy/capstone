# Live Session Checkpoint

> Updated: 2026-10-01 06:56 CST. **Session remains active — not a final handoff.**

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
- `capstone_agent.hosted` now owns hosted API/Worker mode dispatch. The
  historical `grid-agent` and `pypsa-agent` packages are adapter layers only;
  source-level assertions reject direct hosted/CLI process roots and workers
  that bypass Capstone.
- `grid-agent` and `pypsa-agent` now expose explicit migration registration
  hooks for their existing complete Application Profiles. Both provide opt-in
  Thread composition roots over the shared prepared Kernel/Pi bridge in
  `capstone-agent`; the concrete Pi RPC builder writes a bounded runtime
  descriptor and closes the trace on session stop without starting Pi during
  assembly.

## Latest Web Thread checkpoint

- The legacy three-column App and `RunPanel` remain unchanged. The Thread route uses a separate light two-column shell: a copied model pane on the left and an assistant-ui conversation surface on the right, with compact populated-run rendering, answer-level activity, live Attempt timing, terminal state styling, and compact Thread diagnostics.
- `ThreadModelPane.tsx` copies the legacy hero image treatment and reuses the existing `NetworkView` renderer. Fixture mode uses a bounded IEEE-39 preview; live mode fetches the registered `gridctl` diagram (`39` buses / `46` branches) through `CapstoneClient.caseDiagram`.
- `CapstoneAssistantThread.tsx` uses `useExternalStoreRuntime` over the Capstone public event projection. It maps nested `command_accepted`, `attempt_started`, streaming text, and terminal answers into messages; assistant answers use controlled GFM Markdown, compact hover/focus action icons, assistant-ui style generation/stop states, and compact running/final duration labels. Protocol receipts stay in metadata, while long evidence identifiers and per-Attempt model context diagnostics stay behind explicit answer actions. Tool events are grouped into readable activity steps with binding/capability provenance and per-step terminal duration. Result cards are rendered only from current-run admitted references. Failed, cancelled, and interrupted Attempts receive explicit terminal copy and retry affordances. The Composer now uses one automatic-routing input: Enter sends, Shift+Enter inserts a newline, the input stays resizable, and mode tabs/shortcut-help text are absent.
- The Thread route preserves the original App header, compact model controls, registered topology, and viewport-filling two-column layout. The legacy App remains available unchanged.
- Commit `f57c182` injects the full pandapower Thread application into both hosted API and worker (`grid_agent.hosted_worker`). New Threads receive the registered default Profile and execute via the prepared Kernel/Pi Harness.
- Latest verification: App 123 tests; TypeScript/build, package boundaries and diff checks pass. Local API and worker were rebuilt from the current backend source and are healthy. Real browser validation captured empty, running, multi-turn, completed-table, interrupted, resync, historical-live, and 1200/900/600px states under `output/playwright/`; a running Thread showed `正在执行 8 个步骤 · 运行中 16.1s`, and completed answers retained `运行 12.3s` / `运行 17.9s`. The two-turn pandapower run confirms GFM table rendering, answer-owned admitted evidence, grouped tool provenance, independent message scrolling, compact diagnostics, and a visible Composer. The latest density pass removes the hidden action-bar gap, tightens the activity card, hides protocol receipt/context noise from the default flow, and keeps evidence collapsed until requested. The Composer follow-up was rebuilt and browser-checked in `thread-composer-single-input.png` / `thread-composer-enter-shift-enter.png`: mode tabs and shortcut text are gone, Enter sends, Shift+Enter retains a newline, the arrow action is compact, and native textarea resizing remains available. A StrictMode duplicate-effect guard also keeps historical live Attempts from false resync errors.
- A real new Thread (`thr_ad750d83909b8e382a01`) completed a model query with admitted evidence and a full answer. The former accepted-only Thread failed closed during preparation because it predates Profile registration; create a new Thread for user trial.
- The approved Web UI primary contract is `docs/superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md`. It makes typography density and runtime timing hard gates: assistant body 11px, headings remain controlled, body never above 11px except controlled headings, compact state hierarchy, Markdown/GFM, per-answer grouped tool activity, dynamic Attempt duration, visible Composer toolbar, and compact single-line baseline with retained resize.
- Answer-level retry now carries the owning Attempt instruction, so regenerating an older turn cannot accidentally submit the latest turn's text.
- Focused UI coverage now includes Result/Evidence cards, failure/cancel/interrupted terminal projections, failed tool provenance, stale model-label protection, running draft preservation, and compact Thread ID disclosure.

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
- Prepared Application Context failure now restores the prior effective
  selection, emits `selection_reverted`, and fails the Attempt with a bounded
  `capability_context_preparation_failed` result. A failed replacement cannot
  leave a new selection active without prepared resources.
- `switch_model` is a durable control command resolved through the application
  model catalog. It stages `pending_model_switch` and emits
  `model_context_change_pending`; the next normal Turn creates a new immutable
  ModelContext, resets its selection revision, and moves the active grid page
  to the selected model. Preparation failure restores the prior context and
  page with `model_context_reverted`; rollback is fenced to the activating
  Turn so a later Attempt cannot revert a successful switch.
- Selection controls are rejected while a model switch is pending. Browser
  `threadProtocol` and `ThreadProjectionStore` now parse/project pending model
  and selection changes, activation, and context rollback through the same
  typed read model.
- `ThreadCommandFactory` in `capstone-agent` and `buildThreadCommand` in the
  App now build the same strict `capstone-command/1` envelope. They validate
  identity and event cursors but do not submit commands or own cursor state.
  The fixture Web workspace uses the shared builder for ordinary, professional,
  control, profile, and model commands; `CapstoneThreadClient.switchModel` is
  available for a typed model-switch call.
- The Web grid pane exposes a model-context switch control. It renders the
  active model family/revision, disables switching while historical, running,
  or another context change is pending, and shows the accepted receipt. The
  page label and local viewed page follow a newly activated model when the
  user was on the current page; a historical page remains read-only.
- `thread_tui.py` adds the first Textual vertical slice: a two-column grid /
  conversation workspace, bounded model selector, ordinary/professional
  composer actions, public event log, and visible command receipts. It accepts
  only verified `ThreadSnapshot` + `EventPage` values and an injected submit
  callback; it does not create a second Thread state machine or connect to Pi.
  Textual is pinned as `>=8,<9` in the capstone-agent package and its locked
  transitive dependencies.
- The Web Thread workspace is now a live route, not only a fixture: the legacy
  App supports `?thread=new`; the route stores a session-only operator
  token, creates the default IEEE-39 Thread when the private API exposes its
  creator, loads the verified snapshot and event page, and consumes follow-mode
  SSE through the same `ThreadProjectionStore`. Existing `?thread=<id>` routes
  restore a Thread, while `?thread-fixture=...` remains provider-free UI
  regression coverage.
- Host SSE keeps the connection open with cursor polling and heartbeats,
  emits a typed `resync_required` frame when retention creates a cursor gap,
  and preserves the one-shot stream behavior for existing clients. The Web
  distinguishes transient reconnectable failures from verified resync failures.
- `capstone_agent.hosted` is the API/Worker process root used by the local and
  container entrypoint through a typed assembly factory. `grid-agent.hosted`
  remains the pandapower compatibility factory adapter; its worker delegates to
  `capstone_agent.hosted`, and package boundary checks enforce the same rule for
  PyPSA.

## Verification

- Capstone Python suite: 218 passed, 27 skipped.
- TUI/command/fixture focused tests: 12 passed.
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
- `python tools/check_package_boundaries.py` — passed, including hosted-root
  bypass assertions for grid-agent and pypsa-agent.
- `git diff --check` — passed.
- Changed Python-file pyright — 0 errors; App TypeScript check, production
  build, and 103 Vitest tests passed.
- Focused live Thread API coverage: 8 tests passed, including snapshot/event
  access, command idempotency, SSE, and cursor-gap recovery.
- The repository-wide `make check-types` still reports 23 pre-existing errors
  outside this change; the new TUI sources pass pyright with the capstone-agent
  environment (0 errors).
- Cross-package Thread regression is green after the shared bridge move.
- Full `make test` reached 838 passed and one pre-existing
  `grid-agent` checked-in schema drift failure; no failure came from the
  Thread/App changes.
- Commit: `d311cba` completed the live Web Thread workspace, HTTP/SSE route,
  new IEEE-39 entry, and reconnect/resync states. Prior commit: `5882f27`
  shared Thread command builders, Web model switch control, and current-page
  follow behavior. Earlier model switch commit: `0ab2799`
  (Turn-fenced context rollback and Web pending/activation projection).
  Earlier commits: `4d1d274` prepared Context lifecycle; `dcace18` legacy Profile
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

1. Start M2: move from the pandapower compatibility factory to a Capstone-owned
   composite model/authority catalog with real PyPSA model identities and
   family-specific Profile/runtime dispatch.
2. Keep using the real scripted pandapower instructions for deterministic
   Thread/App smoke; do not substitute guessed grid values.
3. Preserve the shared typed Thread client, receipt, cursor, and projection
   contracts while M2 changes only application assembly.

## Recovery constraints

- Never map legacy sessions into Thread snapshots by inventing model revision,
  grid page, evidence, or prepared handles.
- Never expose native Pi/DSH events directly to Web/TUI clients.
- A contribution is process-local and never persisted; Thread stores exact
  Profile references only.
- Never claim an Attempt completed if terminal persistence failed; stale leases
  must be interrupted before a clean retry.
- Preserve unrelated unstaged `.gitignore` addition `.codegraph/`.
- Keep the boundary checker green; a new grid/pypsa hosted or worker entrypoint
  must delegate through `capstone_agent.hosted` / `capstone_agent.worker`.
