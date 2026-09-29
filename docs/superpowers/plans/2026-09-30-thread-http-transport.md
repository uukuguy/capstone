# Thread HTTP transport adapter

## Goal

Provide the browser with a real network transport boundary for `capstone-thread/1` without pretending that the backend route already exists. Protocol parsing, cursor admission, and command reconciliation remain in `CapstoneThreadClient` and `ThreadProjectionStore`.

## Decision

Use a configurable HTTP resource root, defaulting to `/api/v1/threads`. The adapter uses JSON snapshot/event-page reads and a JSON command POST with `Idempotency-Key`; a future SSE adapter can share the same `ThreadTransport` interface. No endpoint is added in this client-only phase.

## Tasks

1. [x] Add failing tests for URL construction, auth/cache policy, command idempotency header, and non-success responses.
2. [x] Implement bounded JSON HTTP transport with injectable `fetch` and resource root.
3. [x] Run focused TypeScript tests and type checks; document the boundary and next backend work.

## Exit criteria

`HttpThreadTransport` never parses Thread documents or invents command identities, and the default Case App remains unchanged until matching server routes are implemented and verified.
