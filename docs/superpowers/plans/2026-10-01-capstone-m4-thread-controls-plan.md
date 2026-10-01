# Capstone M4 Thread Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use TDD to implement this plan task-by-task and request a code review before declaring M4 complete.

**Goal:** Add compact, typed Thread controls for model and Domain Pack Profile selection, trace visibility, stop, and retry while keeping every operation inside the Capstone Thread/Harness command path.

**Architecture:** The API exposes a bounded catalog projection derived from the application-owned model and capability catalogs. The Web client loads that projection beside `ThreadSnapshot` and renders compact controls; selection changes submit `replace_selection` or `switch_model` commands and remain pending until the next terminal projection. Retry submits `retry_new_attempt`, preserving immutable Attempts. Trace is a presentation toggle for projected activity, not a hidden reasoning or direct runtime channel.

**Tech Stack:** Python/FastAPI, TypeScript/React, assistant-ui, Vitest, pytest, CSS.

## Global Constraints

- `capstone-agent` remains the only application host; `grid-agent` and `pypsa-agent` remain compatibility adapters.
- Web controls consume only typed Thread projections and `CommandEnvelope`; no UI code connects directly to Pi, DSH, Authority internals, or Domain Pack implementations.
- Profile selection is at Domain Pack/Profile level; no per-tool switches and no semantic-conflict inference.
- A model switch and Profile selection are staged while an Attempt is active and take effect only through the existing Thread service activation events.
- Retry always creates a new immutable Attempt and never mutates the old Attempt.
- The Composer remains one automatic-route input: Enter sends, Shift+Enter inserts a newline, and the same component is used for empty and populated Threads.
- Empty, running, and terminal controls must retain stable layout and accessible labels; no giant mode tabs or shortcut hint text.

---

### Task 1: Add the bounded Thread catalog projection

**Files:**
- Modify: `packages/capstone-agent/src/capstone_agent/thread_service.py`
- Modify: `packages/capstone-agent/src/capstone_agent/host_api.py`
- Modify: `packages/capstone-agent/src/capstone_agent/model_capability.py`
- Test: `packages/capstone-agent/tests/test_thread_http_api.py`
- Test: `packages/capstone-agent/tests/test_thread_catalog.py`

**Interfaces:**
- Produce `ThreadService.catalog(thread_id) -> dict[str, object]` with schema `capstone-thread-catalog/1`, bounded model entries, and Profile entries compatible with each registered implementation family.
- Add `GET /api/v1/threads/{thread_id}/catalog`; it must enforce the same private Thread authorization and 404 behavior as the snapshot route.
- Keep catalogs that do not implement listing methods valid; return an empty list instead of inventing entries.

- [ ] Write failing tests for model/Profile catalog projection and the authenticated HTTP route.
- [ ] Run the focused pytest tests and confirm they fail because the route/projection is absent.
- [ ] Implement the smallest public projection using `list_entries()` and `profiles_for_family()` when supplied by the application-owned catalogs.
- [ ] Run the focused tests and the existing thread catalog tests.
- [ ] Commit: `feat: expose bounded thread control catalog`.

### Task 2: Parse and transport the catalog in the Web client

**Files:**
- Create: `packages/capstone-app/src/threadCatalog.ts`
- Modify: `packages/capstone-app/src/threadClient.ts`
- Modify: `packages/capstone-app/src/threadHttpTransport.ts`
- Modify: `packages/capstone-app/src/threadProjectionStore.ts`
- Modify: `packages/capstone-app/src/threadProjectionStore.test.ts`
- Test: `packages/capstone-app/src/threadClient.test.ts`
- Test: `packages/capstone-app/src/threadHttpTransport.test.ts`

**Interfaces:**
- `ThreadCatalog` contains strict `models` and `profiles` arrays with model id, display name, implementation family, revision, and Profile id/version/display name/family list.
- `ThreadTransport.getCatalog(threadId)` and `CapstoneThreadClient.catalog(threadId)` are optional-compatible additions; failure to load the catalog leaves the Thread usable with an empty catalog.
- `ThreadProjectionState.catalog` is always a parsed catalog or `null`, never raw JSON.

