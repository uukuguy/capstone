# Thread session management and recovery implementation plan

> **For agentic workers:** Use subagent-driven-development to implement and review each task. The user explicitly requested that discovered problems be fixed.

**Goal:** Let users create and manage Threads from the App, recover connections and drafts, and read long conversations without unbounded initial loading.

**Architecture:** Capstone owns durable Thread metadata, history pagination and execution leases. The App owns navigation, bounded message presentation and browser-session drafts. A Thread is a durable record, not a reserved worker; runtime execution remains per Attempt.

**Tech Stack:** Existing FastAPI, PostgreSQL, React, assistant-ui, TypeScript and Vitest. No new service or dependency.

## Global constraints

- Preserve the four ownership layers and all existing data, artifacts and user edits.
- No new Thread ownership in grid-agent or pypsa-agent.
- Keep compatibility stdout and current-run evidence admission unchanged.
- Existing operator authentication scopes private Threads. Do not claim individual user isolation without an account model.
- Never delete event history to shorten the chat view. Archive is reversible metadata, not deletion or cancellation.
- A running Attempt or active Case blocks archiving. Explicit retry remains required for interrupted execution.
- Do not share credentials between local, cloud-dev and demo. No real Provider request without separate authorization.
- Implement in the current checkout with task-owned staging; JOURNAL and RESUME contain user edits and stay unstaged.
- Test regressions before code changes. Rebuild local API/worker/App before remote verification. Demo remains gated by human acceptance.

### Task 1: Private Thread catalog, archival metadata and reverse history pages

**Ownership:** `packages/capstone-agent/src/capstone_agent/thread_service.py`, `host_api.py`, related backend tests; a small neutral helper module is allowed.

**Interfaces:**

- `GET /api/v1/threads?before=<thread_id>&limit=20&archived=false` returns `{schema:"capstone-thread-list/1", threads:[{thread_id,model_id,implementation_family,created_at,archived,last_event_seq}], next_before_thread_id, has_more}`. Sort by creation time descending, then ID descending; an opaque ID cursor resolves its immutable creation time. Validate limit in 1..50; public demo access is denied.
- `POST /api/v1/threads/{thread_id}/archive` receives `{archived:boolean}` and returns the same bounded descriptor. A running/accepted Attempt or active Case returns 409. New commands to an archived Thread are rejected, while history remains readable. Metadata is stored separately from domain application_state.
- `GET /api/v1/threads/{thread_id}/history?before=<event_seq>&limit=128` returns `{schema:"capstone-thread-history/1",thread_id,before_event_seq,next_before_event_seq,has_more,events:[...]}`. Events use existing public EventEnvelope contracts, ascending order within each reverse page. Omitted before means snapshot.last_event_seq+1. Validate bounded limits, cursor and byte budget, omit diagnostics, and preserve ledger contents. Pages contain strictly earlier events, no gaps among eligible public events, and make cursor progress. Partial Attempts can span pages and are completed when earlier pages load.
- Both PostgreSQL and the in-memory service used by tests support these operations. Schema migration is additive/idempotent. No fake archived status for a backend that cannot persist it.

- [ ] Add service/API regressions for private access, cursor paging, byte bounds, reversible archive, active-work rejection and preserved history. Run them and confirm missing behavior fails.
- [ ] Implement the contracts using bounded SQL queries and exact metadata; include same-stage PostgreSQL coverage where the existing test fixture permits it.
- [ ] Run focused backend tests and self-review; commit only owned source/tests. Report exact contract examples and red/green evidence in the ignored task report.
- [ ] Independent task review; resolve correctness and contract findings before the next task.

### Task 2: User-visible Thread navigation and automatic recovery

**Ownership:** App `ThreadLiveEntry.tsx`, `ThreadFixtureApp.tsx`, new `ThreadSessionMenu.tsx`, `threadSessionState.ts`, transport/client types, styles and related tests. Task 3 subsequently owns projection/history files.

**Interfaces:** Use Task 1 list/archive routes. Existing snapshot/event/command contracts stay unchanged.

