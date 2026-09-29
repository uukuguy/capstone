# Capstone Thread UI Wireframes and Action Matrix

**Status:** Proposed implementation gate. This document makes the Web, Textual TUI, and headless CLI behavior concrete enough to prototype. It does not approve implementation; unresolved items remain explicitly marked.

**Related:** `2026-09-30-capstone-ui-ux-design.md`, `2026-09-30-capstone-ui-ux-deep-review.md`, and the current App in `packages/capstone-app/src`.

## Design direction

Capstone should look like a scientific operations instrument, not a generic chat product or a marketing dashboard. The current App provides useful material: dark blue-green surfaces, mint accent, monospace metadata, restrained borders, answer/reference cards, and a network projection with keyboard support. The redesign keeps those strengths and removes the case-first three-column information architecture.

### Tokens used by the first prototype

| Token | Value | Use |
| --- | --- | --- |
| `canvas` | `#081216` | application background |
| `surface` | `#0c191d` | pane and header background |
| `surface-raised` | `#102126` | cards, drawers, composer |
| `surface-soft` | `#13272b` | selected and hover states |
| `line` | `#20353a` | pane and card borders |
| `text` | `#e9efed` | primary text |
| `muted` | `#98a9a9` | secondary text |
| `accent` | `#7cdbc8` | focus, active, admitted/healthy |
| `queued` | `#d4b46e` | waiting/preparing |
| `danger` | `#dc9789` | failed/interrupted |

The prototype may improve contrast, density, or spacing when measurements show a problem. It must not introduce gradients, glow-heavy cards, hero banners, or decorative motion that compete with the grid and conversation. The existing `Capstone` mark and network visual language may be retained; a component that hides target identity, authority, or recovery state should be redesigned even if it is visually familiar.

## Workspace geometry

### Web desktop (minimum usable desktop: 1200 × 760 CSS px)

```text
┌────────────────────────────────────────────────────────────────────────┐
│ CAPSTONE  Thread title  ● live  IEEE-39 rev 7  Run open   ⋯ commands  │ 56px
├───────────────────────────────────────────────┬────────────────────────┤
│ GRID PANE                                     │ THREAD PANE             │
│ page tabs / current marker                   │ thread header           │
│ model + revision + projection status        │ unread / follow latest  │
│                                              │ message stream          │
│  ┌────────────────────────────────────────┐  │ tool/evidence cards     │
│  │ bounded topology projection            │  │                          │
│  │ fit  zoom  focus  legend               │  │                          │
│  └────────────────────────────────────────┘  │                          │
│ selected element actions                    ├────────────────────────┤
│ page summary / omitted counts               │ composer + send/control   │ min 420px
├───────────────────────────────────────────────┴────────────────────────┤
│ event cursor · active Attempt · connection detail · keyboard hint      │ 28px
└────────────────────────────────────────────────────────────────────────┘
```

- Header: 56–64 px. Footer/status rail: 24–32 px. The footer never replaces an error banner.
- Grid pane: 55–60% of remaining width; minimum 620 px at the desktop breakpoint.
- Thread pane: 40–45%; minimum 420 px. The splitter can move only while both minima remain satisfied.
- Grid page tabs are horizontal and scrollable. Each tab is a stable Grid Model identity, not a Case step. The active model has an accent rule; the viewed historical model has a replay/read-only marker.
- The Thread header contains the title, current model, capability count, `Follow latest`, unread count, and a menu. It does not expose raw IDs by default; copy/details reveal IDs and revisions.
- The composer is sticky at the bottom of the Thread pane. The message list scrolls independently. A drawer overlays the relevant pane and returns focus to the triggering control.

### Web compact modes

| Viewport | Layout | Required behavior |
| --- | --- | --- |
| 900–1199 px | two columns, 50/50 bounded split | collapse nonessential model metadata; keep composer and grid toolbar usable |
| 600–899 px | one surface with `Grid` / `Thread` tabs | global header still shows live Attempt and connection; switching tabs never changes business state |
| < 600 px | full-screen surface + bottom command sheet | model/revision and recovery state remain visible; grid opens as a focused view and returns to Thread |

The old App's three-column layout may remain as a short-lived compatibility view while the new Thread route is built, but the Thread route must use this geometry. A case panel must not reclaim the Thread pane.

