# Global gateway instance picker

Accepted scope: refine the existing sidebar gateway component. List registered instances, switch the global default, add an instance by URL and necessary authentication, and check connectivity asynchronously. Keep the compact upward popover, per-instance status, current selection marker and icon-only refresh-all. Do not create a separate settings dialog.

## Contracts and ownership

- Native application host owns the protected, versioned connection registry and MCP validation. Credentials stay in its private persistent directory, never in public catalog responses or agent task files.
- Instance identity, environment, source label, service version and tools are discovered through MCP; addresses cannot reveal authentication secrets or private service configuration.
- Connectivity checks run in a bounded background batch, not during list rendering. Refresh returns the current snapshot immediately. Connected status and an instance's offline-data flag have separate meanings.
- Select prepares the actual catalog before applying and retains the prior selection on failure. The host prevents switching an actively executing native task's source. The next instruction gets the new publication through the same executor capability path.
- Existing single-connection configuration remains a valid seed. Known private profiles are seeded locally; additions and selection survive restart. Loopback transport mapping is deployment configuration, not frontend IP routing.

## Implementation units

1. `gateway_connections.py` and focused tests: protected persistence, bounded MCP probe, selection, addition, background per-instance state and failure retention.
2. `general_pi_server.py`, `pi_delegation.py`, a small HTTP adapter and tests: authorized host controls, current publication refresh, active-task guard and refreshed model-view providers.
3. `GatewayStatus` and styles/tests: compact picker, states, refresh icon, inline add/validate/save flow. Shared public types contain no authentication values except transient input.
4. Workspace connection store and HTTP transport: one shared global selection, asynchronous refresh polling, immediate selection propagation across retained sessions, transient credential submission only.
5. Canonical local rebuild and Vivaldi check in an existing tab: known profiles, unreachable profile state, refresh, switching, failed add, successful add and actual new-task source discovery. Keep the selected gateway as 本地联调 unless the test explicitly selects another and restores it.

## Verification

Run focused registry, control, transport, component and global-store tests, then App build/types and the canonical local rebuild. Inspect the actual sidebar/popup at desktop and narrow widths. Verify no token appears in responses, labels, logs or browser storage. Record any unverified remote instance rather than claiming it connected. No cloud deployment or full release gate is part of this task.
