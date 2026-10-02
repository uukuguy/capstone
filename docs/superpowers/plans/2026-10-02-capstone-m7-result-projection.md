# Capstone M7 Result Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven development or inline execution to implement this plan task-by-task. Each task ends with a focused test cycle.

**Goal:** Expose admitted pandapower analysis results as a bounded Thread projection and let Web users inspect result tables and focus the matching element in the left grid diagram.

**Architecture:** Domain Packs produce typed result projections from admitted Authority results. `capstone-agent` validates and attaches them to the public Thread read model. The Web client renders the projection and writes only a presentation focus into the existing model pane; it never parses prose or reads raw artifacts.

**Tech Stack:** Python 3.12+, Pydantic/dataclass-style existing Capstone contracts, FastAPI Thread projection, React/TypeScript, assistant-ui message primitives, Vitest, pytest.

## Global Constraints

- Keep ownership direction `Application -> Domain Pack -> Kernel -> registered Authority`.
- Keep result and evidence references bound to the current Thread/Run/Turn/Attempt and model revision.
- Reject non-finite values, unknown element ids, revision mismatches, over-sized projections, and unadmitted references.
- Preserve existing `grid-agent` stdout compatibility and do not add new Thread/result orchestration there.
- Preserve the existing two-column Thread layout and current NetworkDiagram/NetworkLayer contracts.
- M7 does not add answer-summary preferences, feedback persistence, multi-Run, WebSocket controls, real DSH, or a new TUI.
- Run focused tests only; full release rebuild/provider gates are deferred unless a release claim is made.

---

