# M10 Registered PyPSA Topology Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Emit and render an Authority-owned topology diagram for the active registered PyPSA model through the existing Thread network contracts.

**Architecture:** Add an optional application-owned network projection provider to the prepared Thread runtime. The neutral Harness validates the provider's shared `capstone-network-view/2.0` result and persists ordered `network_diagram` and `network_layer` events. The PyPSA application supplies a provider bound to the prepared Authority model reference and Thread revision; the Web projection store consumes the replayed events and renders the matching active model.

**Tech Stack:** Python 3.12, pytest, dataclass/protocol seams, PostgreSQL Thread ledger, TypeScript/React, Vitest, Vite, existing `capstone-network-diagram/1.0` and `capstone-network-view/2.0` contracts.

## Global Constraints

- Authority and Domain Pack own PyPSA semantics and `operator.diagram`; the Kernel never imports PyPSA or receives raw Network objects.
- The provider accepts only a prepared model context and Authority model reference; it does not accept a case ID or caller-selected endpoint.
- The public diagram revision must equal the active Thread `model_revision`; Authority `model_ref` is checked internally and is never emitted as a substitute.
- Missing, malformed, oversized, or revision-mismatched topology emits unavailable state and does not change answer admission.
- Web focus and overlays require matching model ID, model revision, diagram reference, and admitted result references.
- Write each production change after a test has failed for the intended missing behavior.
- Stage only M10-owned files. Preserve existing state-file modifications.

---

### Task 1: Add the neutral prepared-runtime network projection seam

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/thread_network.py`
- Modify: `packages/capstone-agent/src/capstone_agent/harness.py`
- Modify: `packages/capstone-agent/src/capstone_agent/thread_application.py`
- Modify: `packages/capstone-agent/src/capstone_agent/kernel_pi_session.py`
- Test: `packages/capstone-agent/tests/test_thread_network.py`
- Test: `packages/capstone-agent/tests/test_harness.py`
- Test: `packages/capstone-agent/tests/test_thread_application.py`

**Interfaces:**
- Produce `ThreadNetworkProjectionProvider.project(claim, result_refs, evidence_refs, tool_events) -> Mapping[str, object] | None`.
- Produce `ThreadApplicationAssembly.network_projection_factory`, an optional callable receiving `(AttemptClaim, PreparedModelCapabilityContext)` and returning a provider.
- Produce `HarnessPiClient.network_projection(...)` and a neutral helper that returns normalized diagram/layer documents.
- Consume the existing `normalize_network_projection` and `AttemptClaim` contracts.

- [x] **Step 1: Write the failing neutral provider tests.**

Add tests that define a provider returning a valid `capstone-network-view/2.0` document and assert:

```python
def test_harness_pi_client_exposes_bounded_network_projection():
    provider = StaticNetworkProvider(valid_projection())
    client = HarnessPiClient(
        FakePiSession(), network_projection_provider=provider,
    )
    projection = client.network_projection(
        claim, ("result:sha256:" + "a" * 64,), (), (),
    )
    assert projection["schema"] == "capstone-network-view/2.0"

def test_network_projection_rejects_foreign_revision_and_returns_none():
    provider = StaticNetworkProvider(foreign_revision_projection())
    client = HarnessPiClient(FakePiSession(), network_projection_provider=provider)
    assert client.network_projection(claim, (), (), ()) is None
```

Add an assembly test that passes `network_projection_factory` through `from_prepared_authority` and verifies the factory receives the claimed immutable context.

- [x] **Step 2: Run the focused tests and verify the expected RED state.**

Run:

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_network.py packages/capstone-agent/tests/test_harness.py packages/capstone-agent/tests/test_thread_application.py -q
```

Expected: collection or assertion failures because `HarnessPiClient` and `ThreadApplicationAssembly` do not accept the new provider seam.

- [x] **Step 3: Implement the neutral provider contract.**

Create `thread_network.py` with a runtime-checkable protocol and bounded adapter:

```python
class ThreadNetworkProjectionProvider(Protocol):
    def project(
        self,
        claim: AttemptClaim,
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        tool_events: tuple[Mapping[str, object], ...],
    ) -> Mapping[str, object] | None: ...
```

Add `normalize_thread_network_projection(value, claim, admitted_refs)` that calls `normalize_network_projection`, verifies `diagram.model.id == claim.model_context.model_id` and `diagram.model.revision == claim.model_context.model_revision`, and returns only the normalized `schema`, `ordinal`, `diagram`, and `layer` fields. Foreign or invalid values return `None` to the caller.

Extend `HarnessPiClient.__init__` with an optional provider and add `network_projection`; provider exceptions return `None`. Extend `PreparedApplicationPiRuntimeFactory` with `network_projection_factory`; prepare the provider from the exact `AttemptClaim` and `PreparedModelCapabilityContext` before constructing `HarnessPiClient`. Add the matching optional field and parameter to `ThreadApplicationAssembly.from_prepared_authority`.

