# Capstone Thread Client Adapter Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with TDD. Keep the client as a transport adapter and projection owner; do not embed Case or Domain Pack semantics in the browser.

**Goal:** Give the Web client a strict `capstone-thread/1` adapter that loads verified snapshots, catches up through contiguous event pages, sends idempotent commands, and exposes a fixture-backed projection store for the first UI prototype.

**Architecture:** `CapstoneThreadClient` consumes a transport interface and validates every response at the browser boundary. `ThreadProjectionStore` owns snapshot, event cursor, resync state, and pending command receipts; UI components later render this projection. A memory transport is test-only and replays checked-in fixture documents, while HTTP/SSE transport remains a separate adapter.

**Tech Stack:** TypeScript, React package test toolchain, Vitest, Web Fetch/AbortSignal types.

## Global Constraints

- The browser receives bounded `ThreadSnapshot`, `EventPage`, and `CommandReceipt` projections; it never receives Pi/DSH credentials or native runtime channels.
- Event pages must begin at the store cursor and be contiguous; gaps transition to `resync_required` and never skip events.
- Commands carry a caller-provided idempotency key; retry/reconciliation reuses that key and never invents a second command identity.
- Existing `CapstoneClient`, legacy `SessionStatus`, and the compatibility Case App remain unchanged.
- No Provider credentials, network authority objects, or hidden reasoning enter fixtures or browser state.

---

### Task 1: Add the browser-side Thread protocol parser

**Files:**
- Create: `packages/capstone-app/src/threadProtocol.ts`
- Test: `packages/capstone-app/src/threadProtocol.test.ts`

**Interfaces:**
- Produces `parseThreadSnapshot`, `parseEventPage`, and `parseCommandReceipt`.
- Produces `ThreadProtocolError` and the public types `ThreadSnapshot`, `EventEnvelope`, `EventPage`, and `CommandReceipt`.

- [x] **Step 1: Write failing parser tests**
- [x] **Step 2: Run `npm test --prefix packages/capstone-app -- --run src/threadProtocol.test.ts` and verify the missing-module failure**
- [x] **Step 3: Implement strict field, ID, sequence, timestamp, and JSON payload validation matching Python `capstone_agent.thread_protocol`**
- [x] **Step 4: Run the focused parser tests and verify GREEN**
- [x] **Step 5: Commit `feat: add browser thread protocol parser`**

### Task 2: Add the transport-facing `CapstoneThreadClient`

**Files:**
- Create: `packages/capstone-app/src/threadClient.ts`
- Test: `packages/capstone-app/src/threadClient.test.ts`

**Interfaces:**
- `ThreadTransport.getSnapshot(threadId, signal?) -> Promise<unknown>`
- `ThreadTransport.readEvents(threadId, afterEventSeq, signal?) -> Promise<unknown>`
- `ThreadTransport.sendCommand(command, signal?) -> Promise<unknown>`
- `CapstoneThreadClient.load(threadId) -> Promise<ThreadSnapshot>`
- `CapstoneThreadClient.readAfter(threadId, afterEventSeq) -> Promise<EventPage>`
- `CapstoneThreadClient.send(command) -> Promise<CommandReceipt>`

- [x] **Step 1: Write failing tests for response validation, cursor forwarding, and idempotency-key reuse**
- [x] **Step 2: Run the focused tests and verify RED**
- [x] **Step 3: Implement the adapter with no automatic new command key**
- [x] **Step 4: Run focused tests and verify GREEN**
- [x] **Step 5: Commit `feat: add capstone thread client adapter`**

### Task 3: Add the projection store and fixture transport

**Files:**
- Create: `packages/capstone-app/src/threadProjectionStore.ts`
- Test: `packages/capstone-app/src/threadProjectionStore.test.ts`

**Interfaces:**
- `ThreadProjectionStore.load(threadId)` loads a verified snapshot and resets the local cursor.
- `ThreadProjectionStore.catchUp()` reads after the current cursor and applies only contiguous events.
- `ThreadProjectionStore.dispatch(command)` records a pending command and receipt using the original idempotency key.
- `ThreadProjectionStore.state` exposes `connection`, `snapshot`, `eventSeq`, `resyncRequired`, `pendingCommands`, and `viewedGridPageId`.
- `createFixtureTransport(fixture)` replays a checked-in fixture for tests and prototype screens only.

- [x] **Step 1: Write failing tests for load, catch-up, historical viewed page, gap-to-resync, and command receipt reconciliation**
- [x] **Step 2: Run focused tests and verify RED**
- [x] **Step 3: Implement minimal store with client-local viewed page and no business-state mutation from page navigation**
- [x] **Step 4: Run focused tests and all App tests**
- [x] **Step 5: Commit `feat: add thread projection store`**

## Completion gate

This plan is complete when the parser, client, and store pass their focused tests plus the existing `packages/capstone-app` suite, and a fixture transport can render `idle-ieee39`, `historical-live-attempt`, `resync-required`, and `interrupted-attempt` without the legacy Case API. The visual Thread route is the next phase and must consume the store rather than bypass it.
