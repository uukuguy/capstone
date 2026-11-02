# Live Session Checkpoint

3b25c089 implements installation API/runtime/UI; follow-up now adds persistent
per-task/resource/version MCP sessions and closes cleanup races. Explicit
active_tasks registration fences late handlers, relay revoked before shutdown.
Skill materialization uses private disk-backed staging and original input dir FD;
no symlink expansion, partial publication or deleted-directory resurrection.
Managed tasks now use existing disk-backed inputs volume for readonly inputs;
runner.task_resource_inputs provides exact path, no task-supplied path/workspace.
Scratch uses inputs/.managed-installers; persistent package store remains0700.
Model tool schema includes only currently permitted operations; backend rechecks.
Targeted tests422 passed/37 skipped before last refinements; newest focused lifecycle
14 tests and JS6 pass. App15 tests/types passing; no feature rebuild yet.
Next: finish consolidated checks, commit source follow-up, one canonical rebuild and
run prepared .capstone-agent/verify_managed_resources.py in isolated native container.
Acceptance script updated for stateful local MCP calls and exact source/version use.
No external network, CI or remote deployment authorized for this acceptance.


2026-11-03 active Skills/MCP installation implementation. Approved design/plan:
docs/superpowers/{specs/2026-11-02-managed-resource-installation-design.md,plans/2026-11-02-managed-resource-installation.md}.
Added managed_resource_service/http/dispatch/runtime/probe/task.py, private durable
managed-resources volume, workspace-bound PiTaskRequest.managed_workspace from
AttemptClaim.workspace_name, generic agent_managed_resource SDK tool and workbench
Settings panel. Policy remains local-open/intranet-use-only; private directory-mounted
policy is seeded once by deploy/prepare_resource_policy.py (never overwrite revocation).
Installer/probe UID>=2**31 disjoint from task UIDs; store0700; untrusted work executes
only in private per-operation copies under tasks/.managed-installers. No root HTTP
probe, no shared package ownership, no direct persistent-store task reads. MCP error
IPC retains stage/executed=None and uses accepted task deadline. Skill copies use
lock, link-preserving bounded hash validation and atomic publication. Resource-call
result is retained if use policy is revoked after dispatch; later calls deny.
Store schema2 additively migrates v1 to retain parsed non-secret install spec for
updates; old schema1 executors cannot open schema2 (no rollback compatibility claim).
Source checks440 passed/37 skipped plus additional task/security/transport/image
checks; App15 tests and types passed. No CI/remote/deployment yet for this feature.
Next: commit current coherent source unit; unified canonical rebuild; run ignored
.capstone-agent/verify_managed_resources.py in a separate network-none native container
with NET_ADMIN,SETUID,SETGID,CHOWN,DAC_OVERRIDE caps (test no secrets, no gateway/model).
Review/fix acceptance failures; no incremental rebuild until source unit ready.
Dependency environments, protected secret binding and offline preinstall bundle
application remain incomplete. Do not claim whole installation feature complete.
Research server remains offline. Preserve unrelated summer-session-audit.md.


Vivaldi restored (pid61110/window239221): existing project overview tab selected
through AppleScript active-tab index after AX tab click only focused without selecting.
Welcome cards and overview runtime nodes/deployment edges now visually verified.
Top development summary and generated HEAD aligned; final graph refresh pending. No Chrome/new tabs.


Vivaldi GUI path works via orca computer (com.vivaldi.Vivaldi). Existing local
welcome tab visually verified gateway 本机联调/127.0.0.1:18001 and deepseek-flash,
matching sidebar/composer. No Chrome or new tabs. During graph-tab selection
Vivaldi became app_not_found and disappeared from list-apps; no restart attempted.
Graph visual acceptance remains pending. Do not call the browser itself unavailable
merely because the browser-client connector has no connection.


2026-11-02 execution-integrity batch locally accepted. Report:
docs/reports/2026-11-02-multiturn-execution-integrity.md. Main orchestration audit
and fixes completed;462 focused checks passed/33 skipped plus10 image/helper checks.
Unified rebuild passed: API/worker b79f2055; native helper packaged with combined COPY
to remain below Docker layer limit. Live four-round model test passed: generate CSV,
read frozen historical bytes, handle deliberate exit3, read again. HTTP snapshot
restored before each round; browser UI refresh not visually accepted. Isolated
PostgreSQL four rounds also prove continuation after failed business terminal.
No CI or intranet rollout. Server remains offline by user instruction.
Docker cleanup released about11.6GB build cache; keep volumes and running services.
87966cb5 aligns version register and generated overview; links, current-head/source
nodes, symlink and doctor checks pass. Browser unavailable; graph visual acceptance pending.
Next: deploy one verified bundle only when research server returns. Do not replay summer query for transport acceptance.


