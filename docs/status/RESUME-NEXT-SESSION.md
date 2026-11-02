# Live Session Checkpoint

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
