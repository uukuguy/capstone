# Session cleanup and Artifacts navigation

User direction: provide user-controlled cleanup by age instead of adding
pagination controls. Pinned conversations must never enter a bulk deletion;
their existing individual delete action remains available. Do not delete actual
user conversations while implementing or demonstrating the feature.

The navigation footer provides a small anchored cleanup popover, without a
modal backdrop. It accepts a positive number of days and offers 7/30/90-day
presets. The label states that age means creation time. It reads the complete
selected recent or archived catalog through existing bounded transport pages;
no pagination control is added. An incomplete directory disables deletion.
The displayed count and candidate names precede the user's explicit delete
action. Pinned and current conversations are excluded. Unknown dates do not
enter the candidate set.

The confirmed candidate identities are fixed. Each delete uses the existing
application DELETE contract and rereads pin storage just before submission.
Unreadable pin storage stops further deletion. The host still rejects running
conversations. Partial failures remain visible and are never retried
automatically. Closing, stopping, hiding or unmounting aborts unsent operations;
an already-sent request can finish. No new background retention job is created.

The right pane is named **Artifacts**, with **浏览产物** in its directory.
There is no scope selector: the directory reads the current conversation.
The primary group is named **主要产物**, without a per-turn claim.
It does not show a permanent source-grid tab. An instruction
that opens a grid still selects its existing grid view and can restore it
through that instruction's association. View, identity and camera contracts
remain unchanged.

After the user opens the artifact directory, selecting another item preserves
its open state. Explicit summary click or Escape controls folding. The
directory uses a bounded tinted region, distinct group headings and selected
row feedback; the document preview remains a separate white canvas. This
reuses the existing conversation and artifact viewer rather than adding a
second workspace.

The preview toolbar uses flat icons for available reference, locate and download
actions. The unused adopt-as-delivery and inspect actions are absent. Preview
support is separate from context-reference admission: a visible image, slide or
code file must not show a false unsupported-preview warning merely because it
cannot be referenced by the current executor.

Full-screen mode keeps a format-independent frame with separate directory and
preview scrolling. PPT keeps the browse entry. Switching formats does not change
the outer padding or footer geometry. A new selected identity starts its preview
at the top, without resetting the directory's reading position.

Source files use a lazily loaded Lowlight AST renderer, never raw executable
HTML. A language selector, line numbers and copy action share a compact toolbar.
The highlighting budget is 200,000 characters and 4,000 lines, with an explicit
truncation notice; stored files and downloads remain unchanged. HTML/PDF preview
sandbox policies are retained.

Verification covers selection boundaries, pins changing during confirmation,
damaged pin storage, partial failures, unmount/stop cancellation, cursor loops,
popover dismissal and successive artifact selections. Browser checks only
open previews and cancel; they must not confirm destructive actions.