### Textual TUI (minimum target: 120 × 40 cells)

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CAPSTONE  IEEE-39  rev 7  ● live  Run open   [F1 Threads] [F2 Models] [F3 Packs] [F4 Evidence] [F5 Logs] │ 2
├──────────────────────────────────────────────────┬───────────────────────────────────────────────────────────┤
│ GRID (68 cells)                                  │ THREAD (51 cells)                                       │
│ [IEEE-39*] [SciGRID]                             │ ● current Attempt: none                                │
│ model: pandapower · rev 7 · ready               │ assistant / user / tool entries                         │
│                                                  │                                                           │
│ +------------------------------+                 │                                                           │
│ | TGP image or ANSI topology   |                 │                                                           │
│ | fit  zoom  focus             |                 │                                                           │
│ +------------------------------+                 │                                                           │
│ bus/branch focus and summary                   │                                                           │
│                                                  │                                                           │
│                                                  ├───────────────────────────────────────────────────────────┤
│                                                  │ > draft text                                             │
├──────────────────────────────────────────────────┴───────────────────────────────────────────────────────────┤
│ live · cursor 183 · model page IEEE-39 · F7 conversation · Ctrl+K commands · ? keymap                       │ 2
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- The grid gets at least 56% of usable width at 120 columns and the Thread at least 38%; the divider is adjustable in 2-cell increments.
- At widths below 100 cells, the TUI switches to one surface at a time while preserving the header and active Attempt rail.
- `TerminalCanvas` is the only widget allowed to emit TGP or iTerm2 image sequences. A startup probe selects TGP, then runtime fallback selects ANSI/Unicode. Renderer failure never changes the Harness projection.
- TUI drawers are modal screens or overlays. They are not a third permanent column and do not take ownership of Thread state.

## Action matrix

The UI derives actions from four independent axes. This avoids the previous failure mode where “historical view” accidentally hid a live cancel action or “active Attempt” disabled all useful input.

| Action | Transport | Execution | View | Context | Visible placement |
| --- | --- | --- | --- | --- | --- |
| `send_ordinary` | live | idle | live | active | composer primary send |
| `send_professional` | live | idle or `preparing` | live | active/preparing | composer route badge; preparation card if needed |
| `send_control` | live | idle/active/approval | live/historical | any valid live target | active Attempt rail, command palette, explicit control submit |
| `cancel_live_attempt` | live | active/approval | live/historical | any | global live Attempt rail; target is shown |
| `approve` / `deny` | live | approval | live/historical | any | approval card and command palette |
| `model_switch` | live | idle; otherwise staged | live | active | model drawer; pending banner while active |
| `replace_selection` | live | idle; otherwise staged | live | active | capability drawer; one atomic Apply |
| `launch_case` | live | idle | live | active | Case preflight card/drawer |
| `retry_new_attempt` | live | terminal | live | valid target | failed/interrupted card |
| `open_replay` | live/offline with snapshot | any | any | any | answer/evidence/case link |
| `return_live` | live/offline with snapshot | any | historical/replay | any | replay banner |
| `reconnect` / `resync` | any | any | any | any | header, recovery banner, TUI modal |

Rules:

1. When transport is not `live`, the client may render a command but cannot present it as accepted. It retains the draft and shows the missing receipt.
2. `send_control` and `cancel_live_attempt` target the live Attempt explicitly, so viewing another model page does not hide them.
3. `send_ordinary`, `send_professional`, `model_switch`, `replace_selection`, and `launch_case` require the live workspace. A replay banner offers `Return to live` rather than silently mutating history.
4. Every command displays command ID/idempotency key while pending in Diagnostics. A reconnect reconciles the original key; pressing Apply again does not create a new command.
5. A client-side classifier may suggest a route, but only Harness receipts and admission events change the action state.

## Annotated state walkthroughs

### Idle / new Thread

1. `New Thread` opens a creation surface with the default IEEE-39 model name and the resolved revision when available.
2. Header shows `creating` then `live`; grid page shows `loading` or `unavailable` with a textual reason.
3. Once the Thread snapshot is valid, ordinary chat is enabled. A professional request is accepted and may enter `preparing`; the UI never requires a hidden “prepare capabilities” step.
4. If revision resolution fails, the workspace is replaced by a creation error with `Retry` and `Create without model` only if the public contract permits an empty context. No unlabeled grid is shown.

### Active calculation and control

```text
THREAD HEADER  ● Attempt A-17 running · power flow · [Stop]
MESSAGE        You asked for a static analysis…
TOOL CARD      pandapower-static / load_flow · running · source details
COMPOSER       [draft: 停止，切换到 PyPSA] [Send control] [ordinary send disabled]
```

