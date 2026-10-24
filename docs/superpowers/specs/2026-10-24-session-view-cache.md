# Session view cache

Accepted user requirement: switching sessions preserves the conversation and
right-pane content, position and reading state. Recent sessions stay in memory;
a configurable maximum releases the least recently visited view. The session
itself remains persistent and can be reopened.

## Ownership and storage

This is App presentation state. The Thread ledger, Authority results and products
remain owned by their existing services and contracts. A cached selection is a
reader preference, never a result admission or permission grant.

The current view and recently visited views retain their React state and DOM.
React Activity hides inactive views and stops their effects/subscriptions.
Returning to a retained view resumes event catch-up through the existing client.
It does not perform another full version negotiation and store construction.
Do not reorder retained DOM nodes; moving an iframe can reload its document.

The browser keeps lightweight, access-scoped reading snapshots on disk: selected
pane, product reference, answer folds, panel proportions and scroll offsets.
These snapshots contain no file bytes, Provider credentials or Authority objects.
When an evicted view reopens, the host supplies current data and resolves saved
product references through the normal read contract. The browser restores known
offsets after asynchronous content loads. Opaque sandboxed document internals
remain in memory with their iframe; no script or same-origin permission is added
to extract their private state for disk recovery.

The default memory maximum is five sessions. Settings permits a maximum from
one to twenty. The current view counts toward this maximum. The least recently
visited inactive view is released first. The server task is not cancelled.
Automatic release neither deletes the Thread nor changes its archived flag.
Explicit archive/delete releases retained memory. An access-namespace change
releases all retained views. Preview blob URLs live with the retained session
and are revoked on actual release, rather than each time Activity pauses.

## Acceptance

- A→B→A and A→new→A retain actual conversation and right-pane DOM and state.
- Memory hits do not issue a new snapshot/version-negotiation read.
- Lowering the maximum evicts the least recently visited inactive session.
- Eviction/reopen restores lightweight reading state with host-validated content.
- Hidden views stop event subscriptions; return resumes catch-up, with no new
  command or task submission and no cancellation.
- Closing a session releases its preview URLs and retained DOM.
- Desktop/narrow layout and existing session-management behavior still work.

Full preview bytes are not duplicated into a new browser artifact store. The
existing server persistence remains the content recovery source. A future
offline-content cache would need its own storage, freshness and access contract.