- [x] **Step 4: Run the focused tests and verify GREEN.**

Run the same command. Expected: all new and existing Harness/application-composition tests pass.

- [x] **Step 5: Commit the neutral seam.**

```sh
git add packages/capstone-agent/src/capstone_agent/thread_network.py \
  packages/capstone-agent/src/capstone_agent/harness.py \
  packages/capstone-agent/src/capstone_agent/thread_application.py \
  packages/capstone-agent/src/capstone_agent/kernel_pi_session.py \
  packages/capstone-agent/tests/test_thread_network.py \
  packages/capstone-agent/tests/test_harness.py \
  packages/capstone-agent/tests/test_thread_application.py
git commit -m "feat: add Thread network projection seam"
```

---

### Task 2: Persist validated diagram and layer events from the Harness

**Files:**
- Modify: `packages/capstone-agent/src/capstone_agent/harness.py`
- Modify: `packages/capstone-agent/src/capstone_agent/protocol.py`
- Test: `packages/capstone-agent/tests/test_harness.py`
- Test: `packages/capstone-agent/tests/test_protocol.py`

**Interfaces:**
- Consume `HarnessPiClient.network_projection` from Task 1.
- Produce public runtime events `network_diagram` and `network_layer` after a completed Attempt.
- Produce `network_layer_unavailable` with an ordinal when the optional provider has no usable projection.

- [x] **Step 1: Write the failing event-order tests.**

Add a fake runtime with a provider and assert that `HarnessAttemptRunner.run` appends events in this order after the answer path:

```python
event_types = [event.event_type for event in service.events]
assert event_types[-3:] == [
    "network_diagram", "network_layer", "attempt_completed",
]
```

Add a failure test asserting a provider exception leaves `attempt_completed` intact and appends `network_layer_unavailable` with `ordinal == 1`. Add a protocol test that rejects a layer whose embedded `diagram_ref` or `model_revision` is malformed; add a sequence-level validation test for a layer whose identity does not match the preceding diagram.

- [x] **Step 2: Run tests and verify RED.**

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_harness.py packages/capstone-agent/tests/test_protocol.py -q
```

Expected: no network events are appended and the new protocol identity assertion fails.

- [x] **Step 3: Implement event persistence.**

After answer admission succeeds and before `finish_attempt`, call the optional runtime provider with the admitted references and observed tool events. Normalize the projection against the claimed model context. Append:

```python
service.append_runtime_event(
    claim, event_type="network_diagram",
    payload={"diagram": projection["diagram"]},
)
service.append_runtime_event(
    claim, event_type="network_layer",
    payload={"ordinal": projection["ordinal"], "layer": projection["layer"]},
)
```

If no provider or normalization result exists, append `network_layer_unavailable` with `{"ordinal": 1}` only when the application opted into the provider seam. Keep answer admission and terminal persistence authoritative. The provider projection is normalized through `normalize_network_layer` before append; frame validation checks self-contained layer identity fields, while sequence-level diagram/layer identity validation remains in the Thread event replay path.

- [x] **Step 4: Run tests and verify GREEN.**

Run the focused command from Step 2. Expected: event ordering, failure isolation, and identity checks pass.

- [x] **Step 5: Commit Harness event persistence.**

```sh
git add packages/capstone-agent/src/capstone_agent/harness.py \
  packages/capstone-agent/src/capstone_agent/protocol.py \
  packages/capstone-agent/tests/test_harness.py \
  packages/capstone-agent/tests/test_protocol.py