- [ ] Add failing tests for a visible “新建对话” button, recent/archived Thread list, switching via browser history, reversible archive and private-access failures. Creation must occur once under StrictMode.
- [ ] Add failing tests for automatic recovery after thrown SSE errors, clean EOF and temporary 502/503, cancellation on unmount/Thread switch, no retry storm on 401/403, and exact unresolved command recovery without duplicate execution.
- [ ] Add failing tests for per-Thread draft restoration across reload, separation on Thread switch, rejected/lost sends retaining drafts, accepted receipts clearing only the submitted matching draft, unavailable sessionStorage fallback, and stored data containing no tokens/evidence/raw authority data.
- [ ] Implement a compact visible session menu with new/switch/archive/restore actions. Use same-origin history navigation without forcing a full reload. Never silently cancel a live Attempt when creating/switching a Thread.
- [ ] Implement capped exponential connection retry, verified snapshot/cursor catch-up and cancellation. Do not auto-retry a failed/interrupted AI instruction. Persist bounded drafts and exact unresolved command envelopes in browser sessionStorage scoped by API origin, Thread and authentication session; store secrets separately as they already are. Do not force a browser reload during draft entry.
- [ ] Run focused App tests, typecheck and self-review; commit owned files and report red/green evidence.
- [ ] Independent task review and correction.

### Task 3: Bounded chat history and end-to-end acceptance

**Ownership:** App `threadProjectionStore.ts`, `threadProtocol.ts`, `threadHttpTransport.ts`, `threadClient.ts`, `ThreadFixtureApp.tsx`, `CapstoneAssistantThread.tsx`, related tests and documentation.

- [ ] Add failing tests for initial latest history page, loading older pages with stable scroll, merging partial Attempt messages, cursor deduplication with live SSE and reconnect, and retaining missing-receipt reconciliation even when its events fall outside the loaded page.
- [ ] Implement optional transport history support: real HTTP uses reverse history pages, existing fixture transports can retain their current forward replay behavior. Bound the initial history load; expose “加载更早消息”, with a maximum rendered message window and reversible navigation to older windows. Keep full durable history and current-result evidence references unchanged.
- [ ] Preserve current and historical model diagrams through explicit bounded projection/event lookup where the limited history does not include the earlier network event. Do not invent topology or show an old model's diagram as current.
- [ ] Verify the App with real local API, fresh task-owned Threads, new/switch/archive/restore, long history, reload drafts and backend restart recovery without Provider calls. Fix reproduced failures.
- [ ] Run required integration gates, `make capstone-local-rebuild`, and local App browser acceptance on the exact committed source.
- [ ] Deploy that exact tested source to cloud-dev only; verify readiness, source identity, both families, history preservation and new session/recovery paths. Check configuration without making unauthorized Provider requests.
- [ ] Update bilingual product commands if needed, runbook, status index and verification receipts. Ordinary AI conversation remains blocked until dedicated cloud-dev credentials and separate Provider authorization are available; human acceptance precedes demo.
- [ ] Independent final review, corrections, task-owned commit and durable journal/checkpoint.

## Execution record

Backend catalog/archive/history is committed in `508a44d`; App management,
draft/receipt recovery, reverse history integration, bounded caches and idle
subscription handling are committed in `a2dbb5d`. App266 tests and typecheck,
focused backend/API checks, backend pyright and21 disposable-PostgreSQL checks
pass. Local rebuild uses one image across all three backend roles.

Real browser checks use the rebuilt local API and task-owned durable Threads:
new/switch, separate drafts, refresh, API restart auto reconnect, reversible
archive, read-only archival,70 QA text turns,50-message windows, complete reverse
history, latest navigation and390px layout pass. The temporary proxy holds the
local operator secret in memory and rejects Provider instructions. Test text
makes no numerical or authority claim. Receipts: `runs/thread-session-*`;
screenshots: `output/playwright/thread-session-*`.

Full release gates pass; all four cloud-dev services deploy the exact candidate.
Actual hosted browser recovery across the API deployment, drafts/new/switch/
archive/restore, source identity, retained history/network projection, registered
cases, reports and evidence pass. See the
[verification record](../../reviews/2026-10-06-thread-session-management-verification.md).
Provider configuration and human acceptance remain separate, unresolved gates.
Independent review spawn was attempted twice; the tool rejects its inherited
model as unsupported. No agent ran, and independent review is not claimed.
Inline source review and actual verification continue. Ordinary Provider
conversation requires dedicated cloud-dev credentials and separate call
authorization. Demo still requires human acceptance.

## Acceptance boundaries

An open browser retains one event subscription and its bounded UI state; it does not reserve a runtime worker. The API subscription currently polls the database; Task 3 must reduce idle polling and close abandoned subscriptions. Existing execution leases provide exclusivity, not a full user/session pool. The legacy `/old` session host's capacity and idle eviction remain compatibility behavior.

Long model context is a separate Kernel concern. Do not treat UI history paging as model-context compaction or re-admit old evidence to a new Attempt. This delivery bounds user-visible history and preserves truth; any new semantic memory policy needs its own explicit contract.
