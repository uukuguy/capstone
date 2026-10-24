# Scale-aware grid topology views

Status: user-requested capability and proposed service contract, 2026-10-25.
Production-data enterprise research remains the first implementation delivery.

## Observed limitation

The real north model probe contains 14,017 source nodes, 878 exported lines and
4,346 native switch structures. Its regional selection already uses a 330 kV
minimum. Thus voltage filtering alone does not yield a readable regional view.
The gateway declares source-node topology and no trusted electrical bus reduction.
Do not present these nodes as verified in-service electrical buses.

Current NetworkView renders SVG elements for every supplied node and branch.
networkLayout uses a graph-level schematic above 256 nodes, avoiding the small
force layout, but it is not a viewport-culled renderer. Configured acceptance
limits of 100,000 buses and 200,000 branches are bounds, not measured performance.

## Client and gateway responsibilities

Capstone must support large networks, including detailed views. It must not
depend solely on gateway truncation to keep the browser usable. The gateway
must supply scale-aware, bounded presentation projections so a regional overview
does not require downloading and drawing every station terminal and switch.
The gateway continues to own all backend selection and query execution.

Keep the versioned source model separate from its display projection. A display
aggregation is not an electrical equivalent and cannot replace a calculation
model. Unknown switch positions must not be used to infer closed-switch bus
merging or connected operating islands.

## Proposed levels

| Level | Default content | Drill-down |
| --- | --- | --- |
| Regional overview | Stations or station/voltage groups, inter-station corridors and external boundaries | Station group or corridor |
| Station overview | Voltage groups, source-backed busbar references, transformers and external connections | Selected voltage group or device |
| Device detail | Source connection nodes, terminals, switches and individual circuits | Source record and declared quality |

Geographic coordinates are used only when source-backed. Otherwise label the
view as schematic. Station aggregation denotes grouping of source equipment,
not a claim that all internal nodes are electrically connected. Parallel circuit
bundles retain member IDs/counts and can expand. Boundaries and excluded records
remain explicit. Unknown relationships remain unresolved rather than invented.

## Proposed MCP contract to discuss with data-gateway

Request: source model/snapshot reference, region scope, display level, selected
voltage levels, optional parent element or viewport, and node/edge budgets.
Use gateway-published typed parameters; the names above describe semantics,
not already implemented tool arguments.

Response: immutable source and view revisions, aggregation rule/version, stable
node/edge IDs, typed node kinds, explicit endpoints, parent/child or member
references/counts, boundary markers, coordinates with their meaning, quality
and omissions, plus bounded continuation/expansion references when required.

Budget exhaustion must return declared aggregation or continuation, never an
arbitrary first-N subset presented as a full region. An expanded view and its
parent must refer to the same accepted source revision. Aggregate nodes must
not be labelled as electrical buses. The current capstone-network-diagram/1.0
bus-oriented rendering contract needs an explicit extension or adapter for
typed station/group nodes; cosmetic renaming alone is not sufficient.

## Rendering and acceptance

User decision, 2026-10-25: retain this rendering direction for implementation at
an appropriate later boundary. Do not start the renderer migration during the
first production-data research delivery. Target networks include 100,000+ nodes;
do not treat a readable aggregated overview as proof of detailed-scale capacity.

Preferred architecture: WebGL draws batched network geometry; HTML/SVG supplies
controls, accessible selected-object details and sparse overlays. Evaluate
Sigma.js with Graphology first, including custom electrical symbols, parallel
circuits, transformer terminals and task highlighting. It is a candidate, not
an accepted dependency or a measured 100k-node performance claim. Keep the
public diagram/source contract independent of a renderer library.

References checked for the proposal:
[Sigma rendering](https://www.sigmajs.org/concepts/rendering/) and
[custom rendering programs](https://v3.sigmajs.org/docs/advanced/renderers/).
WebGL does not replace worker layout, spatial indexing, level-of-detail loading,
label budgets or hit testing. Test device/browser, node and edge counts, symbol
complexity, load time, frame times, memory and selection latency must be recorded.
Do not promise a fixed frame rate based on node count alone.

- Measure the existing renderer with the actual north projection first. Record
  layout, first interactive render, pan/zoom frame times, hit testing, memory
  and node/edge counts on a named device/browser. Set budgets from measurements.
- Use worker-based layout, spatial indexing, viewport culling and zoom-dependent
  symbols/labels. Evaluate Canvas/WebGL for dense geometry and retain accessible
  controls and selected-object details. Do not send camera changes through
  full-graph React reconstruction or recompute the full layout on hover.
- Preserve existing task/source highlighting, search and selection across levels
  using stable source IDs. A selected device in a collapsed station highlights
  its parent and can be revealed by drill-down.
- Test overview, station expansion, device detail and large-detail interaction
  with the real gateway model. Verify boundary/circuit membership against source
  records. Synthetic stress cases supplement, not replace, the real model.

No sibling-project modification or external message was made for this proposal.
Model calculation remains gated by the separate source quality and Authority
contracts. This requirement does not defer the first production-data research path.
