# Authoritative, Persistent Network Diagrams

## Decision and scope

Replace the current operator network preview for the five registered three-step
cases with one persistent diagram for each case's latest run. A step changes
task focus and an admitted numerical overlay; it does not replace or hide the
case's network.
Keep the existing run controls and the light operator workspace. The diagram
uses a white canvas and engineering-oriented symbols and legend.

SciGRID-DE shows its complete registered network in geographic coordinates:
the installed PyPSA 1.3.0 model has 585 buses, 852 lines, 96 transformers,
and finite coordinates for every bus. IEEE-39 uses the schematic coordinates
in the registered pandapower 3.4.0 `case39` model; its 39 buses, 35 lines, and
11 transformers all appear. The other registered PyPSA cases use their
authority-provided coordinates if suitable and a deterministic electrical
schematic otherwise. The application does not claim that schematic coordinates
are geographic.

This supersedes the 50-bus preview choice in
`2026-09-27-operator-workspace-network-design.md`. That limit remains on the
model-facing `model.topology` capability; it does not limit the operator's
diagram. The App stays deployable with the same API and worker image on local
Compose, Cloud Run, and Railway, with Vercel serving the App. No external map
tile service or runtime download is required.

## Approach and alternatives

Use a typed, bounded presentation projection supplied by each registered
authority through its Domain Pack. It carries complete topology for these
registered cases, finite model coordinates, component types, nominal voltage
when available, model identity and revision, and stable opaque element IDs.
The frontend renders the model once for a revision and layers step-specific
focus and current-run result values over it. This keeps pan/zoom, hover,
selection, and automatic task focus responsive while preserving provenance.

Native pandapower and PyPSA plotting functions can make useful static plots.
A server-rendered SVG would preserve their default visual style but complicate
stable interactive element selection and later result overlays. Hand-maintained
images would diverge from the registered authority. The typed projection is
the selected approach; its symbols and geometry follow domain conventions
without exposing raw simulator objects to the browser.

## Boundaries and data flow

The simulator authorities own topology, coordinates, nominal voltage, and
calculated values. A selected Domain Pack invokes a private, read-only operator
diagram operation on its registered authority. This operation is separate
from the model-facing tool allowlist and is never offered to Pi/LLM. It returns
only scalar presentation data, never a pandapower/PyPSA object, DataFrame,
callable, or model file. The Kernel validates and persists a closed, versioned
projection without importing domain libraries. The authenticated session API
serves that projection; it does not recompute a diagram from answer text.

The projection has explicit safety bounds of 2,000 buses, 4,000 branches, and
2 MiB serialized JSON. The five registered cases fit within them. The
authority rejects duplicate IDs, dangling endpoints, nonfinite coordinates,
and mismatched revision references. If a future registered model exceeds the
bounds, the UI states that the diagram is unavailable instead of presenting
an arbitrary first-N sample as a whole grid. The 50-bus model-facing
`model.topology` contract stays unchanged.

At model open, the worker publishes one base diagram identified by model ID,
revision, and topology fingerprint. A derived scenario revision with unchanged
topology reuses the same geometry; a changed topology publishes a new base
diagram. Each completed step publishes a small layer containing focus IDs and
an optional numerical overlay. A layer may refer only to IDs in its base
diagram. An overlay is accepted only if its result reference is admitted for
that current run and matches the model revision, scenario, and snapshot. An
unavailable layer leaves the last valid base diagram visible and shows a
precise step-state message; it never carries an earlier step's values forward
as if they belonged to the new step. Selecting a historical step restores
only that step's admitted layer. Reconnect/replay reconstructs the same base
diagram and selected layer from durable session events.

The App keeps the latest session ID and view state separately for each case
during the connected browser tab. A case switch is always available, including
while a turn runs. Switching does not create a new session, erase committed
answers, stop an in-flight authority task, or cancel an already started
automatic sequence. On return, the App refreshes that case's status and
replays missed events from its session; the server remains authoritative for
accepted and completed turns. It restores that case's selected step, detail
tab, and diagram camera. Starting a new run is an explicit action that
replaces only the selected case's latest session. Disconnecting stops local
automatic advancement; accepted server work retains its normal state.

## Rendering and interaction

For SciGRID, plot every bus and branch at its model `x`/`y` coordinates with
a fixed geographic aspect ratio, north indicator, and understated coordinate
ticks. Coordinate provenance is labelled as PyPSA model coordinates; no
geographic or administrative boundary is invented. Do not substitute a force
layout when geographic points are close. Use progressive disclosure: the full
network remains visible, while labels appear for the focused/hovered/selected
elements and at sufficient zoom. The fit action frames the complete model.

For IEEE-39 and schematic PyPSA cases, use model schematic coordinates where
present. If absent, derive a stable topology-aware layout from the complete
authority topology, with no model value inferred from geometry. Preserve the
distinct electrical component types: bus, AC line, transformer, and Link
where present. The legend uses the same glyphs as the graph, explains nominal
voltage classes only when sourced from the model, and separates task focus
from result coloring. Never show a Link key in a case with no Links. The
result color scale names the metric, unit, exact domain, and coverage count;
elements without admitted values remain neutral. Tooltip/detail text gives
the exact authority value and result reference. Avoid unexplained traffic-light
thresholds.

The number and heading of each completed timeline step form one selectable,
keyboard-accessible control with a clear selected state; evidence buttons in
the answer remain separate controls. Choosing a step identifies its committed
answer and admitted diagram layer, even after later steps finish. A visible
"latest step" action returns to the current run view.

Pan, wheel/button zoom, fit to whole model, fit to current task, keyboard
navigation, and focus on selecting a timeline step remain available. A new
step may move the camera once to its known target and nearby network context.
Manual camera movement then remains intact until the next explicit step
selection or lifecycle change. A non-grid step keeps the base diagram in view
and presents a neutral task state. The diagram is readable at desktop and
mobile widths, with white chart background, adequate contrast, and no tiny
essential labels.

## Error handling and verification

Invalid authority projections, unknown IDs, wrong revisions, and excessive
payloads fail closed with a visible diagram-state message. A failure in this
observation path does not replace simulator truth or block a valid answer.
Existing stdout JSON and current-run evidence contracts remain unchanged.

Focused tests cover complete SciGRID and IEEE-39 component counts and
coordinates, projection bounds/validation, revision and evidence gating,
diagram persistence across non-grid steps and replay, clickable historical
steps, per-case latest-session restoration while a run is active, independent
case state, correct component legend, value coverage, task focus, and diagram
controls. Verify the rendered
SciGRID and IEEE-39 cases in the local App, including a step with no new
network values. Run the smallest focused tests first, then the repository's
supported gates when needed for this behavior change. Do not run the billed
provider validation without separate authorization.
