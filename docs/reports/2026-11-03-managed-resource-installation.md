# Skills/MCP installation verification

Source: `f92b3202`, following `3b25c089`. This is a local feature milestone,
not complete acceptance of the full installation design.

The workbench Settings menu now exposes Skills/MCP management. Installation,
enable/disable, update, uninstall and preinstall draft/publication use the same
workspace-scoped permission service as the model tool. Local management is open;
the intranet profile allows use only. No client-supplied role grants authority.

Verified behavior:

- 451 backend checks passed, 37 environment-dependent checks skipped (40.28s).
- 47 App checks passed (8.37s); TypeScript and six SDK tests passed.
- Canonical local rebuild passed. API/worker image:
  `e94e4362d2973eb02b689ab41744606cb6eed7e39e9a3f48131c8099ac106c5f`.
  Native executor image:
  `0a6bf1853cb7cefbd96b1bc87c1395ef1ca0a2489ad22def0fc7c80a8137ef81`.
- Real Pi Skill discovery and readonly task materialization passed. Another task
  UID cannot read that materialization or the private package store.
- Real local and remote MCP initialize/discover/call passed. Two counter calls
  returned 1 then 2, proving connection state persists within the task.
- Real pinned Git HTTP acquisition passed under an isolated installer UID,
  followed by actual Pi Skill loading. The controlled Git server ran inside a
  network-none verification container; no external repository was contacted.
- A second replacement container restored exact Skill/MCP versions from a
  persistent volume and called them with external access disabled. The temporary
  verification volume was explicitly removed after the check.
- Disable enforcement, exact-version preinstall publication, and intranet
  use-only policy passed. Publication does not claim a deployment occurred.
- A real model task used `agent_managed_resource` through the workbench API,
  returned the actual empty resource list and permissions, and completed in 6.2s.
  Thread: `thr_4d9ba101dc856595d099`. No business gateway was called.
- The existing Vivaldi tab shows the management panel, actual empty catalog,
  install form and preinstall controls. No new tab or Chrome was opened.
- Read-only security review found no blocking lifecycle or permission issue.

Evidence is under ignored `runs/managed-resources-20261103/`. No CI, push,
remote deployment or historical business replay occurred. Scoped image/cache
maintenance completed after rebuild; user data and existing volumes remain.

Remaining work in the accepted design:

- Isolated dependency environments, protected credential binding and offline
  preinstall bundle application. These currently return explicit unsupported or
  unavailable diagnostics; they do not report success.
- Exact-version preinstall membership presentation after resource updates.
- Workbench recovery controls for pending operation receipts.
- Real-model installation and same-instruction use, beyond the verified actual
  installer/runtime checks and model list operation.

Store schema 2 is additive and preserves schema 1 records. Old schema 1 executors
cannot open schema 2; this milestone does not claim rollback compatibility.
