# Capstone Agent Deep Interaction UX Review

**Scope:** Scenario-level review of the Web, Textual TUI, and headless CLI design in `2026-09-30-capstone-ui-ux-design.md`, cross-checked against the Thread/Run/ModelContext/Harness decisions.

**Review verdict:** **NOT READY FOR UI IMPLEMENTATION.** The visual direction and two-column layout are sound, but the design is currently a component contract rather than a complete interaction design. The missing pieces are concentrated at state boundaries: Thread selection, active input policy, Context freeze, model switching, capability editing, grid-to-composer handoff, Case preflight, replay, and recovery.

## The central missing contract

The design needs one explicit UI state machine around a `ThreadWorkspaceViewModel`. Every surface should render the same derived states:

```text
Thread shell
  ├── connection: connecting | live | reconnecting | resync_required | offline
  ├── run: creating | open | closing | closed | failed
  ├── input: ready | active_attempt | approval_wait | clarification | frozen
  ├── context: preparing | active | switch_pending | selection_pending | failed
  ├── grid view: current | historical | replay | unavailable
  ├── case: none | preflight | running | blocked | completed | cancelled
  └── drawer/modal: none | model | capability | case | evidence | diagnostics | command
```

The current contract lists most individual states but does not define their precedence, the allowed actions in each combination, or which state owns the composer. Without this matrix, Web and TUI implementations will diverge even if they use the same events.

## Existing App baseline assessment

The current App is a useful visual baseline, but it is not yet a Thread UI. The review of `packages/capstone-app/src/App.tsx`, `NetworkView.tsx`, `styles.css`, and the existing session types finds:

### Strengths to carry forward

- The dark blue-green palette, mint accent, monospace metadata, low-radius controls, and restrained borders already give Capstone a coherent engineering identity.
- `NetworkView` has a real projection boundary: fit/zoom/pan/focus, keyboard handling, `role="img"`, a legend, omitted-count messaging, and explicit unavailable states.
- The existing timeline, status LEDs, answer cards, reference chips, and report/evidence details provide a good visual vocabulary for Attempt progress and admitted evidence.
- The top bar and compact brand mark are recognizable and should be retained unless a measured accessibility or density problem requires change.

### Structural gaps to correct

- `CatalogPanel` makes the Case library the primary navigation. A Thread route needs Thread switching and creation first; Case is a drawer/preflight action.
- `RunPanel` assumes one case-owned session and one ordinal workflow. The new workspace must render the current Grid Model and conversation even when no Case exists.
- The current `NetworkStory` is useful for topology focus but can be mistaken for business progress. Replay and Case step state need separate labels and event references.
- `AnswerCard` does not yet expose the authority distinction between admitted current results, historical references, and diagnostic output. A visually successful answer must not imply current evidence.
- Existing session states (`pending`, `ready`, `executing`, `closing`, `completed`, `failed`, `interrupted`) cover the legacy Case flow but do not encode transport trust, viewed/replay state, pending model/profile changes, approval, or a live Attempt viewed from a historical page.
- Existing responsive rules collapse the three columns vertically. That is acceptable for the compatibility App, but it does not provide the requested two-surface Thread interaction or a mobile Grid/Thread mode.

The conclusion is deliberate: preserve the visual material and network interaction where it is sound, while replacing the state model and shell composition. This is an explicit redesign, not a CSS reskin. The detailed geometry, action matrix, and state walkthroughs are now in `2026-09-30-capstone-ui-wireframes.md`.

## Scenario audit

### 1. Start a new Thread

**Expected flow:** create Thread → pin IEEE-39 revision → show one page in `loading` → activate projection → enable composer when the Thread snapshot is live.

**Missing decisions:** whether the user can submit ordinary conversation while the grid projection is loading; what happens when model revision resolves but the diagram is unavailable; where the user chooses a Thread title; how a failed Thread creation is retried; and how a user returns to an existing Thread.

**Required behavior:** allow ordinary conversation after a valid Thread snapshot even if the diagram is unavailable; keep professional/model actions disabled until the relevant capability is ready; expose Thread list/new/rename/archive navigation; never show an empty unlabelled workspace.

### 2. Submit an ordinary or professional Turn

**Expected flow:** composer captures text and optional element reference → UI displays the exact target model/revision and selection revision → Harness freezes the Attempt snapshot → progress/tool/answer events stream → composer returns to ready.

**Missing decisions:** whether a second ordinary message queues, replaces, or is blocked while an Attempt runs; whether a user can edit or withdraw text before submission; how the UI displays `ordinary`, `professional`, `mixed`, and `control` routing; and what happens when professional capability is unavailable.