User requires whole-audit completion before ONE rebuild/acceptance run. Do not rebuild per fix.
Previous rebuild8c875af2 completed; c438fca6 is source-only,352 focused checks passed/32 skipped.
Shared runtime_cleanup preserves primary exceptions while recording cleanup faults; cleanup-only
failure still propagates. Cancellation and projection failures now log safe origins.
Remaining: finish reviewing 103 exception sites inventoried in /tmp/capstone-exception-inventory.txt,
resource/terminal-path audit, then consolidated rebuild and short real-model multi-turn acceptance.
No CI, no remote connection/deployment. Do not claim overall completion.


2026-11-02 terminal audit: cbec0d59 preserves runner errors during concurrent cancellation;
187a8ca8 logs double persistence failures safely. Host114 passed/32 skipped;
restart probe confirms failed terminal settlement, retained workspace and no replay.
Local rebuild receipt /tmp/capstone-persistence-rebuild.log. 2eb26aa1 adds safe incremental capture/transfer fault logs; normal close stays quiet,
next-trigger recovery and single-attempt transfers preserved.129 checks passed/32 skipped.
Rebuild in progress: /tmp/capstone-live-artifact-rebuild.log.
Next: remaining exception boundaries and short real-model multi-turn acceptance. No CI; research server offline.

2026-11-02 active multi-turn integrity repair: see
`docs/reports/2026-11-02-multiturn-execution-integrity.md`.
Intranet Thread thr_52b7e926ea630d064f77 has three parent failures after historical
resource opens. Frozen descriptor lacks saved_at; enriched listing adds it.
Shared matching now preserves legacy display compatibility and immutable identity;
typed missing historical resource returns a recoverable tool receipt. Preparation
tracking now recognizes native model/tool events; execution failures are not user
cancellations. Safe chained failure origins, rollback/partial-admission diagnostics,
and unsettled tool IDs are retained. LLM purpose fallback removed: missing stays blank.
Intranet stays 70c42dab; NO rollout until this batch is verified. No CI. Commits 3cc6a263/f4d66542/b4df210b pass focused checks. Canonical rebuild succeeded with matching API/worker image61aa2b1e; isolated PostgreSQL four-turn continuation passed, including continuation after a failed business round. Live-model acceptance and exception-boundary audit remain open. Research server is unavailable; do not attempt remote connections or deployment. Do not replay the summer query.

Welcome page now shows current session gateway and selected LLM using existing connection state. App134+33 focused checks and TypeScript pass. Browser unavailable; visual acceptance remains open. Canonical local rebuild passed with matching API/worker image833051c6 and scoped cache cleanup; receipt /tmp/capstone-welcome-rebuild.log.

2026-11-02 capacity correction: see docs/reports/2026-11-02-capacity-recovery-audit.md.
Relay model/gateway slots separated; gateway concurrency four queues 28 calls in
normal/debug. MCP total budget defaults to unlimited; positive budgets remain.
Soft recovery works in debug; safe preflight returns exact bounds without revoking
the task. All model-visible effective bounds are injected before the first call;
full 171-dimension contract is task-local. Python279 passed/34 skipped; App116,
types, SDK9 and gatewayJS13 passed. No CI or summer replay. 4d57c083 canonical
local rebuild is ready; backend b0c546f4/native3315fc64; scoped cleanup receipt
.capstone-agent/cache-maintenance-20261102-192640-94609.log. Intranet images
4d57c083 are built but NOT deployed. User requires finishing this batch of main
execution-chain fixes before one intranet rollout; do not deploy incrementally.
Saved bundle: .capstone-agent/intranet-capacity-4d57c083/. Large-product streaming, durable receipt/history
paging and sizing reviews remain open; do not claim all defaults validated.

2026-11-02 summer chain audit: docs/reports/2026-11-02-intranet-summer-chain-audit.md.
Both63LLM; Qwen22m49s/80109output tokens/195tool events versus dsv4
15m22s/31457output/74tool events. Actual PPTs verified: Qwen16pages/6pictures/3tables;
dsv4 11page data-availability assessment/0pictures/2tables. Prompts differ.
70c42dab fixes blank-prefix explicit purpose retention and report executable mode;
44App+44Python tests, types, canonical rebuild and intranet rollout pass.
UID10001 directly generated HTML/PPT; new Qwen saved response_intent survives completion.
Gateway weather errors and long-window timeout have saved parameters/request IDs in audit.
Generic batch preflight, observation reuse and construction checks remain pending.
No business replay or CI; browser unavailable. Original installation feature remains incomplete.


