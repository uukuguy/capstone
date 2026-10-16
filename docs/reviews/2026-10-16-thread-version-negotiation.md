# Thread version negotiation

Source: `2d3f86c6`, final UI correction `a2efb791`. Shared-foundation Task 2 preparation slice.

The existing HTTP service now accepts explicit or default v1, echoes the version,
and rejects unsupported versions before task creation or command execution.
Authentication and public-demo restrictions still apply first. JSON and SSE
responses expose the version through CORS and preserve both Vary dimensions.

The Python client declares v1. The App starts with default v1 and sends the
version header only after a successful server advertisement. This preserves
old cross-origin servers whose CORS allowlist lacks the new header. Neither
client probes support by repeating a write. Missing response headers remain
compatible with old v1 servers; an explicit mismatch stops parsing.

The App shows an upgrade message, stops automatic reconnect for protocol
failures, and keeps the loaded projection, cursor and draft. A pending command
receipt cannot hide the upgrade message. Existing network recovery remains.

## Verification

- Scoped local gates: 1345 backend tests passed, 65 skipped; 628 Kernel tests;
  519 App tests before final review corrections; 15 client and 3 registered-worker
  tests. Package boundaries, types and App build passed.
- Final App corrections: 148 focused tests passed, then 93 transport/component
  tests passed after the pending-receipt regression was added; TypeScript passed.
- Independent review identified legacy CORS and pending-receipt message masking.
  Both were corrected and covered by focused tests.
- Final App suite: 522 passed and build passed; later status-label correction:
  79 component tests and TypeScript passed.
- Canonical local-dev rebuild passed at a2efb791. API and both workers share
  image `sha256:09ce1cb6753cdbc24a1c8fb9a55c8d9cb12fe053a5ddd6505bfc180a55a60488`.
  All 1146 files/link targets per role match Git. Receipt:
  `runs/thread-version-negotiation/local-identity.json`.
- Real browser: existing Thread JSON and SSE advertise v1; version 2 command
  returns 406 and leaves the snapshot unchanged. Synthetic wrong-version SSE
  shows the upgrade message and retains the draft with one stream request.
  The page was restored afterward; no business command or Provider call ran.
- Browser legacy-CORS fixture: reads and writes succeed without the new header;
  a direct request with that header fails preflight, proving the compatibility case.
- Graph: 21 nodes/27 edges, checked at 1280 and 1920 widths; no overlap,
  crossing, through-card path or horizontal overflow. Final merge graph is regenerated.
- Hosted PR acceptance remains pending.

## Scope

Only v1 is implemented and advertised. Version 2 returns 406. No model-free
Thread, Profile assembly, object CAS, storage migration or continuous executor
is claimed. Task 2 remains in progress. No Provider request or cloud release
belongs to this slice.
