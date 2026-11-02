# Live Session Checkpoint

Updated: 2026-11-03. Active Skills/MCP installation work remains open.

Source3b25c089 +f92b3202 implements API, protected transport, isolated installer,
workbench Settings panel, generic model tool and per-task MCP sessions.
451 backend/47 App/6 SDK checks and types pass. Canonical rebuild ready;
API/worker e94e4362, native0a6bf185. Real controlled Skill/local/remote MCP and
pinned Git HTTP acquisition pass. A second replacement container restores exact
versions with external access disabled. Temporary test volume removed.
Real workbench model list operation completes6.2s in thr_4d9ba101dc856595d099.
Existing Vivaldi panel visually verified (window239221); no new tabs/Chrome.
Report: docs/reports/2026-11-03-managed-resource-installation.md.
Evidence: runs/managed-resources-20261103/; no CI/push/remote deployment.

Active next batch (not rebuilt): root fixed exact-version preinstall membership;36 tests pass.
capacity_inventory_audit implemented pending operation recovery UI;19tests/types pass,
now owns new managed_resource_bundle.py/tests ONLY. Needs root installer.install_prebuilt
seam (expected_resource/publication before publish). capacity_contract delivered
managed_resource_dependencies.py/tests (24pass), now owns managed_resource_secrets.py/tests.
Root owns integration: runtime sync_output=True, dependency env in probe not helper,
Skill returned dependency runtime; trusted secret scope and protected values channel;
installer prebuilt verification without downloads, then operator CLI.
No additional rebuild until coherent source batch complete. Source changes are uncommitted;
previous accepted image f92b3202 remains current. Latest docs commit2caee426.

Next coherent batch before another rebuild:
1. Exact-version preinstall membership and pending operation recovery UI.
2. Isolated dependency installation and protected secret-reference binding.
3. Offline preinstall bundle application through same installer contracts.
4. Real model install-and-use within one instruction and cross-session reuse.
Do not claim complete feature acceptance. Existing code explicitly rejects unsupported
requirements; do not silently discard them. Store schema2 cannot run on oldschema1 executors.

Research server is offline; intranet remains70c42dab. No remote calls/deployment.
Preserve unrelated docs/reports/2026-11-01-summer-session-audit.md and all user data.
Right panel still opens only when primary products arrive. No CI without consent.
Main-chain accepted local scope documented in 2026-11-02-multiturn-execution-integrity.md.
Use canonical rebuild after coherent source batch; scoped cleanup is mandatory.
