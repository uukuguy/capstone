# Intranet deployment acceptance

Annotated acceptance tag `intranet-20261103-1206-25c71f85` is pushed at the exact
runtime source. Its annotation records main/CI, image IDs, container identities
and this receipt. It does not claim full release acceptance.

Main PR88 merged as `0b68c6073c0440b2197dd4daa730127079e70b9b`.
The user explicitly authorized a one-time scoped main gate. CI41574376803 passed
macOS24s and Linux33s. This is not full release acceptance; the four existing
offline-installer test failures remain recorded in KNOWN-ISSUES.

## Exact runtime source

Runtime source: `25c71f85a494d72a44396c4c711b7bc9b4385daa`, now contained in main.
Its packages, Dockerfile, deploy and configs match the accepted PR head exactly;
later changes are tests, CI and control records. The original user milestone tag
remains fixed at771259a7.

Target: `capstone-intranet`, `/home/dmdba/capstone-intranet`,
http://192.168.72.63:5173/.

| Role | Exact image ID |
| --- | --- |
| API and native worker | `sha256:ba233b829a85cabb695b36819bd88685ad70012818bacea61cf27dead90226f0` |
| Native executor | `sha256:5abc0e56d36b1c22b12d706092ea73eac956883b2e7266b928e760402dc21546` |
| App | `sha256:a0b7d4f957850b44b0a1c29dd7ca2260277b6a89e35ceaeef268fc5f36d9a50f` |

All images are Linux amd64. The native image exceeded Docker's layer-depth limit
on import. Its exported rootfs was imported as a single layer, with original OCI
environment, command, working directory and port configuration checked unchanged.
Local and server offline checks passed22 capabilities,24 packages and15 commands.
The original OCI configuration, rootfs and conversion receipt remain in the
ignored preparation directory. This is an image-packaging change, not a runtime
source change.

## Data and activation

The existing project, database, object store and runtime volumes were retained.
The prior ledger was backed up to `private/backups/pre-25c71f85/ledger.dump`.
Original environment and Compose files are in `private/backups/release-25c71f85/`.
Previous70c42dab images remain for rollback. Secret values were not displayed.

The first activation omitted the project-name option and started a separate
temporary `capstone` project. It could not bind the existing API port and did not
replace the intranet services. Its task-created containers and networks were
stopped; volumes were preserved. Activation was then run with explicit
`-p capstone-intranet`. No administrator branch-protection bypass was used.

API, worker, native executor and App are healthy. API/worker image IDs match.
API and executor resource-management flags are0. The browser input catalog says
management disabled, and the existing Vivaldi tab shows the disabled Skills/MCP
management entry. Installed-resource use permissions remain separate.

## Real acceptance

Thread: `thr_b07d19dc343fe57aa59d`.

- First attempt `attempt_ae04b166f365db08`: completed24.3s,3 model responses,
  CSV saved and downloaded.
- Continuation `attempt_2352a02d237f501e`: completed43.2s,3 model responses,
  read the immutable saved bytes without replacing the file.
- CSV:28 bytes; SHA256 `834ed3f44e9258a2dbbacd7eface5de04b5d6def40f02e59d999479002abf37e`.
- API snapshot restoration, repeated download identity and existing-tab browser
  refresh passed. The restored page shows both completed instructions and CSV.
- One recoverable tool error occurred: `file` was unavailable (exit127); the
  model recovered with `od`/Python. This is not a zero-error receipt.

This validates the deployed native conversation/product path. The CSV contains
a supplied release string, not Authority or business evidence. No historical
summer case or full model install-and-use conversation was replayed. Professional
solver profiles, cloud development and demo deployments were not promoted.

Evidence: `runs/intranet-release-20261103/`. Source/image staging and conversion
receipts: `.capstone-agent/main-intranet-25c71f85/`. Scoped local build-cache
maintenance completed after image use; other projects and persistent data remain.
