# Intranet development deployment

The user authorized a separate Capstone development installation on
`dmdba@192.168.72.63`. Its default gateway is `内网联调` at port 18001, and its
default model is the registered intranet dsv4 profile at 192.168.72.69:18804.
The shared App toolbar now displays `深度研究` as a disabled, grey control, with
no hover highlight and a not-allowed cursor. Restored drafts cannot enable it.
The underlying research implementation remains available for future development;
this change does not replay, cancel or rewrite historical tasks.

## Isolation and sources

The installation uses `/home/dmdba/capstone-intranet`, Compose project
`capstone-intranet`, separate PostgreSQL/object-store/runtime volumes, and fresh
operator/control/storage secrets. Only the explicitly selected gateway credential
is carried into a protected mount. No local task history or commercial model key
is copied. Gateway, Kubernetes and the existing PostgreSQL service are unchanged.

Backend/native source is `815d17f15a0d2c91243f9da9f26ccf0dfc767323`. The App includes
the later disabled-style correction `bf1cd421`. Backend API and native worker must
run the same image. The App uses a same-origin proxy, so its bundle has no secrets.
The default installation starts the enterprise/native path; professional solver
workers are optional and require separate provider configuration.

This host has CentOS 7, kernel 3.10 and Docker 26.1.4. It cannot fetch public images.
Linux amd64 images are built locally and transferred with checksums. The existing
proxy-enabled BuildKit builder is used; both CLI token retrieval and build steps
need their existing proxy settings. No server DNS or global Docker configuration
was changed. On this kernel, a first transaction that creates, flushes and populates
the nftables table fails with ENOENT. Each rule and subsequent atomic updates work.
The intranet startup command therefore creates the empty table before invoking
the unchanged resource-seed/executor entry point. Closed/open/closed rule updates
were verified in a disposable container network namespace; normal task admission
still waits for complete policy installation. No host firewall rules were changed.
The prepared App is built in the exported repository layout because
its capacity module imports the repository-owned configuration.

## Verification

155 focused App checks passed in 7.54 seconds; types passed. Two focused checks
also verified that an old `deep_research=true` draft submits with the option off.
The existing browser tab showed the disabled grey control. No CI was started.
The canonical local rebuild is ready with backend image
`e926f2631b5c4eb6d5c6113f39c79ab3913d9968a2c3677d6d38f4733d3fa643`;
cleanup receipt is `.capstone-agent/cache-maintenance-20261101-183028-20516.log`.

Fresh gateway initialization and catalog loading succeeded with 55 published tools.
The dsv4 model-list endpoint confirms availability and a 1,048,576-token context.
The remote App and `/health/ready` return 200. API and native worker use the same
image `2efd4737331dcadefdbddc9368f4b96cc004e389c12f01c1adaee4410837f8ad`.
The default-model metadata export completed in 32.900 seconds: five model calls,
four tool calls, zero errors and no repeated requests. The generated providers.csv
was downloaded and its hash verified. First model start took 3.413 seconds.
Thread: `thr_5558ffe853f7d0a7da77`; attempt: `attempt_5b7684ca548d8974`.
Receipts: `runs/intranet-deploy-20261101/`. Entry: http://192.168.72.63:5173/.
This validates the enterprise/native path, not optional professional workers.

## Browser closeout

Initial HTTP deployment exposed two secure-context assumptions: UUID generation
and SHA-256. Commits15259421 and054b27a6 use shared HTTP-compatible implementations;
file integrity checks remain mandatory. Nine digest/transport checks and types pass.
Commit146f35b0 allows omitted optional worker families. The intranet API now checks
only the enabled native worker; thread-access returns200 in0.060 seconds.
API/native-worker final image is
`f5d9158fce352440588ba2bab9e3c0c13424538c2734ea92f5af2c58a6ff5a2b`.
Its base is815d17f1 plus the146f35b0 launcher patch, with regenerated catalog snapshot.
Final App source054b27a6. Existing Vivaldi tab shows the restored session, dsv4,
内网联调 and disabled research control. Browser CSV preview passes with hashes enabled.
Screenshot: runs/intranet-deploy-20261101/http-browser.png. No new business replay.