### Task 1: Define and validate the shared ResultProjection contract

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/result_projection.py`
- Modify: `packages/capstone-agent/src/capstone_agent/thread_protocol.py`
- Modify: `packages/capstone-app/src/threadProtocol.ts`
- Create: `packages/capstone-agent/tests/test_result_projection.py`
- Create: `packages/capstone-app/src/resultProjection.test.ts`

**Interfaces:**
- `ResultProjection` and nested immutable records validate the public `capstone-result-projection/1.0` shape.
- `normalize_result_projection(value, *, admitted_refs, diagram_ids)` returns a bounded JSON mapping or raises `ThreadProtocolError`/`ValueError`.
- `ThreadSnapshot` exposes `result_projections` under the public snapshot projection; raw application state remains private.
- TypeScript exports `ResultProjection`, `ResultMetric`, `ResultTable`, `ResultElementRef`, `ResultOverlay`, and `parseResultProjection`.

- [ ] **Step 1: Write failing Python contract tests** for valid summary/table/element data, unadmitted refs, wrong revision, NaN/Infinity, unknown element ids, and list/row limits.
- [ ] **Step 2: Implement the bounded Python records and normalizer.** Use explicit scalar checks, finite-number checks, ref-prefix checks, and fixed maximums. Do not accept arbitrary nested JSON in metric values or table cells.
- [ ] **Step 3: Add the projection field to the public Thread snapshot.** Parse and re-emit only normalized projections; preserve snapshots without projections for ordinary/offline answers.
- [ ] **Step 4: Mirror the same limits in TypeScript** and make malformed projections produce the existing typed protocol error rather than a render crash.
- [ ] **Step 5: Run focused checks.**

```sh
cd packages/capstone-agent
uv run pytest -q tests/test_result_projection.py tests/test_thread_protocol.py
cd ../capstone-app
npm test -- --run src/resultProjection.test.ts
```

- [ ] **Step 6: Commit** `feat: add bounded Thread result projection contract`.

### Task 2: Project pandapower admitted calculations into ResultProjection

**Files:**
- Create: `packages/pandapower-domain-pack/src/pandapower_domain/result_projection.py`
- Modify: `packages/pandapower-domain-pack/src/pandapower_domain/presentation.py`
- Modify: `packages/pandapower-domain-pack/src/pandapower_domain/answer_admission.py` only if the existing admission return type needs the projection attached
- Create: `packages/pandapower-domain-pack/tests/test_result_projection.py`
- Modify: the existing Capstone worker/admission integration test fixture that submits a completed answer

**Interfaces:**
- `PandapowerResultProjector.project(context, calculation, *, thread_id, run_id, turn_id, attempt_id, admitted_refs, diagram)` returns a normalized `ResultProjection`.
- The projector consumes domain state and admitted result/evidence references only; it never receives a raw network object or artifact path for browser use.
- The first supported capability is `analysis.powerflow.ac.run`; non-converged or unsupported capabilities return an unavailable/partial projection with a typed reason.

- [ ] **Step 1: Add failing projector tests** for a converged AC power flow with total active loss, network counts, one structured line-result table, one line `ElementRef`, and a loading overlay. Add rejection tests for a revision mismatch, missing evidence, and non-finite result.
- [ ] **Step 2: Implement projector mapping** from existing `CalculationState`/presentation fields. Keep labels and units domain-owned. Use only result rows whose ids exist in the registered `NetworkDiagram`.
- [ ] **Step 3: Attach the projection during completed-answer admission** so it is persisted with the immutable Attempt/Turn outcome and reappears after snapshot reload/resync.
- [ ] **Step 4: Add a PyPSA-compatible projector protocol fixture** without inventing PyPSA values. A missing PyPSA projector must produce a typed unavailable state.
- [ ] **Step 5: Run focused domain and worker checks.**

```sh
cd packages/pandapower-domain-pack
uv run pytest -q tests/test_result_projection.py tests/test_answer_policy.py
cd ../../packages/capstone-agent
uv run pytest -q tests/test_result_projection.py tests/test_thread_protocol.py tests/test_thread_service.py
```

- [ ] **Step 6: Commit** `feat: project admitted pandapower analysis results`.

### Task 3: Add server read-model and resync integration

**Files:**
- Modify: `packages/capstone-agent/src/capstone_agent/thread_service.py`
- Modify: `packages/capstone-agent/src/capstone_agent/thread_protocol.py` if Task 1 leaves a read-model adapter seam
- Modify: `packages/capstone-agent/src/capstone_agent/thread_http.py` or the existing Thread route module only if a projection detail route is required
- Create/modify: `packages/capstone-agent/tests/test_thread_result_projection.py`

**Interfaces:**
- Completed answer projection is available from `ThreadSnapshot.result_projections` and is keyed by immutable `attempt_id`/`result_id`.
- `ThreadService` rebuilds projections from durable snapshot/event state after reconnect; no browser-only cache is authoritative.
- A detail route is optional in the first implementation; if the bounded snapshot fits the existing limit, do not add a second endpoint.

- [ ] **Step 1: Write an integration test** that submits an admitted result, reads the public snapshot, serializes/deserializes it, and confirms projection identity, refs, revision, table rows, and element refs survive.
- [ ] **Step 2: Add retry and historical assertions.** A retry creates a new projection identity; the previous projection remains attached to its old Attempt. A historical snapshot cannot mutate active model focus.
- [ ] **Step 3: Add resync and malformed-state tests.** Invalid projection data becomes a typed unavailable projection or protocol rejection according to the existing Thread recovery policy; it must not silently disappear.
- [ ] **Step 4: Run the focused server suite** and check `git diff --check`.

```sh
cd packages/capstone-agent
uv run pytest -q tests/test_thread_result_projection.py tests/test_thread_protocol.py tests/test_thread_service.py
git diff --check
```

- [ ] **Step 5: Commit** `feat: expose result projections in Thread snapshots`.

### Task 4: Render result details and grid focus in Web

**Files:**
- Modify: `packages/capstone-app/src/threadProtocol.ts`
- Modify: `packages/capstone-app/src/CapstoneAssistantThread.tsx`
- Modify: `packages/capstone-app/src/ThreadFixtureApp.tsx`
- Modify: `packages/capstone-app/src/ThreadModelPane.tsx`
- Modify: `packages/capstone-app/src/NetworkView.tsx` only where the existing focus API needs a typed element id
- Modify: `packages/capstone-app/src/styles-light.css`
- Create: `packages/capstone-app/src/ResultProjectionPanel.tsx`
- Create: `packages/capstone-app/src/ResultProjectionPanel.test.tsx`
- Modify: `packages/capstone-app/src/CapstoneAssistantThread.test.tsx` and `ThreadCaseInteraction.test.tsx` as needed

**Interfaces:**
- `ResultProjectionPanel` receives a parsed projection and `onSelectElement(ref)`; it never receives a fetcher or raw result ref that it can dereference itself.
- `ThreadFixtureApp` owns the shared presentation focus and passes `elementReference` into `ThreadModelPane`.
- The assistant action row keeps fixed `结果`/`证据`/`更多` slots. Result is enabled only for a matching admitted projection; future actions remain disabled with a reason.

- [ ] **Step 1: Write failing component tests** for compact metrics, a readable table, disabled/unavailable states, result action opening the panel, and row selection calling the focus callback.
- [ ] **Step 2: Implement `ResultProjectionPanel`** with loading/unavailable/stale/resync states, scalar formatting, bounded table rendering, and no long hashes in primary content.
- [ ] **Step 3: Add assistant-message result action wiring.** Use the Attempt id to select the matching projection; keep evidence action behavior unchanged and preserve the existing duration/activity controls.
- [ ] **Step 4: Add shared focus state wiring.** Validate model id and revision before writing focus; show the existing compact element reference area and a visible invalid-focus message when validation fails.
- [ ] **Step 5: Add overlay rendering** only for ids present in the current diagram and matching revision. Do not alter diagram source or active model context.
- [ ] **Step 6: Run the focused App tests and build.**

```sh
cd packages/capstone-app
npm test -- --run src/resultProjection.test.ts src/ResultProjectionPanel.test.tsx src/CapstoneAssistantThread.test.tsx src/ThreadCaseInteraction.test.tsx
npm run build
```

- [ ] **Step 7: Commit** `feat: add Web result details and grid focus`.

### Task 5: M7 lightweight integration closeout

**Files:**
- Modify: `docs/status/CURRENT-STATE.md` only for structural M7 facts
- Modify: `docs/status/RESUME-NEXT-SESSION.md` for the active checkpoint
- Append: `docs/status/JOURNAL.md`
- Create: `packages/capstone-agent/tests/test_m7_result_projection_boundary.py` only if one cross-package boundary assertion is still missing

- [ ] **Step 1: Run the compact integration matrix** covering one pandapower answer, result rendering, row-to-diagram focus, retry identity, and resync. Use existing fixtures and no provider credentials.
- [ ] **Step 2: Review the diff for ownership leaks** into `grid-agent`/`pypsa-agent`, raw artifact exposure, prose parsing, and revision-less focus.
- [ ] **Step 3: Run `git diff --check` and the focused Python/App suites.** Do not run release/provider gates for this demo-stage milestone.
- [ ] **Step 4: Record the M7 result and any deferred gaps** in the status files and append-only journal.
- [ ] **Step 5: Commit** `docs: close M7 result projection verification`.

## Verification Summary

The M7 finish line is the focused Python + Web matrix from Tasks 1–5. A full release claim still requires the repository's broader rebuild and release gates; that is outside this demo-stage milestone.
