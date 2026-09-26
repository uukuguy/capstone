# Operator Network Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a readable light operator workspace with automatic three-turn execution and a truthful, interactive current-run network diagram.

**Architecture:** Keep the existing API/worker image and session ledger. The selected application worker emits a bounded `network_view` frame after a committed turn, built only from its registered authority's projection. The host persists the frame alongside session events, and the App renders its typed payload; a separate client coordinator advances the existing idempotent commands one at a time.

**Tech Stack:** Python 3.11+, FastAPI, PostgreSQL, pandapower gridctl, PyPSA model authority, React 19, TypeScript 7, Vite 8, SVG, Vitest.

## Global Constraints

- Keep `Application -> Domain Pack -> Kernel -> registered Authority`; no raw pandapower/PyPSA object crosses the worker or browser boundary.
- Preserve the grid CLI's exact `question_id`/`answer_output` stdout envelope and current-run evidence admission.
- Keep one backend image for local, Cloud Run, and Railway, with the independent Vercel App using the same `/api/v1` contract.
- No Provider call, cloud deployment, credential in bundle, or change to ignored user data.
- Preserve the unrelated staged `.codex/config.toml`; commit only named task paths.
- Use focused tests first. Avoid repeating full suites unless a concrete risk requires them.

## File map

- `packages/capstone-app/src/autoRun.ts`: pure next-command decision based on durable session state.
- `packages/capstone-app/src/NetworkView.tsx` and `networkLayout.ts`: accessible SVG, deterministic schematic layout, pan/zoom/focus and numeric legend.
- `packages/capstone-app/src/App.tsx`, `types.ts`, `api.ts`, `styles.css`: integrate automatic mode, selected turn, view fetching, and light visual system.
- `packages/capstone-agent/src/capstone_agent/network_view.py`: validate and normalize bounded domain presentation projections.
- `packages/capstone-agent/src/capstone_agent/worker.py`, `protocol.py`, `session.py`, `host_api.py`: emit, persist, and serve network view events.
- `packages/grid-agent/src/grid_agent/worker.py` and `validation/run.py`: form grid view from gridctl's bounded network dataset queries and admitted per-element run results.
- `packages/pypsa-agent/src/pypsa_agent/worker.py`: form PyPSA view from `model.topology` and current-run dispatch results.
- Tests adjacent to each affected Python package and in `packages/capstone-app/src/`.
- `README.md`, `README.zh-CN.md`, `docs/RUNBOOK.md`: aligned feature and operator instructions.

---

### Task 1: Automatic command progression

**Files:**
- Create: `packages/capstone-app/src/autoRun.ts`, `packages/capstone-app/src/autoRun.test.ts`
- Modify: `packages/capstone-app/src/App.tsx`, `packages/capstone-app/src/App.test.tsx`

**Interfaces:**
- Consumes: `SessionStatus`, `CaseCard.instructions`, `CapstoneClient.createSession/submitTurn/close`.
- Produces: `nextAutomaticAction(status: SessionStatus | null, count: number): 'start' | 'wait' | { submit: number } | 'close' | 'done'`.

- [ ] **Step 1: Write a failing decision test.** Assert `null -> start`, pending/executing/closing -> wait, ready with `accepted_turns > completed_turns` -> wait, ready with next instruction -> `{submit: completed_turns+1}`, ready after all turns -> close, terminal state -> done.

```ts
expect(nextAutomaticAction({ ...ready, accepted_turns: 1, completed_turns: 0 }, 3)).toBe('wait')
expect(nextAutomaticAction({ ...ready, accepted_turns: 1, completed_turns: 1 }, 3)).toEqual({ submit: 2 })
```

- [ ] **Step 2: Verify red.** Run `npm --prefix packages/capstone-app test -- autoRun.test.ts`; expect missing export.
- [ ] **Step 3: Implement the pure decision and a guarded App effect.** Keep automatic mode in tab memory. For each session+ordinal use a stable `crypto.randomUUID()` key held in a ref; never issue the next command while a request is pending. Start from the current `ready` state, stop on error/401/failure/interruption, and expose **停止自动执行**; the accepted turn is allowed to finish.

```ts
export function nextAutomaticAction(status: SessionStatus | null, count: number) {
  if (!status) return 'start'
  if (['failed', 'interrupted', 'completed'].includes(status.state)) return 'done'
  if (status.state !== 'ready' || status.accepted_turns > status.completed_turns) return 'wait'
  return status.completed_turns < count ? { submit: status.completed_turns + 1 } : 'close'
}
```

- [ ] **Step 4: Add component tests for start-to-close, stop, failure, reconnection replay, and manual submit.** The mocked SSE emits ordered `ready`, three `answer_committed`, and `completed`; assert each instruction and close is called exactly once.
- [ ] **Step 5: Verify green and commit named files.** Run focused Vitest and `npm --prefix packages/capstone-app run check`; use `git commit --only` on the four task files.

