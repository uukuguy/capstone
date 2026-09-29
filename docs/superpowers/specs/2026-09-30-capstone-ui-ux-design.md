# Capstone Agent Web / CLI / TUI UI/UX Design

**Status:** Proposed design contract for the single-Run interaction milestone. It is derived from the accepted Thread, ModelContext, event, Harness, grid-page, and runtime decisions in `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`.

**Review status: NOT READY.** The latest deep review found contradictions in the action-precedence rules below. These rules are unresolved proposals, not implementation instructions. Completion and PASS claims in earlier review revisions are withdrawn; see `2026-09-30-capstone-ui-ux-deep-review.md`, “Reopened findings”.

**Scope:** Web App, Textual terminal UI, and headless CLI presentation. This document defines presentation behavior and interaction semantics; it does not replace the public `capstone-thread/1` protocol, `capstone-harness`, Domain Packs, or Authority contracts.

## Product interaction model

Capstone presents three surfaces of one workspace:

1. **Conversation is the command surface.** The user asks questions, starts Case batches, switches models, changes capability packages, cancels work, retries failed Attempts, and approves pending actions from the Thread.
2. **The grid is the truth surface.** The left workspace shows the current registered model projection, validated focus, and admitted overlays. It never derives topology or numbers from assistant prose.
3. **Evidence is the audit surface.** Tool source, model revision, selection revision, result/evidence references, Case steps, and replay controls remain available without crowding the main conversation.

The same action has one meaning in every client. A button, keyboard shortcut, API command, or clear conversational control request ends at the same Harness `CommandEnvelope`. A viewport gesture remains presentation-local; a model switch or professional analysis is a durable application action.

## Shared state shown by every client

Each client consumes `ThreadSnapshot` plus `EventPage` and maintains a local projection store. The business state shown in the primary workspace is:

- connection state: `connecting`, `live`, `reconnecting`, `resync_required`, or `offline`;
- Run state: `created`, `open`, `closing`, `closed`, or `failed`;
- current model: display name, exact revision, implementation family, and `active_grid_page_id`;
- viewed grid page: local `viewed_grid_page_id`, which may be a historical read-only page;
- current selection: enabled Profile/Domain Pack labels and `selection_revision`;
- current Turn/Attempt: phase (`created`, `accepted`, `running`, `waiting`, `committing`, terminal), progress, cancellation/approval state, retry availability, and runtime mode;
- active Case, when present: Case version, pinned Context snapshot, current step, completed steps, and blocked reason;
- latest authoritative answer, admitted results/evidence, and bounded source references.

The UI must always distinguish `active` from `viewed`. A historical page can be inspected without changing the current ModelContext. A model switch is confirmed by `model_context_activated`, after which the default follow-current behavior selects that model's page.

## Workspace controller and input policy

All clients derive a `ThreadWorkspaceViewModel` from the shared projection. Its action precedence is:

1. `resync_required` or `reconnecting`: freeze all state-changing actions; allow only reconnect, verified snapshot reload, help, and exit.
2. `replay` or a historical read-only view: freeze send, model switch, capability edits, Case controls, and element analysis; allow navigation and `Return to live`.
3. `run=closed|failed`: freeze business actions and show replay/read-only controls.
4. `approval_wait`: focus the approval surface; allow approve, deny, cancel, and diagnostics.
5. `active_attempt`: allow streaming, cancel, approval response, and explicitly accepted pending controls; disable new ordinary/professional Turn submission in v1.
6. `context=preparing|switch_pending|selection_pending`: show the pending target and keep the old effective Context visible until activation; disable a second conflicting change.
7. `ready`: enable the composer, model/profile actions, Case launch, and grid element actions when their page is active and valid.

The composer may retain a draft while input is disabled. Every submitted Turn displays a frozen target chip containing model ID/revision, ModelContext ID, selection revision, and optional element reference. A pending model or capability change is shown separately and never rewrites an in-flight Turn's chip. Reconnect and snapshot replacement preserve drafts only when their client-local target remains valid; otherwise the draft is retained as plain text with an explicit “review target before sending” state.

Clear conversational controls can bypass the ordinary composer route and create a control Turn/command. The UI never creates a second ordinary/professional Turn while one Attempt is active. A cancel, approval, retry, or pending model/profile command remains available through the command surface defined by Harness.