## Shared presentation correction — 7ea289f2

Both local and intranet now include the shared PPT theme, clock-domain correction,
progress-registration diagnostics and model-purpose fallback. Answer presentation
extracts an explicit body when the model supplies its boundary; unmarked legacy
text is retained. This is not a guarantee against all model-authored preambles.
The saved summer deck contained no figure blocks. Styling does not create missing
business evidence. No historical task or original artifact was overwritten.

Focused checks: App167, agent45, PPT25; types pass. Real intranet dsv4 task
`thr_572b4a3d70b78bc84c06` / `attempt_4cb5164c6791bac2` finished in5.895s,
1model call,0tools, final answer `验证完成`. Browser showed the bold fallback
`整理回答`,2.1s model time and5.9s total. Model omitted the action comment and
answer markers in this exact-output task. Evidence: `runs/presentation-fix-20261101/`.

API/native worker image:58f78932b1b5a0a0a151a5d6f631beac9a14a4cf2b07dc06491377fa9d4f4b72.
Native executor:7a3259b0e545e1e64ed87f9f856f2126ecc14a7213fd368ad82789ec009a6b6b.
App:07691b798e3d34ee90f0faecfef4fb23caf291478fd9e4b362cc350ee72926be.
All four services healthy. No CI. No full summer replay. Concurrency remains one
native task per worker, recorded separately at the user's request.

## Current update — 601b5909 (2026-11-02)

Source `601b590951d934b3065a4dc32c51dd199a826bec` is now active on the same
intranet installation. Default model: `Qwen3.8-Flash-Next`,
`http://192.168.72.69:8013/v1`; models discovery reports262144 context tokens.
API, native worker and executor all select the intranet preset. Gateway remains
`内网联调`. Public App bundle contains the exact source identity.

No dependency pins changed. Source layers were built on the verified intranet
images; backend packages/configs/tools and the App were refreshed from the exact
Git snapshot. The native base reached Docker's layer limit, so its filesystem
was flattened with its environment, working directory and startup command
preserved before adding current files. Original images remain available.
Runtime configuration and both Compose files have `.before-601b5909` rollback
snapshots under `/home/dmdba/capstone-intranet`; secrets were retained there.
No volumes were removed, and no task was active at the switch.

All four application services are healthy; `/health/ready` passes. API and worker
share image `1a04d3fbc7e3968473d6de1637bbe6091033d4951aaf3057a1488baccd07b460`.
Native image: `d4f55584814d9981b0e3d6086a9e1e913b53d4bc2465232ba0955f4617887995`.
App image: `53278c310819119911faf2c359cad3c920bf4c2b455be88a0995039587484e9c`.
A new session selected Qwen automatically and created deployment-check.csv in
24.8 seconds, with one tool call and no tool errors. The17-byte downloaded CSV
matched its saved SHA256. Thread `thr_7e1eb68384073e55f217`,
attempt `attempt_75db5a50c924b67f`; receipts in
`runs/intranet-update-20261102-601b5909/`. Browser connection was unavailable;
visual acceptance was not performed. No CI or historical business replay.

Canonical local rebuild also passed with API/worker image `9d1aac231841012645367cb39991b75ee3209146cc2b359fd07ee61e5354f495`;
scoped cleanup receipt: `.capstone-agent/cache-maintenance-20261102-153322-97910.log`.
Managed-installation runtime/API/UI integration remains pending.

## Artifact panel timing — App939a4d74

The intranet App now serves939a4d74. Starting an instruction selects its product
scope without opening the right panel. The existing primary-product event opens
it when a product is available. Manual scope changes remain respected.
23 execution regression checks and types passed. API readiness and the served
App revision pass; backend/native remain601b5909. No task replay or CI.
Rollback: runtime.env.before-app-939a4d74. Browser unavailable in this session.
