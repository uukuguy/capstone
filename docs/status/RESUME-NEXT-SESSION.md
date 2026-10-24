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

Three canonical rebuilds completed, latest /tmp/capstone-gateway-frozen-rebuild.log
(session11376; cleanup receipt052308-45103). Source hashes match797ddf9a, but the
real UID probe found a security blocker: mode0600 on the host bind still allowed
UID10000 to open the connection file. NO credential bytes were printed and no
real model task was started. General Pi was deliberately stopped before repair.
The fix mounts under /run/capstone-private/data-gateway, with an image-native
root0700 parent and a startup guard.14 gateway/actual-child checks now pass.
Next rebuild must use CAPSTONE_DATA_GATEWAY_CONNECTION_FILE set to
/run/capstone-private/data-gateway/connection.json. Verify real setuid open is
denied, gateway41 remains available and all role hashes/images match BEFORE any
model task. Use ROOT deploy/local.env and model assets by explicit paths; the
gateway mount uses its original directory. App5173 still serves ROOT dev.

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
