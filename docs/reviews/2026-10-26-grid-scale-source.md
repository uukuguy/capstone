# Large topology and gateway source verification

Status: local implementation verified; dev PR integration and actual primary
entry closeout are pending. No cloud, demo or main release.

Latest product source7ba27575 includes the requested Escape change.15 focused
workspace tests and types passed. In visible Vivaldi8.2, the current tab loaded
the source view; pressing Escape with focus outside the composer left navigation
expanded. Actual405/1003 geometry was visually inspected there. Subsequent UI
checks reuse that Vivaldi tab; Chromium scale figures below predate this request.

## Implemented behavior

- Each instruction determines resource relevance. Explicit targets win, clear
  continuations may inherit context, and unrelated instructions do not resume
  old tasks. Stored resources remain available without becoming a global goal.
- The existing workspace has an on-demand source topology tab. It does not fetch
  the gateway while hidden or replace the conversation/composer/model directory.
- Source groups use a separate typed contract. Region, station and equipment
  expansion preserve source revisions, selection rules, independent cursors,
  gaps, boundaries and unresolved endpoint identities. Parallel records retain
  separate IDs. Display groups never become calculation models.
- Large formal diagrams dispatch before legacy synchronous layout. A worker
  owns layout and spatial indexes; WebGL uses bounded viewport geometry and
  level of detail. Search, picking, task attention, history, states and selected
  details retain stable IDs. Screen-space collision checks bound labels.
- Source questions freeze a bounded observation with explicit sample limits and
  open a model-free enterprise question draft. The user confirms submission.
  Existing formal model selection remains intact.

The backend admits only fixed source operations. Browser requests cannot select
MCP endpoints, credentials or arbitrary tools. The protected connection is kept
in ignored operator state. Browser filesystem access to it returned403.

## Actual gateway checks

Gateway1.30.0 publication and actual business-copy records were read through the
protected application API. These are source observations, not solver evidence.

| View | Nodes | Connections | Check |
| --- | ---: | ---: | --- |
| North regional | 405 | 1003 | Both streams completed under one view reference; zero unresolved endpoints |
| Chaoyang station | 44 | 10 | Source expansion reference; browser search and station expansion passed |
| Selected breaker detail | 3 | 2 | Source expansion reference; station/equipment API reads passed |

Discovery retains six regions and four groups from the published definition
dictionary. The first assumed discovery shape was rejected by live validation;
d9b72190 adds actual-shape tests and preserves station parent references.
An early station503 did not reproduce with the exact captured request; subsequent
public and browser reads succeeded. No permissive validation bypass was added.

The source declares a330kV regional minimum, external-stub retention, six source
quality gaps, no verified electrical bus reduction and no verified operating
measurements. These flags remain visible and travel with question material.

Real UI-created Thread `thr_1b22f19781911c68df3c`, Attempt
`attempt_1fc523da0b0f5290` completed in114.6s. Its answer separates405/1003
source-declared totals from50/50 sampled records, explains snapshot/quality
limitations and declines unsupported power-flow/connectivity claims. Two saved
products support the extraction. This proves the source-question path, not a
response-time acceptance or an electrical calculation.

The next unrelated instruction in that same Thread/Work asked for a one-sentence
2FA explanation. Attempt `attempt_deed15fd345d4333` completed in3.93s, used a
text-only response with no tool calls, and did not restart the grid plan. Thus
retained source material did not become an obligation for the unrelated turn.

## Measured scale

Apple M3 Max, Chromium155, ANGLE Metal WebGL1,1098×396 canvas,DPR1. The synthetic
graph contains120000 nodes and239300 edges. Initial level of detail draws24000
nodes and40000 edges; zoom reveals more detail. It does not draw every glyph at
once or prove arbitrary-grid readability.

| Fixture | Worker index | First frame | Search |
| --- | ---: | ---: | ---: |
| Provided synthetic coordinates, renderer11011b76 | 891ms | 1064ms | 184ms including120ms debounce |
| No coordinates, schematic worker, rendererbe9bd1e2 | 587ms | 771ms | 183ms including debounce |

The provided-coordinate case recorded120 pan/zoom animation-frame intervals:
p50 16.7ms,p95 18.1ms,max18.6ms. Indexed pick was0.5ms; WebGL error was0.
These are browser scheduling intervals, not GPU timer-query measurements.
Main JS heap was85MB initially and280MB after motion; worker and GPU memory are
excluded. The no-coordinate case recorded about85–86MB main JS heap and51.5ms
locate latency. These measurements supplement the actual source checks.

The narrow actual North pane was inspected after fit/label refinement. Labels
are sparse and non-overlapping; the405/1003 overview remains dense. Search,
zoom and station drill-down provide detail. The layout is explicitly schematic.

## Checks and runtime

- Source policy:19 passed,1 Docker opt-in skipped.
- Protected API/source projection:31 focused cases passed in1.63s; types clean.
- CI scope/content guards:103 cases passed in1.01s. Legacy transport changes,
  unknown paths, Authority/foundation/dependency mixes and releases still widen.
- Renderer:69 focused cases passed in1.54s, plus bounded selection/fit cases.
- Final resize regression638302d1 preserves camera width/center across a hidden
  resource panel and wide/portrait changes; six focused cases and types pass.
- Source workspace and existing Work consumers:44 passed in6.59s; types clean.
- Canonical rebuild used the protected gateway mount and pinned assets. Final
  API/all worker image8f2b58af953a matched; native image5c6f09fa99ba. Source
  topology and instruction-policy hashes match checked-in files exactly.
  Readiness passed and scoped cleanup receipt031132-36100 was saved.

Local detailed receipts and screenshots are retained in ignored
`outputs/grid-scale-20261026/`. Provider credentials are absent from them.
Scoped CI duration, final independent review and primary-entry integration
must be recorded before closing this package.

Independent final review at638302d1 found no Important/Critical blockers and
confirmed the earlier quality, focus, return, scene identity and resize repairs.
The later Escape change only removes the global sidebar key listener and updates
its existing regression. No professional tools or deployment grants changed.
