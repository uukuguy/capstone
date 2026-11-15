# Bounded resource reads: local verification

Status: local implementation, real large-file task, recovery and final source-panel presentation passed. Product source21b8f7c8; backend code unchanged from real-model source53c0969d. Dev integration and a separately approved CI remain pending. Owner: capstone-agent/capstone-app. Branch: feat/resource-range-reads-20261115. [Approved design](../superpowers/specs/2026-11-15-resource-range-read-design.md); [implementation plan](../superpowers/plans/2026-11-15-resource-range-reads.md).

## Delivered boundary

The application freezes uploaded resource identities and permits bounded byte reads through the existing private native control channel. agent_resource_read is optional beside whole-file open. It is published only for admitted uploads, with no fixed first action. Historical native products retain their existing whole-file path; no new range grant is inferred for them. Domain Pack, Kernel, Authority and current-run evidence rules are unchanged.

Receipts bind Thread, Attempt, task, request, resource version/hash, byte range and fragment hash. The ledger retains the public receipt and a private bounded fragment. Precise retries reuse the accepted result and accounting, including after source loss. PostgreSQL receipt lookup, usage aggregation and keyset pagination do not fetch unrelated receipt bodies into application memory. Candidate cleanup records a durable tombstone under the same Thread lock as acceptance; object deletion occurs after that transaction. Barrier tests cover both concurrency orders and preserve the accepted winner. Crash reconciliation is an explicit bounded maintenance call; no automatic background scheduler is claimed.

Ordinary source/range/quota failures return bounded tool errors. Required retention failure, corrupt retained bytes, cancellation and debug-capacity failures remain fatal. Native responses are atomic and validate exact receipt fields and previews against verified bytes. Completed request files do not starve later batches. Public API projections contain no storage keys or host paths.

Current defaults: 1 MiB per read, 64 MiB and 1,024 accepted reads per Attempt, 8 KiB preview, 30-second source-I/O budget. These are configurable processing budgets, separate from upload/storage allowance and model context. They are not architecture-wide file-size ceilings.

## Local checks and fixes

- Fresh worktree setup, pinned Pi installation and doctor passed. Existing resource baseline: 51 passed in 7.08 seconds.
- Full focused gate at source85cfe843: 359 Python checks passed, 33 explicitly skipped; 80 App checks passed; five Node checks, typecheck and build passed. The skipped cases are the existing unsupported historical-profile combinations plus one memory-only case that requires a recreated PostgreSQL service. Skips are not counted as passes.
- Follow-up actual task-admission fix53c0969d: 242 affected checks passed, 32 existing profile cases skipped. App and other backend code remained unchanged. Review found no remaining blocker in that fix.
- Final source-panel fix21b8f7c8: 82 parent-selected App checks passed across seven direct-consumer files; worker typecheck/build also passed. Sources now precede report content, with separate ProductRef and resource-read counts. Independent recheck found no new blocker. Earlier overlapping counts are not added together.
- Scope/governance checks: 124 passed in 3.75 seconds. New route is resource-ranges; main and explicit release classification remain full release. No CI was run for this package.

Review repairs include strict frontend cursor/resource/UTF-8 checks, truthful per-receipt coverage, sequential request starvation, non-atomic JSON publication, preview forgery, typed local failure delivery, orphan fragments and cleanup/acceptance races. Each material repair has a reproducing regression. Initial integrated checks also caught missing exhaustive capacity-policy metadata for the five new dimensions; all 137 direct consumers passed after that correction.

## Real deployment and model task

Canonical source53c0969d rebuild completed readiness before the real model task with backend image9485f28a051c69dd6da09fe204e3f9a8e54aec8f7902e85509a8214ca463b695. Final canonical rebuild at21b8f7c8 completed readiness; API and all three workers now run image sha256:04085d24f54b8fc162fdd9727359cc07fe73d2ee16089a9aef9bfb8ad7ddd045. Native executor image remains sha256:de54a10176baadd94070e3cc4f39151f4a39da6d7fa15bc518eb11b8c156dad1. Backend source files are identical between these two commits. API/native transport, port, receipt-contract and SDK-tool files matched the tested checkout byte-for-byte. Native image layer count remained37; new files use existing COPY groups. Final project-scoped cache maintenance completed in apply mode; receipt cache-maintenance-20261115-141645-42385.log. Candidate App uses5178. No cloud/demo deployment occurred.

An actually allocated CSV of 1,077,936,128 bytes was uploaded over the existing API in 257 parts, taking24.682seconds. Sent bytes equal the full file size; no sparse-size shortcut was used. SHA-256: 0d74a81cdff1c40ea7ec8345f55882c474d615eb7fc7332afa73ab24b1b9d2f2. Content is a synthetic transport fixture, not business or simulator evidence. Evaluation values stayed outside model instructions.

