# Authoritative Network Diagrams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This session executes inline because the user already approved implementation and has not requested delegation.

**Goal:** Show one complete, professional, persistent network diagram per registered case, with historical step layers and per-case latest-run restoration.

**Architecture:** Each registered authority provides a private scalar operator diagram projection. The neutral session worker persists one base diagram per topology fingerprint and a small admitted layer per completed step. The App keeps latest session state per case, replays missed events on return, and renders authoritative coordinates with distinct electrical symbols.

**Tech Stack:** Python 3.12+ authority workers and FastAPI, PostgreSQL session ledger, React 19, TypeScript 7, SVG, Vitest, pytest.

## Global Constraints

- Preserve `question_id` and `answer_output` stdout, stderr diagnostics, and current-run evidence admission.
- The model-facing PyPSA `model.topology` remains limited to 50 buses; operator diagram operations are not offered to Pi/LLM.
- The operator diagram is bounded to 2,000 buses, 4,000 branches, and 2 MiB of serialized JSON. A model beyond bounds fails closed; no arbitrary first-N preview is labelled complete.
- SciGRID-DE must display all 585 buses, 852 lines, and 96 transformers at its PyPSA coordinates. IEEE-39 must display all 39 buses, 35 lines, and 11 transformers at its schematic coordinates.
- A case switch preserves its latest session, committed answers, selected completed step, detail tab, camera, and active automatic progression in the connected browser tab.
- The API/worker image and App contract remain identical on local Compose, Cloud Run, Railway, and Vercel. No remote map tiles or billed Provider validation.
- Preserve unrelated staged `.codex/config.toml` and ignored runtime/authentication state. Stage only task-owned paths.

---

## File structure

- `packages/pypsa-model-authority/src/pypsa_model_authority/operations.py`: private `operator.diagram` scalar read, separate from advertised capabilities.
- `packages/grid-simulator/src/grid_simulator/operations.py` and one private contract definition: gridctl operator diagram with model GeoJSON points and endpoints.
- `packages/pypsa-agent/src/pypsa_agent/network_view.py` and `packages/grid-agent/src/grid_agent/network_view.py`: authority result adapters and admitted step layers.
- `packages/capstone-agent/src/capstone_agent/network_view.py`, `protocol.py`, `worker.py`, `host_api.py`: closed diagram/layer schemas, once-per-topology publication, durable replay, authenticated read.
- `packages/capstone-app/src/types.ts`, `networkValidation.ts`, `api.ts`, `App.tsx`: typed v2 view and independent latest session state by case.
- `packages/capstone-app/src/networkLayout.ts`, `NetworkView.tsx`, and App CSS: complete coordinate plotting, electrical glyphs, clear legend, focus, per-case camera.
- Focused adjacent Python and Vitest test files cover contract, replay, case switching, and visual behavior.

### Task 1: Authority diagram projections

**Files:**
- Modify: `packages/pypsa-model-authority/src/pypsa_model_authority/operations.py`
- Modify: `packages/grid-simulator/src/grid_simulator/operations.py`
- Create: `packages/grid-simulator/src/grid_simulator/capabilities/definitions/operator.diagram.get.json`
- Create: `packages/pypsa-model-authority/tests/test_operator_diagram.py`
- Test: `packages/grid-simulator/tests/test_models.py`

**Interfaces:**
- Consume `executor.invoke("operator.diagram", {"model_ref": model_ref})` on PyPSA and `executor.invoke("operator.diagram.get", {"context_ref": context_ref})` on gridctl.
- Produce `{model_ref|revision_ref, coordinate_system, buses, branches}` with scalar IDs, labels, finite `x/y`, optional `vn_kv`, branch kind and endpoints. Do not publish these operations in model-facing catalogs.

- [ ] **Step 1: Write failing authority tests.** Assert SciGRID component counts and PyPSA coordinates, IEEE-39 component counts and schematic GeoJSON coordinates, plus absence from `environment.describe`.

```python
assert len(diagram["buses"]) == 585
assert len(diagram["branches"]) == 852 + 96
assert all(bus["x"] is not None and bus["y"] is not None for bus in diagram["buses"])
assert "operator.diagram" not in {item["id"] for item in described["executable_capabilities"]}
```

- [ ] **Step 2: Run those exact tests and verify expected missing-operation failures.** Use the existing package venvs, targeting only the new tests with `pytest -q`.
- [ ] **Step 3: Implement the private reads.** PyPSA iterates all buses/lines/links/transformers from a verified model revision. gridctl loads only the verified context, parses `net.bus.geo` Point coordinates, and maps all registered line/trafo endpoints. Validate counts and finite coordinates before returning.

