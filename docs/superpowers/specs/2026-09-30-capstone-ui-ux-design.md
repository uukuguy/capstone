# Capstone Agent Web / CLI / TUI UI/UX Design

**Status:** Proposed design contract for the single-Run interaction milestone. It is derived from the accepted Thread, ModelContext, event, Harness, grid-page, and runtime decisions in `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`.

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
- Run state: `open`, `closing`, `closed`, or `failed`;
- current model: display name, exact revision, implementation family, and `active_grid_page_id`;
- viewed grid page: local `viewed_grid_page_id`, which may be a historical read-only page;
- current selection: enabled Profile/Domain Pack labels and `selection_revision`;
- current Turn/Attempt: phase, progress, cancellation/approval state, retry availability, and runtime mode;
- active Case, when present: Case version, pinned Context snapshot, current step, completed steps, and blocked reason;
- latest authoritative answer, admitted results/evidence, and bounded source references.

The UI must always distinguish `active` from `viewed`. A historical page can be inspected without changing the current ModelContext. A model switch is confirmed by `model_context_activated`, after which the default follow-current behavior selects that model's page.

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

The canvas renders the bounded `GridDiagramProjection` or `GridDiagramProjection`-compatible network view. It exposes:

- fit-to-view, zoom, pan, and focus controls;
- a `Follow current` toggle for automatic agent-driven focus;
- a compact overlay legend with metric, unit, source reference, and revision;
- visible `loading`, `unavailable`, `partial`, `stale`, and `read-only replay` states;
- a selected-element toolbar with `Ask about this` and `Analyze this` actions;
- a model/revision line that remains visible when the viewport is zoomed.

Agent focus never erases a user's manual viewport. With `Follow current` off, a new focus is shown as a non-invasive “analysis focus available” action. Pan, zoom, hover, and ordinary selection are local UI state. Element questions carry model Context and element IDs, never screen coordinates or image IDs.

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

Each drawer has a clear title, close action, focus return target, and keyboard navigation. Drawer content is read-only unless an explicit command control is present.

### Responsive Web behavior

- **≥ 1200px:** two-column workspace; drawers overlay from the right or bottom.
- **900–1199px:** two columns with a narrower grid and collapsible conversation context header.
- **< 900px:** one primary surface at a time with `Grid` and `Thread` tabs; the current page and active Attempt status remain pinned in the header.
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

Recommended keyboard map:

| Key | Action |
| --- | --- |
| `Tab` / `Shift+Tab` | move between operable regions |
| `Ctrl+G` | focus or maximize grid |
| `Ctrl+T` | focus conversation/composer |
| `Ctrl+K` | open command palette |
| `Ctrl+M` | open model drawer |
| `Ctrl+P` | open capabilities drawer |
| `Ctrl+E` | open evidence drawer |
| `Ctrl+D` | open diagnostics drawer |
| `f` | toggle follow-current grid focus |
| `r` | fit grid to viewport |
| `Esc` | close drawer/modal or clear local focus |
| `Ctrl+C` | request cancellation for the active Attempt |
| `?` | show the complete keymap |

The command palette exposes the same public commands as the Web menu. Destructive or state-changing actions show a confirmation line with target model/Attempt IDs before dispatch when the action is not already explicit in the input.

### TGP and ANSI presentation

The TUI consumes the same bounded projection in both modes. A local renderer chooses TGP, iTerm2 inline image, or Unicode/ANSI based on `TerminalCapabilitySnapshot`. It never changes the projection, event stream, or evidence. A failed image write, resize, stale placement, or unsupported protocol switches to ANSI/Unicode and displays a small status marker explaining the degradation. Color is never the only indicator: focus uses labels/borders, loading uses text, and failures use an icon plus text label.

## Headless CLI

`capstone run` is optimized for scripts and automation, `capstone chat` for a line-oriented interactive session, and bare `capstone`/`capstone tui` for the full TUI. All three use `CapstoneThreadClient` and the same Harness commands.

- `capstone run` writes one final JSON object to stdout by default; status, progress, and diagnostics go to stderr.
- `capstone run --events` writes canonical bounded events as JSONL and does not mix in the final envelope.
- `capstone chat` prints a compact prompt containing current model, revision, selection revision, and connection state; streamed answer text and control confirmations remain readable without ANSI color.
- `--json`, `--no-color`, and `--events` are presentation flags only; they never change routing, admission, or evidence.
- A stale cursor or interrupted Attempt prints the stable error class, last safe event sequence, and the recovery action; it never claims a resumed run without a verified checkpoint.

The frozen `grid-agent run`, `analysis`, and `report` commands remain separate compatibility surfaces.

## Shared interaction states

| State | Web | TUI | Headless CLI |
| --- | --- | --- | --- |
| Connecting | header indicator + disabled send | status bar + disabled composer | stderr progress |
| Resync required | blocking recovery banner with snapshot reload | modal recovery screen | structured error + exit code |
| Model loading | page skeleton with revision | page status line | stderr status |
| Attempt running | streaming text + phase card + cancel | progress card + cancel key | stderr progress |
| Approval requested | inline approval card with expiry | modal/drawer approval prompt | prompt on stderr, command input |
| Capability required | answer-side action to open capabilities | capability drawer action | structured error/action hint |
| Case blocked | step timeline with retry/cancel | batch drawer/card | stderr event + nonzero result state |
| Historical page | read-only banner | page marker/status line | replay/event output only |
| Run closed | read-only Thread with replay | read-only TUI | final snapshot/events only |

The same stable error class and related IDs appear in each surface. Client-specific wording can be shorter, but it cannot change the meaning or retryability.

## Visual and accessibility system

The Web visual system is dark-first and information-dense for engineering work: deep navy background, slate surfaces, high-contrast foreground, green running/healthy state, amber queued/waiting state, and red failure state. The generated master design system is stored at `design-system/capstone-agent/MASTER.md` and is the source for tokens, spacing, typography, motion, and contrast checks.

- Use Fira Sans for readable UI text and Fira Code for model IDs, revisions, event cursors, tool IDs, and code-like values.
- Use one consistent SVG icon family with accessible labels; do not use emoji as icons.
- Maintain visible keyboard focus and a minimum 4.5:1 text contrast ratio.
- Never use color alone for state; pair color with text, border, icon, or pattern.
- Respect `prefers-reduced-motion`; streaming and status remain understandable without animation.
- Keep clickable targets at least 44×44 CSS pixels on Web; TUI controls must have a visible text or key equivalent.
- Preserve logical tab order: global controls, grid pages, grid actions, conversation messages, composer, drawers.
- Live updates use polite announcements for progress and assertive announcements only for errors, approvals, cancellation, and resync requirements.
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

