# Capstone Agent Web / CLI / TUI UI/UX Design Review

**Reviewed:** `docs/superpowers/specs/2026-09-30-capstone-ui-ux-design.md` and the accepted interaction architecture in `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`.

**Initial verdict:** **FLAG — architecture is coherent, but implementation should wait for the blocking interaction details below.** The two-column workspace, one-page-per-model rule, shared Thread projection, Harness command path, explicit evidence boundary, and TGP fallback direction are sound. The review found no product-boundary contradiction, but several interaction contracts were underspecified.

## Findings

### BLOCK-01 — TUI keymap conflicts with terminal control characters

The proposed `Ctrl+M`, `Ctrl+T`, `Ctrl+P`, and `Ctrl+D` bindings overlap common terminal/editor meanings: carriage return, transpose, history navigation, and EOF. `Ctrl+C` also needs an explicit cancel-versus-exit rule. These collisions can make the composer unreliable and can make a destructive action appear to have failed.

**Required correction:** use function keys or Textual-native bindings for drawers and panes, reserve `Ctrl+C` for a documented two-step cancel/exit behavior, and expose the complete keymap through `?` and the command palette. No key may have a different meaning while the composer has focus unless the focused control displays that behavior.

### BLOCK-02 — TGP output ownership is not implementable yet

The contract selects TGP but does not state how raw graphics escape sequences coexist with Textual's screen repaint and widget layout. Writing escape sequences from an arbitrary widget can be overwritten or leave stale placements after resize.

**Required correction:** define a dedicated TUI `TerminalCanvas`/image sink that owns placement IDs, clear/redraw order, resize invalidation, and ANSI fallback. If the active Textual backend cannot provide that ownership, the renderer must select ANSI/Unicode before emitting TGP. No other widget may write terminal graphics sequences.

### HIGH-01 — Resynchronization needs an explicit command freeze

The design shows a resync banner/modal but does not state which actions are disabled while the local projection is untrusted. Sending a command from a stale projection risks duplicate or stale model changes.

**Required correction:** while `resync_required`, freeze send, model/profile controls, Case controls, and page actions; keep only reconnect/reload and exit available. Replace the projection atomically from a verified snapshot, reset local viewed-page state to a valid page, then resume event reading after `base_event_seq`.

### HIGH-02 — Historical-page actions need a safe affordance rule

The grid includes `Ask about this` and `Analyze this`, while historical pages are read-only. Without an explicit disabled state, users can dispatch a request against a retired Context.

**Required correction:** historical pages show a read-only banner; element analysis actions are disabled in v1 and offer `Use this model` as the only state-changing path. Element questions become enabled only after the page is the active current model.

### HIGH-03 — Evidence authority states are visually conflated

Tool cards currently combine admitted result/evidence links with generic tool activity. Reference output, diagnostic output, unadmitted result data, and current-run admitted evidence must have distinct labels and actions.

**Required correction:** render at least `admitted/current`, `historical`, `reference/non-authoritative`, and `diagnostic/unadmitted` states. Only `admitted/current` may be presented as support for the current answer or used by a follow-up evidence action.

### HIGH-04 — Web focus and live-region behavior needs a concrete contract

The design mentions keyboard navigation and announcements but omits skip links, drawer focus trapping/restoration, focus-not-obscured behavior, and the target after a streamed message or error.

**Required correction:** add skip-to-workspace and skip-to-Thread links, modal/drawer focus trap plus restoration, a persistent visible focus ring, and explicit polite/assertive live-region assignments. Resync, approval, cancellation failure, and integrity errors move focus to their action surface.

### MEDIUM-01 — “Live” lacks source freshness context

A connected event stream does not prove that a grid projection or Authority result is current. The header needs a last-event/cursor indicator and grid overlays need revision/source freshness metadata.

**Required correction:** show connection state separately from data freshness, including last event time/cursor and `stale`/`unavailable` labels where applicable.

### MEDIUM-02 — Error cards need stable recovery metadata

The state table names broad states but does not require the stable error class, retryability, related IDs, last safe sequence, and action hint already defined by the Harness contract.

**Required correction:** every surfaced error uses those fields and maps to the same action wording across Web, TUI, and CLI.

### MEDIUM-03 — CLI interruption and multiline input are unspecified

The headless output contract is clear, but `capstone chat` does not define multiline input, first/second interrupt behavior, or exit codes for interrupted/resync-required commands.

**Required correction:** document input delimiters and interruption behavior; keep stdout machine-readable in headless mode and put recovery guidance on stderr.

## Passed areas

- The primary Web/TUI workspace follows the requested grid-left, conversation-right structure.
- One page per distinct Grid Model and separate active/viewed page state are explicit.
- Controls converge on Harness commands instead of client-local business mutations.
- Current-model projections and evidence are separated from assistant prose.
- Case batches, blocked steps, retries, cancellation, and pinned Context are represented.
- TGP is presentation-only and has a Unicode/ANSI fallback direction.
- Raw hidden reasoning and runtime-native events are excluded from the public UI contract.
- Shared `ThreadSnapshot`/`EventPage` semantics support Web, TUI, CLI, and recovery.

## Review score

| Dimension | Verdict | Reason |
| --- | --- | --- |
| Product/architecture fit | PASS | UI follows Thread/Harness/Authority ownership. |
| Information architecture | PASS | Two surfaces plus hideable context drawers are coherent. |
| Interaction safety | PASS | Resync, historical-page, and command freeze rules are explicit after correction. |
| TUI implementability | FLAG | The design boundary is explicit; a real TerminalCanvas prototype remains required. |
| Web accessibility | PASS | Focus, skip links, live regions, and modal restoration are specified; implementation checks remain. |
| State/evidence clarity | PASS | Freshness and authority labels are now distinct and actionable. |

After BLOCK-01 and BLOCK-02 are corrected, the UI contract is suitable for an implementation plan. HIGH and MEDIUM findings should be closed in the same design revision before UI code is written.

## Post-correction status

The design contract was revised after this review:

- BLOCK-01 is closed by replacing drawer shortcuts with function keys and defining composer focus plus cancel/exit behavior.
- BLOCK-02 is closed at the design level by assigning TGP ownership to a dedicated `TerminalCanvas`, with a mandatory pre-emission ANSI fallback when Textual cannot guarantee repaint ownership.
- HIGH-01 through HIGH-04 are closed at the design level by freezing commands during resync, disabling historical-page analysis, adding authority-state labels, and defining focus/live-region behavior.
- MEDIUM-01 through MEDIUM-03 are closed at the design level by adding freshness metadata, stable error recovery fields, and CLI multiline/interruption rules.

**Final design verdict:** **PASS WITH IMPLEMENTATION GATES.** The contract is suitable for an implementation plan. A TUI prototype must still verify `TerminalCanvas` repaint behavior on Ghostty/iTerm2 and focused Web/TUI accessibility checks must run against the implemented controls before claiming UI completion.
