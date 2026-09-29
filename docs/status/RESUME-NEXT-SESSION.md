# Live Session Checkpoint

> Updated: 2026-09-30 07:30 CST. Session remains active.

## TL;DR

- The strict `capstone-thread/1` client foundation is implemented: typed snapshot/event/receipt parsing, `CapstoneThreadClient`, `ThreadProjectionStore`, fixture runner, and four recovery-oriented fixtures.
- A fixture-backed Web two-column Thread workspace is available for UI validation, and `HttpThreadTransport` is ready for the future real server contract. The legacy Case App remains the default route and is untouched.
- The server-side HTTP/SSE projection, isolated Postgres Thread store, and injected model-pinned Thread creation route are implemented and tested; the neutral `AuthorityThreadModelCatalog` now validates Authority identity records without importing a Domain Pack.
- Thread command admission now rejects unsupported command kinds and empty/multiline message payloads before emitting `command_accepted`; actual Harness Attempt execution is still pending.

## Where things stand

- Branch: `main`, ahead of `origin/main` by 132 commits.
- Task work is committed through `99d3172`; the journal records Thread creation, HTTP/SSE projection, Postgres persistence, public-demo isolation, client creation, model-catalog normalization, and command admission.
- Working tree also contains the append-only journal and this active checkpoint; the unrelated user change in `.gitignore` (`.codegraph/`) remains unstaged and must be preserved.
- Verification completed:
  - `npm test --prefix packages/capstone-app` — 14 files, 86 tests passed.
  - `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests --ignore=packages/capstone-agent/tests/test_registered_workers.py -q` — 125 passed, 23 skipped.
  - `npm run check --prefix packages/capstone-app` — passed.
  - `npm run build --prefix packages/capstone-app` — passed.
  - `make doctor` — passed.
  - `git diff --check` — passed.
- Fixture route examples:
  - `/?thread-fixture=idle-ieee39`
  - `/?thread-fixture=historical-live-attempt`
  - `/?thread-fixture=resync-required`
  - `/?thread-fixture=interrupted-attempt`
- `create_host_app` accepts an explicit `ThreadService`, exposes `/api/v1/threads` creation plus snapshot/event/command/SSE routes, and hosted startup initializes the isolated Postgres Thread tables. Creation still requires an application-injected Authority-backed `ThreadModelCatalog`; `AuthorityThreadModelCatalog` is the neutral adapter, and no fake revision is used.
- Thread routes reject public demo credentials until a separately bounded registered-demo Thread scope is defined; the existing Case demo remains available only through its compatibility paths.
- `CapstoneThreadClient.create()` and `HttpThreadTransport.createThread()` now consume the same pinned snapshot contract as later loads; the fixture UI still remains fixture-backed until a live Web route is wired.
- Existing backend ledger records are not sufficient to fabricate the new Thread contract: they do not contain the required model-context/grid-page identity and Harness command semantics.

## What this session delivered

- Python Thread protocol and fixtures:
  - `packages/capstone-agent/src/capstone_agent/thread_protocol.py`
  - `packages/capstone-agent/tests/fixtures/thread-ui/`
  - `packages/capstone-agent/src/capstone_agent/thread_fixture_runner.py`
- Browser protocol and client boundary:
  - `packages/capstone-app/src/threadProtocol.ts`
  - `packages/capstone-app/src/threadClient.ts`
  - `packages/capstone-app/src/threadProjectionStore.ts`
- Fixture-backed Web prototype:
  - `packages/capstone-app/src/ThreadFixtureApp.tsx`
  - `packages/capstone-app/src/threadUiFixtures.ts`
  - isolated Thread workspace styles in `packages/capstone-app/src/styles.css`
  - query entry in `packages/capstone-app/src/App.tsx`
- Configurable HTTP transport:
  - `packages/capstone-app/src/threadHttpTransport.ts`
  - JSON snapshot/event-page/command transport with `Idempotency-Key`; protocol validation remains in the client layer.
- Interrupted-Attempt control correction:
  - historical pages expose return-to-current-model;
  - interrupted current attempts expose replay/retry controls;
  - current model page does not show the historical-only return action.
- Design and plan records remain under:
  - `docs/superpowers/specs/`
  - `docs/superpowers/plans/`
  - `design-system/capstone-agent/MASTER.md`

## Next steps (immediate, action-level)

1. Wire the hosted application’s selected Authority to `AuthorityThreadModelCatalog`, including the exact registered IEEE-39 revision and implementation family, without adding a forbidden capstone-agent → Domain Pack import.
2. Add authorization and integration tests for catalog selection, Thread creation, event-page cursors, SSE reconnect, and `resync_required` after compaction.
3. Implement Harness command execution beyond admission: route ordinary/professional turns, model switches, package selection, and immutable Attempt creation through the approved control boundary.
4. Keep the legacy Case App as the default until Thread creation, execution, and recovery tests pass. Then wire the Web workspace to `HttpThreadTransport` behind an explicit route/configuration.
5. Add the Textual Python TUI as another projection client. Reuse the public Thread snapshot/event/command semantics; do not duplicate business state in widgets.
6. Add the single `capstone` executable/TUI mode only after the shared server/client contract is stable. Preserve `capstone run` final-JSON and `--events` JSONL behavior separately from the frozen `grid-agent` compatibility envelope.

## Don't go down these paths again (ruled out)

- Do not map legacy `/api/v1/sessions` into `capstone-thread/1` by inventing missing model context, grid-page identity, or authority evidence.
- Do not connect the browser or TUI directly to Pi/DSH native runtime channels. They remain replaceable Harness runtime adapters.
- Do not make native runtime events the public contract; `capstone-harness` must normalize and enrich the bounded public event stream.
- Do not replace the legacy Case App before the real Thread route and recovery behavior are verified.
- Do not treat fixture success as production readiness; the current Web route is a deliberate prototype.
- Do not stage or revert the unrelated `.gitignore` `.codegraph/` change.

## Ready-to-paste commands / configs

```sh
npm test --prefix packages/capstone-app
npm run check --prefix packages/capstone-app
npm run build --prefix packages/capstone-app
make doctor
make capstone-app-dev

# Fixture prototype
open 'http://localhost:5173/?thread-fixture=idle-ieee39'

# Inspect state at the next session start
git status --short --branch
git log -8 --oneline
```
