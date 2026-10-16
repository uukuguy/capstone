# Live Session Checkpoint

Updated: 2026-10-16. Active recovery record.

## Current action

- USER CORRECTION: standalone Work UI rejected. Do not merge current frontend. review_work_ui is implementing shared presentation reuse; owns App source only. Root owns docs. Follow accepted enterprise design/prototype, preserve mature conversation components. AGENTS.md now records this rule. Backend remains valid; frontend tests are not design acceptance.

- feat/thread-work-context from dev12cc9875. Product35e014df implements v2 Work ledger and no-model entry; da3ddfb1 fixes viewport scrolling/mobile header. Both committed, not yet pushed/merged.
- Final local backend1427 passed/2 skipped with isolated PostgreSQL; App533 passed/build; types, boundaries, doctor and independent backend/UI reviews passed. No Provider calls.
- Canonical local rebuild35e014df passed; API/worker/worker-pypsa image30ac7e42, each matches1152 source files. New rebuildda3ddfb1 is next. Identity script /tmp/verify-pack-selection.py; receipt runs/thread-work-ledger/local-identity.json.
- Real saved model-free Thread thr_c32d0f45308b7340e885 / Work work_72ec2e783115bfec6d5e. Model/Attempt null, event1, blocked execution_unavailable. Browser work-entry; mobile390 and desktop1280 inspected.
- Finish rebuild/refresh/legacy smoke, update report/register and graph, normal shared-agent dual-platform PR to dev, then control closeout and application branch synchronization. Do not claim Task2/continuous execution complete.
- Production Claim/Profile binding and historical research association remain Task2; continuous Pi execution Task3. Both application branches remain preparation-only at12cc9875.
- Dirty docs are task-owned plus inherited JOURNAL/RESUME/generated graph. Preserve all. Maincf72393b, cloud-dev24d9a325, demo faa6af9 and user e2eaee2 unchanged.
- Graph server127.0.0.1:29483; use cache-busting query. Geometry /tmp/check-control-graph.js. Regenerate on final dev HEAD, retain977601f9/d4600ddc as fixed nodes.

## Control and recovery

- Current register/graph belong on dev. Important commits need nodes; use ui-ux-pro-max, verified ancestry, source edges, geometry and screenshots. Regenerate after final branch synchronization; avoid an infinite self-SHA control loop.
- Preserve original stash a91a148494f520e973f5d63158916b42a5df6773 and /tmp/capstone-pre-convergence-root-work.tar.gz; detached Pi worktreeabf2f797 and all var/data remain. Temporary control stash93d02be8e1a2e4e1afc53601bf0ff9d7626102da was applied, made durable in PR47 and dropped; original recovery stash remains.
- Git network: http.proxy=http://127.0.0.1:7897, HTTP/1.1, gh auth git-credential. Rebuild uses process-local HTTP_PROXY/HTTPS_PROXY/ALL_PROXY at that proxy and NO_PROXY=127.0.0.1,localhost; no system proxy change.
- Final generated snapshot and recovery log may remain dirty on dev to show the actual final HEAD without creating another control loop.
