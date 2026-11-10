# Live Session Checkpoint

> Updated: 2026-11-10 17:33 CST. Session remains active; this is not a final handoff.

## Current result and immediate next step

- Service-bus title statistics and per-tool details are implemented. Only current-call provenance is counted. Job accumulation is ignored, unknown is not zero, host-marked reuse is excluded and graph/event projections deduplicate by call ID.
- User authorized deployment to local-dev and dky3-dev. Both now run the exact tested source `eb481485bb21ce0b36d7fdd8ba53f0218e5be9ab`. No other stage changed. Both pass458 backend and275 native exact-source file checks.
- Isolated implementation checkout: `/Users/sujiangwen/orca/workspaces/capstone/ppt-template-library-20261110`, branch `uukuguy/ppt-template-library-20261110`. HEAD `1b9e6772` adds only child persistence/graph tests and CI allowlist registration after deployed eb481485. Runtime product revision is f3d1f5cf.
- Next: finish canonical report/control snapshot browser check, copy task-owned control/report updates into candidate, focused documentation checks, commit and push branch plus deployment tag. No PR exists. Then request one explicit focused macOS CI approval before opening/updating a PR. Do not trigger CI without that approval.

## Verified stages

- local-dev API and three workers share image `f8488c5b5e927a11bf79c50c620c013dc56a41d212ac55da8f0a39637418a95f`; native `382a14ced31d344e3a2e4301aca669e0bad8a5432a1f01709ebfd2cf0f18d922`. Canonical rebuild completed: /tmp/capstone-service-bus-rebuild-persistence.log. Existing canonical image-source label is development; the source bytes and image digests establish identity.
- Local App launcher PID92961 uses the candidate checkout. /__capstone-build showed product f3d1f5cf, repository eb481485, dirty false, local-dev. Later test/docs changes may change repository metadata; do not confuse that with product revision.
- Local real source task `thr_d380ead17af9fe8e21e1` completed24.90s: one source attempt69.339ms. Discovery statistics are absent and stay unknown. Process title/details and full reload pass. The earlier trial `thr_ef754df5cd25910032ad` completed28.90s but failed statistics propagation; its receipt is retained separately. Fix f3d1f5cf has failing-then-passing persistence regression.
- Local final-source PPT thread `thr_f47f3cf9fa60fed92cc6` completed33.81s; State Grid default, four downloads and full render receipt/digests pass.
- dky3-dev is SSH root@192.168.72.66, deployment root /data/capstone-dky3-dev. API/worker image `1582f4266b7d`, native `3f84382d948c`, App `405f4258bfda`; all four healthy and exact eb481485 source labels. RootFS layers108/41/20. Prior images and protected configs/database dump remain private/backups/deploy-eb481485/.
- Remote real task `thr_dcac776c667066f52c1f` completed89.41s: one source attempt59.346ms, actual State Grid template tool, four downloaded product digests, two PDF pages inspected, browser title and reload pass. Public receipt: docs/reports/receipts/2026-11-10-dky3-dev-eb481485.json.
- Annotated tag `dky3-dev-20261110-1729-eb481485` exists locally at deployed eb481485; not yet pushed at checkpoint. Tag annotation records exact images, roles, task, backup and verification receipt.
- Browser plugin list is empty; documented troubleshooting completed. Existing Playwright CLI session capstone-unified has one owned Capstone tab; reuse it. It currently shows dky3-dev. The pointer action first hit the existing footer overlay; keyboard opening worked. Track that as separate existing polish, not new scope.

## Implementation and bounded evidence

