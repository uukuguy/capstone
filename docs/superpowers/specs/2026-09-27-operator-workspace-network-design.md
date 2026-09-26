# Operator Workspace Readability, Automation, and Network View

## Decision

Refine the existing Capstone operator App for the registered three-turn pandapower
and PyPSA cases. Raise reading comfort, move the workspace to a restrained light
palette, add an explicit automatic run action, and show a bounded, interactive
network view tied to the selected case and committed steps. The frontend and the
versioned API behave identically on local Compose, Cloud Run with Vercel, and
Railway with Vercel. No Provider request is introduced by opening a case or
using automatic mode.

## Alternatives

The selected approach obtains network topology and per-element measurements
through the registered authority and an explicit, bounded domain presentation
contract. This costs more than a static illustration but keeps model identity,
revision, and result provenance intact. A pre-rendered SVG per case would be
fast but could silently drift from the registered model. A schematic assembled
from case titles and instructions would look useful without being authoritative.

## Operator experience

Use a warm, very light slate page background, white working cards, dark ink
body text, muted teal for interaction, and restrained amber/coral for warnings.
The network canvas is white, matching common engineering diagrams. Body copy
is at least 14 px on the main working surface, and instruction/answer/report
text is approximately 15–16 px with generous line height. Tiny monospaced
labels remain supplemental; any essential status or unit is readable without
them. Maintain clear keyboard focus, contrast, and mobile stacking.

The desktop workspace keeps case selection, the instruction/answer timeline,
and run details. The network view sits adjacent to the timeline as a primary
work surface; smaller screens place it after the case summary and before the
timeline. Preserve the manual start, submit-next, and close controls. Add one
explicit **自动完成** action on an unstarted case and on a ready session. On an
unstarted case it creates one session, waits for ready, submits each registered
instruction in order, waits for its committed answer, then closes the session
and waits for the final report. On a ready session it continues at the first
uncommitted instruction. The mode never overlaps commands, skips a failed
turn, or starts another session. The operator can stop future automatic steps;
the currently accepted turn finishes normally. A failed or interrupted run
stops automatic advancement and preserves committed answers. Reconnect or
stream replay must not submit a duplicate; the client coordinates against
persisted status and stable idempotency keys for accepted commands.

The graph supports wheel/trackpad or button zoom, drag pan, **适配全图**, and
**回到当前任务**. Selecting a timeline step focuses its known target. Starting or
committing a step automatically animates to the relevant node or branch and
leaves enough neighboring context to understand the connection. Manual pan or
zoom is respected until the next explicit step selection or lifecycle change;
there is no continuous recentering. If a step has no identified model element,
focus the relevant visible network region or fit the graph and say why.

## Data and trust boundaries

The authority owns topology and current-run numerical facts. A Domain Pack
adapts them into a small, typed network presentation projection; the Kernel
remains domain neutral, and the application only renders the projection. Do
not send raw pandapower/PyPSA objects, DataFrames, arbitrary model files,
unbounded coordinates, authority internals, or unverified reference strings
to the browser. The projection identifies the registered model, revision,
source, coordinate quality, visible bus/branch counts, omitted counts, and
stable opaque element IDs. It includes bounded buses and lines, links, and
transformers with endpoints and optional finite coordinates. Diagram layout
is deterministic when coordinates are missing or unsuitable; it is labelled
schematic rather than geographic. Large models such as SciGRID-DE show a
bounded subset with an explicit truncation label and never imply a full-grid
view.

The first opened model of a run makes its topology available; before that,
the App displays the registered model name and a clear pending state. A
read-only, authenticated session endpoint serves the current-run projection
from the selected worker's authority path. Sequenced events notify the App
when the projection is ready or changes. The backend persists only bounded
projection data or references needed for replay, so an API replica can serve
it after reconnect. This route uses the same token, identity, size limits, and
cross-origin policy as other `/api/v1` routes. A domain without a valid
projection shows a precise unavailable state; a chart is never synthesized
from answer prose.

Registered case step metadata may identify a target element or region, but
highlighting requires matching that ID against the current projection. A
committed result may add a numeric overlay only when a current-run admitted
authority result supplies per-element values for the same model revision and
scenario/snapshot. The legend names the metric and unit. Examples are line
loading percent and bus voltage in per unit; the App does not derive these
from prose or invent thresholds. Continuous color scales are accompanied by
an exact value on focus/hover and a textual key. Elements without a value
stay neutral. If the result contains only aggregate or ranked values, color
only the identified elements and label partial coverage. If a scenario or
snapshot is ambiguous, show topology and highlights without a numerical
overlay. A selected historical step retains its own admitted overlay and
never silently inherits values from a later turn.

## Components and flow

1. A bounded network-projection contract and selected Domain Pack adapters
   fetch topology through the already registered authorities. The host stores
   and serves the current-run view without importing simulator internals.
2. A focused App network component validates the projection, draws accessible
   SVG buses/branches on a white canvas, provides pan/zoom/fit controls, and
   displays provenance, legend, omission, and unavailable states.
3. The App run coordinator owns manual or automatic command progression. It
   advances only after observed durable state says the previous command was
   committed. It stops on user request, error, failure, interruption, or
   disconnection; resuming is explicit.
4. Timeline selection and session events select graph focus and optional
   admitted value overlay. Graph navigation state stays separate from run
   state so gestures cannot change execution.

## Verification

- Focused backend tests cover authority projection identity, finite bounds,
  omission reporting, admission of matching current-run overlays, unavailable
  projections, and read authorization/replay.
- Focused App tests cover single-flight automatic progression, stop/resume,
  failure/interruption, manual control, topology/overlay gating, and focus
  behavior. Check accessible controls and representative narrow/mobile layouts.
- Run the smallest relevant tests first, then supported repository gates where
  feasible without repeating broad suites needlessly. Verify a local Compose
  browser run for one pandapower and one PyPSA case, including automatic mode,
  graph interaction, per-step focus, report, and evidence. No billed Provider
  validation or cloud deployment is part of this change.
