# Thread session management and recovery implementation plan

> **For agentic workers:** Use subagent-driven-development to implement and review each task. The user explicitly requested that discovered problems be fixed.

**Goal:** Let users create and manage Threads from the App, recover connections and drafts, and read long conversations without unbounded initial loading.

## Current scope: 2026-10-06 11:24

The user defers the user system and history-session management. Remove the
session list, user association and automatic title requests from this delivery.
Keep the active Thread workspace, a small New conversation action, draft/reconnect
recovery and durable messages/results/evidence. Existing stored data is retained.
For earlier messages inside the active conversation, use a small text action
“查看之前的对话”; remove the large paging button and implementation-count banner.
All changes must pass the local rebuilt App before another cloud release.

Deferred work, with no scheduled release:

- [ ] Backend user ownership derived from the active Thread, with no browser identity registry.
- [ ] User-scoped recent/archived conversations, switching, archive and restore.
- [ ] Short conversation titles generated from dialogue by LLM, with persistence and failure isolation.
- [ ] A separate UI review before enabling these controls.
- [ ] A retention contract for empty Threads and expired history/artifacts, with explicit preservation and deletion rules.

The immediate priority is server resource lifecycle: bounded model-context
cache, idle eviction, active-work protection, runtime deadlines, bounded live
connections and constant-size wake throttling. Keep the thresholds in the shared
runtime contract so local/cloud startup remains aligned. Acceptance must show
zero retained contexts after idle expiry with the page still open, and an old
Thread must execute again after resource preparation. User/history UI remains deferred.

Local acceptance for source `c68f6e1` passes: active contexts are pinned; both
workers reach retained0/active0 with the App still open; the same Thread then
completes a new catalog Turn and its history remains readable. Actual
pandapower power flow and PyPSA dispatch/AC validation pass. Stream capacity is
released on disconnect. Receipt: `runs/thread-lifecycle-local-acceptance.json`.
Railway connectivity recovered and the single guarded cloud-dev rollout of
`c68f6e1` passes. All backend source/runtime hashes match local acceptance.
The actual root App, retained draft/history, exact catalog question, both
families' calculations, reports/evidence, registered cases, stream release and
cold Thread reuse pass. Both caches reach retained0/active0 with the page open.
Receipt: `runs/thread-lifecycle-cloud-acceptance.json`. The user accepted cloud-dev
and authorized promotion of this exact source. Demo deployment acceptance passes:
`runs/demo-promotion-20261006/acceptance.json`. Additional user-use and load tests
follow the [expanded validation plan](2026-10-06-session-load-and-recovery-validation.md),
first locally and then in cloud-dev. Demo stays on the accepted source during
these checks.

The completed checks below record earlier iterations. They do not authorize
shipping the deferred features. The interrupted cloud-dev rollout must return
its workers to the last verified images; API/App were not updated in that rollout.

**Architecture:** Capstone owns durable Thread metadata, history pagination and execution leases. The App owns navigation, bounded message presentation and browser-session drafts. A Thread is a durable record, not a reserved worker; runtime execution remains per Attempt.

**Tech Stack:** Existing FastAPI, PostgreSQL, React, assistant-ui, TypeScript and Vitest. No new service or dependency.

## Global constraints

- Preserve the four ownership layers and all existing data, artifacts and user edits.
- No new Thread ownership in grid-agent or pypsa-agent.
- Keep compatibility stdout and current-run evidence admission unchanged.
- Existing operator authentication scopes private Threads. Do not claim individual user isolation without an account model.
- Never delete event history to shorten the chat view. Archive is reversible metadata, not deletion or cancellation.
- A running Attempt or active Case blocks archiving. Explicit retry remains required for interrupted execution.
- Provider credentials are separate by default. The user's current function-validation instruction permits existing credentials and an open, no-login Thread workbench. Preserve stage database, bucket and evidence isolation.
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
- [ ] Update bilingual product commands if needed, runbook, status index and verification receipts. Verify ordinary AI conversation with the existing Provider credentials authorized for the current function-validation stage; human acceptance precedes demo.
- [ ] Independent final review, corrections, task-owned commit and durable journal/checkpoint.

## Execution record

This record describes the earlier `a2dbb5d` acceptance. The user's later
function-validation instruction supersedes its dedicated-credential requirement;
the open-entry work below requires fresh local and cloud-dev acceptance.

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

## Navigation layout correction

The user rejected the separate full-width session toolbar after viewing the
deployed App. Keep the accepted session functions and place their controls in
the existing PageHeader action group. A separate toolbar wastes working space;
putting the controls inside the conversation would make workspace navigation
depend on the chat pane. The shared header is the existing navigation boundary.

Files: `AppHeader.tsx` accepts optional `actions: ReactNode`;
`ThreadFixtureApp.tsx` passes optional `headerActions` and renders a creation
error in the chat notices; `ThreadLiveEntry.tsx` supplies the session menu in
that slot. `ThreadSessionMenu.tsx` uses named icon buttons; `styles.css` anchors
its list to the right of the header and keeps touch targets at least44px.
Mobile controls retain accessible names while hiding their text; narrow screens
hide the secondary project link. No API, session or authority contract changes.