- 18e87f4b: adapter-issued, host-verified service-bus projection; current counters independent of latest ten details; UI title and expandable details.
- f3d1f5cf: retain typed DTO through delegated_runtime application and child-event persistence.
- eb481485: joint focused presentation-library/service-bus macOS gate. 1b9e6772: child/graph regression checks only.
- Focused gateway/relay/host/graph/transport295 pass/32 skips; persistence/diagnostics99 pass; App323 pass plus child/graph143 focused checks (overlap, do not add counts); governance256 pass/3 skips; types pass. Proposed PR scope resolves presentation-library. No new CI or independent-review acceptance.
- Current 三区研发 connection gateway-3fdd43699bbb4c40ae0a19f795240f3c; instance0c266ac6-bf86-4137-ab7c-0e283331ab1f. Catalog fe9077d7fd55dd2472c5b7666ca46f9e946ed4f8f23b438fc0d126ff0e5b71a3,14 business+5 platform tools. Contract/zero-source receipts runs/2026-11-10-gateway-service-bus/.
- No inference policy change: bounded real trials obeyed current schemas and no redundant source-read defect was observed. Do not add business-name routing, fixed first actions, broad monitoring, IG2–IG4 or a full release gate.
- PPT library prior acceptance covers blue import, one-render override, explicit publication/selection, independent cross-session reuse, restore to State Grid, unchanged content/dependency hashes and protected source bundles. Stable-ID version updates and quota/GC remain explicit design gaps.
- Independent review tools failed configured model/transport earlier. Do not claim independent review. No need for another runaway retry.

## Private operational references

- Root ignored receipts: .capstone-agent/service-bus-live-20261110/, service-bus-deployment-20261110/, template-library-live-20261110{,-diagnostics,-service-bus}/.
- Root drivers: verify_service_bus_live.py, verify_template_library_final_source.py, download_dky3_template_trial.py; remote verify/activate scripts are under service-bus-deployment-20261110/.
- Feature staging .capstone-agent/service-bus-deployment-20261110/ contains exact git-archive source, native input allowlist projection, final Dockerfiles and same-origin dky3 App build. Root staging holds125MB141 amd64 .debs and candidate.tar.gz. Remote source/build logs /data/capstone-dky3-dev/builds/eb481485/.
- Remote build failures were contained before activation: apt --no-download local-file bug, staged executable permission, unavailable registry. Final offline dpkg install, canonical CLI modes and installed App dependency base pass. Do not describe derivative images as clean release-image acceptance.
- App helper's standalone export omitted its shared capacity JSON. The staged repository layout adds that exact-source JSON; build passes. No product-source workaround or dependency/runtime secret was copied.
- Scoped local cache cleanup is still due after final validation/use; use deploy/cleanup_local_build_cache.py --apply, never global prune.

## Git, recovery and preserved work

- PR100 merged remote dev d7358eac, accepted a1978ffb. Approved CI42759192341 passed4m29s after first failure42744202996. Those approvals are consumed; no approval exists for this follow-up.
- Actual dev checkout stays d5c9b1fe,11 local audit commits beyond origin/dev. Product tree there matches remote dev; actual running local runtime is the recorded feature candidate. Do not pretend the candidate has merged.
- Canonical control/worklist owner is actual dev. VERSION-CONTROL and PROJECT-OVERVIEW have been regenerated there for eb481485 deployment;20 graph checks pass. Browser graph inspection is next.
- Preserve recovery branch recovery/investigation-closeout-dev-20261110 and stash accc48a278cbb6c3bdeb7afaa7eac07005f446f7. Old investigation/foundation workspaces are detached; do not delete their dirty observations. Old presentation branch cadc2f3a contains duplicate render code already in dev; do not merge blindly.
- Root mixed control history is preserved. Other dirty user paths remain: deploy/intranet/README.md, docs/reports/2026-11-06-three-dev-deployment.md, plans/2026-11-05-structured-tool-batches.md, specs/2026-10-07-capstone-core-evolution-discussion.md, specs/2026-11-05-direct-thinking-preview.md. Do not stage these unrelated files.
- New/updated task reports: presentation-template-library, service-bus-execution-records, receipt JSON and service-bus-closeout plan. Root untracked prior intranet deployment report is related stage history; preserve it when recording current dky3 state. Stage only explicit reviewed paths.