The draft remains editable. `Send control` opens a small preview: “Stop Attempt A-17; then switch to PyPSA?” If the dependent switch is explicit and resolvable, Harness records a control plan. If not, it records a clarification request and preserves the draft. The direct `Stop` button never guesses a model switch.

### Pending model switch

The model drawer shows the target model, exact revision, implementation family, default Profile set, and a preparation estimate/status. After receipt:

```text
LIVE CONTEXT  IEEE-39 / rev 7 / active
PENDING       PyPSA-39 / rev 3 / switch after Attempt A-17
GRID          continues showing IEEE-39, marked “current until activation”
THREAD        banner: “Switch accepted · waiting for Attempt boundary”
```

`model_context_activated` changes the active marker and automatically selects the existing PyPSA page. A failed preparation keeps IEEE-39 active and presents a retryable error with the original command identity.

### Approval

An approval card appears in the Thread and owns focus:

```text
APPROVAL REQUIRED  tool: contingency_analysis
source              pandapower-static@1.0 / Profile P-2
reason              operation can change the registered model
expires             00:42
[Approve] [Deny] [Cancel Attempt] [View source]
```

The global live Attempt rail remains visible. Expiry becomes a terminal approval rejection with a new-Attempt retry action where allowed.

### Historical page while live work runs

The grid header shows `viewing SciGRID / rev 2 · historical` and a `Return to live` button. The top header still shows `Attempt A-17 running · [Stop]`. Historical element actions are disabled. The user can stop the live Attempt without changing the viewed page; the stop receipt names A-17.

### Replay and evidence

Opening a result or evidence chip adds a banner:

```text
REPLAY  event 148 · model IEEE-39 rev 7 · read-only
source  admitted/current at Attempt A-12 · [Return to live] [Copy reference]
```

Replay cards expose the authority label, source Profile, result/evidence reference, and event sequence. They never become current evidence by being copied or selected.

### Reconnect and strict recovery

During reconnect, the header and composer show `reconnecting · commands paused`. A verified snapshot replaces the projection atomically, then the client catches up after `base_event_seq`. If the active Attempt lost continuity, the card becomes `interrupted · retry creates new Attempt`; it never says resumed. Draft text survives as text, while stale element chips are marked for review.

### Case batch and blocked step

The Case card shows version, pinned model/profile context, and a step rail. A blocked step has two explicit paths:

- `Retry same context`: rerun the failed step with the same Context and selection revision.
- `Correct context and restart`: cancel the batch, edit the staged packages/model, and show which committed steps will be reused or rerun.

The UI must not imply that a package conflict was automatically resolved. Tool cards show package/profile provenance so the professional can diagnose it.

## Headless CLI contract

### Command shapes

```text
capstone                         # Textual TUI
capstone tui [--thread-id ID]    # explicit TUI
capstone chat [--thread-id ID]   # line-oriented interaction
capstone run --question TEXT     # one final JSON object on stdout
capstone run --events ...        # canonical JSONL events, no mixed prose
capstone run --new-thread ...    # create and pin default IEEE-39
```

`capstone chat` prints a short prompt with model, revision, selection revision, connection, and active Attempt. `/send` ends multiline input; `Ctrl+D` at an empty line also submits. `Ctrl+C` cancels the active Attempt once and exits only after a second press or explicit confirmation.

Headless approval is deterministic:

- with an interactive TTY, print a bounded approval prompt to stderr and accept `y`, `n`, or `cancel`;
- with stdin not attached to a TTY, emit an approval-required terminal event/result to stderr/JSONL and exit with a stable nonzero code; never hang and never auto-approve;
- if a receipt is lost, reconcile by command ID/idempotency key before retrying; never submit a new key automatically.

The compatibility `grid-agent run`, `analysis`, and `report` envelopes remain untouched.

## Prototype and review gates

Before implementation is called UI-ready, the prototype must demonstrate:

1. the eight reopened scenarios in the deep review using one shared fixture stream;
2. equivalent command receipts and visible action states in Web and TUI;
3. composer draft retention, stale element invalidation, and scroll/unread behavior;
4. one model page per identity, active versus viewed markers, and historical replay;
5. TGP failure, resize, placement cleanup, and ANSI fallback on Ghostty and iTerm2;
6. headless approval, resync, interruption, and exact exit codes;
7. visual continuity with the existing App while removing the case-centric three-column shell.

The implementation plan must not start from component names alone. Each component is accepted only after its state fixture, command target, receipt behavior, and recovery path are specified.