git commit -m "feat: persist Thread topology events"
```

---

### Task 3: Bind the PyPSA provider to the registered model context

**Files:**
- Modify: `packages/pypsa-agent/src/pypsa_agent/network_view.py`
- Modify: `packages/pypsa-agent/src/pypsa_agent/thread_capabilities.py`
- Modify: `packages/pypsa-agent/src/pypsa_agent/hosted.py`
- Test: `packages/pypsa-agent/tests/test_worker_network_view.py`
- Test: `packages/pypsa-agent/tests/test_hosted_thread.py`
- Test: `packages/pypsa-model-authority/tests/test_operator_diagram.py`

**Interfaces:**
- Consume the prepared `PreparedModelCapabilityContext` and the Task 1 provider factory.
- Produce `build_pypsa_thread_network_provider(context) -> ThreadNetworkProjectionProvider`.
- Produce a generic provider path that calls `operator.diagram` with the prepared Authority `context_ref`, independent of scripted case IDs.

- [x] **Step 1: Write the failing PyPSA provider tests.**

Add a provider-free unit test with a fake prepared source binding:

```python
provider = build_pypsa_thread_network_provider(
    context_with_binding(model_id="regional-six-bus",
                         model_revision="revision:sha256:" + "a" * 64,
                         context_ref="pypsa:regional-six-bus"),
)
projection = provider.project(claim, (), (), ())
assert projection["diagram"]["model"]["id"] == "regional-six-bus"
assert projection["diagram"]["model"]["revision"] == claim.model_context.model_revision
```

Add a test that the fake executor receives exactly `operator.diagram` and `{"model_ref": "pypsa:regional-six-bus"}`, and a test that an Authority response with a different `model_ref` is rejected. Add an integration assertion that `build_registered_pypsa_thread_application()` exposes a non-null provider factory.

- [x] **Step 2: Run tests and verify RED.**

```sh
uv run --project packages/pypsa-agent pytest packages/pypsa-agent/tests/test_worker_network_view.py packages/pypsa-agent/tests/test_hosted_thread.py -q
uv run --project packages/pypsa-model-authority pytest packages/pypsa-model-authority/tests/test_operator_diagram.py -q
```

Expected: the provider builder and application factory are missing.

- [x] **Step 3: Implement the PyPSA provider.**

Add a provider class in `pypsa_agent.network_view` that reads the selected prepared source binding executor, invokes `operator.diagram`, verifies the returned Authority `model_ref` equals the prepared binding `context_ref`, and builds a shared projection with:

- model ID from `context.model_context.model_id`;
- model revision from `context.model_context.model_revision`;
- source `pypsamodelctl`;
- Authority coordinate system, buses, and branches;
- ordinal `1`, empty focus IDs, empty next-focus IDs, and no overlay.

Pass a `network_projection_factory` through `build_pypsa_thread_application` and register it from `hosted.py`. Retrieve the prepared `AuthorityModelBinding` and source endpoint from the context-scoped prepared profile; do not cache across model contexts. Keep the existing case-specific `build_pypsa_network_view` path unchanged for compatibility.

- [x] **Step 4: Run tests and verify GREEN.**

Run both commands from Step 2. Expected: provider, authority, and existing case network tests pass.

- [x] **Step 5: Commit the PyPSA provider.**

```sh
git add packages/pypsa-agent/src/pypsa_agent/network_view.py \
  packages/pypsa-agent/src/pypsa_agent/thread_capabilities.py \
  packages/pypsa-agent/src/pypsa_agent/hosted.py \
  packages/pypsa-agent/tests/test_worker_network_view.py \
  packages/pypsa-agent/tests/test_hosted_thread.py \
  packages/pypsa-model-authority/tests/test_operator_diagram.py
git commit -m "feat: bind PyPSA topology to Thread model context"
```

---

### Task 4: Replay dynamic topology in the Thread API and Web model pane

**Files:**
- Modify: `packages/capstone-app/src/threadProjectionStore.ts`
- Modify: `packages/capstone-app/src/ThreadFixtureApp.tsx`
- Modify: `packages/capstone-app/src/ThreadModelPane.tsx`
- Modify: `packages/capstone-app/src/threadProtocol.ts`
- Modify: `packages/capstone-app/src/types.ts`
- Test: `packages/capstone-app/src/threadProjectionStore.test.ts`
- Test: `packages/capstone-app/src/NetworkView.test.tsx`
- Test: `packages/capstone-app/src/ThreadFixtureApp.test.tsx`
- Test: `packages/capstone-app/src/networkValidation.test.ts`

**Interfaces:**
- Consume replayed `network_diagram` and `network_layer` EventEnvelope payloads.
- Produce `ThreadProjectionState.networkView: DiagramNetworkView | null`.
- Produce model-pane rendering that prefers the matching event-backed diagram over a preview diagram.
- Preserve the existing `previewDiagram` fallback for legacy/case flows.

- [x] **Step 1: Write the failing Web tests.**

Add a projection-store fixture containing a `network_diagram` event and matching `network_layer` event. Assert:

```typescript
expect(store.state.networkView?.diagram.model.revision).toBe(snapshot.activeModelContext.modelRevision)
expect(store.state.networkView?.layer.diagram_ref).toBe(store.state.networkView?.diagram.ref)
```

Add a model-switch event followed by a diagram for the old revision and assert `networkView === null` until a matching new-revision diagram arrives. Add a render test that focus for an element absent from the dynamic diagram is refused and the diagram remains visible.

- [x] **Step 2: Run tests and verify RED.**

```sh
cd packages/capstone-app
npm test -- --run src/threadProjectionStore.test.ts src/ThreadFixtureApp.test.tsx src/NetworkView.test.tsx src/networkValidation.test.ts
```

Expected: TypeScript/state assertions fail because the store has no dynamic network view.

- [x] **Step 3: Implement replay and rendering.**

Extend the TypeScript network types and event parser with bounded `network_diagram` and `network_layer` payload parsing using the existing `parseNetworkView`/diagram validation rules. Track the current model-context diagram and layer in `ThreadProjectionStore.applyEvent`; clear them on `model_context_activated`, `model_context_reopened`, and `model_context_reverted`. Ignore events whose `modelContextId` or model revision does not equal the active context.

Pass the resulting `networkView` to `ThreadModelPane`. Select the event-backed diagram for the active page, retain the optional preview fallback, and build result overlays/focus only after checking model ID, model revision, diagram reference, and element membership. Historical pages render read-only and do not reuse the active dynamic diagram.

- [x] **Step 4: Run tests and verify GREEN.**

```sh
cd packages/capstone-app
npm test -- --run src/threadProjectionStore.test.ts src/ThreadFixtureApp.test.tsx src/NetworkView.test.tsx src/networkValidation.test.ts
npm run build
```

Expected: all selected tests and the production build pass.

- [x] **Step 5: Commit Web replay and rendering.**

```sh
git add packages/capstone-app/src/threadProjectionStore.ts \
  packages/capstone-app/src/ThreadFixtureApp.tsx \
  packages/capstone-app/src/ThreadModelPane.tsx \
  packages/capstone-app/src/threadProtocol.ts \
  packages/capstone-app/src/types.ts \
  packages/capstone-app/src/threadProjectionStore.test.ts \
  packages/capstone-app/src/NetworkView.test.tsx \
  packages/capstone-app/src/ThreadFixtureApp.test.tsx \
  packages/capstone-app/src/networkValidation.test.ts
