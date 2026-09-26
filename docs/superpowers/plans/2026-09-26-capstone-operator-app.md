# Capstone Operator App Implementation Plan

> **For agentic workers:** Execute each checkbox in order with focused red/green tests and review each committed unit. Inline execution is selected by the user's approval and repository collaboration constraints.

**Goal:** Ship a polished Vite App that drives registered three-turn pandapower and PyPSA demonstrations through the same `/api/v1` contract used locally and on Vercel.

**Architecture:** The browser holds only the operator token in tab memory. A typed API client fetches a fixed catalog, submits each registered instruction with an idempotency key, consumes sequenced SSE through `fetch`, and renders committed answers, admitted references, evidence, and report. View state remains independent of provider-specific hosting.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, Playwright.

## Global constraints

- The App is an application presentation layer; no raw simulator data, network files, local paths, or credentials in the bundle or URL.
- No Provider request occurs by opening the App or selecting a case.
- Frontend API base URL is configured; the same `/api/v1` paths and response types work locally, on Cloud Run, and on Railway.
- Maintain visible keyboard focus, semantic controls, reduced-motion support, and responsive layouts.
- Keep the staged `.codex/config.toml` untouched.

## File map

- `packages/capstone-app/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `index.html`: independent app toolchain.
- `packages/capstone-app/src/api.ts`: typed fetch, bearer header, SSE cursor, bounded responses and reconnection.
- `packages/capstone-app/src/types.ts`: API and display types.
- `packages/capstone-app/src/App.tsx`: case selection and session lifecycle composition.
- `packages/capstone-app/src/components/`: catalog, timeline, reference and report panels.
- `packages/capstone-app/src/styles.css`: tokens, grid, typography, responsive and state styling.
- `packages/capstone-app/src/*.test.tsx`: interaction and accessibility behavior.
- `packages/capstone-app/e2e/`: one local scripted smoke path at desktop and narrow viewport.

---

### Task 1: API client and token entry

**Interfaces:** `CapstoneClient(baseUrl, token)` with `catalog()`, `createSession(selection)`, `submitTurn(sessionId, instruction, key)`, `close(sessionId, key)`, `status(sessionId)`, `events(sessionId, after, signal)`, `turn(sessionId, ordinal)`, `result(sessionId)`, `report(sessionId)`, `evidence(sessionId, ref)`.

- [ ] Add client tests with mocked `fetch`: token only in Authorization header, retry uses same idempotency key, SSE parser ignores keepalives and duplicate sequences, abort stops streaming, 401 clears active authorization state.
- [ ] Run `npm test -- --run src/api.test.ts` in `packages/capstone-app`; expect module missing.
- [ ] Implement bounded response parsing and a cursor-based SSE reader. Persist no token in localStorage, sessionStorage, URL, or logs.
- [ ] Run the focused test and typecheck; commit only app client/toolchain files.

### Task 2: Case workflow

**Interfaces:** `App` composes `CatalogPanel`, `TurnTimeline`, `RunSummary`; state machine `locked -> selecting -> ready -> executing -> reviewing -> completed|interrupted|failed`.

- [ ] Add UI tests for catalog grouping, exact ordered instructions, start without automatic turn execution, one turn at a time, answer/ref display, reconnect, and interrupted state.
- [ ] Run focused UI tests; expect failures.
- [ ] Implement the three-column console with concise case provenance and boundary copy, professional slate/cyan tokens, and mobile stacking. The only action that sends a turn is the explicit submit control.
- [ ] Run focused tests, accessibility assertions, and typecheck; commit owned UI files.

### Task 3: Evidence and report detail

**Interfaces:** `DetailPanel` accepts admitted refs and run ID; never constructs an object key or reads a local path.

- [ ] Add tests for selecting admitted references, 404/unavailable evidence, bounded report rendering, explicit loading states, keyboard navigation, and narrow viewport panel behavior.
- [ ] Run the focused tests; expect failures.
- [ ] Render report text as safe text/Markdown with no arbitrary HTML execution; display interpretation boundary beside numerical claims and keep the active turn visible.
- [ ] Run focused tests and one Playwright scripted desktop/mobile flow against the real local host; commit owned UI and test files.

### Task 4: Local and Vercel build

- [ ] Add a test that the production bundle contains no operator token and `VITE_API_ORIGIN` config changes the API origin without route changes.
- [ ] Run the focused test; expect failure until config is wired.
- [ ] Wire Vite dev proxy and the Vercel static build/rewrite configuration; add app setup to `Makefile` and align shared commands in `README.md` and `README.zh-CN.md`.
- [ ] Run `npm run build`, `npm test`, `git diff --check`, and a browser visual check at desktop/mobile sizes; commit owned files.

## Review gate

Inspect the rendered UI for the approved engineering-console direction. Verify a demo completes through the real local API, with no Provider request, and that the final result/report/evidence belong to the selected session.
