# Skills/MCP installation verification

Final source candidate: `6b28807a`, following `16f29d35`, `f92b3202` and `3b25c089`.
Final API/worker image: `9abfcd9c65cd99da113d8aa2356cfcab0640440eb3a96561b5d4bfb683ea3ff6`.
Final native image: `a1978dffa301de7b9723139e83acdd74e896ab2654c88ab515d9773cd9f74f72`.
Final model list task: `thr_f15b5f9a52b2c6e3dd9c`, completed7.2s and returned actual operation contracts.
Core installation was first accepted at f92b3202. The dependency/binding/bundle batch
was then verified at16f29d35; final contract-image verification passed.

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

Completion batch:

- 460 direct backend consumer checks passed,37 environment checks skipped (29.06s).
  After the final operation-contract addition,170 resource checks and6SDK tests
  passed. These suites overlap; their counts are not added together.
- 51 App tests and TypeScript passed. Pending installation can be queried by its
  original request ID; uncertain installation cannot be submitted again from the
  panel. After browser reload, a saved request ID can be entered explicitly.
- Preinstall membership now matches the exact installed version. Updating a
  resource does not relabel its old published pin as the current version.
- Real binary Python wheel installation, dependency import and protected MCP
  startup passed. The wheel came from a controlled in-container HTTP fixture.
- Real locked npm installation and Node MCP import passed. A test lifecycle script
  remained unexecuted. No external registry was contacted.
- Protected bindings rotate on later calls; revoked scope is rejected before
  dispatch. Binding files and values are excluded from packages and manifests.
- Real offline bundle import restored the exact resource version, its vendored
  dependencies and separately bound target credentials. The fixture registry was
  stopped and external access disabled before import. The operator export CLI passed.
- Parameter schemas are now returned by the list operation before selection and
  enforced by the same backend contract. The model need not guess runtime fields.

Supported scope and limits:

- Git acquisition uses an exact HTTP(S) commit. Credential binding currently covers
  runtime MCP headers/environment; it does not implement private Git authentication.
- Dependency installation supports root exact Python requirements and npm lockfiles.
  Python source builds, undeclared transitive resolution, npm lifecycle scripts,
  workspaces and unsupported lock formats fail explicitly.
- Skill load returns the private dependency environment for its scripts. It does
  not change the task's global interpreter environment.
- Offline bundle application explicitly targets a workspace; new workspaces are
  not automatically provisioned. Publishing a workbench draft
  does not update other deployments. The standalone offline operator command
  refuses remote acquisition; live remote MCP requires network-enabled verification.
- Multi-resource application is sequential. On partial failure, earlier verified
  installs remain; no successful application receipt is written.
- Model routing was verified with a real list operation. Same-instruction
  install-and-use is covered through the actual installer/runtime path, but has
  not been verified as an end-to-end model conversation.

Store schema 2 is additive and preserves schema 1 records. Old schema 1 executors
cannot open schema 2; this milestone does not claim rollback compatibility.