**Required behavior:** v1 allows one active Attempt per Run; disable ordinary submission while active, while keeping cancel/approval and permitted controls available; show a target-context chip on every submitted Turn; use an explicit `capability_required` card with an action to open selection rather than silently retrying as ordinary.

### 3. Use a grid element to ask a question

**Expected flow:** select bus/branch → show element identity and model revision → choose `Ask about this` or `Analyze this` → add a structured element reference to the next Turn → send → clear or retain the chip according to the result.

**Missing decisions:** how selection is represented in the composer; whether changing pages invalidates the selection; whether a stale element can be sent; how keyboard users select an element; and whether `Analyze this` is a control or a professional Turn.

**Required behavior:** show a removable `element_kind/element_id` chip; page or Context changes invalidate it with a visible reason; historical/unavailable/stale pages disable analysis; keyboard focus and a textual element list provide a non-canvas path; `Ask about this` creates a Turn, while `Analyze this` uses the professional route with the same structured reference.

### 4. Switch model from chat or grid

**Expected flow:** user asks or chooses a model → resolve exact catalog entry → show compatibility/default Profile preview → accept command → wait for active Attempt boundary → prepare new Context → activate → select the existing model page.

**Missing decisions:** how pending switch appears while an Attempt runs; whether the user may continue viewing the old model; whether a failed preparation preserves the old page; how Profile defaults are previewed; and how same-model revision changes are explained.

**Required behavior:** show a persistent `switch pending after Attempt N` banner; keep old Context active until `model_context_activated`; show the target model, revision, and Profile set before confirmation; on failure keep the old active page and show a retryable error; after success converge `active_grid_page_id` and the default viewed page.

### 5. Edit capability selection

**Expected flow:** open Capabilities drawer → inspect package descriptions and tool counts → stage enable/disable changes → review diff → apply one `replace_selection` command → prepare new contribution set → activate at a Turn boundary.

**Missing decisions:** whether each checkbox dispatches immediately; how pending changes are distinguished from effective selection; how a failed preparation is shown; how semantic overlap is explained; and how selection behaves while a Case is running.

**Required behavior:** use a staged selection editor with `Effective now` and `Pending next Turn` sections; one Apply action submits the atomic change; show exact Profile versions and implementation family; never claim that overlap was automatically resolved; disable editing during a pinned Case except through cancellation.

### 6. Launch and run a Case

**Expected flow:** choose Case → inspect version, steps, model requirement, and Context pin → confirm → run one step at a time → show current step and committed outputs → complete or block.

**Missing decisions:** whether Case launch is a drawer action or a chat command; what preflight checks are visible; how a blocked step offers retry; how users return to normal chat; and whether the user can inspect a future step before it runs.

**Required behavior:** provide a Case preflight card with exact version, model/revision, selected Profiles, step count, and known requirements; once started, show a batch rail in the Thread; keep future steps visibly pending; block later steps after required failure; expose retry/cancel only for valid targets; restore normal composer state after completion/cancellation.

### 7. Approval, cancellation, and interruption

**Expected flow:** approval requested or cancel pressed → show exact Attempt/tool/source/reason and expiry → accept decision → stream terminal event → update composer and cards.

**Missing decisions:** whether approval blocks all other controls; how expiry looks; how a cancellation that becomes `interrupted` differs from a confirmed cancel; and how a retry relates to the original answer.

**Required behavior:** approval modal/card owns focus until decision or expiry; cancellation keeps the user in the same Thread and shows admission cutoff; `cancelled` and `interrupted` have different recovery actions; retry always says “new Attempt” and links the prior Attempt.

### 8. Reconnect and strict recovery

**Expected flow:** transport loss → reconnect → read events after cursor → detect gap or invalid cursor → block actions → replace projection from verified snapshot → resume.

**Missing decisions:** how the UI distinguishes temporary reconnect from an interrupted Attempt; whether a user can submit during reconnect; how local viewed page and scroll are restored; and what the user sees when no verified checkpoint exists.

**Required behavior:** disable all state-changing controls during `reconnecting` and `resync_required` except reconnect/reload/exit; never label a recovered Attempt as resumed without a verified checkpoint; show `Attempt interrupted — retry creates a new Attempt`; restore the last safe page only after snapshot verification.

### 9. Historical replay and evidence inspection

**Expected flow:** open evidence or prior step → enter read-only replay with `view_seq` → inspect answer/grid/tool source → exit replay → return to current live page.

