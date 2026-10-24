# Live Session Checkpoint

Updated 2026-10-25. Active enterprise data gateway design; no deployment change.

Accepted dev is 346de403 after PR56/57. Main checkout remains on dev; its two
post-merge metadata changes (journal and overview) are preserved. Recovery refs
and ignored user data remain intact. Do not repeat release CI for development.

Worktree .worktrees/dev-macos-ci uses feat/enterprise-data-gateway. Design0d20a8f2,
adapterda48a15a, relay4c50c9a1, native integratione39fd6c3 and guidance/verifier
45394040 are committed. Twelve gateway/actual-child checks pass, plus100 focused
host checks and62SDK checks. Pi setup/install/doctor completed in this worktree.
Initial missing-runtime and loopback-proxy failures are environment issues;
after setup/NO_PROXY, host66 and chat14 checks pass, and existing graph execution
checks pass. No real model task has been started yet.

Canonical local rebuild is active under /tmp/capstone-gateway-local-rebuild.log
(exec session21487). Host health already publishes41 gateway tools. Wait for
readiness and scoped cleanup. Freeze final source and rebuild again if runtime
hashes differ after the later authentication-code correction. Do not start
model work against mismatched bytes. Use ROOT deploy/local.env and model assets
via explicit paths; gateway connection is mounted from its original directory,
never copied into task storage. App on5173 still serves ROOT dev (UI unchanged).

User accepted production-data enterprise-research first. Capstone only explores
and obtains data through MCP; backend selection/switching belongs to data-gateway.
Later deliveries unify conversations and admit gateway models into calculation.

Real authenticated MCP discovery passed: server1.30.0, 47 published tools.
North topology downloads for pandapower JSON and PyPSA NetCDF passed full hashes,
SDK loads and strict power-flow refusal. No electrical calculation was run.
Receipts: ROOT outputs/data-gateway-20261025/discovery.json and
outputs/data-gateway-20261025/network-models/report.json. No process is active.

Written contract: docs/superpowers/specs/2026-10-25-enterprise-data-gateway-design.md.
Plan: docs/superpowers/plans/2026-10-25-enterprise-data-gateway.md.
Next: run scripts/verify_data_gateway_research.py for series, followup on the same
thread/work, and bounded semantic-table exploration; use --poll-only to resume
without resubmission. Save under ROOT outputs/data-gateway-20261025. Inspect
actual reports/source/hash, then browser refresh recovery. Finish control update,
dev PR scoped checks and actual dev integration. No release workflow or cloud/demo.

Current model files support topology inspection, not valid power-flow or
optimisation. Our existing diagram needs capstone-network-diagram/1.0 projection,
source/revision identity and suitable layout/filtering; integration is pending.
User chose identical SDK versions: pandapower3.4.0/PyPSA1.3.0 in both projects;
coordinate gateway locks without cross-version tests. Do not remove invalid-parameter
sentinels or enable disabled equipment to obtain an apparent calculation.
