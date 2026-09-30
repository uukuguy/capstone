# Live Session Checkpoint

> Updated: 2026-09-30 09:10 CST. **Session remains active — not a final handoff.**

## TL;DR

- `capstone-thread/1` now persists accepted commands as immutable `Turn + Attempt` targets.
- Harness runtime events are normalized before persistence; Pi and DSH remain replaceable runtime adapters.
- Attempt execution now has claim, lease renewal, bounded runtime-event append, terminal commit, stale-lease interruption, and a neutral worker polling seam.
- Accepted Attempts now carry an immutable full `ModelContextSnapshot`; Worker claim fails closed and interrupts if the persisted context is missing or differs from the active context.
- Hosted CLI now accepts an application-injected Thread catalog and runtime factory; without them production Thread execution remains disabled.
- `ThreadApplicationAssembly` now keeps the Authority model catalog and Pi runtime factory as one application-owned pairing; hosted API/CLI can consume the pair without importing Domain Packs.
- The independent `capstone-model-capability-spi` package now defines exact profile descriptors, immutable selections, trusted sealed registry resolution, and closeable context handles.
- `CapstoneModelCapabilityCatalog` now applies exact model default, implementation-family default, then empty selection; explicit selections only check exact registration and declared family compatibility.
- Thread model contexts now carry enabled Profile references (empty remains backward-readable); the Web parser projects the same optional selection shape.
- `ApplicationPiRuntimeFactory` now wraps the application-selected Pi session factory without importing Domain Packs into `capstone-agent`.
- Web-side `HttpThreadTransport` and `CapstoneThreadClient` now expose a strict SSE event stream with cursor de-duplication.
- `ThreadProjectionStore.consumeEvents()` now applies contiguous Attempt lifecycle events to the shared snapshot and freezes on gaps.
- The legacy Case App remains the default; no production Authority catalog or live Web Thread wiring has been enabled.

## Current implementation

- `packages/capstone-agent/src/capstone_agent/thread_protocol.py` — strict snapshot, event-page, and receipt contracts.
- `packages/capstone-agent/src/capstone_agent/thread_service.py` — InMemory/Postgres Thread stores, admission, Attempt lifecycle, leases, and expired Attempt interruption.
- `packages/capstone-agent/src/capstone_agent/thread_catalog.py` — injected Authority identity adapter; no Domain Pack imports.
- `packages/capstone-agent/src/capstone_agent/harness.py` — Pi/DSH runtime seam, bounded event normalization, Attempt runner, heartbeat lease renewal.
- `packages/capstone-agent/src/capstone_agent/thread_worker.py` — one-at-a-time Attempt tick and polling loop with injected runtime factory.
- `packages/capstone-app/src/threadHttpTransport.ts` and `threadProjectionStore.ts` — public client transport/projection, still not the default App route.

## Verification

- `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests --ignore=packages/capstone-agent/tests/test_registered_workers.py -q` — 143 passed, 25 skipped after stale-snapshot fencing coverage.
- `npm test --prefix packages/capstone-app` — 14 files, 91 tests passed; `npm run check` and production build passed.
- Latest Web projection check — 14 files, 92 tests passed; TypeScript check passed.
- Latest Python Thread check — 147 passed, 25 skipped; assembly-to-Worker-to-SSE and missing-authorization coverage passed.
- Latest Python Thread check — 149 passed, 27 skipped; context snapshot integrity coverage passed. Postgres integration remains environment-gated when `CAPSTONE_TEST_DATABASE_URL` is unset.
- Latest Python Capstone check — 153 passed, 27 skipped after Model Capability Catalog coverage; the SPI remains a local editable dependency with no runtime imports into the Kernel.
- Latest checks — Python 156 passed, 27 skipped; Web 93 tests passed, TypeScript check/build passed; selected Profile references round-trip through Thread and Web snapshots.
- `make test-model-capability-spi` — 13 passed; preparation rollback attempts every close and preserves cleanup errors.
- Package boundary checker tests — 61 passed; stdlib-only imports and zero runtime dependencies enforced for the SPI.
- SPI wheel/sdist build passed under `.capstone-agent/build/model-capability-spi`.
- Postgres Thread integration with `CAPSTONE_TEST_DATABASE_URL` — 3 passed.
- `python tools/check_package_boundaries.py` — passed.
- `git diff --check` — passed.
- Commits: `6339986` Attempt worker lifecycle; `db3295e` bounded runtime payloads; `9909484` hosted injection seam; `9c7662c` Pi runtime assembly; `322f8ae` typed SSE client; `e9d43ee` lifecycle projection; `6e4105b` SSE resync coverage; `28ad1b0` stale-snapshot fencing.

## Immediate next action

1. Add the trusted application profile adapter that registers the current pandapower/PyPSA Domain Pack assemblies with this catalog without moving those imports into neutral runtime modules.
2. Prepare selected profile handles at a Turn boundary and make the Attempt runtime factory consume that immutable prepared context.
3. Supply one real selected application adapter at the deployment composition root: resolve IEEE-39 from the registered Authority and create the prepared Pi session for each claimed Attempt.

## Recovery constraints

- Never map legacy sessions into Thread snapshots by inventing model revision, grid page, or evidence.
- Never expose native Pi/DSH events directly to Web/TUI clients.
- Never claim an Attempt completed if terminal persistence failed; stale leases must be interrupted before a clean retry.
- Preserve the unrelated unstaged `.gitignore` addition `.codegraph/`.
