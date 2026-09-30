# Live Session Checkpoint

> Updated: 2026-09-30 08:08 CST. **Session remains active — not a final handoff.**

## TL;DR

- `capstone-thread/1` now persists accepted commands as immutable `Turn + Attempt` targets.
- Harness runtime events are normalized before persistence; Pi and DSH remain replaceable runtime adapters.
- Attempt execution now has claim, lease renewal, runtime-event append, terminal commit, stale-lease interruption, and a neutral worker polling seam.
- The legacy Case App remains the default; no production Authority catalog or live Web Thread wiring has been enabled.

## Current implementation

- `packages/capstone-agent/src/capstone_agent/thread_protocol.py` — strict snapshot, event-page, and receipt contracts.
- `packages/capstone-agent/src/capstone_agent/thread_service.py` — InMemory/Postgres Thread stores, admission, Attempt lifecycle, leases, and expired Attempt interruption.
- `packages/capstone-agent/src/capstone_agent/thread_catalog.py` — injected Authority identity adapter; no Domain Pack imports.
- `packages/capstone-agent/src/capstone_agent/harness.py` — Pi/DSH runtime seam, bounded event normalization, Attempt runner, heartbeat lease renewal.
- `packages/capstone-agent/src/capstone_agent/thread_worker.py` — one-at-a-time Attempt tick and polling loop with injected runtime factory.
- `packages/capstone-app/src/threadHttpTransport.ts` and `threadProjectionStore.ts` — public client transport/projection, still not the default App route.

## Verification

- `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests --ignore=packages/capstone-agent/tests/test_registered_workers.py -q` — 138 passed, 24 skipped.
- Postgres Thread integration with `CAPSTONE_TEST_DATABASE_URL` — 3 passed.
- `python tools/check_package_boundaries.py` — passed.
- `git diff --check` — passed.
- Commit: `6339986 feat: execute durable thread attempts through harness workers`.

## Immediate next action

1. Add an application-owned runtime factory and worker startup path that selects the registered Authority/model context without importing Domain Packs into `capstone-agent`.
2. Add authorization and integration coverage for catalog-backed Thread creation, worker execution, SSE reconnect, and compaction resync.
3. Keep production Thread execution disabled until the exact Authority catalog and runtime factory are injected by the application.

## Recovery constraints

- Never map legacy sessions into Thread snapshots by inventing model revision, grid page, or evidence.
- Never expose native Pi/DSH events directly to Web/TUI clients.
- Never claim an Attempt completed if terminal persistence failed; stale leases must be interrupted before a clean retry.
- Preserve the unrelated unstaged `.gitignore` addition `.codegraph/`.
