# Managed Resource Installation Implementation Plan

> **For agentic workers:** Use subagent-driven-development for bounded implementation tasks and review. Continue within the approved scope; do not ask again between tasks.

**Goal:** Install persistent Skills/MCP through the workbench and conversation, enforce deployment-specific permissions, and promote verified versions into preinstall manifests.

**Architecture:** The application authorizes resource actions; the managed executor owns installation and loading. Reuse accepted resource snapshots and the existing task event path. Keep resource packages outside task scratch, and use the same loading contracts for installed and preinstalled resources.

**Tech Stack:** Python, existing HTTP API/executor transport, durable resource metadata, Pi SDK, React/TypeScript.

## Global Constraints

- Installations persist; there is no temporary installation option.
- Local development explicitly enables all known application resource actions. Intranet deployment disables management by default and permits use of enabled resources.
- Select permission policy through deployment configuration, never browser IP or model text. An absent or invalid policy fails closed.
- Open conversation access does not confer administrator status. Use authenticated backend context.
- Resource installation does not grant business data access or remove task isolation and network controls.
- Preserve historical resource versions, tool contracts and results. New resource sets apply only to subsequent execution steps.
- No CI without explicit user consent. No remote deployment while the research server is disconnected.
- Preserve unrelated `docs/reports/2026-11-01-summer-session-audit.md`.

## Task 1: Shared permission policy

**Files:** create `packages/capstone-agent/src/capstone_agent/resource_permissions.py`,
`configs/runtime/resource-permissions.json`, `packages/capstone-agent/tests/test_resource_permissions.py`.

**Interfaces:** `ResourcePrincipal(subject: str, roles: tuple[str, ...])`;
`ResourcePermissions(path: Path, profile: str)`;
`require(principal, workspace, action) -> policy_revision`;
`allowed_actions(principal, workspace) -> list[str]`.

- [ ] Write focused tests for local allow, intranet use-only, trusted role override, workspace restriction, malformed policy, unknown action, and live policy revocation.
- [ ] Implement one deterministic policy evaluator. Read the current file for each decision; use a canonical digest as revision. Never trust caller-supplied role fields at the public HTTP boundary.
- [ ] Explicit action vocabulary:

```python
RESOURCE_ACTIONS = frozenset({
    'resources.install', 'resources.enable', 'resources.disable',
    'resources.update', 'resources.uninstall', 'resources.use',
    'resources.preinstall.manage',
})
```

