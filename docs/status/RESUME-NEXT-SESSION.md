# Live Session Checkpoint

Updated 2026-10-25. Active enterprise data gateway design; no deployment change.

Accepted dev is 346de403 after PR56/57. Main checkout remains on dev; its two
post-merge metadata changes (journal and overview) are preserved. Recovery refs
and ignored user data remain intact. Do not repeat release CI for development.

Worktree .worktrees/dev-macos-ci uses feat/enterprise-data-gateway. Commit
0d20a8f2 records the proposed integration contract, execution draft, core notebook
and independent model probe. Runtime gateway integration is not implemented.

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
Next: written-contract review, then implement host-owned remote adapter, protected
task relay, actual research tool propagation/source admission, and real multi-turn
research acceptance. Preserve current local PowerMCP and Authority contracts.

Current model files support topology inspection, not valid power-flow or
optimisation. Our existing diagram needs capstone-network-diagram/1.0 projection,
source/revision identity and suitable layout/filtering; integration is pending.
Gateway SDK versions differ from Capstone pins. Do not remove invalid-parameter
sentinels or enable disabled equipment to obtain an apparent calculation.