**Missing decisions:** how replay mode is entered from a message, Case step, or evidence reference; how the current live model is kept visible; what actions are disabled; and how replay differs from viewing a historical model page.

**Required behavior:** show a replay banner with `view_seq`, base event sequence, model revision, and read-only state; disable send, model switch, capability edits, element analysis, and Case controls while replaying; provide `Return to live`; keep replay cursor client-local.

### 10. Close Run and revisit Thread

**Expected flow:** close command → show drain/cancel impact → Run closes → Thread becomes read-only but replayable → Thread list can reopen the record.

**Missing decisions:** where close is exposed, what happens to an active Case, how a closed Thread differs from an offline Thread, and how a user starts a fresh Thread with IEEE-39.

**Required behavior:** close is in the command palette/top bar, displays active work and consequence, requires confirmation when work is active, and leaves a clear `Read-only — Run closed` header. New Thread is a separate action and never mutates the closed record.

## Cross-surface gaps

### Thread navigation is absent

The design has a Thread title and ID but no Thread list, creation, rename, archive, or deep-link behavior. Web needs a navigable workspace route; TUI needs a Thread picker/new-thread command; CLI needs explicit `--thread-id` and a creation path. This is a high-severity information architecture gap.

### Composer ownership is absent

The composer needs a formal contract: when it is enabled, which actions bypass it, how pending Context/selection is displayed, how element references attach, how multiline input works, and what happens to draft text during reconnect or model switching. A visible composer alone does not define a safe interaction.

### Evidence and answer hierarchy is absent

The design names evidence drawers and tool cards but does not define which answer text is authoritative, which result is current, which reference is historical, and which output is diagnostic. Every result card needs an authority state and a clear action policy.

### Grid scalability is absent

The authority projection may contain hundreds or thousands of buses/branches. The design needs a density/overview mode, omitted-count treatment, focus search, and a rule for when labels/overlays are hidden. A two-column layout alone does not make the network readable.

### Web/TUI parity is stated but not demonstrated

The document says the clients share commands and read models, but it does not provide a parity table for all state transitions. The implementation plan needs one scenario fixture that drives both clients from the same EventPage and asserts equivalent visible state and enabled actions.

## Priority before implementation

1. Freeze the `ThreadWorkspaceViewModel` state precedence and composer policy.
2. Add Thread navigation and lifecycle screens.
3. Specify the ten flows above as transition tables with enabled/disabled actions.
4. Add explicit element-reference, pending-switch, staged-capability, Case-preflight, replay, and recovery components.
5. Define grid scalability and TGP prototype gates.
6. Only then create Web/TUI component implementation plans.

## Post-correction status

The UI/UX contract was expanded after this deep review with a `ThreadWorkspaceViewModel` action-precedence model, explicit Thread navigation, composer target/context freezing, one-active-Attempt input policy, element-reference invalidation, model-switch and staged-capability flows, Case preflight, replay/recovery behavior, grid-scale rules, and a TUI Thread picker.

The added text is a candidate correction, not proof of closure. Three prototype/verification activities remain useful after the contradictions below are resolved:

1. Build a Web state-fixture matrix that verifies enabled/disabled actions for each workspace state.
2. Prototype `TerminalCanvas` on Ghostty and iTerm2 to verify Textual repaint, resize, placement cleanup, and ANSI fallback.
3. Test large-network projection performance and choose concrete level-of-detail thresholds from measured projections rather than arbitrary UI constants.

**Updated verdict: NOT READY.** The earlier PASS conclusion was premature and is withdrawn. The following counterexamples remain open; adding a state-controller name has not resolved them.

## Reopened findings

These are design defects found by tracing concrete operations against the current text. Recommendations below are proposals; none is marked resolved without a consistent transition table and a walkthrough of its visible states.

