# Live Session Checkpoint

Updated: 2026-10-16. Active-session recovery record.

## Current action

- Active branch feat/thread-version-negotiation from a36634e3. Runtime commits2d3f86c6/a2efb791 add v1 negotiation and clear upgrade feedback. Local gates and independent review passed. Final local rebuild and PR integration are in progress; do not claim v2 or Task2 complete.
- Scoped gates:1345 backend/65 skipped,628 Kernel,522 final App,15 client,3 registered-worker; types/build/boundaries passed. Final status-label regression79 passed. Legacy CORS browser fixture passed; explicit wrong-version SSE retains the draft and stops retries.
- First rebuild failed at Docker Hub token DNS/timeout. Process-local HTTP_PROXY/HTTPS_PROXY/ALL_PROXY=http://127.0.0.1:7897 fixed access; canonical rebuild succeeded, then repeated for final App correction. Logs /tmp/thread-version-rebuild-final.log. No system proxy or pinned dependency changes.

- User correction resolved by PR43/a36634e3:977601f9 now has a fixed card; dynamic dev-head also represents the current commit, with same-SHA deduplication. Both required documentation jobs passed (1m13s/1m56s); root dev and both preparation branches synchronized locally/remotely to a36634e3. Fix branch closed. Source runtime remains055a335f. Continue Task2 production Profile/v2/frontend work.
- PR #41 merged normally into dev85b6706f. Exact08556cc2 passed CI38898130414:Linux6m4s/macOS6m3s; merge tree equality verified. Old38894817486 was superseded/cancelled, not accepted.
- Control PR #42 merged977601f9 after both documentation jobs passed (1m8s/1m37s). Its fixed graph node remains visible after PR43. Implementation, CI and control branches are closed.
- Graph must show the actual85b6706f product merge, requested d4600ddc and exact local-dev source055a335f. Ordinary CI/control commits stay in history details. No runtime rebuild for this control-only closeout.

## Accepted state and scope

- Accepted product dev:85b6706f (PR41); current control HEADa36634e3 (PR43); Task1 product merge:d8fe6e27 (PR36). Main cf72393b unchanged. Application preparation branches are synchronized without independent implementation.
- Task2 slice055a335f adds WorkBinding/TaskContext, Work-owned research persistence and Harness normalization. No-model and model-change research restores by Work. Legacy model-owned files remain unchanged. Context grants no permissions.
- Production Claim, legacy association migration, Profile, Thread v2, Postgres and frontend are not connected. Task2 remains in progress; Task3 owns production continuous Pi/action receipts.
- Independent review found no blockers; requested malformed-context and cross-run/model-change tests were added.

## Verification and runtime

-44 identity/research tests;1332 backend passed/65 skipped; three source modules pyright clean. make check-integration passed, including39 E2E cases and24/24 capability coverage. Do not repeat broad checks without new code/failure.
- User requires short early-development CI.08556cc2 adds shared-agent/App dependency regression on both platforms,15-minute test-step limit. Registered workers are a separate target because the backend aggregate excludes them. Native bridges/professional/dependency/build changes remain broader; release remains complete.49 policy tests and independent review passed; local selected checks106.40s plus workers48.77s; hosted jobs about6 minutes including setup. Rule is in AGENTS.md/lifecycle.
- Initial five local HTTP failures came from macOS system proxies. NO_PROXY/no_proxy=127.0.0.1,localhost fixed23 relay/server tests and the full suite. Logs:/tmp/capstone-work-identity-tests-clean.log and /tmp/capstone-work-identity-tests.log. No product fix needed.
- Canonical local-dev rebuild at055a335f passed. API/dual workers image sha256:4a4c6fb7199d3df92516dcbaa1a02024504e10b3e9f2ea69ffdd5c4da0647d7f; each role matches1145 Git file/link objects. Receipt:runs/work-research-identity/local-identity.json. Compare symlink targets separately.
- Ready8767/App5173 source055a335f dirty=false/existing Thread browser checks passed. No Provider call or new-task submission; no enterprise UI acceptance claim.
- Graph20 nodes/26 edges passes1920/1280 geometry: no overlap/crossing/through-card path/overflow. Fixed977601f9 and currenta36634e3 cards and ancestry edge verified in the browser. Screenshot:output/playwright/dev-head-node-fixed.png. Browser sessionproject-alignment:http://127.0.0.1:29483/docs/status/PROJECT-OVERVIEW.html; geometry:/tmp/check-control-graph.js.
- User e2eaee2 package,19173,main,local-demo/cloud-demo and cloud-dev unchanged. Do not rebuild runtime for control-only edits.

## Next shared-foundation slice

- Plan:docs/superpowers/plans/2026-10-16-enterprise-unified-execution.md Task2; contract:docs/superpowers/specs/2026-10-16-enterprise-protocol-decisions.md.
- host_api.py is the server; thread_http.py is a client. ThreadCreator currently defaults a model and schedules professional preparation; no-model entry must skip those unrelated actions.
- thread_service.py owns memory/Postgres/DDL. Required model columns need additive migration and Work associations; preserve historical data and exact-key retry before protocol-upgrade checks.
- Domain manifest/profile and composition need explicit native/authority assembly; do not silently downgrade incomplete professional configuration.
- Frontend:ThreadLiveEntry.tsx, threadHttpTransport.ts, threadProjectionStore.ts, threadProtocol.ts. Version requests and event streams, reuse existing conversation/results.
- Next visible acceptance: old professional Thread readable; no-model Thread/Work creation; object CAS and exact-key retry; refresh/reconnect; explicit old-client upgrade prompt. Provide actual URL/source and observable results.
- Application branches stay preparation-only until their required foundation runs. Demo1/2 are external examples, not production metrics, special APIs or fixed flows.

## Recovery

- Slice report:docs/reviews/2026-10-16-work-research-identity.md.
- Preserve stash a91a148494f520e973f5d63158916b42a5df6773, /tmp/capstone-pre-convergence-root-work.tar.gz, detached Pi worktreeabf2f797 and all var/data.
- Git network may require http.proxy=http://127.0.0.1:7897, HTTP/1.1 and gh auth git-credential. No force push or protection bypass.
