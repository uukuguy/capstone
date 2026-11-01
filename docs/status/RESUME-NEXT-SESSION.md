# Live Session Checkpoint

Updated 2026-11-01 20:00. Active correction, not final acceptance.

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
