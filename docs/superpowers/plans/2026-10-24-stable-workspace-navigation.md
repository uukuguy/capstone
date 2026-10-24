# Stable workspace navigation

Accepted cache refinement: retain at most the configured recent session views
(default5); evict least recently visited inactive views and restore lightweight
disk reading state on reopen. Automatic eviction is not business archival and
does not cancel execution. Memory DOM/iframe retention, cap1cold recovery and
932App/type/doctor checks pass. Design and exact evidence are linked from
docs/reviews/2026-10-24-session-view-cache.md. Existing Git integration remains
pending across the accumulated candidate.

Recovery closeout: archive pagination and stale-request regression fixes are locally verified. Fresh full App suite927/927, TypeScript/doctor/diff, actual archived API pagination and desktop/narrow browser checks pass. Canonical rebuild and118runtime source checks pass. Git integration remains a separate pending boundary because the working tree includes accumulated cross-package changes; see the verification review.

User-approved scope: independent desktop session/conversation/product columns; independently hidden sidebars; sensible default224px navigation and60:40 remaining conversation/product split. Both dividers support dragging, keyboard adjustment and persistent user preferences. Small screens retain overlays instead of squeezed columns.

Session navigation uses same-page history, retains its list and scroll position during thread recovery, keeps the current item visible, and distinguishes selected from hovered items. Compact previous/next actions follow the displayed session order and disable at list boundaries. Existing isolated task execution and product components stay unchanged.

- [x] Reproduce independent visibility, saved widths and session navigation failure cases.
- [x] Correct shared frame CSS/state, add navigation divider and retain the existing product divider.
- [x] Remove whole-page session navigation and transient empty navigation; restore scroll within the navigation container only.
- [x] Add shared previous/next actions to both version adapters and preserve browser history behavior.
- [x] Run focused App/type checks, canonical local rebuild and browser checks of desktop/narrow layouts, drag persistence, switching and reload.
- [x] Update durable status and canonical dev overview with verified scope.

This is a presentation change. It does not run a new research benchmark or change the accepted338s/59-tool reference.

Expanded accepted scope: fixed new-session entry, pinned groups, row menus, inline rename, archive recovery and separately confirmed deletion. Read-only catalogs and selection persist during target recovery; no temporary generic current-session insertion. Delete removes the inactive thread ledger, not stored blob bytes or external Authority state. See the verification review for actual checks and remaining persistence scope.
