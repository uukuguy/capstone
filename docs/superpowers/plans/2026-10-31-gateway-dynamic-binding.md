# Gateway dynamic binding implementation plan

Status: direction and returned-action contract approved; implementation active.

**Goal:** retain generic efficient execution while obtaining concrete operations
from each current gateway connection.

**Architecture:** only the data-gateway MCP adapter may know agreed gateway-level
entry tools. Business operations and provider choices come from live discovery.
Execution and presentation consume validated bindings and versioned result contracts.

## Constraints

- Do not modify the sibling gateway repository or invent published metadata.
- Preserve task grants, protected credentials, current-run receipts, source identity,
  bounded reads and task ownership checks.
- Do not move business tool name tables into another file and call them dynamic.
- A changed operation contract invalidates its binding before another invocation.
- Provider preference and fallback belong to current discovery, not global policy.

## Task 1: agree the discoverable binding contract

- [x] Reconnect, read initialization, call discovery and inspect tools/list.
- [x] Confirm tools expose safety annotations and a toolset tag, but no unambiguous
  machine-readable operation-role binding for automatic view handlers.
- [x] Agree the existing returned-action contract; no semantic role registry.
- [x] Verify live preparing/running/succeeded/read, inspection, build, full artifact
  download, pagination, drilldown and reference rejection. Evidence remains in the
  root checkout under `runs/gateway-next-action-20261031/`.

The model selects the initial business call from fresh discovery and exact
contracts. Continuations use only the current `data.next_action` or
`provenance.agent_guidance.next_actions`. Pending tasks honor
`poll_after_seconds` and `not_before_seconds`. Successful inspection has no next
action; failed tasks carry `data.error` and no next action. Task state and view
state are separate: a direct view has `state=ready`; read actions come from
`data.streams.*.read` or guidance. Result handlers recognize supported versioned
payload schemas, never business tool names. Existing model discovery response
supplies concrete `electrical_views` call bindings. Reuse those bindings without
inventing tool names, operation-role metadata or a second scheduler.

Evidence: `runs/gateway-selection-20261031/binding-audit-{0,1,2}.json`.

## Task 2: adapter binding and current-connection policy

Files: `data_gateway_mcp.py`, `data_gateway_relay.py`, adapter-focused tests.

- [ ] Add tests with arbitrary provider IDs and renamed business operations.
- [ ] Build immutable, connection-scoped bindings from actual discovered results.
- [ ] Keep exact invocation names/schemas/hashes in adapter-owned bindings.
- [ ] Reject ambiguity and unsupported contracts explicitly; do not select first.
- [ ] Test reconnection, provider changes, revoked grants and contract drift.

## Task 3: generic execution policy

Files: `resources/gateway-tool-use.mjs`, `general-tool-discovery.mjs`,
`tool-composition.mjs`, their direct consumers and focused JS tests.

- [ ] Replace the fixed readonly_sql classification and global fallback policy
  with current provider selection metadata supplied through the adapter.
- [ ] Retain bounded search/load, observation receipts and protected execution.
- [ ] Test identical behavior after toolset, provider and business-tool renaming.
- [ ] Verify business/provider_global/provider_fallback ordering follows discovery.

## Task 4: typed presentation without operation-name branches

Files: `grid_source_topology.py`, `grid_electrical_view.py`, `general_pi_server.py`,
`delegated_runtime.py`, `pi_delegation.py` and focused presentation/receipt tests.

- [ ] Use discovered bindings and returned actions for open/read/job continuation.
- [ ] Dispatch by supported versioned result contracts, not invocation names.
- [ ] Keep verified source descriptors, revision binding and cross-task rejection.
- [ ] Test renamed tools, unknown result contracts, forged descriptors, paging,
  asynchronous jobs and cancelled/expired operations.

## Task 5: real acceptance and integration

- [ ] Use focused macOS checks and direct-consumer checks; no release suite.
- [ ] Rebuild using make capstone-local-rebuild and finish scoped cache cleanup.
- [ ] Reconnect and run a real directory-to-CSV case and a supported view case.
- [ ] Verify saved products, restored conversation, source identity and receipts.
- [ ] Update canonical status/control records, review and integrate through dev PR.

## Current limits

The earlier Beijing CSV retry
passed through send_message; it proves the current execution entry works, not
that fixed view bindings or toolset policy have been removed. Live tool-renaming
and a second actual gateway instance remain distinct acceptance gaps; local tests
must exercise arbitrary business names and instance-bound references.