- [ ] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_resource_permissions.py -q`; review and commit only owned files.

## Task 2: Durable resource identities and preinstall manifests

**Files:** create `managed_resources.py`, `managed_resource_manifest.py` beside `resource_permissions.py`, and matching focused tests.

**Interfaces:** `ManagedResourceStore(root: Path, permissions: ResourcePermissions)` owns resource metadata and immutable package references. Public operations take a trusted principal and workspace. Installation receipts include id, kind, source, pinned revision, digest, enabled state, availability and diagnostics. `preinstall_manifest(profile)` exports exact installed versions without secrets or task paths.

- [ ] Test registration across reopening, atomic version publication, duplicate request id, stale expected revision, workspace isolation, enable/disable, retained historical references and permission revocation before publish.
- [ ] Implement transactional metadata with operation receipts and immutable versions. Keep operation receipts distinct from business task orchestration; do not create another task scheduler.
- [ ] Implement preinstall draft membership, versioned publication, export/import validation and explicit binding overrides. Export no credentials; require target-environment secret references.
- [ ] Test that adding a draft does not mark an existing deployment updated; removing a draft does not uninstall existing resources.
- [ ] Run the two focused test files, review and commit.

## Task 3: Installation adapters and actual load verification

**Files:** create `managed_resource_installation.py`, `managed_resource_mcp.py`; adapt `resource_installation.py`, `native_resources.py` and `general_pi_resource_seed.py`; add focused adapter tests.

**Interfaces:** a parsed source request describes resource kind, pinned source and workspace. An installer returns a verified package/connection receipt, not model-authored tool definitions. All publication passes through Task 2.

- [ ] Add Skill package validation and reuse Pi skill discovery. Preserve relative scripts and dependencies; reject escaped paths and credential files. Execute dependency installation in the isolated installer environment, never the API process.
- [ ] Add remote MCP connection verification and local MCP managed launch. Read actual server instructions and published contracts; do not require gateway-specific methods or hard-code business names.
- [ ] Check permissions before install and again before publication. Enforce the current network setting. Capture sanitized stage diagnostics and persist failed receipts without replacing the active version.
- [ ] Exercise a real small Skill and a controlled MCP service; distinguish installed, enabled and available. Verify disconnected recovery without automatic downloads.
- [ ] Implement loading preinstall manifests through the same adapters, including offline package data and target runtime compatibility checks.
- [ ] Run focused tests, review and commit.

## Task 4: Host, executor and conversation integration

**Files:** create `managed_resource_http.py` and `resources/managed-resource-tools.mjs`; modify `host_api.py`, `pi_delegation.py`, `general_pi_server.py`, `resources/general-sdk.mjs` and identity packaging lists; add route and SDK tests.

- [ ] Expose list, installation request/status, enable/disable, update, uninstall and preinstall management routes. Validate exact fields; derive workspace and principal from authenticated request context.
- [ ] Route management operations over the existing protected executor transport. Persist trusted origin/authorization with an operation, not model-provided administrator claims.
- [ ] Publish generic resource management tools through the same permission service. Report progress through existing task events. Duplicate or uncertain outcomes resolve through operation receipts rather than blind retry.
- [ ] At a tool-call boundary, record a new accepted resource set and refresh the task's allowed capabilities. Preserve all prior snapshots and existing data-gateway instance binding.
- [ ] Check `resources.use` and resource enabled state before subsequent execution. Avoid full catalog reload on ordinary instruction startup when the resource revision is unchanged.
- [ ] Verify current-instruction install/use, next-instruction reuse, denied API and model operations, and historical replay identity. Review and commit.

## Task 5: Workbench resource management

**Files:** create `packages/capstone-app/src/ManagedResourcesPanel.tsx` and transport/types/tests; integrate with `ThreadCommandMenu.tsx` and the existing settings toolbar.

- [ ] Show installed resources with version, availability and preinstall state. Display server-returned action permissions; backend remains authoritative.
- [ ] Provide install, enable/disable, update, uninstall and “加入预安装清单”. Display precise install diagnostics and installed-versus-ready states.
- [ ] Show preinstall draft versus deployed status separately. Do not claim other servers changed when a manifest is edited.
- [ ] Verify controls, error rendering and existing conversation UI. Reuse an existing browser tab or headless component harness; do not replay business tasks. Review and commit.

## Task 6: Deployment defaults, recovery and acceptance

**Files:** `compose.yaml`, `deploy/intranet/compose.yaml`, `deploy/general-pi.Dockerfile`, `deploy/intranet/README.md`, installation design and status records.

- [ ] Add durable package/metadata storage, explicit local-open policy and intranet-restricted override. Do not make ignored environment credentials part of source or bundles.
- [ ] Verify normal restart and container recreation, exact version restoration, offline local use, failed upgrade rollback, queued-policy revocation and referenced-version retention.
- [ ] Verify preinstall export/import in a separate test root with a real Skill and MCP fixture. Do not deploy to the disconnected intranet host.
- [ ] Run only affected tests and type checks; perform canonical local rebuild and its scoped cleanup. No CI.
- [ ] Review complete feature and permission bypass paths. Update recovery, implementation/deployment distinctions and project overview. Record any unmet acceptance explicitly.

## Execution status

- Plan prepared; Task 1 starts first. Remaining tasks depend on its authorization contract.
- The preinstall design is approved. No resource installation, publication or remote deployment has yet occurred.