- [x] Integrate the session menu into the shared header and remove its standalone bar.
- [x] Run the existing App behavior tests, TypeScript and production build.
- [x] Rebuild the local services; inspect the real App at desktop,390px and320px.
- [x] Verify new/switch/archive/restore and drafts still work through the real API.
- [ ] Commit only owned changes and deploy the tested App to cloud-dev; inspect
  the actual served header, menu and mobile layout before reporting acceptance.
- [ ] Ordinary Provider acceptance and human approval continue to gate demo.

## Open workbench entry

The user explicitly requests direct entry like the earlier App, without a
front-end login, and use of existing Provider credentials during function
validation. Keep Provider secrets in the backend. `CAPSTONE_THREAD_OPEN_ACCESS`
is an explicit hosted setting, true by default in local Compose. Host middleware
accepts unauthenticated App requests when selected. `/api/v1/thread-access`
returns only its schema and `open` or `operator` mode, never credentials.
ThreadLiveEntry waits for this mode before creating a client or a Thread,
preventing duplicate creation under StrictMode. Open mode sends no token;
operator mode and older hosts still support their existing entry.

- [x] Add and verify failing API/settings and no-login StrictMode regressions.
- [x] Implement hosting/CLI/API mode and App discovery, connection error/retry.
- [x] Rebuild current local source and verify from an empty browser session.
- [x] Verify the reported catalog query and both authority families locally,
  using only task-owned Threads and a bounded number of actual AI turns.
- [ ] Complete integration/release gates, deploy locally verified source to cloud-dev and
  limited actual App acceptance. Demo still requires user manual acceptance.

Cloud9846d48 actual catalog and pandapower calculations pass. PyPSA opening
exposes a30s Attempt lease interruption, so cloud acceptance remains pending.
The local repair adds independent lifecycle renewal and preserves polling after
a failed iteration; five blocked-phase regressions, lost-lease guards, direct
Harness and an isolated PostgreSQL check cover it. The repaired source must
pass a fresh local rebuild and App check before the next backend rollout.

## Runtime configuration and startup parity

The user requires application logic to be validated locally and cloud runtime
configuration/startup to be locked independently. Cloud9cbdc13 exposes an API
startup snapshot that keeps PyPSA unavailable after its worker becomes ready.
Use live family-health callbacks and the shared versioned workbench profile.
The launcher fixes selectors and role commands, waits for API dependencies and
records secret-free contract/artifact hashes. Pin multi-platform base images;
keep infrastructure and credentials environment-specific. A checked-in receipt
comparison rejects stage, role, source/config/package/model drift. Upload each
worker once and wait for current health/identity before API deployment.

- [x] Reproduce stale availability and add memory/SQL service recovery regressions.
- [x] Add shared launcher/profile and drift/Provider/dependency-wait checks.
- [x] Finish current local rebuild, full release gates and real App recovery checks.
- [ ] Compare exact local/cloud runtime receipts and perform actual cloud Thread acceptance.
- [ ] Record final evidence and leave demo unchanged pending human acceptance.

## Acceptance boundaries

## Browser session list and conversation titles

The user rejects the global environment list, model IDs as conversation names,
large buttons in the main brand header, and the low-value open/details controls.
The user corrects browser-history scope: the backend owns a simple anonymous
user and each Thread belongs to that user. A fresh page creates a user and its
first Thread. New dialogue inherits the active Thread's user; list queries
derive user scope from that active Thread. Refresh resumes the same Thread and
user. The App needs no browser identity/history store and no login. Preserve
legacy Threads with separate anonymous owners rather than inventing ownership.
Move compact session controls into the conversation heading, remove open and
details, show a bounded scroll list with model/time as secondary information,
and preserve archive/restore, drafts and history. Close the panel on Escape
or outside click. Use a backend, tool-free LLM request after the first successful
turn to create a short title. Persist it once, with bounded input/timeout;
title errors must not change the completed answer or its evidence. Existing
unnamed Threads gain a title after their next successful turn.

- [x] Verify anonymous user grouping, title persistence/failure isolation and controls locally.
- [x] Rebuild local App/API/workers and inspect desktop/mobile real App.
- [ ] Deploy the locally verified exact source to cloud-dev and inspect real App.
- [ ] Finish retained-Thread cloud catalog/pandapower checks; demo needs human acceptance.

## Acceptance boundaries (continued)

An open browser retains one event subscription and its bounded UI state; it does not reserve a runtime worker. The API subscription currently polls the database; Task 3 must reduce idle polling and close abandoned subscriptions. Existing execution leases provide exclusivity, not a full user/session pool. The legacy `/old` session host's capacity and idle eviction remain compatibility behavior.

Long model context is a separate Kernel concern. Do not treat UI history paging as model-context compaction or re-admit old evidence to a new Attempt. This delivery bounds user-visible history and preserves truth; any new semantic memory policy needs its own explicit contract.
