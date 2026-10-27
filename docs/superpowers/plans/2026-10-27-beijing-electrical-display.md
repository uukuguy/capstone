# Beijing electrical topology delivery

> For agentic workers: use subagent-driven-development for independent units.
> Preserve other workers' edits and user data. The existing purpose-aware design
> and the user's explicit implementation request authorize this continuation.

**Goal:** Open the discovered Beijing provincial grid in the real workbench,
render its complete overview, drill into actual electrical devices, and restore
the same view after refresh through components reusable for any published scope.

**Architecture:** MCP owns identities, schema, frozen versions and connectivity.
Application adapters admit bounded typed pages. The UI loads overview streams
first, then local closures on demand; the existing large-network renderer owns
symbols, layout, selection and camera. No LLM loop per page; no invented edges.

## Constraints and acceptance

- Sibling data-gateway is read-only. Use its MCP publication for real calls;
  docs/superpowers/specs/2026-10-27-progressive-grid-view-loading.md is a developer reference.
- Do not hard-code Beijing IDs or province-specific call sequences in product code.
- Keep v1/calculation views compatible; no solver or calculation import work.
- Initial overview downloads summary_nodes/summary_edges only, each cursor to completion.
- User clarification: once overview is complete, show it immediately and keep it
  interactive while remaining detail pages download in the background. Chat and
  subsequent agent instructions remain usable independently of download state.
- Background pages use bounded concurrency and version-bound IndexedDB storage,
  not an unbounded in-memory full-network scene. Show per-stream progress and
  pause/resume; selected local closures take priority. A new model aborts obsolete
  requests. Cache failure keeps the overview usable and reports a paused download.
- Distinguish source station-line aggregation from actual node-breaker connectivity.
- Bounded concurrency, cancellation/generation isolation, version checks and exact
  identities remain mandatory. Preserve loaded content on a recoverable page error.
- New business acceptance uses a new conversation in the existing Vivaldi tab.
- Test changed layers; no unrelated solver or release gate. Integrate normal dev PR.

### Task 1: Admit published v2 views

Own packages/capstone-agent/src/capstone_agent/grid_electrical_view.py,
resources/gateway-electrical-view-v2.schema.json and tests/test_grid_electrical_view.py.
Inspect related routing only if needed and coordinate before changing shared files.

- [ ] Read live tool schemas and the sibling published v2 JSON schema. Confirm
  root provincial selection and the exact manifest/page shapes before editing.
- [ ] Add failing checks for v2 root open, summary pages, grid/station/edge targets,
  inherited child schema, cross-view cursor/version rejection and v1 compatibility.
  Example input: `{'model_ref': discovered_ref, 'representation': 'source_node_breaker',
  'view_schema': 'gateway-electrical-view/2'}`. Never construct discovered_ref from a province name.
- [ ] Extend closed request/response projections and retain published identity,
  expand_target, coverage and source-endpoint fields. Keep declared stream limits.
- [ ] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_grid_electrical_view.py -q`,
  inspect diff, commit only owned files, and report exact commands/results.

### Task 2: Decode and project overview/detail scenes

Own packages/capstone-app/src/electricalModelView.ts,electricalModelScene.ts,
electricalModelFixtures.ts and their focused tests; layout/symbol consumers only as needed.

- [ ] Add fixtures for v2 summary nodes/edges, multi-page totals, missing endpoints,
  version drift and v1 detail compatibility. Preserve actual device IDs and source refs.
- [ ] Extend `parseElectricalViewOpen`, `parseElectricalViewPage`,
  `loadElectricalModelView` with explicit overview versus closure stream selection.
- [ ] Project summary groups and aggregated lines distinctly, with expandable targets;
  project station busbars, switches, transformer windings and true connections through
  existing source layout. Display names on canvas; IDs remain searchable in details.
- [ ] Run focused Vitest files; verify all routes keep original endpoint identities.

### Task 3: Hierarchical workbench loading and task routing

Own ElectricalModelWorkspace.tsx/tests and needed threadViewRouting/transport
consumers. Coordinate any backend request-binding changes with Task1.
New electricalViewCache.ts/electricalViewDownload.ts own asynchronous page storage
and background progress; their tests verify no closure/agent lock while downloading.

- [ ] Discover provincial entries from the live catalog; request supported v2 explicitly.
- [ ] Load the full current summary layer with per-stream progress, then render it.
  Expand nodes/edges through returned targets and original parent/version fields.
- [ ] Show source preparation separately from download progress; poll bounded jobs
  without resubmitting builds. Cancel obsolete loads; keep completed content on pause/error.
- [ ] Implement breadcrumb back navigation, device/line identification and focus,
  explicit unavailable targets/gaps, and version-bound refresh restoration.
- [ ] Preserve task-request versus manual-navigation priority and existing conversation UI.
  Run focused workspace/routing/transport tests and App build before commit.

### Task 4: Real acceptance and integration

User acceptance clarifications during live testing:

- Use gateway `name` in the catalog, title and breadcrumbs. Keep `model_ref` in
  source/version details. Do not maintain a local province ID/name mapping.
- A single station selection exposes a primary “进入电气接线” action above the
  canvas. Search results offer the same action. Double-click is an optional
  shortcut; zoom does not imply hierarchy navigation. Show the current level
  and a clear return path.
- Record overview first paint and complete detail-cache commit from the same
  model-open origin, plus selection scope, counts and cache conditions. Record
  agent/gateway preparation separately; do not present warm-view loading as
  complete natural-language latency.
- Validate the literal instruction “打开北京电网”, not only manual model selection.
- Keep device/port placement coherent around the 500-node layout threshold;
  preserve all source edges and their electrical versus membership semantics.

- [ ] Read live Beijing overview and representative station/transformer/line closures;
  record unique counts, page counts, source identity, missing-data limits and timings.
- [ ] Canonical rebuild; verify API/worker image identity/readiness and scoped cleanup.
- [ ] Submit Beijing display request visibly in new Vivaldi conversation; verify overview,
  busbar/transformer/line symbols, group/edge drilldown, selection, back and refresh.
- [ ] Review scoped combined diff, fix material findings, commit evidence/control state,
  merge normal dev PR and verify actual-dev entry point. Do not call readiness
  publication alone UI acceptance or mark missing source connectivity complete.
