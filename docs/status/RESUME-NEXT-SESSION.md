# Live Session Checkpoint

Updated: 2026-11-03. User requested temporary disablement of Skills/MCP management
for intranet deployment. Source adds deployment switch, disabled settings entry,
API input-catalog flag and executor permission gate; resource use unchanged.
Intranet overlay defaults switch0 for API/native; local remains enabled.
Focused26 Python pass/5skip,50App pass and types pass. No CI/build/remote deployment.
Research server remains offline. Next intranet rollout must include this batch.
Current deployed local runtime still6b28807a; disabled-gate source not rebuilt.

Skills/MCP installation supported scope is locally implemented
and verified. Source6b28807a follows16f29d35, f92b3202 and3b25c089.

Current local backend/API/worker image:
9abfcd9c65cd99da113d8aa2356cfcab0640440eb3a96561b5d4bfb683ea3ff6.
Native image:a1978dffa301de7b9723139e83acdd74e896ab2654c88ab515d9773cd9f74f72.
Canonical rebuild ready, identities match, scoped cache maintenance completed.
460 backend consumer checks passed/37skipped before final contract change;
170 managed checks+6SDK passed after it. Suites overlap. App51 and types passed.

Actual checks: Pi Skill discovery/readonly task copy; exact Git HTTP acquisition;
local/remote MCP discovery/calls; per-task state; separate replacement-container
version restoration; binary pip wheel and npm lock installation (scripts disabled);
protected MCP binding rotation/revocation; offline bundle restore with vendored deps
and target credentials after fixture registry stopped; operator export CLI.
Final actual model list:thr_f15b5f9a52b2c6e3dd9c,7.2s,one managed tool/no gateway.
Live API publishes12 operation contracts. Existing Vivaldi manager and graph checked;
no new tabs or Chrome. Graph reflects runtime6b28807a and intranet70c42dab.
Report:docs/reports/2026-11-03-managed-resource-installation.md.
Evidence:runs/managed-resources-20261103/. No CI/push/remote deployment.

Supported limitations: exact HTTP(S) Git commits; root exact Python requirements
and npm lockfiles; no source builds or undeclared transitive Python resolution;
MCP runtime credential binding, not private Git auth. Skill returns script env,
not global task interpreter mutation. Preinstall is explicit operator apply per
workspace; no automatic provisioning of new workspaces. Bundle partial failure
retains earlier verified installs and writes no successful application receipt.
Same-instruction install/use runtime is verified, but full model install-and-use
conversation remains unverified. Do not describe that as end-to-end acceptance.

UI entry: Settings -> Skills/MCP management. Persistent, workspace-wide installs;
local permissions open/intranet-use-only. Unknown install outcome:query original
request ID, no replay. Protected binding file is backend-owned; values never enter
packages/manifests. Historical versions remain frozen and retained.

Research server is offline; intranet remains70c42dab. No remote calls/deployment.
Preserve unrelated docs/reports/2026-11-01-summer-session-audit.md and user data.
Right panel opens only when primary products arrive. No CI without consent.
Use one canonical rebuild after a coherent source batch; scoped cleanup required.