git commit -m "feat: render replayed PyPSA topology in Thread"
```

---

### Task 5: Provider-free Thread and release verification

**Files:**
- Modify: `packages/capstone-agent/tests/test_thread_application.py`
- Modify: `packages/capstone-agent/tests/test_thread_postgres.py`
- Modify: `packages/capstone-agent/tests/test_thread_protocol.py`
- Modify: `packages/capstone-app/src/threadUiFixtures.ts` only if a bounded dynamic topology fixture is required
- Modify: `docs/superpowers/plans/2026-10-04-capstone-m10-pypsa-topology-provider.md` to mark completed items
- Test: existing provider-free and E2E suites

**Interfaces:**
- Consume Tasks 1–4 public contracts.
- Produce an end-to-end proof that a registered PyPSA model emits a replayable current-model diagram and that switching models replaces it without cross-revision focus.

- [x] **Step 1: Write the failing provider-free Thread regression.**

Add a deterministic prepared-context test that creates a Thread for `regional-six-bus`, runs one accepted Attempt with a scripted runtime, reads the event page, and asserts the event sequence contains matching `network_diagram` and `network_layer` documents. Add a second-context test that switches to another registered model and rejects the first model's diagram as active.

- [x] **Step 2: Run the regression and verify RED.**

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_application.py packages/capstone-agent/tests/test_thread_postgres.py packages/capstone-agent/tests/test_thread_protocol.py -q
```

Expected: the new topology event assertions fail before the integration wiring is complete.

- [x] **Step 3: Implement only test fixtures and plan checkboxes.**

Use the existing provider-free deterministic runtime and real registered model fixture. Do not add a second Authority, fake raw Network object, or case-specific shortcut. Update the M10 plan checkboxes only after the corresponding tests and code pass.

- [x] **Step 4: Run the complete verification gates.**

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests -q
uv run --project packages/pypsa-agent pytest packages/pypsa-agent/tests -q
uv run --project packages/pypsa-model-authority pytest packages/pypsa-model-authority/tests -q
cd packages/capstone-app && npm test -- --run && npm run build
cd ../..
make check-types-validation
make test-e2e
make capstone-local-rebuild
curl -fsS http://127.0.0.1:8767/health/ready
curl -fsSI http://127.0.0.1:5173/
git diff --check
```

Expected: all scoped Python tests pass with only the existing Starlette warning, App tests/build pass, Pyright reports zero errors, E2E and registered-worker gates pass, local rebuild reports healthy API/App and identical worker image digests.

- [x] **Step 5: Commit the final M10 verification record.**

```sh
git add packages/capstone-agent/tests/test_thread_application.py \
  packages/capstone-agent/tests/test_thread_postgres.py \
  packages/capstone-agent/tests/test_thread_protocol.py \
  packages/capstone-app/src/threadUiFixtures.ts \
  docs/superpowers/plans/2026-10-04-capstone-m10-pypsa-topology-provider.md
git commit -m "test: verify M10 topology provider end to end"
```

- [x] **Step 6: Journal each commit and update the active checkpoint.**

Append one concise entry to `docs/status/JOURNAL.md` for every implementation commit and rewrite `docs/status/RESUME-NEXT-SESSION.md` as an active checkpoint with the next M10 review action. Do not rewrite the structural snapshot with session narration.