### Task 2: Bounded worker network view contract

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/network_view.py`
- Modify: `packages/capstone-agent/src/capstone_agent/protocol.py`, `worker.py`, `session.py`, `host_api.py`
- Test: `packages/capstone-agent/tests/test_network_view.py`, `packages/capstone-agent/tests/test_host_api.py`

**Interfaces:**
- Consumes: one registered application callback `Callable[[int], Mapping[str, object] | None]` after each answer commit.
- Produces: `network_view` event with `ordinal` and validated `view`, plus authenticated `GET /api/v1/sessions/{session_id}/network?ordinal=N`; 404 until available.

- [ ] **Step 1: Write failing validator and route tests.** Reject duplicate bus IDs, branches with absent endpoints, nonfinite coordinates or values, more than 50 buses/100 branches, mismatched `ordinal`, overlong labels, and absent source/revision. Require auth and session identity; assert a replayed event returns identical JSON.

```python
def test_network_view_rejects_missing_endpoint():
    with pytest.raises(ValueError):
        normalize_network_view({"schema": "capstone-network-view/1.0", "ordinal": 1,
            "model": {"id": "ieee39", "revision": "revision:sha256:" + "a" * 64,
                      "source": "gridctl"},
            "buses": [{"id": "0", "label": "0", "x": None, "y": None}],
            "branches": [{"id": "line:11", "kind": "line", "from_bus": "0",
                          "to_bus": "9"}], "omitted": {"buses": 0, "branches": 0},
            "focus_ids": [], "overlay": None})
```

- [ ] **Step 2: Verify red.** Run only new validator and route tests; expect missing module/route.
- [ ] **Step 3: Implement normalization.** Whitelist fields and exact schema, bound UTF-8 payload to 250 KiB, use `math.isfinite`, validate allowed branch kinds and overlay metric/unit/value IDs. Never pass raw authority documents through.
- [ ] **Step 4: Extend `PreparedWorker` with optional `network_reader`.** After `answer_committed`, call it once for that ordinal and emit `network_view` if valid. A projection failure is observational: log a bounded warning, keep the committed answer, and do not make the run fail. Permit the new frame kind in the protocol and session reader; the existing ledger stores its ordered event.

```python
@dataclass(frozen=True, slots=True)
class PreparedWorker:
    application: _IncrementalApplication
    run_id: str
    evidence_reader: Callable[[str], object | None]
    network_reader: Callable[[int], Mapping[str, object] | None] | None = None