## Thread navigation and lifecycle

Thread navigation is part of the product shell, not a hidden API detail. Web uses a route such as `/threads/{thread_id}` with a recent Thread switcher, `New Thread`, rename, and recovery markers. Textual exposes the same picker through the command palette and a dedicated function key; headless CLI accepts `--thread-id`, `--new-thread`, and a clear error when neither an existing Thread nor creation intent is supplied.

The Thread picker shows title, last activity, current model, Run state, connection/recovery marker, and unread event count. Opening a Thread first loads its verified `ThreadSnapshot`, then catches up by `event_seq`; it never reuses a stale in-memory projection from another Thread. `New Thread` creates the default IEEE-39 page and starts a separate Run record. A closed Thread remains selectable for replay but cannot be mutated.

## Detailed interaction contracts

### New Thread and model loading

Thread creation renders a labeled IEEE-39 page in `loading` state and a connection status immediately. Ordinary conversation becomes available after the Thread snapshot and current Run are valid, even if the diagram later becomes `unavailable`. Professional/model actions remain disabled until the relevant ModelContext and capability contribution are ready. A failed revision resolution is a creation error with retry/new-thread actions; it never renders an unlabeled empty workspace.

### Grid element to composer

Selecting a bus or branch creates a local element reference chip with element kind, ID, label, model revision, and page status. `Ask about this` creates an ordinary or professional Turn according to the action; `Analyze this` explicitly requests the professional route. The chip is removable. Switching page, entering replay, receiving a new model Context, or losing projection validity marks it stale and disables send until the user removes it or returns to the referenced page. Keyboard and text-list selection provide a non-canvas path.

### Model switch and capability editing

The model drawer previews target model ID/revision, implementation family, default Profile set, and preparation status before dispatch. During an active Attempt it becomes `pending after Attempt N`; the existing Context remains the only effective target. Capability editing is staged: the drawer shows `Effective now`, a pending diff, exact Profile versions, and one atomic `Apply next Turn` action. Preparation failure keeps the previous Context/selection and exposes the stable error class, retryability, and action hint.

### Case preflight and batch mode

Case launch opens a preflight card containing exact Case version, step count, model/revision requirement, selected Profiles, and Context pin. Confirmation creates the batch relation; future steps remain visibly pending. The Thread composer changes to “Case active” and accepts only permitted control input until the batch completes or is cancelled. A blocked step shows the failed Attempt, required admission that failed, retry target, and cancel action. Completion restores normal input and leaves the step rail available for replay.

### Replay and recovery

Evidence links and Case steps enter replay with a visible `view_seq`, base event sequence, model revision, and read-only banner. `Return to live` restores the current active page without mutating Thread state. During reconnect/resync all state-changing controls are disabled. A verified snapshot replaces the projection atomically; the client then reads after `base_event_seq`. An interrupted Attempt is rendered as interrupted and offers `Retry as new Attempt`; the interface never calls it resumed without a verified checkpoint.

### Grid scale and readability

The renderer uses projection-provided counts, omitted metadata, and optional level-of-detail hints. For large networks it starts in an overview mode with labels reduced, preserves focus search by stable element ID, and allows a focused neighborhood view. Omitted buses/branches and unavailable coordinates remain visible as text status. Numeric overlays expose metric, unit, source reference, and revision; the UI does not invent values when projection coverage is partial.

## Web workspace

### Desktop shell

