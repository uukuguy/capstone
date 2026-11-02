# PPTX preview and conversation restoration

The App now renders authenticated PPTX products in the existing right pane.
The reader loads Office Kit only when needed, reads an App-created blob URL,
and renders one slide at a time as a passive SVG image. It does not send files
to an external viewer. Original file download remains available. Empty or
invalid decks show a readable error. Expanded reading hides the directory,
product metadata and actions, while preserving slide navigation and pane exit.
Office Kit is MIT licensed; the browser entry does not import its Node renderer.
Renderer reference: https://github.com/office-kit/pptx/tree/main/packages/preview

The summer report continuation attempt_397aad042f70e71f finished at 19:59:34
and published a 16-slide, 1,175,855-byte PPTX. Vivaldi displayed the actual
saved deck and its second slide. The user then produced a revised deck in the
same conversation; the App also displayed that revision. This verifies file
presentation, not the report's numerical conclusions. The original request's
current-year coverage is still incomplete; a 2025 deck does not fulfill a 2026
data request automatically.

Conversation bodies now have a separate in-memory archive of accepted commands,
attempt starts/outcomes and artifact descriptors. Raw tool events and token
deltas remain bounded. The App reads older ledger pages in the background,
retains conversation records only, and leaves the live cursor unchanged.
Switching threads clears the archive; stale page responses cannot populate the
new thread. The broken older-conversation button stays hidden.

Verification: 79 focused App tests passed, including raw-window eviction with
all eight conversation records restored, repeated restoration without duplicate
records, PPTX page boundaries and rejection of external document URLs.
TypeScript and the production App build passed. Vivaldi rendered the actual
16-page report locally. Full backend rebuild/readiness is recorded separately
in the session journal. No cloud deployment or dev integration is claimed.
