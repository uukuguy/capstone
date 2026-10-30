# Gateway dynamic binding implementation plan

Status: direction approved; adapter wire contract requires gateway agreement.

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
- [ ] Agree how discovery identifies supported operation semantics, input/output
  contracts, continuation actions, source/provider identity and revision.
- [ ] Obtain an actual published example. Field names remain unspecified until
  the gateway owns and publishes them; this plan does not establish a wire schema.

Evidence: `runs/gateway-selection-20261031/binding-audit-{0,1,2}.json`.

## Task 2: adapter binding and current-connection policy

Files: `data_gateway_mcp.py`, `data_gateway_relay.py`, adapter-focused tests.

- [ ] Add tests with arbitrary provider IDs and renamed business operations.
- [ ] Build immutable, connection-scoped bindings from the agreed publication.
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

- [ ] Use adapter-produced bindings for open/read/job/continuation operations.
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

No product implementation is changed by this plan. The earlier Beijing CSV retry
passed through send_message; it proves the current execution entry works, not
that fixed view bindings or toolset policy have been removed. Task 1 wire-contract
agreement is required before implementing automatic presentation bindings.
