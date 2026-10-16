# Live Session Checkpoint

Updated: 2026-10-16. Active-session recovery record.

## Current action

- PR44 merged32f18d24 normally into dev; merge tree exactly matches tested1a695af4. PR45 control closeout merged199833bc after both documentation jobs passed; tree equalsc185e0aa. Root dev and both application preparation branches are synchronized; implementation/control branches closed. Final graph is regenerated on dev. Continue Task2 from this baseline.
- Runtime sourcea2efb791 (protocol implementation2d3f86c6 plus UI status correction). Do not rebuild for subsequent documentation-only commits.
- Task2 remains in progress. Only v1 negotiation is implemented; v2, model-free Threads, Profile assembly, production Work/Claim binding and object CAS remain open.

## Verification and runtime

- CI38907004425 passed exact1a695af4: Linux4m58s/macOS8m35s. Shared-agent dependency scope; no full release claim.
- Local gates:1345 backend passed/65 skipped,628 Kernel,522 App,15 client,3 registered-worker. Boundaries, types and App build passed. Final UI label correction79 component tests and TypeScript passed. Independent review cleared legacy CORS and pending-receipt masking corrections.
- Browser: real existing Thread JSON/SSE advertisev1; version2 command returns406 without changing snapshot. Synthetic wrong-version SSE shows upgrade state, preserves draft and makes only one stream request. Legacy CORS fixture allows default-v1 reads/writes and rejects the new custom header. Test server stopped; App restored; no business command or Provider call.
- Canonical local-dev rebuild passeda2efb791. API/worker/worker-pypsa share image sha256:09ce1cb6753cdbc24a1c8fb9a55c8d9cb12fe053a5ddd6505bfc180a55a60488. All1146 Git files/link targets match per role. Receipt:runs/thread-version-negotiation/local-identity.json.
- Rebuild initially failed on Docker Hub token DNS/timeout. Process-local HTTP_PROXY/HTTPS_PROXY/ALL_PROXY=http://127.0.0.1:7897 fixed it; no system/pin changes. Final log:/tmp/thread-version-rebuild-final.log.
- App5173/API8767. Maincf72393b, user e2eaee2/19173, local-demo/cloud-demo faa6af9 and cloud-dev24d9a325 remain unchanged.
- Browser sessions:offapp (real App) and project-alignment (http://127.0.0.1:29483/docs/status/PROJECT-OVERVIEW.html). Geometry script:/tmp/check-control-graph.js. Final upgrade screenshot:output/playwright/thread-version-upgrade-final.png.
- Final dev graph:22 nodes/29 edges;1280/1920 checks have no overlap, crossing, through-card path or overflow. Actual199833bc, product32f18d24, runtimea2efb791 and fixed977601f9 nodes verified. Screenshot:output/playwright/thread-version-final-dev.png. Local generated snapshot and recovery log stay uncommitted to avoid a self-SHA control loop.
- Reports:docs/reviews/2026-10-16-thread-version-negotiation.md and 2026-10-16-work-research-identity.md.

## Next shared-foundation slice

- Plan:docs/superpowers/plans/2026-10-16-enterprise-unified-execution.md Task2; contract:docs/superpowers/specs/2026-10-16-enterprise-protocol-decisions.md.
- WorkBinding/TaskContext and Work-owned research are integrated from055a335f/PR41. No-model component recovery works; legacy model-owned history remains. Context does not grant access.
- host_api.py is the server; thread_http.py is a client. ThreadCreator currently chooses a default model and prepares it. The no-model entry must skip those unrelated actions.
- thread_service.py owns memory/Postgres/DDL. Add Work and minimum-protocol associations without fake models or loss of old data; preserve exact-key retries before minimum-protocol checks.
- DomainManifest/DomainRuntimeProfile currently require Authority fields. Add explicit native/authority assembly; keep professional checks with authority execution, not every task. Do not silently downgrade invalid professional configuration.
- Frontend:ThreadLiveEntry.tsx, threadHttpTransport.ts, threadProjectionStore.ts, threadProtocol.ts. Reuse conversation/results and extend wire parsing together with storage and command contracts.
- Next visible acceptance: old professional Thread readable; model-free Thread/Work creation; object CAS and same-key retry; refresh/reconnect; explicit upgrade response. Task3 owns continuous Pi execution/action receipts.
- Two application branches remain preparation-only until their required foundation runs. Demo1/2 are external examples, not special APIs, metrics or fixed workflows.

## Control and recovery rules

- Graph/register live on dev. Show actual dev HEAD as a node and retain requested977601f9/d4600ddc fixed nodes. Keep product merge32f18d24 and exact runtime sourcea2efb791 distinct. Use ui-ux-pro-max, real ancestry, geometry and screenshot checks. Regenerate after final branch synchronization; do not start an infinite self-SHA documentation loop.
- Short development CI is required: shared-agent/App scoped dependency checks,15-minute step limit. Native bridges, professional tools, dependencies/build and unknown paths remain broader; main releases are full.
- Preserve stash a91a148494f520e973f5d63158916b42a5df6773, /tmp/capstone-pre-convergence-root-work.tar.gz, detached Pi worktreeabf2f797 and all var/data.
- Git network may require http.proxy=http://127.0.0.1:7897, HTTP/1.1 and gh auth git-credential. No force push or protection bypass.