Thread thr_af1c01138acab387bae2; Work work_18f0f016a8be8166b540; resource resource_9553359b18e1617dcebc48d557bd8bc4, version1. The first attempt failed before Provider access because task admission did not yet publish the new tool. That failed record remains. The authenticated /tasks regression reproduced400 and passed202 after53c0969d, while historical-only range access remained rejected.

Actual model attempt attempt_7096c7384e103acd completed in about29.3seconds. It called agent_resource_read for three4096-byte slices, then native bash to save its report. No agent_resource_open was called. Exact half-open byte intervals:

| Part | Range | Returned bytes |
| --- | --- | --- |
| Head | [0,4096) | 4096 |
| Middle | [538967552,538971648) | 4096 |
| Tail | [1077932032,1077936128) | 4096 |

All three fragment digests match bytes read independently from the original file. Total model-returned source bytes:12,288. The saved report identified sample values137/251/389, matched the held-out fixture, stated partial coverage and excluded grid/calculation claims. range-sample-report.md is5,231bytes, digest3b7ac095b4173f816794073cf67b6b10d7bb8218edcf75280bdeb8550e9516d7. sample-notes.json also remains saved. Model wording is not certified Authority truth; one minor filename/marker wording ambiguity remains nonblocking editorial follow-up, with original text preserved.

An operator streamed the entire original resource after analysis and verified its full byte count/hash unchanged. This separate integrity read is not part of the model's12,288-byte range-use measurement.

## Bounded I/O and recovery

An additional current-source probe used real isolated PostgreSQL and a disk ObjectStore adapter, including the same full-size file and a cross-upload-part interval. It selected12,416bytes in four ranges. Actual source object reads totalled20MiB: only five intersecting4MiB upload parts. Retained fragment writes totalled12,416bytes. Full-object iteration was disabled in that measurement adapter. Peak process RSS was106,643,456bytes, including interpreter, upload and metadata work; it is not API-only or range-only RSS, and these disk-adapter numbers are not deployed S3 latency claims.

After the probe recreated its service and deleted only its own isolated source part files, exact retries returned identical receipts/content without new source reads or duplicate accounting. Private retained fragments remained. Production source data was not deleted. The dedicated test database container was stopped after checks.

The deployed API was also actually restarted. The public read page and saved report bytes were identical afterward. In the existing Vivaldi Capstone tab, the saved report showed three exact source receipts. Keyboard Tab/Return opened a bounded4096-byte preview. Refresh restored the report and receipt data; switching to the existing paragraph-validation conversation and back restored the same selected report/source ranges. After final presentation correction and rebuild, the App showed 成果引用来源·0 and 资源读取来源·3 before the report. Another actual refresh restored the same report and three receipts with details collapsed by default. These checks did not create new reads. Final API readback preserved the original report bytes.

## Evidence and remaining scope

The actual dev control page was regenerated and checked in the existing Vivaldi tab. It shows dev51fc1cc1, candidate21b8f7c8 and its local-dev deployment as separate nodes, with distinct ancestry and deployment edges. Screenshot: runs/resource-range-validation-20261115/browser-control-graph.png. Documentation links, CLAUDE.md symlink, focused resource-ranges classification, diff whitespace and make doctor passed. CI and dev integration remain pending.

Root ignored runs/resource-range-validation-20261115/ retains fixture/transfer metadata, model commands and events, exact read receipts, saved report, after-restart responses, full source integrity receipt, measured-ranges.json and browser screenshots. It contains no saved operator/Provider tokens. CI approval has not been granted for this package; no push/PR was performed.

Deferred requirements remain explicit: durable full-analysis processing checkpoints, automatic calculation restart, streaming document parsers, large-product sharded indexes/row location, cross-Profile sharing and remote S3/GCS scale acceptance. This slice does not claim complete enterprise-resource acceptance or a cloud performance result.

## Dev integration acceptance

PR115 merged f185c080 after the single user-approved macOS resource-ranges CI43686809091 passed in229seconds. Exact tested head6f5605d4:360 backend passed/33 explicit skips,82 App passed,5 Node passed,271 governance passed/3 skips, typecheck/build passed. Counts are separate gate outputs, not additional model trials. Source branches were closed after ancestry, content equivalence, PR and dirty-worktree checks; recovery stashes6a7f6cfe/c63a3fc1 remain.

Actual dev was synchronized and rebuilt with make capstone-local-rebuild. API and all three workers share image sha256:5517fe25971f84400d0d481d435508d9e44d0c6bfaf6ece0ad807973150e2e7e. Readiness and default App5173 passed. Existing Vivaldi Capstone tab shows saved report, ProductRefs0/resourceReads3 before its body. Public receipts and complete resolved report equal the original acceptance bytes/projections. Evidence: dev-reads.json, dev-report-readback.json, browser-dev-default.png. Scoped cache receipt cache-maintenance-20261115-145058-70873.log completed in apply mode. Cloud/demo remain unchanged. This closeout documentation is prepared locally and requires a separate approved CI before its own PR integration.
