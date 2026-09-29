# Fixture-backed Thread UI prototype

## Goal

Exercise the agreed two-column Web Thread workspace without replacing the legacy Case App. The prototype must render the four canonical Thread states through `ThreadProjectionStore`, keep local grid-page navigation separate from the active model context, and expose the recovery/control gates users must understand before a real API transport is connected.

## Scope

- Add TypeScript fixture documents matching the checked-in `capstone-thread/1` UI fixtures.
- Add a Web-only fixture screen with grid projection on the left and conversation/control projection on the right.
- Add a query-string entry point (`?thread-fixture=<id>`) while leaving the default Case App unchanged.
- Keep all visual state derived from the projection store; no Case API or Pi/DSH runtime is used.

## Tasks

1. [x] Add typed fixture documents and a small fixture selector.
2. [x] Add the Thread fixture screen and tests for idle, historical active, and resync states.
3. [x] Add the query entry point and scoped styles; run the App test/build gates.

## Exit criteria

The four fixtures can be opened through the query entry point, controls are visibly gated by connection/execution/view state, historical navigation does not change `active_grid_page_id`, and the legacy App tests remain green.