| ID / priority | Reproduction and conflicting rules | User consequence | Required design resolution |
| --- | --- | --- | --- |
| R1 / blocking | During an active calculation, type “停止，切换到另一个模型”. The composer is disabled or replaced by Cancel, yet conversational controls are promised. | The primary command surface disappears at the time control matters most; a button cannot express the full request. | Separate editable draft, message submission, business execution scheduling, and control execution. Specify what happens to control, ordinary, mixed, and ambiguous input while busy; do not let frontend classification decide authorization. |
| R2 / blocking | While a live Attempt runs, inspect an old model page. The historical-view rule freezes model changes and Case controls, but the same page offers “Use this model”; replay takes precedence over approval/cancel. | Users cannot perform the advertised model switch, or stop live work while viewing history. | Distinguish live execution state, inspected model, replay cursor, and connection trust. Historical writes stay disabled; any live cancellation targets the explicit live Attempt independently. Provide an action matrix instead of one global priority ladder. |
| R3 / blocking | Create Thread with pinned IEEE-39 metadata and no live handles, then request power flow. Professional actions are disabled until capability preparation, while architecture starts preparation on the first executable Turn. | The first professional interaction can never initiate preparation. | Accept a valid request against declared capabilities, render preparation, then execute or report failure. Diagram availability must be independent from calculation readiness. |
| R4 / high | Send “切换到 SciGRID，然后计算潮流”; model preparation is slow or fails. Control turns and business turns are specified separately, with no dependency relation. | Calculation may start on the old model, disappear, or require the user to retype the second clause. | Specify a visible dependent request sequence: resolution, pending switch, activation, business submission, and failure disposition. If v1 does not support compound requests, define an explicit clarification flow preserving the unsent instruction. |
| R5 / high | Submit a model switch, server accepts, connection drops before receipt. Reload snapshot or re-press Apply. | A second command may be created; a cancelled UI request may still activate later. | Define local pending-command identity, reconciliation by the original idempotency key/command ID, acceptance versus activation, and superseding/withdrawing pending changes. No automatic new-key resend. |
| R6 / high | Select a line on an old revision, draft a question, browse another tab, return after that model has changed revision. Current text implies returning to the page can unblock Send. | A stale reference can be attached to a new model state; incidental tab browsing may also discard valid context. | Bind attachments to stable model/revision/element identity; page focus alone must not validate or invalidate a reference. Specify historical explanation versus current computation and preserve user text. |
| R7 / high | A Case step blocks because a package needs adjustment. Selection is pinned; edits require cancelling the Case. | Users can only repeat the same failure or abandon the batch. “Blocked-step recovery” is incomplete. | Distinguish same-context retry from corrected-context restart; show what committed steps remain and what will rerun. Reassess global Case pinning as a proposal against the user's instruction-sequence model. |
| R8 / high | `capstone run` is invoked by a script and reaches approval. The headless state table requires interactive input, while no-input behavior and exit codes are unspecified. | Automation can hang or leave unclear live work. | Define noninteractive approval-required output, attachment/resolution path, timeout/disconnect policy, exact exit codes, and final JSON/JSONL terminal semantics. |

### Layout and operation details still missing

- **Conversation reading:** when the user scrolls up during streaming, define scroll anchoring, unread indicator, return-to-latest, tool-card expansion and preserved selection. Specify how cancelled partial answers and retries are grouped so they cannot look committed.
- **Model tabs:** specify overflow, stable model identity versus duplicate display names, revision badges, active/viewed markers, keyboard selection, and whether hiding a tab removes only presentation state. Use one page per model throughout.
- **Two-pane workspace:** give minimum usable pane widths and terminal cell dimensions, splitter keyboard controls, compact-mode transitions, per-Thread viewport retention, and what happens when a drawer covers the input or selected element.
- **Information hierarchy:** raw Context IDs, sequence numbers and revisions are currently prescribed in the primary header, composer and replay banner. Default views should identify the model and action outcome; inspect/copy details can reveal internal identifiers. Choose the hierarchy explicitly instead of displaying every field everywhere.
- **Evidence interaction:** distinguish an immutable admitted historical result from a currently applicable result and from current-Attempt admissibility. Opening old evidence must preserve its provenance; a label or UI action cannot grant reuse in a new Attempt.
- **TUI operations:** Ctrl+K still overlaps editor behavior; Ctrl+C lacks idle, selected-text, cancellation-pending, and exit-with-live-worker cases. Image placement ownership does not yet define picking, image-to-cell hit testing, overlay labels, or mouse/keyboard parity.
- **Visual direction:** the generated MASTER originally used a generic operations landing template with hero/CTA sections, glow and staggered motion. This pass reclassified it as a product token draft, aligned its palette/typography with the existing App, and explicitly removed those patterns from the Thread workspace. A browser visual prototype is still required before calling the visual system validated.

### Evidence required to close this review

The draft action matrix and annotated Web/TUI/CLI walkthroughs now live in `2026-09-30-capstone-ui-wireframes.md`. Closing this review still requires user review of the proposed behavior, fixture-driven state tests for R1–R8, and a limited TGP/browser prototype. Those prototypes can test feasibility, but cannot silently approve unresolved interaction choices. Keep unapproved behavior explicitly proposed.