- [ ] Write failing parser, transport URL, and store-loading tests.
- [ ] Run the focused Vitest tests and confirm the expected missing-interface failures.
- [ ] Implement strict parsing, HTTP GET, and best-effort store loading.
- [ ] Run the focused tests and existing projection/client tests.
- [ ] Commit: `feat: project thread control catalog in web client`.

### Task 3: Render compact model/Profile controls

**Files:**
- Modify: `packages/capstone-app/src/ThreadFixtureApp.tsx`
- Modify: `packages/capstone-app/src/ThreadModelPane.tsx`
- Modify: `packages/capstone-app/src/CapstoneAssistantThread.tsx`
- Modify: `packages/capstone-app/src/threadUiFixtures.ts`
- Modify: `packages/capstone-app/src/styles-light.css`
- Modify: `packages/capstone-app/src/styles.css`
- Test: `packages/capstone-app/src/ThreadFixtureApp.test.tsx`
- Test: `packages/capstone-app/src/CapstoneAssistantThread.test.tsx`

**Interfaces:**
- Model options come from the typed catalog, with the active snapshot model as the safe fallback.
- A compact Profile menu displays only Profiles compatible with the active implementation family, shows checked active Profiles, stages a replacement selection through `replace_selection`, and shows pending state from the snapshot.
- The Composer footer accepts a compact controls slot. It exposes a trace/activity toggle but no mode tabs or per-tool switches.
- Model switching remains the existing `switch_model` command and automatically updates the model page from `active_grid_page_id`.

- [ ] Add failing UI tests for catalog-driven model options, Profile replacement payload, pending state, and the compact trace toggle.
- [ ] Run the focused UI tests and confirm failure before implementation.
- [ ] Implement the controls with stable empty/running layout, 36px hit targets, SVG icons, and `aria-label`/tooltip text.
- [ ] Run focused UI tests and the app type check.
- [ ] Commit: `feat: add compact thread model and profile controls`.

### Task 4: Make retry and activity controls honor Attempt semantics

**Files:**
- Modify: `packages/capstone-app/src/ThreadFixtureApp.tsx`
- Modify: `packages/capstone-app/src/CapstoneAssistantThread.tsx`
- Test: `packages/capstone-app/src/ThreadFixtureApp.test.tsx`
- Test: `packages/capstone-app/src/CapstoneAssistantThread.test.tsx`

**Interfaces:**
- The answer action “重新运行” submits `retry_new_attempt` with the original `attempt_id` (or `turn_id`) and never resubmits the original text as a new automatic Turn.
- Stop remains `cancel_live_attempt` in the Composer while running; trace visibility only changes projected activity display.
- Activity summary and final duration remain attached to the corresponding assistant Attempt.

- [ ] Add failing tests that inspect the retry command payload and confirm old Attempt messages remain unchanged.
- [ ] Run focused UI tests and confirm the expected failure.
- [ ] Implement command wiring and activity visibility.
- [ ] Run all Web tests and build.
- [ ] Commit: `fix: preserve immutable attempt retry semantics in web thread`.

### Task 5: Verify, review, and update the recovery baton

**Files:**
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Modify: `docs/status/JOURNAL.md`
- Create: `docs/reviews/2026-10-01-capstone-m4-code-review.md`

- [ ] Run focused Python and Web tests, `npm run check`, `npm run build`, boundary checks, `make doctor`, and `git diff --check`.
- [ ] Run `make capstone-local-rebuild` because the API source changes.
- [ ] Dispatch an independent code reviewer with the M4 plan and final diff; fix all Important/Critical findings.
- [ ] Record exact verification counts, rebuild result, review verdict, and next M5 action in status/JOURNAL.
- [ ] Commit: `docs: record M4 controls checkpoint`.

## Self-review

- The plan covers the M4 contract’s catalog, compact controls, trace, stop, retry, pending state, one-page-per-model projection, and verification gates.
- No task grants the UI direct access to Pi, DSH, raw Authority objects, or individual tools.
- Catalog absence is represented as an empty typed projection, so legacy adapters do not block ordinary Thread use.
