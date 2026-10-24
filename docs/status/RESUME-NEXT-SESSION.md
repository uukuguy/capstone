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

Private-parent fix2f9c6b56 is committed and pushed; no PR yet. Canonical rebuild
/tmp/capstone-gateway-private-rebuild.log completed. API/3worker imagee69d4f1b6e56,
nativeb605fa2b1a6c, exact five-role source hashes, ready200, gateway41 and actual
setuid10000 open denial passed. Receipt: ROOT
outputs/data-gateway-20261025/local-source-verification.json.14 gateway checks,
102focused host checks pass. Independent review agent failed to launch due to
unavailable configured model; do not claim independent review. Manual audit done.

IMPORTANT ACTIVE MODEL RUN: thr_1897f293f4778aa394ad / work_933aff1d8c8316ffd4db /
attempt_a064c1744e3f09b5. Observer exec44788, log/tmp/capstone-gateway-real-series.log,
ROOT outputs/data-gateway-20261025/real-series-1. Native graph children have
successfully called actual gateway discovery/query and semantic prepare/execute.
Wait for the original attempt; do NOT rebuild or edit runtime or submit a duplicate.
Browser sessiongateway-real shows the Thread. Poll-only resumes the saved receipt.

An earlier real UID probe found that a mode0600 host bind was readable; no
credential bytes were printed and no model had started at that point. The native
host was stopped, repaired with image-native root0700 /run/capstone-private and
fixed-path startup validation, then reverified with a real denied open. Keep
CAPSTONE_DATA_GATEWAY_CONNECTION_FILE=/run/capstone-private/data-gateway/connection.json.
Use ROOT deploy/local.env and model assets by explicit paths; the gateway mount
uses its original directory. App5173 still serves ROOT dev (UI unchanged).

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