The Web App uses a dark-first operations workspace with two primary columns:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Capstone · Thread · connection · current model · Run controls         │
├───────────────────────────────────────┬──────────────────────────────┤
│ Grid Workspace                        │ Thread Conversation          │
│ model pages / topology / overlays     │ messages / progress / input  │
│                                       │                              │
└───────────────────────────────────────┴──────────────────────────────┘
```

At desktop widths, the grid column starts at 55–60% and the conversation column at 40–45%. The split is user-resizable within bounded limits. The conversation remains on the right, matching the user's requested reading flow from model to dialogue. A permanently visible third information column is not used.

The top bar contains the Capstone mark, Thread title and ID, connection/recovery indicator, current model badge, Run state, and a compact command menu. The current model badge shows the model name and revision; clicking it opens the model switch drawer rather than changing state immediately.

### Grid workspace

The grid header contains one tab per distinct Grid Model identity in the Thread. A tab shows model name, implementation family, active/current marker, and projection status. There is never more than one page for a model. A historical tab can be viewed read-only; `Use this model` is the explicit `model_switch` action.

The canvas renders a bounded grid projection (`capstone-network-diagram/1.0`, `capstone-network-view/2.0`, or a future `GridDiagramProjection`). It exposes:

- fit-to-view, zoom, pan, and focus controls;
- a `Follow current` toggle for automatic agent-driven focus;
- a compact overlay legend with metric, unit, source reference, and revision;
- visible `loading`, `unavailable`, `partial`, `stale`, and `read-only replay` states;
- a selected-element toolbar with `Ask about this` and `Analyze this` actions when the page is the active current model;
- a model/revision line that remains visible when the viewport is zoomed.

Agent focus never erases a user's manual viewport. With `Follow current` off, a new focus is shown as a non-invasive “analysis focus available” action. Pan, zoom, hover, and ordinary selection are local UI state. Element questions carry model Context and element IDs, never screen coordinates or image IDs. Historical pages show a read-only banner; their element analysis actions are disabled in v1 and offer `Use this model` as the explicit transition.

### Thread conversation

The conversation pane contains:

- a compact Thread header with the active model and enabled capability count;
- a virtualized chronological message list;
- user turns, assistant answers, control confirmations, clarification requests, and bounded progress cards;
- tool activity cards showing `ToolSourceRef`, status, duration, admitted result/evidence links, and retry/copy details;
- Case batch cards with step state and the blocked reason when applicable;
- a composer with model/context hint, trace-level selector, attachment/action affordances reserved for later milestones, and send/cancel controls.

Assistant messages are labeled as AI-generated content. Streaming text appears incrementally; the composer remains visible and changes to `Cancel` when the current Attempt is cancellable. A long operation always shows a phase/status card before the answer arrives. `trace_level=detailed` adds bounded explanation summaries in a collapsible card; it never exposes raw hidden reasoning.

### Drawers and overlays

Drawers are opened from the top command menu or keyboard shortcuts and overlay the workspace without creating a third permanent column:

- **Models:** registered model catalog, exact revision, implementation family, and switch action;
- **Capabilities:** Profile/Domain Pack descriptions, current selection revision, enable/disable/replace actions, and empty-selection explanation;
- **Case:** Case catalog, version, pinned Context, step timeline, retry/cancel actions;
- **Evidence:** admitted results, evidence references, artifact links, source metadata, and replay entry points;
- **Diagnostics:** connection, resync, runtime mode, error class, command receipts, and restricted diagnostic summaries.

Each drawer has a clear title, close action, focus return target, focus trap while modal, escape route, and keyboard navigation. Drawer content is read-only unless an explicit command control is present. A drawer never obscures the focused control; focus returns to the invoking control after close.

### Responsive Web behavior

- **≥ 1200px:** two-column workspace; drawers overlay from the right or bottom.
- **900–1199px:** two columns with a narrower grid and collapsible conversation context header.
- **< 900px:** one primary surface at a time with `Grid` and `Thread` tabs; the current page and active Attempt status remain pinned in the header. The tabs are keyboard-operable and expose selected state to assistive technology.
- **< 600px:** full-width conversation or grid surface, bottom command sheet, and no horizontal scrolling. The grid can open as a focused full-screen view and return to the Thread without changing business state.

Responsive changes affect presentation only. They never create a new Thread, Run, ModelContext, or event.

## Textual TUI

### Default layout

The default `capstone` command enters a Textual TUI using the same two-column model:

```text
┌──────────────────────────────────────────────────────────────┐
│ IEEE-39 · rev … · Run open · live · [model] [capabilities]   │
├──────────────────────────────┬───────────────────────────────┤
│ GRID                         │ THREAD                        │
│ page tabs                    │ messages                      │
│ TGP / ANSI projection        │ progress / tool source        │
│ overlay + focus              │ composer                      │
├──────────────────────────────┴───────────────────────────────┤
│ status · event cursor · shortcuts · current Attempt           │
└──────────────────────────────────────────────────────────────┘
```

The grid column is left and the conversation column is right. Widths are adjustable but bounded so the Thread composer and grid labels remain usable. Navigation, capabilities, Case, evidence, and diagnostics are hideable drawers or modal screens, never a dense permanent third column.

The TUI owns `ThreadProjectionStore`, cursor/reconnect state, local focus, scroll position, viewed page, and terminal capability state. Widgets render and dispatch public commands; they do not own Thread, Run, ModelContext, Turn, Attempt, tool, result, or evidence state.

### TUI page behavior

- one page tab per Grid Model identity;
- the current model page carries an active marker;
- a historical page can be inspected without switching the business Context;
- `m` or the model drawer invokes explicit `model_switch`;
- `f` toggles follow-current focus behavior;
- `r` fits the current diagram to the viewport;
- page status shows `loading`, `ready`, `unavailable`, `partial`, or `read-only`;
- TGP is selected after the startup capability probe, with runtime fallback to ANSI/Unicode;
- image placements and cache keys stay local to the TUI.

### TUI conversation behavior

The composer accepts ordinary questions, professional requests, Case commands, and control language. Clear controls are resolved by Harness before Pi/DSH work begins. Control confirmations and clarification requests appear as structured conversation entries. Tool cards show source Profile/Domain Pack and result/evidence references; a user can open the capability drawer from the card to disable a package for later Turns.

Recommended keyboard map. Function keys are used for drawers so terminal line-editing control characters retain their normal meanings. Single-letter shortcuts are active only when the composer is not focused; while typing, the user uses the command palette or function keys.

| Key | Action |
| --- | --- |
| `Tab` / `Shift+Tab` | move between operable regions |
| `F1` | open Thread picker / create Thread |
| `F6` | focus or maximize grid |
| `F7` | focus conversation/composer |
| `Ctrl+K` | open command palette |
| `F2` | open model drawer |
| `F3` | open capabilities drawer |
| `F4` | open evidence drawer |
| `F5` | open diagnostics drawer |
| `f` | toggle follow-current grid focus |
| `r` | fit grid to viewport |
| `Esc` | close drawer/modal or clear local focus |
| `Ctrl+C` | first press requests cancellation; second press exits after confirmation |
| `?` | show the complete keymap |

The command palette exposes the same public commands as the Web menu. Destructive or state-changing actions show a confirmation line with target model/Attempt IDs before dispatch when the action is not already explicit in the input. Key bindings are displayed in the focused control and in `?`; no binding silently overrides composer editing.

### TGP and ANSI presentation

The TUI consumes the same bounded projection in both modes. A dedicated `TerminalCanvas` owns image placement IDs, clear/redraw ordering, resize invalidation, and the final terminal write. No other widget emits graphics escape sequences. A local renderer chooses TGP, iTerm2 inline image, or Unicode/ANSI based on `TerminalCapabilitySnapshot`; if Textual cannot grant the canvas ownership needed for safe repaint, it selects Unicode/ANSI before emitting TGP. It never changes the projection, event stream, or evidence. A failed image write, resize, stale placement, or unsupported protocol switches to ANSI/Unicode and displays a small status marker explaining the degradation. Color is never the only indicator: focus uses labels/borders, loading uses text, and failures use an icon plus text label. Every image view has a textual grid summary for assistive tooling and terminal logs.

## Headless CLI

`capstone run` is optimized for scripts and automation, `capstone chat` for a line-oriented interactive session, and bare `capstone`/`capstone tui` for the full TUI. All three use `CapstoneThreadClient` and the same Harness commands.

- `capstone run` writes one final JSON object to stdout by default; status, progress, and diagnostics go to stderr.
- `capstone run --events` writes canonical bounded events as JSONL and does not mix in the final envelope.
- `capstone chat` prints a compact prompt containing current model, revision, selection revision, and connection state; streamed answer text and control confirmations remain readable without ANSI color.
- `--json`, `--no-color`, and `--events` are presentation flags only; they never change routing, admission, or evidence.
- A stale cursor or interrupted Attempt prints the stable error class, last safe event sequence, and the recovery action; it never claims a resumed run without a verified checkpoint.
- `capstone chat` accepts multiline input with an explicit end-of-input command (`Ctrl+D` at an empty line or `/send`); `Ctrl+C` cancels the active Attempt on the first press and exits only after a second press or explicit confirmation. Headless exit codes distinguish committed, cancelled, interrupted, rejected, and resync-required outcomes; recovery text remains on stderr.

The frozen `grid-agent run`, `analysis`, and `report` commands remain separate compatibility surfaces.

## Shared interaction states

| State | Web | TUI | Headless CLI |
| --- | --- | --- | --- |
| Connecting | header indicator + disabled send | status bar + disabled composer | stderr progress |
| Resync required | blocking recovery banner with snapshot reload; send, model, capability, Case, and page actions disabled | modal recovery screen with only reload/reconnect/exit | structured error + exit code |
| Model loading | page skeleton with revision | page status line | stderr status |
| Attempt running | streaming text + phase card + cancel | progress card + cancel key | stderr progress |
| Approval requested | inline approval card with expiry | modal/drawer approval prompt | prompt on stderr, command input |
| Capability required | answer-side action to open capabilities | capability drawer action | structured error/action hint |
| Case blocked | step timeline with retry/cancel | batch drawer/card | stderr event + nonzero result state |
| Historical page | read-only banner; element analysis disabled until `Use this model` | page marker/status line; element analysis disabled | replay/event output only |
| Run closed | read-only Thread with replay | read-only TUI | final snapshot/events only |

The same stable error class and related IDs appear in each surface. Client-specific wording can be shorter, but it cannot change the meaning or retryability. An error surface includes the stable class/code, retryability, related IDs, last safe event sequence, and an action hint. After `resync_required`, the client atomically replaces its projection from the verified snapshot, resets the viewed page to a valid page, and resumes only after reading events after `base_event_seq`.

Evidence and tool outputs use explicit authority labels: `admitted/current`, `historical`, `reference/non-authoritative`, or `diagnostic/unadmitted`. Only `admitted/current` may support the current answer or be offered as a current-evidence follow-up action.

## Visual and accessibility system

The Web visual system is dark-first and information-dense for engineering work: deep navy background, slate surfaces, high-contrast foreground, green running/healthy state, amber queued/waiting state, and red failure state. Connection state is separate from data freshness: the header shows connection plus last event time/cursor, while a grid projection shows its model revision, source, and `stale`/`unavailable` status where applicable. The generated master design system is stored at `design-system/capstone-agent/MASTER.md` and is the source for tokens, spacing, typography, motion, and contrast checks.

- Use Fira Sans for readable UI text and Fira Code for model IDs, revisions, event cursors, tool IDs, and code-like values.
- Use one consistent SVG icon family with accessible labels; do not use emoji as icons.
- Maintain visible keyboard focus and a minimum 4.5:1 text contrast ratio.
- Never use color alone for state; pair color with text, border, icon, or pattern.
- Respect `prefers-reduced-motion`; streaming and status remain understandable without animation.
- Keep clickable targets at least 44×44 CSS pixels on Web; TUI controls must have a visible text or key equivalent.
- Provide skip-to-workspace and skip-to-Thread links, preserve logical tab order, and keep focus visible and unobscured: global controls, grid pages, grid actions, conversation messages, composer, drawers.
- Drawers and modal screens trap focus while open and restore focus to their trigger when closed. Resync, approval, cancellation failure, and integrity errors move focus to their action surface.
- Live updates use polite announcements for progress and assertive announcements only for errors, approvals, cancellation, and resync requirements. Streamed answer text uses a bounded live region rather than announcing every token.
- Tool and evidence cards expose source and status in text so screen readers do not need to interpret the grid image.

## UI acceptance criteria

The UI milestone is complete when:

1. Web and TUI can create/load a Thread, display IEEE‑39, submit a Turn, stream progress, show a committed answer, and recover by `event_seq`.
2. Model tabs maintain one page per model, preserve historical pages, and distinguish viewed page from active ModelContext.
3. A clear conversational control and an equivalent button/shortcut produce the same command receipt and canonical events.
4. Tool cards show `ToolSourceRef`; professional claims without admitted results show a bounded capability/evidence state.
5. Case launch, step progress, blocking failure, retry, cancellation, and completion are visible in both Web and TUI.
6. TGP failure falls back to ANSI/Unicode without losing grid state; Web remains usable when image or diagram projection is unavailable.
7. Keyboard-only Web navigation, TUI keyboard navigation, reduced motion, contrast, and explicit error/recovery states pass focused UX checks.
