# Model work resume implementation plan

> Execute inline in this session. The user has approved the design and requested continuation.

**Goal:** Switching an opened model resumes its latest working Context and view without adding a model.

**Architecture:** Keep private saved Context snapshots in stable workspace entries; keep models/1 public fields unchanged. Normalize client working pages from opened membership, while retaining Context/Attempt replay separately.

**Tech Stack:** Python/PostgreSQL Thread ledger, TypeScript/React projection store, Vitest and headless Playwright.

## Task 1: Durable saved working Context

Files: `packages/capstone-agent/src/capstone_agent/thread_model_workspace.py`, `thread_service.py`, `tests/test_thread_model_workspace.py`.

- [x] Add A -> B -> A tests expecting A's original Context/selection, retained results, reload and close behavior; run them red.
- [x] Add private `work_context` to workspace entries with old-shape migration. Validate Context/model identity and unique model keys. Exclude private fields from models/1. Synchronization saves the active Context even when the entry is already current.
- [x] Resume an existing entry's saved Context. Prepare Authority baseline only for a fresh Context. Seed legacy entries from retained exact-identity Context records under the Thread lock.
- [x] Run focused PostgreSQL tests and backend suite. Verify resumed Attempt prior results remain Context scoped.

Run: `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_model_workspace.py -q`; `make test-capstone-agent`.

## Task 2: Model working pages and view restoration

Files: `packages/capstone-app/src/threadProjectionStore.ts`, `ThreadFixtureApp.tsx`, `ThreadModelPane.tsx`, `NetworkView.tsx`, their test files.

- [x] Keep the red duplicate-model regression; add member-based working-page, restored overlay and same-model historical-view checks.
- [x] Add explicit model working-page projection from authoritative opened membership; retain historical Context views independently. Stop using the Context page array as model navigation for current servers.
- [x] On activation reuse the saved Context view; fetch replay on cache miss. Keep original source instruction metadata. Save camera by exact identity/view and retain draft/message anchor.
- [x] Run App tests/build, integration gates and doctor/boundary checks; rebuild using `make capstone-local-rebuild`.
- [x] Verify a fresh isolated Thread A -> B -> A on desktop/mobile, without Provider requests. Verify same-tab reload, exact source views and no duplicate model members. Archive only owned validation Threads.
- [x] Update verification report and state checkpoint; commit only owned paths.

Receipt: [local verification](../../reviews/2026-10-08-thread-model-work-resume-local-verification.md). Independent review and remote acceptance remain pending.
