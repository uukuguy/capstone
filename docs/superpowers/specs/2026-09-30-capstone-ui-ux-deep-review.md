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

The design is now suitable for an implementation plan, with three implementation gates still required:

1. Build a Web state-fixture matrix that verifies enabled/disabled actions for each workspace state.
2. Prototype `TerminalCanvas` on Ghostty and iTerm2 to verify Textual repaint, resize, placement cleanup, and ANSI fallback.
3. Test large-network projection performance and choose concrete level-of-detail thresholds from measured projections rather than arbitrary UI constants.

**Updated verdict:** **PASS WITH IMPLEMENTATION GATES.** The design is no longer only a component inventory; it now specifies the user decisions and recovery behavior at the major state boundaries.