```python
if capability == "operator.diagram":
    _exact_keys(arguments, {"model_ref"})
    network = store.load_network(_text(arguments, "model_ref"))
    return _operator_diagram(network, model_ref)
```

- [ ] **Step 4: Re-run focused authority tests and verify both model-facing catalogs remain unchanged.** Commit only authority source, contract, and test paths.

### Task 2: Closed base diagram and step-layer protocol

**Files:**
- Modify: `packages/capstone-agent/src/capstone_agent/network_view.py`
- Modify: `packages/capstone-agent/src/capstone_agent/protocol.py`
- Modify: `packages/capstone-agent/src/capstone_agent/worker.py`
- Modify: `packages/capstone-agent/src/capstone_agent/host_api.py`
- Test: `packages/capstone-agent/tests/test_network_view.py`
- Test: `packages/capstone-agent/tests/test_host_api.py`

**Interfaces:**
- Produce `capstone-network-diagram/1.0` base with fingerprint, model ID/revision/source, coordinate system, buses and branches; `capstone-network-layer/1.0` with ordinal, diagram fingerprint, focus IDs, and optional admitted overlay.
- Worker emits `network_diagram` when the model revision or topology fingerprint changes, then `network_layer` for each committed step. The App may reuse rendered geometry when only the revision changes. `GET /api/v1/sessions/{id}/network?ordinal=N` resolves the matching durable base and layer into `capstone-network-view/2.0`.

- [ ] **Step 1: Write failing schema, worker-order, and API replay tests.** Cover duplicate/dangling IDs, finite coordinates, 2 MiB/count limits, step without layer retaining base, wrong ordinal, and authenticated historical reads.

```python
assert normalize_network_diagram(base)["fingerprint"] == expected_fingerprint
assert normalize_network_layer(layer, base)["ordinal"] == 2
assert [event.kind for event in emitted if event.kind.startswith("network_")] == [
    "network_diagram", "network_layer", "network_layer", "network_layer",
]
```

- [ ] **Step 2: Run focused tests and verify expected missing-schema/event failures.**
- [ ] **Step 3: Implement closed validators and worker publication.** Derive fingerprint from canonical topology/coordinates, not an arbitrary worker string. Raise the worker frame bound only as needed to carry the specified 2 MiB projection plus envelope. Keep failed diagram projection observational so committed answers remain valid.

```python
diagram = normalize_network_diagram(projection["diagram"])
layer = normalize_network_layer(projection["layer"], diagram)
if (diagram["model"]["revision"], diagram["fingerprint"]) != last_diagram_key:
    emit("network_diagram", {"diagram": diagram})
emit("network_layer", {"ordinal": ordinal, "layer": layer})
```

- [ ] **Step 4: Implement API reconstruction from ledger events and run focused protocol/API tests.** Commit only host, protocol, and tests.

### Task 3: Domain adapters and evidence admission

**Files:**
- Modify: `packages/pypsa-agent/src/pypsa_agent/network_view.py`
- Modify: `packages/grid-agent/src/grid_agent/network_view.py`
- Modify: `packages/pypsa-agent/src/pypsa_agent/worker.py`
- Modify: `packages/grid-agent/src/grid_agent/worker.py`
- Test: `packages/pypsa-agent/tests/test_worker_network_view.py`
- Test: `packages/grid-agent/tests/test_worker_network_view.py`

**Interfaces:**
- Consume private authority diagrams from Task 1 and produce `{diagram, layer}` for Task 2.
- Preserve stable IDs (`line:<id>`, `transformer:<id>`, `trafo:<index>`) and admit overlay values only when the result reference belongs to the committed turn and its revision matches the diagram model.

- [ ] **Step 1: Write failing adapter tests for full counts, reuse across non-grid steps, and invalid overlay revision/reference.**

```python
assert len(view["diagram"]["branches"]) == 948
assert view["layer"]["overlay"] is None  # no per-element result this turn
assert view["diagram"]["model"]["revision"] == model_ref
```

- [ ] **Step 2: Run focused tests and verify expected first-50/revision failures.**
- [ ] **Step 3: Replace bounded preview reads with private authority diagram reads; keep `model.topology` unchanged.** Make layer construction a separate helper so a non-grid step can still publish an empty layer against the known base.
- [ ] **Step 4: Run focused adapter tests and a single registered worker case per authority.** Commit adapter source and tests.

### Task 4: Per-case latest-run state and completed-step selection

**Files:**
- Modify: `packages/capstone-app/src/App.tsx`
- Modify: `packages/capstone-app/src/api.ts`
- Modify: `packages/capstone-app/src/types.ts`
- Modify: `packages/capstone-app/src/networkValidation.ts`
- Test: `packages/capstone-app/src/App.test.tsx`
- Test: `packages/capstone-app/src/networkValidation.test.ts`

