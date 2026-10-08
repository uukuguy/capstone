# Thread Opened Models Implementation Plan

> **For agentic workers:** Execute inline in this session with test-driven development and focused review. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved nonempty opened-model collection, current model, close lifecycle and historical topology association.

**Architecture:** Application-owned model membership persists separately from snapshot/1 and Case state. Immediate control commands use existing Thread receipts, locks and ledger cursors; Attempts retain immutable Contexts. Authority-backed baseline topology and exact historical Attempt projections remain separate.

**Tech Stack:** Python, PostgreSQL/psycopg, React/TypeScript, Vitest, local Compose/Vite.

## Global constraints

- [Approved design](../specs/2026-10-08-thread-open-models-design.md), including §6.1, governs this package. User approval: 2026-10-08.
- Preserve user sessions, unrelated changes and main-worktree var/ data; no Provider calls or cloud release.
- Keep domain semantics outside Kernel; use registered Authority projections, never raw model objects.
- Global calculation-tool preferences do not govern model controls; no automatic reenablement.
- Keep the legacy delayed switch/reopen contract, compatibility stdout and current-run evidence rules.
- Maximum opened models: 64; workspace JSON: 64 KiB; reject overflow without truncating membership.

## Task 1: Durable membership and immediate commands

**Files:** Create `packages/capstone-agent/src/capstone_agent/thread_model_workspace.py` and `packages/capstone-agent/tests/test_thread_model_workspace.py`; modify `thread_service.py`, `host_api.py` and `test_thread_postgres.py` in their existing directories.

**Interfaces:** `read_models(thread_id) -> dict`; GET `/api/v1/threads/{thread_id}/models` returns schema `capstone-thread-model-workspace/1`, `thread_id`, `run_id`, `event_seq`, `current_entry_id`, `models`, `blocked_reason`. Each model has stable `entry_id`, registered identity/revision/family/name and `last_active_seq`.

Commands: `open_model {model_id}`, `activate_model {entry_id}`, `close_model {entry_id}`. Controls finish without a Turn/Attempt. Current-close uses the greatest prior activation sequence; final-close rejects `last_model_required`. Successful activation emits existing `model_context_activated`, then `model_workspace_changed`; receipt points to the final committed control event.

Historical reopen uses `open_model {model_id, model_revision}`. It reuses an exact opened entry or rejects unavailable registered revisions; it must not substitute the latest catalog version.

- [x] Test initial migration, open/activate without messages, exact revision after catalog drift, duplicate open no-op, stable order, inactive/current/final close, failed target, cursor conflicts, live Attempt/Case locks and legacy delayed activation.
- [x] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_model_workspace.py -q`; confirm missing behavior fails before source edits.
- [x] Implement bounded validated membership and shared transition preparation; store PostgreSQL workspace JSON separately and update it under the existing Thread row lock with Context/events/receipt.
- [x] Recheck idempotency after the PostgreSQL lock; reject conflicting identities without changing membership. Migrate old active-only rows idempotently.
- [x] Run the focused memory and isolated PostgreSQL tests, then commit only task-owned paths.

## Task 2: Baseline topology and historical replay

**Files:** Modify `thread_catalog.py`, `thread_management.py`, `thread_service.py`, `host_api.py`, application-owned registered model adapters in `packages/grid-agent/src/grid_agent/hosted.py` and `packages/pypsa-agent/src/pypsa_agent/`, and their owning tests.

**Interfaces:** Application-selected catalog exposes optional `diagram(model_id, model_revision) -> Mapping`; controls admit a normalized exact-model `network_diagram` event before activation completion. Historical `network-events` accepts a bounded `context_id` and optional `attempt_id`, with the Context document and up to four exact admitted events. No user-selected endpoints or model execution are exposed.

- [x] Test wrong model/revision rejection, preparation failure without partial switch, zero-tool model access, and no Attempt creation.
- [x] Test historical replay after model close and event cursor truncation, same model/different Context and exact Attempt layers; missing diagrams remain unavailable.
- [x] Add registered baseline providers using Authority public projection contracts; persist admitted topology in the Thread ledger and retain it after close.
- [x] Add typed Context/Attempt-targeted replay, preserving no-query legacy endpoint output.
- [x] Run backend/network/application focused tests and commit the verified source.

## Task 3: Client contracts, recovery and historical views

**Files:** Create `packages/capstone-app/src/threadModelWorkspace.ts` and its tests; modify `threadClient.ts`, `threadHttpTransport.ts`, `threadProjectionStore.ts`, `threadHistory.ts` and their tests.

**Interfaces:** `client.models(threadId)` parses the bounded typed projection; `store.state.modelWorkspace` represents server truth. `store.refreshModels()` reconciles workspace and snapshot through the same ledger cursor. Context-targeted network replay rebuilds historical pages/tasks without modifying the live snapshot.

- [x] Add failing parser, load/refresh/receipt-loss and cursor-race tests. Preserve old fixture/transport support without claiming durable support where no models endpoint exists.
- [x] Integrate workspace refresh on load and workspace events; mutations remain unavailable until workspace cursor and active Context agree.
- [x] Recover historical topology by Context/Attempt, not model-name page identity; retain exact layer evidence admission and bounded caches.
- [x] Run focused Vitest tests and App build, then commit verified source.

## Task 4: Compact model menu and explicit control instructions

**Files:** Modify `ThreadModelDirectory.tsx`, `ThreadFixtureApp.tsx`, `ThreadModelPane.tsx`, `threadCatalog.ts`, `threadFeedback.ts`, `styles-light.css` and their tests; update `threadSystemNotices.ts` only if admitted outcomes need projection changes.

- [x] Add failing tests for current-name trigger, opened collection, separate registered directory, direct activation/close and final-close guard; disabled mutations remain browsable.
- [x] Add direct application controls with receipt catch-up, retained drafts/reading focus and compact system notices; no generated user/assistant turn.
- [x] Add bounded no-space Chinese open/activate/close parsing, opened-only resolution, explicit compound control/task boundaries and error draft retention. Submit combined analysis once after successful activation.
- [x] Preserve readonly historical topology; expose explicit exact-version open and return-current actions without implicit activation when browsing.
- [x] Verify keyboard focus, 44px touch controls, desktop/mobile popover bounds; run all App tests/build.
- [x] Apply the user's timestamp and instruction/answer grouping corrections; check actual event time, compact metadata, desktop/mobile spacing and consecutive history anchors.

## Task 5: Integration acceptance

- [x] Run `make doctor check-package-boundaries`, `make test`, `make test-e2e`, `make validate`; run workspace persistence/concurrency tests against an isolated PostgreSQL instance.
- [x] Run `make capstone-local-rebuild`; confirm readiness, API/worker identity and actual Vite entry.
- [x] Use background headless Playwright with isolated registered-model sessions: open/switch/close, zero-tool controls, refresh, history diagram replay, consecutive actions, drafts and focus. No user Chrome or Provider calls.
- [x] Check links, CLAUDE symlink and `git diff --check`; record exact evidence and limitations in a local verification report, update CONV-06 status and recovery checkpoint.
- [x] Commit task-owned changes; leave independent review/cloud release status explicit and preserve unrelated dirty paths.
