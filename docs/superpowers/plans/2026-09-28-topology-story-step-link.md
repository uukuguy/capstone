# Topology Story Step Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one validated post-run topology story with cumulative per-step snapshots, optionally selected by a bounded LLM planner, and let the App replay those snapshots from the completed run.

**Architecture:** A neutral Kernel completion hook exposes the already-running provider session to an injected presentation projector without adding topology semantics to the Kernel. Domain adapters build authority-backed candidate directories and deterministic snapshots; the capstone worker validates and emits a replayable story before `completed`; the Host API and App read and select the persisted story after completion.

**Tech Stack:** Python 3.11 packages and pytest; strict JSON-lines worker protocol; FastAPI host API; React + TypeScript Vite App; existing authority result/evidence admission and network diagram validators.

## Global Constraints

- Preserve `Application -> Domain Pack -> Kernel -> registered Authority` ownership and dependency direction.
- LLM output may select only bounded candidate keys; authority owns topology, coordinates, metrics, result references, and evidence.
- Keep the pandapower compatibility stdout envelope exactly one JSON object with `question_id` and `answer_output`.
- Keep `GET /api/v1/sessions/{session_id}/network?ordinal=N` unchanged and add a separate authenticated story endpoint.
- Generate the story once after the final answer; App must not refresh topology while a step is executing.
- A malformed, unavailable, or timed-out planner must fall back without failing answer submission, report generation, or session completion.
- Preserve the untracked `.codex/` directory and unrelated working-tree edits; stage only task-owned files.
- Use current-run admitted refs and matching authority revisions; never infer electrical values from answer prose.

---

## Task 1: Add the neutral completion projection hook

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runtime_protocols.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runner.py`
- Modify: `packages/capability-agent-kernel/tests/application/test_runner.py`
- Test: `packages/capability-agent-kernel/tests/application/test_completion_projection.py`

**Interfaces:**
- Consumes: existing `ApplicationRequest`, `PreparedApplicationRuntime`, `ProviderSession`, `ApplicationWorkspace`, `ApplicationContextStore`, and `FinalizedTurn`.
- Produces: `CompletionProjectionContext`, `CompletionProjector`, and `ApplicationOutcome.completion_projection` for worker-owned story assembly.

- [ ] **Step 1: Write failing hook contract tests**

Create `test_completion_projection.py` with a fake provider and a projector that records invocation order:

```python
def test_completion_projector_runs_after_last_committed_turn_before_provider_stop(profile, tmp_path):
    calls: list[str] = []

    class Provider:
        def start(self):
            calls.append("start")

        def prompt_and_wait(self, question, **kwargs):
            calls.append(f"prompt:{question}")
            return "answer"

        def stop(self):
            calls.append("stop")

    def project(context):
        calls.append(f"project:{len(context.completed_answers)}")
        assert context.request.response_mode == "text"
        assert context.provider is not None
        return {"schema": "test-projection/1.0", "steps": len(context.completed_answers)}

    application = AgentApplication(
        profile=profile,
        provider=Provider(),
        workspace_root=tmp_path,
        completion_projector=project,
    )
    outcome = application.run(ApplicationRequest("fixture", ("one", "two")))

    assert outcome.status == "completed"
    assert outcome.completion_projection == {"schema": "test-projection/1.0", "steps": 2}
    assert calls[-2:] == ["project:2", "stop"]
```

Add a second test asserting a projector exception produces a completed outcome with `completion_projection is None` and a bounded `completion_projection_unavailable` diagnostic.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
pytest -q packages/capability-agent-kernel/tests/application/test_completion_projection.py
```

Expected: FAIL because the constructor, context type, outcome field, and invocation path do not exist.

- [ ] **Step 3: Implement the neutral hook**

Add the following types to `runtime_protocols.py` without importing any domain package:

```python
@dataclass(frozen=True, slots=True)
class CompletionProjectionContext:
    request: ApplicationRequest
    prepared: PreparedApplicationRuntime
    bindings: Mapping[str, object]
    workspace: ApplicationWorkspace | None
    store: ApplicationContextStore | None
    completed_answers: tuple[FinalizedTurn, ...]
    provider: ProviderSession | None


class CompletionProjector(Protocol):
    def __call__(self, context: CompletionProjectionContext) -> object | None: ...
```