**Interfaces:**
- Maintain `Record<applicationId + caseId, CaseRunState>` in current tab, where state includes latest session ID, status, turns, report, result, diagram/layers, selected step, detail tab, and camera.
- Apply replay events only to their owning session/case. Switching active case reconnects/replays and refreshes server status; it does not abort an automatic sequence. An explicit new run resets only the selected case.

- [ ] **Step 1: Write failing App tests.** Start case A, commit one turn, switch to B, return to A, and assert same session ID, answer, selected step, diagram, and no new `createSession`; also switch while executing and verify background automatic progression.

```tsx
fireEvent.click(screen.getByRole('button', { name: '案例 B' }))
fireEvent.click(screen.getByRole('button', { name: '案例 A' }))
expect(createSession).toHaveBeenCalledTimes(1)
expect(screen.getByText('已打开模型。')).toBeTruthy()
```

- [ ] **Step 2: Run focused Vitest tests and verify case reset/disabled selection failures.**
- [ ] **Step 3: Implement per-case state and session-aware event updates.** Use functional state updates keyed by case and session identity, and server status on return. Keep token in memory; do not put credentials in storage.
- [ ] **Step 4: Make each completed step number/heading one accessible selection control; add a latest-step action and restore its historical layer.** Run focused App and validation tests, then commit.

### Task 5: Professional complete-network rendering

**Files:**
- Modify: `packages/capstone-app/src/networkLayout.ts`
- Modify: `packages/capstone-app/src/NetworkView.tsx`
- Modify: `packages/capstone-app/src/styles-light.css`
- Test: `packages/capstone-app/src/NetworkView.test.tsx`
- Test: `packages/capstone-app/src/networkLayout.test.ts`

**Interfaces:**
- Consume the validated base diagram and selected step layer. Geographic mode preserves all PyPSA coordinates and fixed aspect ratio; schematic mode uses authority coordinates or a deterministic topology-aware fallback.
- Render only types actually present: bus, AC line, transformer, Link, task focus; overlay scale with unit/domain/coverage; exact hover detail.

- [ ] **Step 1: Write failing layout and component tests.** Assert 585 geographic nodes remain coordinate based, transformer glyph and its legend appear, absent Link key stays hidden, neutral non-grid layer keeps the graph, and camera resets only on new focus selection.

```tsx
expect(screen.getAllByTestId('network-bus')).toHaveLength(585)
expect(screen.getByText('变压器')).toBeTruthy()
expect(screen.queryByText('Link')).toBeNull()
expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
```

- [ ] **Step 2: Run focused Vitest tests and verify expected preview/legend/layout failures.**
- [ ] **Step 3: Implement complete geographic and schematic layouts and electrical glyphs.** Make the white chart clear at overview scale, show labels on focus/hover/zoom, keep controls and per-case camera, and separate symbol legend from value scale.
- [ ] **Step 4: Run focused rendering tests, TypeScript check, and production build.** Commit renderer and tests.

### Task 6: Local application verification and documentation

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Preserve the same `/api/v1` paths, auth policy, and Compose/Cloud Run/Railway/Vercel build contract.

- [ ] **Step 1: Run focused Python authority/worker/API tests and App tests.** Address only concrete failures.
- [ ] **Step 2: Rebuild the local API/worker image and load the local App.** Inspect SciGRID full 585/948 diagram, IEEE-39 39/46 schematic, transformer/Link legend, step 1→2 non-grid persistence, completed-step return, case A→B→A restoration, and current-run evidence coloring.
- [ ] **Step 3: Update both READMEs and runbook with accurate controls and model provenance.** Keep Chinese and English shared facts aligned.
- [ ] **Step 4: Run `make doctor`, relevant repository gates required by `AGENTS.md` for behavior changes, `git diff --check`, production build, and symlink/link checks.** Avoid repeating a broad suite without a specific remaining risk; record any skipped gate and its reason.
- [ ] **Step 5: Review the diff, stage only task-owned files, commit, journal, and update an active recovery checkpoint.** Do not include `.codex/config.toml`.

## Plan self-review

- Spec coverage: full authority topology, no LLM capability widening, durable base/layer replay, per-case session restoration, historical selection, professional rendering, local/cloud contract, and verification all map to Tasks 1–6.
- The existing 1,000,000-byte worker frame is below the 2 MiB projection bound; Task 2 includes a bounded frame-size update.
- The installed SciGRID and IEEE-39 assets already supply coordinates; the UI may still show explicit unavailable state if another registered model lacks valid coordinates or exceeds bounds.
