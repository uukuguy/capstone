# Capstone M7 Result Projection and Grid Link Design

**Status:** Approved design for implementation planning

**Date:** 2026-10-02

**Scope:** Expose admitted professional-analysis results in the Thread Web workspace and link result records to the current grid diagram.

## 1. Goal

M7 adds a trustworthy result-reading path for the existing single-Run Thread. A completed professional Turn may expose a compact result summary, a structured table, and references to model elements. Selecting a result row updates the left grid projection so the referenced bus, line, transformer, or other registered element is highlighted.

The first end-to-end business path is pandapower AC power-flow output. The public contract is domain-neutral and can be populated by PyPSA Domain Packs later. When a selected domain or capability has no result projection, the client displays an explicit unavailable state and never invents values.

## 2. Non-negotiable boundaries

```text
Thread Web client
  -> ThreadSnapshot / ResultProjection
  -> Capstone application
  -> Domain Pack result projector
  -> registered Authority result and evidence
```

- The browser does not parse assistant Markdown to derive values, model identity, or element references.
- The browser does not read Authority artifacts, raw DataFrames, pandapower networks, PyPSA Networks, or private object storage.
- A ResultProjection is admitted only for the current Thread/Run and the model context and revision recorded by the producing Attempt.
- A projection cannot change the active ModelContext. It can request a bounded presentation focus only.
- Domain Packs define business labels, units, table columns, and element-reference semantics. Kernel and Harness only carry bounded typed data.
- `grid-agent` and `pypsa-agent` remain compatibility/adaptation packages; no new result UI or Thread orchestration is added there.

## 3. Public ResultProjection contract

The public read model uses a bounded `capstone-result-projection/1.0` shape. A projection is attached to one completed answer and contains:

```text
ResultProjection
  schema: capstone-result-projection/1.0
  result_id: stable result projection identity
  result_ref: admitted result reference
  evidence_refs: admitted evidence references
  thread_id, run_id, turn_id, attempt_id
  model_context_id, model_id, model_revision
  source: { capability_id, domain_pack_id, implementation_family }
  status: completed | partial | unavailable
  summary: bounded list of MetricItem
  tables: bounded list of ResultTable
  element_refs: bounded list of ElementRef
  overlay: optional bounded NetworkOverlay
```

`MetricItem` contains a stable metric id, reader-facing label, finite numeric or string value, unit, and optional severity. `ResultTable` contains a stable table id, title, bounded column definitions, and bounded rows whose cells are scalar display values. `ElementRef` contains model id, model revision, element kind, and element id. `NetworkOverlay` contains a metric, unit, source reference, and bounded values keyed only by admitted element ids.

The projection must preserve the result and evidence references used for admission. It must reject non-finite numbers, mismatched model revisions, unknown element ids, oversized lists, and references outside the current Run. An unavailable projection contains a typed reason and no fabricated metrics.

## 4. Server and Domain Pack flow

When a Domain Pack submits an admitted completed answer, its result projector converts the Authority result into the public projection. The application associates the projection with the answer and makes it available through the existing Thread read model. The projection is immutable for that Attempt; a retry produces a new Attempt and a new projection identity.

The application read model exposes only the bounded projection. If a projection is too large for the snapshot, the public contract may expose a detail reference and a bounded summary, but the detail query must still return the same admitted, revision-bound projection through the Thread API. The first implementation may keep the complete bounded projection in the snapshot to avoid introducing a second transport before the shape is stable.

The projector must support the existing pandapower calculation state, including total active loss, solver/convergence status, model counts, line or bus result tables when present, and evidence references. It must use the Domain Pack's registered capability and result schema rather than infer fields from prose. PyPSA registration may provide the same contract independently; absence of a registered projector is a normal unavailable state.

## 5. Web interaction

Each completed professional answer keeps a fixed compact action row:

- **结果**: enabled when an admitted ResultProjection exists; opens the result detail surface.
- **证据**: enabled when admitted evidence references exist; opens the current-Run evidence surface.
- **更多**: contains disabled future actions with an explicit reason where the capability is not implemented.

The result detail surface is compact and readable. It shows the projection title/source, model and revision, summary metrics first, then tables, then the available element references. It does not repeat long hashes in the main content. A table row with an element reference is selectable. Selecting it sends only a presentation selection to the shared Thread projection store and highlights the corresponding element in the left diagram.

The result surface handles these states explicitly: loading, completed, partial, unavailable, stale revision, and resync required. It never silently removes an operation slot. Historical Thread pages are read-only and cannot alter the current model page.

## 6. Grid linkage

The left pane continues to use the existing `NetworkDiagram` and `NetworkLayer` projections. M7 adds a typed `elementReference`/focus update to the shared presentation store. The focus is valid only when model id and model revision match the viewed page. A valid selection highlights the element and exposes its kind/id in the existing compact reference area. An invalid or unavailable element produces a visible “无法定位到当前模型元件” state without changing the diagram source.

The overlay is applied only when the projection's model revision equals the diagram revision and every overlay id is present in the diagram. Overlay styling remains a presentation detail; numeric truth stays in the ResultProjection and admitted result.

## 7. Failure and recovery behavior

- Missing result or evidence admission leaves the action disabled with a reason.
- A malformed or mismatched projection is rejected server-side and appears as a typed unavailable result; the assistant answer remains visible.
- A reconnect/resync rebuilds the projection from the Thread snapshot/event page. The client does not retain an independently authoritative result cache.
- Retrying an Attempt creates a new immutable result projection. The prior answer and projection remain readable in history.
- A model switch is disabled while an Attempt or Case step is active. After switching, old projections remain attached to their original model revision and cannot focus the new page.

## 8. Acceptance criteria

1. A pandapower AC power-flow answer with admitted result/evidence references exposes a valid `capstone-result-projection/1.0`.
2. The projection carries model context, model revision, source capability, result reference, and evidence references.
3. Summary metrics and at least one structured result table render without raw Markdown parsing or raw artifact access.
4. Selecting an element-bearing row highlights the matching element in the left diagram and rejects revision mismatches.
5. Missing, partial, stale, and unavailable states are visible and do not hide action slots.
6. Retry, reconnect, and historical views preserve projection identity and current-Run admission rules.
7. The same public contract accepts a PyPSA projector without changing Web or Harness code; no PyPSA data is fabricated when one is not registered.
8. Focused Python and Web tests cover contract validation, admission/revision checks, rendering, selection, and resync.

## 9. Explicitly deferred

- Answer summary mode and global reading preferences.
- Feedback persistence and conversation project storage.
- Multi-Run, WebSocket human-in-the-loop controls, and real DSH runtime.
- Final Textual/Rust/Go TUI redesign.
- General-purpose workflow/DAG execution.