Import the types under `TYPE_CHECKING` where needed to keep the runtime module dependency-neutral. Add `completion_projector: CompletionProjector | None = None` to `AgentApplication.__init__`, retain it on the instance, and add `completion_projection: object | None = None` at the end of `ApplicationOutcome` with a default.

Immediately after the final turn loop and before report publication, build `CompletionProjectionContext` and invoke the callback once. Catch ordinary exceptions, record `completion_projection_unavailable`, and continue with `completion_projection = None`; do not catch `BaseException`. Include the value in both completed and failed `ApplicationOutcome` construction paths.

- [ ] **Step 4: Run the focused tests and the existing runner tests**

Run:

```bash
pytest -q packages/capability-agent-kernel/tests/application/test_completion_projection.py packages/capability-agent-kernel/tests/application/test_runner.py
```

Expected: PASS, with no change to existing answer or report behavior.

- [ ] **Step 5: Commit the Kernel hook**

```bash
git add packages/capability-agent-kernel/src/capability_agent/application/runtime_protocols.py \
  packages/capability-agent-kernel/src/capability_agent/application/runner.py \
  packages/capability-agent-kernel/tests/application/test_completion_projection.py \
  packages/capability-agent-kernel/tests/application/test_runner.py
git commit -m "feat: add neutral completion projection hook"
```

## Task 2: Implement the validated topology story model and merger

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/network_story.py`
- Create: `packages/capstone-agent/tests/test_network_story.py`
- Modify: `packages/capstone-agent/src/capstone_agent/network_diagram.py`

**Interfaces:**
- Consumes: normalized `NetworkDiagram`, admitted `NetworkView`/`NetworkLayer` data, candidate-key plans, and ordered completed-step records.
- Produces: `normalize_network_story(value, admitted_refs_by_ordinal)`, `build_cumulative_story(diagram, step_inputs, plan)`, and `TopologyPlanner` / `TopologyPlan` structural contracts.

- [ ] **Step 1: Write failing story validation and merge tests**

Add fixtures for one three-bus diagram, two result refs, and three step inputs. Cover:

```python
def test_story_keeps_one_diagram_and_accumulates_prior_focus():
    story = build_cumulative_story(diagram(), step_inputs(), valid_plan())
    assert story["schema"] == "capstone-network-story/1.0"
    assert story["steps"][1]["current_focus_ids"] == ["bus:2"]
    assert story["steps"][1]["history_focus_ids"] == ["line:1"]


def test_story_rejects_foreign_overlay_reference():
    value = story_with_overlay_source("result:foreign")
    with pytest.raises(ValueError, match="admitted"):
        normalize_network_story(value, {1: ("result:step-1",)})


def test_story_drops_unknown_plan_key_and_uses_fallback():
    story = build_cumulative_story(diagram(), step_inputs(), plan_with_unknown_key())
    assert story["plan_source"] == "fallback"
    assert story["steps"][0]["current_focus_ids"] == ["line:1"]