App939a4d74 delays right-panel auto-open until a generated primary product arrives.
23 execution tests and types pass; intranet App updated and API ready;
backend/native remain601b5909. Browser unavailable; no CI.


Qwen3.8-Flash-Next registered at192.168.72.69:8013/v1, intranet default.
Models endpoint reports262144 context;28 focused tests pass,1 skips; local/intranet
Compose preset resolution passes. Canonical local rebuild and intranet deployment
completed for601b5909; four services healthy, Qwen CSV task24.8s/one tool/no errors,
download SHA256 verified. Browser unavailable; no visual acceptance. No CI.
Rollback configs: /home/dmdba/capstone-intranet/*.before-601b5909.


2026-11-02 milestone closeout: user selected current dev as the milestone scope.
All implementation commits are already on local dev. PR84 merged into remote dev at a0ab3d10 after scoped CI41395958065 passed.
PR85 main CI41396086929 passed81 tests but failed historical formatting.
User approved retry; CI41396861782 passed on both platforms (16s/20s).
PR85 merged main d4b59a0f; published annotated milestone-intranet-20261102-d4b59a0f.
PR86 returned accepted main and records to remote dev at1b3760cd.
CI41398901567 passed macOS in19s; local and remote dev match.
Merged milestone branches were closed; the annotated source tag remains.
Do not start another CI without user approval. Current workflow forces full dual-platform
release checks for main; adjust to the agreed lightweight merge scope before triggering it.
Intranet deployment remains 7ea289f2; current dev is not deployed there.


Accepted design: `docs/superpowers/specs/2026-11-02-managed-resource-installation-design.md`.
Installations persist; no temporary mode. Resource management uses one permission gate.
Local defaults allow application actions; intranet defaults restrict management actions.
Preinstall promotion is approved. Core implementation is committed; runtime/API/UI integration remains incomplete.

Active implementation now follows `docs/superpowers/plans/2026-11-02-managed-resource-installation.md`.
Permission core fdc55904/74ed2f39 passes14 tests and independent review; deployment defaults ef05b7b9
pass synthetic Compose resolution (not deployed). Durable store cb3f98f6/49b3bb25 passes28 tests and review.
MCP transport d129b49c passes real local stdio verification;12 focused tests after revocation-race fix.
Installer c0774749 is committed and verified;
root owns MCP transport and remaining runtime/API/UI/deployment integration. No CI, no remote access.
Installation is not yet available through the workbench. Do not claim full delivery or deployed permissions.

`43c31e3a` changes scope-switch defaults to the newest primary by saved time.
Manual version selection survives directory updates.53 focused tests and types passed.
`6470c554` puts copy first in answer actions;133 component checks passed.
Local rebuild ready: `/tmp/capstone-latest-primary-rebuild.log`.
API/worker image `286db9663be85944bb8b643ffa170ae23dfa4970baa9e684dad1b9cedce7df2b`; App `6470c554`.
Scoped cleanup receipt: `.capstone-agent/cache-maintenance-20261102-001753-45814.log`.

Instruction products implemented in `2ca06418`: paired instruction/answer actions,
stable persisted numbering, scoped directory and all-products toggle. Execution start
opens its scope once; manual choices are preserved. Focused checks, types and browser
component verification passed. Evidence: `runs/instruction-products-20261101/`.
Canonical local rebuild ready; log `/tmp/capstone-instruction-products-rebuild.log`.
API/worker retain identical backend image `9cf4677d`; App source is `2ca06418`.
Scoped cleanup receipt: `.capstone-agent/cache-maintenance-20261102-000230-5077.log`.
No CI, remote deployment or business replay. Preserve unrelated untracked summer audit.

Updated 2026-11-01 23:13. Artifact version display correction.

Commitaa1cd3e8 groups instruction output cards by task/attempt/host path identity.
Latest version shown, older versions preserved behind closed history. No filename
heuristics or cross-task merging.150 focused checks and types passed.
Browser grouping check passed. User then requested timestamps:5830be18 adds saved_at
from ledger event time to both output cards and file directory; original files unchanged.
162 App checks,13 API checks passed;1 integration test skipped;types passed.
Timestamp browser fixture and persisted historical directory passed. Local rebuild ready,
API/worker image9cf4677d9ae9667fe86974247e07c28b5b240981daba7fb35960f64082f8f85f.
Cleanup receipt232349-17334. Latest selected by saved_at even after mixed-order hydration.
19 additional order/helper checks passed; no remote deployment.
Historical disconnected-server constraint was superseded by the authorized2026-11-02 deployment. Evidence runs/artifact-versions-fix-20261101/.

Earlier server disconnection was resolved on2026-11-02; deployment601b5909 is active.
Commit2800da79 fixes PDF sandbox rejection and application/octet-stream filename
fallback. Browser reproduced restricted-frame failure versus normal13-page view.
17 focused App/transport tests and types passed; actual component browser preview
and canonical local rebuild passed. Same backend image1be4fbda; App2800da79.
Scoped cleanup receipt cache-maintenance-20261101-230249-59432.log. Evidence runs/pdf-preview-fix-20261101;
log /tmp/capstone-pdf-rebuild.log. No CI, no business task replay.

Shared correction commit `7ea289f2`: PPT theme; API-clock elapsed time;
queued wording; step-registration diagnosis; purpose fallbacks; explicit final
answer body. Focused App 167 / agent 45 / PPT 25 passed; types passed.
Local canonical rebuild ready, backend image
`1be4fbda8a3db000df717ae1e163b73447ff76d8bf238c95ad004f1a29b1fa3a`.
Cleanup receipt `.capstone-agent/cache-maintenance-20261101-195735-86660.log`.
Remote incremental images tagged 7ea289f2 active; all four services healthy.
API/worker image58f78932b1b5a0a0a151a5d6f631beac9a14a4cf2b07dc06491377fa9d4f4b72.
Short dsv4 task5.895s,1LLM,0tools,Chinese answer and browser passed.
Changed executor/report files match local and intranet byte-for-byte.
Logs `/tmp/capstone-presentation-remote-up.log`; task verification script
`/tmp/capstone-presentation-trial.py`, evidence `runs/presentation-fix-20261101/`.
No CI, no summer replay, no new visible tab. Do not claim full chart/business
acceptance: previous model created zero figure blocks. Prompt now distinguishes
failed retrieval from absent data and requires supported comparisons.
Answer boundary is explicit; legacy unmarked text is preserved, not heuristically
stripped. Real exact-output task had no preamble but omitted markers; do not claim all
English-prefix cases are prevented.

Intranet entry http://192.168.72.63:5173; SSH dmdba, dir
/home/dmdba/capstone-intranet. Single worker serializes tasks; user asked to record
only. Existing user task finished. Remote clock is ~327 seconds behind browser;
this explains inflated live elapsed. All 123 executor source hashes were equal
before correction; gateway misuse was reproduced locally with dsv4, not a proven
deployment mismatch. Saved audit `runs/intranet-deploy-20261101/summer-final-records.json`.
Control register and graph now record the intranet deployment and source. Preserve unrelated
`docs/reports/2026-11-01-summer-session-audit.md`.

## Main path remains separate

## Current work

User requested one unified correction, not separate business-tool patches.
Dev implementation `2b347fc6` combines task-local direct/composed successful-read
reuse, exact retrieval preflight, normalized observation access, typed CSV
preparation and model network-failure diagnostics. No business names or routes
were added. Concurrency remains 4. See
[implementation report](../reports/2026-11-01-unified-observation-pipeline.md).

73 focused Node checks and 94 focused Python/worker checks passed. Additional
host checks passed. No CI. Canonical rebuild passed readiness and image parity:
`f96b8e7fb2fbf0c56c152916cc84dd0760d44d2e0984a8873d4335caa603aeeb`.
Cleanup receipt: `.capstone-agent/cache-maintenance-20261101-180419-53195.log`.
Short real trial `thr_06440e24643ca2748769` / `attempt_696255a1871bc668` completed
26.030 seconds, 7 model responses, 8 tools, zero errors. Direct/composed reuse,
explicit refresh and typed CSV/source manifest passed; downloads verified.
Evidence: `runs/unified-pipeline-validation-20261101/`. Existing browser tab reused.
Control graph, source edges and deployment card inspected in the existing browser
tab; local document links, symlink, doctor and diff checks passed. Business scope
and full-task read-count efficiency are not certified by this metadata trial.
Next work must use the saved diagnosis; do not claim full summer-task acceptance.
Do not repeat the full summer task automatically.

## Prior results and limits

The authorized summer rerun ended after 589.524 seconds during confirmed network
loss: 58 model responses, 282 tools, 8 tool errors. Its 162 sequence calls included
37 identical extra reads; 35 repeated a successful batch to repair local extraction.
Evidence: `runs/summer-rerun-20261101/`; thread `thr_4201a737211f31836047`.
This is not accepted business delivery. Scope selection remains model judgement.

The intermediate `8f9f59d5` runtime passed reuse/refresh mechanics in a 36.085-second
metadata trial, but had 3 shell exploration errors. The unified pipeline addresses
that access/preparation path. Evidence: `runs/read-reuse-validation-20261101/`.
Current browser validation tab: `thr_06440e24643ca2748769` on 127.0.0.1:5173.