```

- [ ] **Step 5: Add the read-only route.** Search the persisted session events for the requested `network_view` ordinal, verify session exists, and return the view with the existing auth/CORS/no-store middleware. Validate ordinal range 1–3 and response bound.
- [ ] **Step 6: Verify focused Python tests and commit named files.** Check that a projection error does not alter `answer_committed` or the two-field grid CLI output.

### Task 3: Registered authority projections for both application workers

**Files:**
- Modify: `packages/grid-agent/src/grid_agent/worker.py`, `validation/run.py`, `packages/pypsa-agent/src/pypsa_agent/worker.py`
- Test: `packages/grid-agent/tests/test_worker_network_view.py`, `packages/pypsa-agent/tests/test_worker_network_view.py`

**Interfaces:**
- Consumes: prepared Domain Pack executors and current-run `context_ref`/`model_ref` from the exact registered case.
- Produces: `PreparedWorker.network_reader(ordinal)` returning the Task 2 schema.

- [ ] **Step 1: Write failing domain tests.** For IEEE-39, assert real bus/branch endpoints, model revision, the line-11/17 focus at the registered step, and no numerical overlay before an admitted per-element result. For PyPSA, assert six-bus, SciGRID-DE, and AC/DC topologies come from `model.topology`, preserve `coordinate_status`/omitted counts, and never show a dispatch value before the dispatch turn.
- [ ] **Step 2: Verify red** with only the new domain test files.
- [ ] **Step 3: Expose the grid scripted transport to its worker during execution.** Add an optional `on_transport` callback in `validation.run.execute_application_case`, called after transport construction. Give the worker a read-only `current_context_ref` property. After first committed turn, call `prepared.bindings['grid'].endpoint.executor.invoke('model.dataset.query', ...)` for `network.buses` and `network.branches`, paging in bounded 50-row slices; convert only the schema-described `index`, `name`, `kind`, `from_bus_index`, and `to_bus_index` fields. Require the same `context_ref` and `revision_ref` on all pages. Stop at 50 buses/100 branches and count omissions. For the ranking/voltage overlay, use only the exact current turn's admitted authority result and explicitly mapped per-element fields.

```python
executor = prepared.bindings["grid"].endpoint.executor
buses_page = executor.invoke("model.dataset.query", {
    "context_ref": context_ref, "dataset": "network.buses",
    "select": ["index", "name"], "offset": 0, "limit": 50,
})
branches_page = executor.invoke("model.dataset.query", {
    "context_ref": context_ref, "dataset": "network.branches",
    "select": ["index", "kind", "name", "from_bus_index", "to_bus_index"],
    "offset": 0, "limit": 50,
})
assert buses_page["revision_ref"] == branches_page["revision_ref"]
```

- [ ] **Step 4: Build PyPSA view through the source binding.** Use the current registered `model_ref` from `CaseProvider`. Invoke `model.topology` through `prepared.bindings['source'].endpoint.executor` when its result is not already present for the same revision. Convert the bounded buses/lines/links/transformers; carry the authority's coordinate-quality and omission labels. Map `top_line_loading` only from a committed dispatch result for the matching model revision and current ordinal; a ranking gives partial coverage.
- [ ] **Step 5: Verify focused tests and commit named files.** Probe all five registered cases without a Provider request. Ensure an unsupported metric yields topology with neutral color, not a fabricated value.

### Task 4: Interactive network canvas and light visual system

**Files:**
- Create: `packages/capstone-app/src/NetworkView.tsx`, `networkLayout.ts`, `NetworkView.test.tsx`
- Modify: `packages/capstone-app/src/types.ts`, `api.ts`, `App.tsx`, `styles.css`, `App.test.tsx`

**Interfaces:**
- Consumes: Task 2 `/network?ordinal=N` and sequenced `network_view` events.
- Produces: diagram with `focusIds`, `overlay`, zoom/pan/fit/return-to-task controls and provenance/coverage labels.

- [ ] **Step 1: Write failing layout and component tests.** The deterministic layout gives finite positions to all visible buses, preserves distinct provided coordinates, fits within SVG viewBox, and does not infer geography from schematic positions. Verify pan/zoom bounds, fit, task focus, selected historical step, partial overlay legend, and neutral missing values.

```ts
expect(layoutNetwork(view).every((bus) => Number.isFinite(bus.x) && Number.isFinite(bus.y))).toBe(true)
expect(screen.getByRole('button', { name: '回到当前任务' })).toBeTruthy()
expect(screen.getByText('仅对 3 条有结果的线路着色')).toBeTruthy()
```

- [ ] **Step 2: Verify red** with focused Vitest.
- [ ] **Step 3: Implement typed API and event integration.** Fetch the latest available view after a `network_view` event, validate schema/model/ordinal before storing it, and retain historical ordinal views. Clear the set when session or case changes. Clicking a timeline item selects its view and focuses its registered IDs; lifecycle transitions focus the current step once. A missing projection is visibly unavailable without blocking answers.
- [ ] **Step 4: Implement SVG interaction.** Render branches before buses with accessible titles; support pointer drag, wheel zoom, keyboard/button zoom, fit-all and task-focus. Recenter on a new step selection or commit, and keep manual navigation until the next transition. Limit zoom to a useful fixed interval such as `0.6–4`, clamp the view to the canvas, and respect reduced motion.
- [ ] **Step 5: Replace the dark palette and tiny body styles.** Use shared CSS tokens for warm light background, white cards, ink text and teal accent. Set instruction, answer, report, case summary, detail and control text to at least 14 px; use 15–16 px for primary reading. Keep only supplementary eyebrows and short IDs below 14 px. Put the diagram in a white card next to the timeline on wide screens and before it on mobile.
- [ ] **Step 6: Verify focused Vitest, TypeScript and production build; commit named files.** Inspect desktop and 390 px layouts in a browser, including keyboard focus and no horizontal overflow.

### Task 5: Operational acceptance and documentation

**Files:**
- Modify: `README.md`, `README.zh-CN.md`, `docs/RUNBOOK.md`, `docs/status/CURRENT-STATE.md`, `docs/status/JOURNAL.md`

**Interfaces:** The existing Compose/Vercel/Cloud Run/Railway settings remain unchanged.

- [ ] **Step 1: Update bilingual product notes and runbook.** Explain manual/automatic modes, stop semantics, model-only versus current-run coloring, schematic/truncated topologies, and diagram controls. Keep English and Chinese shared facts aligned.
- [ ] **Step 2: Run focused backend/App tests and `make doctor`.** Run repository-wide gates only if focused coverage leaves a concrete cross-package regression risk; do not invoke billed Provider validation.
- [ ] **Step 3: Rebuild the local backend image, start Compose, and run one pandapower and one PyPSA registered case through the App.** Confirm ordered three turns, report/evidence, network view, per-step focus and any admitted overlay; inspect desktop and 390 px viewport. Verify same API image roles and Vite production build.
- [ ] **Step 4: Check source hygiene.** Run `git diff --check`, `git status --short`, local links, and `test -L CLAUDE.md`; confirm `.codex/config.toml` remains untouched and no ignored secrets entered the image or repository.
- [ ] **Step 5: Commit only task paths, journal the result, and update the live checkpoint if this changes recovery boundaries.**