```

Also test that values, coordinates, and result refs in a plan object are ignored, and that incompatible metrics are not carried forward.

- [ ] **Step 2: Run the new tests and verify failure**

```bash
pytest -q packages/capstone-agent/tests/test_network_story.py
```

Expected: FAIL because the story module and schema do not exist.

- [ ] **Step 3: Implement strict normalization and cumulative merge**

Define bounded typed aliases and functions with these signatures:

```python
class TopologyPlanner(Protocol):
    def plan(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


def normalize_network_story(
    value: object, *, admitted_refs_by_ordinal: Mapping[int, Sequence[str]],
) -> dict[str, Any]: ...


def build_cumulative_story(
    diagram: Mapping[str, Any],
    step_inputs: Sequence[Mapping[str, object]],
    plan: Mapping[str, object] | None,
) -> dict[str, Any]: ...
```

Reuse `normalize_network_diagram` and `normalize_network_layer` rather than duplicating their identity and metric rules. The merger must build `history_focus_ids` from earlier validated selections, prefer the current ordinal's compatible overlay, and carry forward only the last overlay with the same metric and diagram revision. Limit focus IDs to 20 per existing layer bounds and preserve deterministic ordering.

Add a `build_fallback_plan(candidate_directory_by_step)` helper that selects the first three authority-ranked candidates per step and returns the same candidate-key shape as an LLM plan with `plan_source="fallback"`.

- [ ] **Step 4: Run focused story and existing diagram tests**

```bash
pytest -q packages/capstone-agent/tests/test_network_story.py packages/capstone-agent/tests/test_network_diagram.py packages/capstone-agent/tests/test_network_view.py
```

Expected: PASS.

- [ ] **Step 5: Commit the story model**

```bash
git add packages/capstone-agent/src/capstone_agent/network_story.py \
  packages/capstone-agent/src/capstone_agent/network_diagram.py \
  packages/capstone-agent/tests/test_network_story.py
git commit -m "feat: add cumulative topology story contract"
```

## Task 3: Add pandapower and PyPSA candidate/fallback adapters

**Files:**
- Create: `packages/grid-agent/src/grid_agent/network_story.py`
- Create: `packages/grid-agent/tests/test_network_story.py`
- Create: `packages/pypsa-agent/src/pypsa_agent/network_story.py`
- Create: `packages/pypsa-agent/tests/test_network_story.py`
- Modify: `packages/grid-agent/src/grid_agent/worker.py`
- Modify: `packages/pypsa-agent/src/pypsa_agent/worker.py`
- Modify: `packages/grid-agent/src/grid_agent/network_view.py`
- Modify: `packages/pypsa-agent/src/pypsa_agent/network_view.py`

**Interfaces:**
- Consumes: domain executor, registered case ID, current model/context revision, committed result refs, per-step authority call records, and optional `TopologyPlanner`.
- Produces: `build_grid_story(...)` and `build_pypsa_story(...)` callbacks matching `CompletionProjector`, each returning a normalized `capstone-network-story/1.0` mapping.

- [ ] **Step 1: Write failing adapter tests**

For pandapower, use the existing fake executor and ranked `result.branches.rank` fixture. For PyPSA, use the existing `TopologyExecutor` and dispatch fixture. Assert candidate directories contain only registered IDs and admitted refs, that fallback reproduces the current final focus behavior, and that a planner selecting an allowed candidate changes focus without changing overlay values.

Example test shape:

```python
def test_grid_story_planner_can_change_focus_but_not_values(fake_executor):
    planner = StaticPlanner({"steps": [{"ordinal": 3, "focus_candidate_keys": ["c2"],
                                         "primary_candidate_key": "c2",
                                         "presentation": "highlight"}]})
    story = build_grid_story(fake_executor, context_ref="context:1", case_id="pandapower-scripted-task",
                             completed_steps=grid_steps(), planner=planner)
    assert story["steps"][2]["current_focus_ids"] == ["line:17"]
    assert story["steps"][2]["overlay"]["values"][0]["value"] == 83.2
```

- [ ] **Step 2: Run adapter tests and verify failure**

```bash
pytest -q packages/grid-agent/tests/test_network_story.py packages/pypsa-agent/tests/test_network_story.py
```

Expected: FAIL because adapter modules and completion callback wiring do not exist.

- [ ] **Step 3: Implement domain-owned candidate directories and fallback**

Implement `build_grid_story` and `build_pypsa_story` with explicit bounded inputs:

```python
def build_grid_story(
    *, executor: NetworkExecutor, context_ref: str, case_id: str,
    completed_steps: Sequence[Mapping[str, object]], planner: TopologyPlanner | None,
) -> dict[str, object]: ...


def build_pypsa_story(
    *, executor: DiagramExecutor, model_ref: str, model_id: str, case_id: str,
    completed_steps: Sequence[Mapping[str, object]], planner: TopologyPlanner | None,
) -> dict[str, object]: ...
```

Build candidate keys deterministically (`c1`, `c2`, …) from authority-returned ranked elements. Pass only bounded summaries and candidate metadata to the planner. Resolve planner keys back through the candidate map, discard invalid selections, and call `build_cumulative_story` with authority values. Reuse the existing case restrictions and diagram cache. Do not parse element IDs or numerical values from `answer_output`.

In each worker `_prepare`, create a completion projector closure that receives `CompletionProjectionContext`, reconstructs ordered per-step records from the existing workspace/context events, calls the adapter, and returns the normalized story. For scripted-demo mode pass `planner=None`; for provider mode construct a `ProviderTopologyPlanner` around the context's provider and use a five-second timeout wrapper. If the provider cannot accept the planning prompt, return `None` so the adapter selects fallback.

- [ ] **Step 4: Run domain-focused tests and existing worker tests**

```bash
pytest -q packages/grid-agent/tests/test_network_story.py packages/pypsa-agent/tests/test_network_story.py \
  packages/grid-agent/tests/test_worker_network_view.py packages/pypsa-agent/tests/test_worker_network_view.py \
  packages/capstone-agent/tests/test_registered_workers.py
```

Expected: PASS; existing per-step projections remain unchanged.

- [ ] **Step 5: Commit the domain adapters**

```bash
git add packages/grid-agent/src/grid_agent/network_story.py packages/grid-agent/src/grid_agent/network_view.py \
  packages/grid-agent/src/grid_agent/worker.py packages/grid-agent/tests/test_network_story.py \
  packages/pypsa-agent/src/pypsa_agent/network_story.py packages/pypsa-agent/src/pypsa_agent/network_view.py \
  packages/pypsa-agent/src/pypsa_agent/worker.py packages/pypsa-agent/tests/test_network_story.py
git commit -m "feat: build domain topology stories"
```

## Task 4: Extend worker protocol, ledger replay, and Host API

**Files:**
- Modify: `packages/capstone-agent/src/capstone_agent/protocol.py`
- Modify: `packages/capstone-agent/src/capstone_agent/session.py`
- Modify: `packages/capstone-agent/src/capstone_agent/worker.py`
- Modify: `packages/capstone-agent/src/capstone_agent/host_api.py`
- Modify: `packages/capstone-agent/tests/test_worker.py`
- Modify: `packages/capstone-agent/tests/test_network_api.py`
- Create: `packages/capstone-agent/tests/test_network_story_api.py`

**Interfaces:**
- Consumes: `ApplicationOutcome.completion_projection` and normalized story output.
- Produces: strict `network_story` session event and `GET /api/v1/sessions/{session_id}/network-story`.

- [ ] **Step 1: Write failing protocol and API tests**

Add a protocol test that accepts a valid story frame and rejects an unknown story field or a story whose diagram revision does not match a step. Add API tests asserting the endpoint returns 404/409 before completion, returns the persisted story after completion, and returns the same bytes on repeated reads.

```python
def test_network_story_endpoint_returns_persisted_story(authenticated_client, completed_session):
    first = authenticated_client.get(f"/api/v1/sessions/{completed_session}/network-story")
    second = authenticated_client.get(f"/api/v1/sessions/{completed_session}/network-story")
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["schema"] == "capstone-network-story/1.0"
```

- [ ] **Step 2: Run protocol/API tests and verify failure**

```bash
pytest -q packages/capstone-agent/tests/test_network_story_api.py packages/capstone-agent/tests/test_network_api.py
```

Expected: FAIL because the event kind, payload validation, worker emission, and route do not exist.

- [ ] **Step 3: Implement event validation and replay**

Add `network_story` to `_PAYLOAD_FIELDS`, required fields, and `Frame.__post_init__`; validate with `normalize_network_story`. After `prepared.application.run_stream` returns completed, read `outcome.completion_projection`, emit exactly one `network_story` frame before `completed` when it is valid, and emit `network_story_unavailable` metadata only when no valid story exists. Keep evidence reads available after completion.

In `host_api.py`, scan ledger events once, normalize the stored story, and return it only when the authenticated session is completed. Never regenerate it. Add the route to the existing bounded response behavior and ensure foreign session IDs remain rejected by `get_session`.

- [ ] **Step 4: Run worker/API and protocol regression tests**

```bash
pytest -q packages/capstone-agent/tests/test_worker.py packages/capstone-agent/tests/test_network_api.py \
  packages/capstone-agent/tests/test_network_story_api.py packages/capstone-agent/tests/test_protocol.py
```

Expected: PASS, including existing frame ordering and current `/network` behavior.

- [ ] **Step 5: Commit the worker and API contract**

```bash
git add packages/capstone-agent/src/capstone_agent/protocol.py packages/capstone-agent/src/capstone_agent/session.py \
  packages/capstone-agent/src/capstone_agent/worker.py packages/capstone-agent/src/capstone_agent/host_api.py \
  packages/capstone-agent/tests/test_worker.py packages/capstone-agent/tests/test_network_api.py \
  packages/capstone-agent/tests/test_network_story_api.py
git commit -m "feat: expose replayable topology stories"
```

## Task 5: Load and render story snapshots in the App

**Files:**
- Modify: `packages/capstone-app/src/types.ts`
- Modify: `packages/capstone-app/src/api.ts`
- Modify: `packages/capstone-app/src/App.tsx`
- Modify: `packages/capstone-app/src/NetworkView.tsx`
- Modify: `packages/capstone-app/src/networkValidation.ts`
- Modify: `packages/capstone-app/src/App.test.tsx`
- Modify: `packages/capstone-app/src/NetworkView.test.tsx`
- Modify: `packages/capstone-app/src/networkValidation.test.ts`
- Create: `packages/capstone-app/src/networkStoryFixture.ts`

**Interfaces:**
- Consumes: authenticated `GET /network-story` response and existing `NetworkDiagram` renderer.
- Produces: local story state, selected ordinal, and current/history focus rendering without new browser authority calls.

- [ ] **Step 1: Write failing TypeScript tests**

Add a fixture with a shared diagram and three snapshots. Test that:

```tsx
it('loads story only after completion and selects the final step', async () => {
  renderWorkspace({ client, app, caseCard })
  expect(client.networkStory).not.toHaveBeenCalled()
  emitCompleted()
  await waitFor(() => expect(client.networkStory).toHaveBeenCalledTimes(1))
  expect(screen.getByText('截至步骤 3')).toBeTruthy()
})

it('switches the topology to the selected cumulative snapshot', async () => {
  click(screen.getByRole('button', { name: '步骤 1' }))
  expect(screen.getByTestId('network-current-focus')).toHaveTextContent('line:11')
  expect(screen.getByTestId('network-history-focus')).toHaveTextContent('')
})
```

Update the NetworkView test to assert current-focus and history-focus classes differ and that only the selected snapshot overlay is colored.

- [ ] **Step 2: Run App tests and verify failure**

```bash
npm test --prefix packages/capstone-app -- --run src/App.test.tsx src/NetworkView.test.tsx src/networkValidation.test.ts
```

Expected: FAIL because `NetworkStory`, `networkStory`, and selected snapshot state do not exist.

- [ ] **Step 3: Implement client types, API method, and validation**

Add `NetworkStory`, `NetworkStoryStep`, and `NetworkStoryPlanSource` types matching the Python contract. Implement:

```ts
type NetworkStoryClient = {
  networkStory(sessionId: string, signal?: AbortSignal): Promise<NetworkStory>
}
```

using the existing bounded GET retry helper. Add `parseNetworkStory(raw: unknown): NetworkStory | null` that validates the shared diagram with `parseNetworkDiagram`, step ordinals, focus IDs, overlay refs, and `plan_source`; reject any story whose step diagram identity or model revision differs.

- [ ] **Step 4: Implement post-completion loading and local selection**

In `CaseWorkspace`, add `networkStory` and `selectedNetworkOrdinal` state. Clear both in `clearRun`. In the `completed` event branch, call `client.networkStory(sessionId)` exactly once, parse it, store it, and select the greatest ordinal. Do not call it from `answer_committed` or while executing. On restore/reconnect, load it once if status is already completed.

Pass the selected `NetworkStoryStep` plus the shared diagram into `RunPanel` and `NetworkView`. Keep preview rendering when no story exists. Add a compact step selector near the topology heading using already completed ordinals.

- [ ] **Step 5: Implement current/history focus rendering**

Extend `NetworkView` props with `storyStep?: NetworkStoryStep | null` and render:

- current focus IDs with the existing strong focus color;
- history focus IDs with a muted outline/class and no claim of abnormality;
- only the selected step's `overlay` values using the existing metric-specific color scale;
- a bounded label `截至步骤 N` and fallback/partial status when applicable.

Do not alter geometry or coordinates in the browser.

- [ ] **Step 6: Run App tests and build**

```bash
npm test --prefix packages/capstone-app -- --run src/App.test.tsx src/NetworkView.test.tsx src/networkValidation.test.ts
npm run build --prefix packages/capstone-app
```

Expected: PASS and a production build with no TypeScript errors.

- [ ] **Step 7: Commit the App integration**

```bash
git add packages/capstone-app/src/types.ts packages/capstone-app/src/api.ts \
  packages/capstone-app/src/App.tsx packages/capstone-app/src/NetworkView.tsx \
  packages/capstone-app/src/networkValidation.ts packages/capstone-app/src/networkStoryFixture.ts \
  packages/capstone-app/src/App.test.tsx packages/capstone-app/src/NetworkView.test.tsx \
  packages/capstone-app/src/networkValidation.test.ts
git commit -m "feat: replay topology story in app"
```

## Task 6: Run integrated acceptance and record evidence

**Files:**
- Modify: `docs/status/JOURNAL.md` (append-only entries only)
- Modify: `docs/status/RESUME-NEXT-SESSION.md` (checkpoint only if the active session continues)
- Test: `packages/capstone-agent/tests/test_registered_workers.py`
- Test: `validation/` provider-free application acceptance fixtures

**Interfaces:**
- Consumes: completed Tasks 1–5 and existing registered pandapower/PyPSA cases.
- Produces: verified story replay evidence and a durable journal entry.

- [ ] **Step 1: Run focused Python integration tests**

```bash
pytest -q packages/capability-agent-kernel/tests/application/test_completion_projection.py \
  packages/capstone-agent/tests/test_network_story.py packages/capstone-agent/tests/test_network_story_api.py \
  packages/grid-agent/tests/test_network_story.py packages/pypsa-agent/tests/test_network_story.py
```

Expected: PASS with planner success, malformed-plan fallback, and replay equality covered.

- [ ] **Step 2: Run the provider-free registered application acceptance**

```bash
make validate-application
```

Expected: both pandapower scripted cases complete, retain current-run evidence, and expose a valid story without an external Provider.

- [ ] **Step 3: Run repository gates required for the changed scope**

```bash
make doctor
make test-e2e
make validate
git diff --check
```

Expected: all supported offline gates pass; any known unrelated root pytest collection issue is recorded separately rather than treated as a feature regression.

- [ ] **Step 4: Perform one authorized Provider browser check**

Start the App at `http://127.0.0.1:5173/`, run one registered PyPSA case, verify that the topology stays unchanged while steps execute, then verify that completion loads one story and clicking steps 1–3 changes current/history emphasis without changing the shared geometry.

- [ ] **Step 5: Journal the verified result**

Append one line to `docs/status/JOURNAL.md` with the completed test gates and commit hash. If work continues past the recovery threshold, refresh `docs/status/RESUME-NEXT-SESSION.md` as an active checkpoint; do not rewrite `CURRENT-STATE.md` with session narration.

## Self-review checklist

- [x] Spec sections 1–12 map to Tasks 1–6.
- [x] Every new public schema has a validator test and replay test.
- [x] The Kernel hook is domain-neutral and does not import grid or PyPSA code.
- [x] LLM output cannot introduce topology, coordinates, values, or refs.
- [x] Existing single-step API and compatibility stdout contracts are preserved.
- [x] Planner failure is explicitly non-fatal and covered by tests.
- [x] No `TODO`, `TBD`, `FIXME`, or unspecified “handle appropriately” step remains.
