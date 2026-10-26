# Purpose-aware electrical diagrams implementation plan

> **For agentic workers:** Use subagent-driven-development for independent implementation units. Preserve other workers' edits and user data.

**Goal:** Render any registered gateway grid through one purpose-aware, hierarchical electrical diagram component, with real source connectivity and explicit gaps.

**Architecture:** The gateway owns published model identities, equipment, terminals, connections, partitions and readiness. The application admits bounded typed projections; shared worker layout and rendering preserve source identities. Source node-breaker diagrams remain distinct from Authority-admitted calculation models.

**Tech stack:** Existing Python protected gateway relay, TypeScript/React workspace, Web Worker scene index, WebGL renderer.

## Status and constraints

- Accepted direction, 2026-10-26; compatible source-diagram implementation is underway; new gateway contract acceptance remains pending.
- Gateway response prioritizes B(source structure) and C(element-map plus calculation_bus_branch). Exact proposed tools are open_network_model_view/read_network_model_view; neither is released yet. Preserve source_node_breaker/calculation_bus_branch distinctions. Optimization and Dameng consistent extraction remain later dependencies.
- Contract proposal: [gateway handoff](../specs/2026-10-26-purpose-grid-model-gateway-handoff.md). Proposed names are not callable tool parameters.
- The user owns submission and implementation in the sibling data-gateway project. Do not edit that repository.
- No North-specific algorithms, fixed regional default, fabricated connectivity or unknown-switch bus reduction.
- Preserve existing conversation, explicit instruction resource scope, model selection and IEEE39 path.
- Use the existing Vivaldi tab for visible acceptance. No full release or unrelated solver gates.
- Keep source, selection, scenario, derived-model and view revisions distinct and bound across pages and drill-down.
- Initial hierarchical display must not fetch all equipment. An explicit full-view action can retain the existing bounded full download.

## 1. Source incidence projection and layout

Files: new `packages/capstone-app/src/electricalSourceScene.ts` and tests; new `electricalSourceLayout.ts` and tests. Consumers: `networkScene.ts`, `networkSceneIndex.ts`.

- [ ] Define a pure projection from admitted source records into typed devices, actual connection junctions and distinct membership relations. Preserve every original ID and selected-source reference.
- [ ] Add small independent test graphs: two busbars with bus coupler; two/three transformer windings; missing generator/load connections; a node shared across station declarations; parallel lines.
- [ ] Use actual busbar devices as layout anchors. Render them as busbar segments; route attached source connections through distinct visual anchors without creating new electrical nodes.
- [ ] Place connected feeder devices in deterministic lanes and separate unresolved/isolated equipment. Membership is not a conducting wire. Unknown switch state remains neutral.
- [ ] Keep layout within a station/voltage partition and bounded worker work; do not run global all-pairs layout across100K objects.
- [ ] Verify connected endpoint identity and original edge cardinality before and after layout; test no synthetic connectivity and stable selection mappings. Commit this tested unit.

## 2. Shared polyline rendering and interaction

Files: `networkScene.ts`, `networkSceneIndex.ts`, `networkScene.worker.ts`, `networkScenePresentation.ts`, `networkWebGL.ts`, `networkSymbols.ts`, and affected tests.

- [ ] Add explicit routed edge geometry and attachment metadata without changing formal Authority diagram semantics.
- [ ] Index, cull, draw and pick every polyline segment, including bends outside the direct endpoint box. Focus must fit the complete selected route.
- [ ] Render busbars, two/three-winding symbols, open/closed/unknown switches, generator/load symbols and non-conducting membership distinctly. Label the symbol convention; do not claim certified standard compliance without verification.
- [ ] Test parallel-circuit selection, crossing without junction, true shared-node junction, zoom/camera restoration and selected task highlighting.
- [ ] Re-run affected scene/renderer and existing IEEE39 consumers; inspect actual station detail in Vivaldi before visual acceptance. Commit the tested unit.

## 3. Generic discovery and hierarchical workspace

Files: `gridSource.ts`, `GridSourceWorkspace.tsx`, `threadHttpTransport.ts`, their tests; protected projection `grid_source_topology.py` only when required by a published contract.

- [ ] Replace implicit North selection with discovered model/scope selection or an admitted current-instruction view. Handle no models, unavailable models and historical views explicitly.
- [ ] Start navigation with the selected purpose/partition. Keep overview, station inventory and electrical connection views visibly distinct.
- [ ] Verify the existing `equipment` plus `station:<ID>` selector before using it. The fresh protected probe on2026-10-26 returned503; code support alone is not runtime acceptance.
- [ ] Keep cancel/generation protection, parent/source/selection checks, independent page streams and exact object identity. Do not fall back to an invisible full-network fetch on a failed child request.
- [ ] Use released gateway expansion references for voltage/bay scopes. Disable unavailable expansions with an explicit reason rather than synthesize new upstream arguments.
- [ ] Test two arbitrary model IDs, per-instruction view changes, manual navigation priority, source drift, cancellation and restoration. Commit this tested unit.

## 4. Published purpose-model contract integration

Dependency: data-gateway owner supplies released schema/tool publication and reproducible responses from the handoff acceptance matrix.

- [ ] Compare the published contract with the proposal; record differences and update adapters. Preserve old topology-v1 compatibility.
- [ ] Admit only exact registered semantic tools and schemas. Keep gateway authentication/backend selection out of model/browser payloads.
- [ ] Select overview/electrical topology/power-flow/optimization at an ordinary agent loop step. Do not introduce another mandatory model classifier or Deep Research startup.
- [ ] Bind returned view descriptors to the current instruction and verified source receipt. Preserve model and device mappings when displaying calculation results.
- [ ] Test unsupported purpose vs unchecked readiness vs source gaps; no implicit purpose downgrade, build, solver run or repeated readiness probes.

## 5. Real acceptance and integration

- [ ] Verify North and a second registered grid using the same component; save sanitized source/view references and request counts.
- [ ] In existing Vivaldi tab, view overview, station/bay single-line, busbar/transformer/device details, task highlight, continuation and refresh.
- [ ] Verify the graph against actual source connections. Record ambiguous/missing ports and states; do not use visual readability as numerical acceptance.
- [ ] Run one purpose-specific power-flow preparation path; stop on deterministic missing-input/mapping gaps and save the exact report. Historical North attempt already exists; do not repeat it without changed inputs or a necessary new acceptance boundary.
- [ ] Measure100K+ hierarchical download, bounded local layout, frame times, memory, search and segment picking. Existing120K synthetic rendering is baseline evidence, not acceptance of new routing.
- [ ] Run affected checks, canonical rebuild for changed runtime sources, ready/image checks and scoped cache cleanup. Integrate through dev PR; verify actual dev entry and update canonical control records.

## Completion rule

Mark implementation, local real acceptance, merge and deployment separately. The new electrical diagram and purpose-model integration are not complete until released gateway contracts and actual diagram acceptance pass. Preserve the existing verified source-view milestone without relabelling it as this new electrical-diagram delivery.
