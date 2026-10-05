# Thread model state repair

> Execute the user-authorized repair in this session. Use an independent
> code-review agent before delivery. Preserve unrelated work and user data.

**Goal:** Opening a registered grid model, the next instruction, and the Web
topology use the same admitted Thread model and revision.

**Architecture:** The application owns model selection and Thread identity.
Domain tools cannot silently change that identity. Registered authorities
provide model catalogs, topology, numerical results, and evidence. The Kernel
retains neutral contracts; no grid semantics move into it.

## Confirmed reproduction

Local Thread `thr_78b4cd7935dfc821176f` opens RTS in tool event 21, but its
Thread remains `ieee39`. The next flow turn opens IEEE in event 31. Normal
pandapower Thread composition has no network projection provider. The Web
model exporter includes only IEEE although the authority supports RTS.

## Tasks and acceptance

- [x] Align the application catalog with the registered authority. Keep exact
  source-backed revisions, bounded exports, and default IEEE. Check every
  exported model and startup duration; no caller-selected factories.
- [x] Route exact model-open phrases, including the Chinese model suffix,
  through explicit Thread selection and its activating instruction. Preserve
  the original request; show rejections and recover the draft. Both selector
  and conversation paths must activate the selected model before analysis.
- [x] Bind model-facing tools and each fresh prompt to the selected model.
  Reject foreign context/revision result or evidence admission before answer
  commit. Keep catalog informational queries and ordinary conversation valid.
- [x] Wire the normal pandapower topology provider to the exact prepared
  authority binding. Project focus from admitted endpoint evidence, never
  from prose, a fixture, or a hardcoded line. Keep current/historical identity
  and no-topology states explicit.
- [x] Audit pending switches, reopening, rollback, history, result focus,
  transport failure, reload and replay. Fix related confirmed defects with
  failing tests first. Preserve live cancellation and family ownership.
- [x] Verify real authority open/flow/endpoint behavior without Provider I/O,
  App interactions and replay in a headless browser, focused backend/App/JS
  tests and appropriate integration gates. Rebuild the actual local path
  with `make capstone-local-rebuild`. Do not deploy cloud or call Providers.
- [x] Resolve independent review findings; record actual checks and limits,
  commit only task-owned paths, and update the journal and recovery checkpoint.

## Main implementation paths

- `packages/grid-agent/src/grid_agent/thread_catalog_export.py` and its tests:
  application-selected authority catalog export.
- `packages/capstone-app/src/threadCatalog.ts`, `ThreadFixtureApp.tsx`,
  `threadProjectionStore.ts` and their tests: command routing and view state.
- `packages/grid-agent/src/grid_agent/hosted.py`,
  `application/thread_capabilities.py`, `thread_network_view.py` and their tests:
  prepared pandapower binding and operator topology projection.
- `packages/capstone-agent/src/capstone_agent/kernel_pi_session.py` and tests:
  neutral active-bound reference admission and per-Attempt model guidance.
- Domain tool registration/validation paths only if needed to enforce the
  application-selected tool constraints. Keep compatibility tools unchanged.

Evidence and review reports: ignored `runs/capstone-thread-model-fix/`.
Do not rewrite old events or repair user sessions by guessing model identity.
