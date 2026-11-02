# Research chain repair — 2026-10-18

## Latest checkpoint: application budget, progress paging, and failure receipt

The new source candidate fixes three separate defects. Canonical local rebuild passed; API and all three workers use `sha256:e8897449f5c3083d5e3f4597d019f3907456e33efc5e75b3fc99ad290834058e`. Fresh upload, initial report, ordinary feedback, revised report, task-delivery versioning and reload/download acceptance passed locally. This does not establish general stability or cloud acceptance.

- The native runtime now reads `CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS` (default 600). The optional `CAPSTONE_ENTERPRISE_RESEARCH_TIMEOUT_SECONDS` overrides it only for the accepted enterprise-research profile. The local test configuration sets 1800 seconds. Both resource admission and the frozen execution request use the selected value. Finite positive application values above 3600 are accepted; 7200 is tested. This is a visible execution budget, not a short connection deadline or a completion claim.
- The 128-event/64-KiB limit now bounds the unacknowledged transport window. A monotonic cursor permits subsequent pages. The worker validates contiguous event IDs before publication and acknowledges only after delivery to the parent ledger. Four real HTTP test cases each preserved 300 events. This does not claim recovery of an executor process lost before acknowledgement.
- Failed native results use `capstone-pi-task-result/2` with only a validated failure code and phase. Existing version-1 receipts remain readable. The public answer uses the recorded reason and, for deadline failures, the actual frozen budget. Raw exception text stays private. Failed receipts retain their reason after host restart. Rollback to an old strict version-1 reader is not verified.

Latest focused verification: 195 passed, 15 skipped (PostgreSQL variants without a configured test database). The preceding broader run passed 209 with the same 15 skips, including network-policy and artifact-publication coverage. The local rebuild script check passed. The live delivery gate below passed.

Fresh browser session `thr_36dbeb15686568c7a3e6` uploaded all four original sample files through the file input. All four appeared as removable draft attachments before submission. Selected `explore-data` and submitted the ordinary report request at 06:37:21 UTC. Attempt `attempt_5480ae54cfcc78d0`, native task `pi-7ab5cc6cca46d8a224eceb31829d0888db9cac70c5f46a43faac993eb3a67bac`, completed as recorded below. External access remains off. No Provider task is now active.

### Fresh upload result and ordinary revision

The first request completed at 06:42:37 UTC (about 5 minutes 17 seconds). No follow-up request was needed to finish it. The native receipt is completed, with 29 artifacts and 51 observation sources. The parent ledger records completion at event 1622. Progress continued beyond the former lifetime cap. The App presents one primary HTML report and folds supporting, reproduction and process files into separate groups.

Actual App download: `outputs/research-budget-acceptance/report.html`, 95,493 bytes, SHA256 `b2e06fce1106815b1acdb8bc0def217097e9bb3d3768a20baf62c7e1a3f923ee`. It contains nine inline SVG charts and ten tables, with no external resource dependencies. The file was rendered independently through a loopback static server because the browser automation blocks file URLs. Report access after App reload passed. The UI adopted it as task delivery version 1, named “两月现货与新能源分析报告”.

The first artifact is not perfect: chart 7 contains twelve negative-height SVG rectangles, so the two small reduction series do not render. The report also needs clearer province-hour wording. Submitted only ordinary user feedback at 06:47:57 UTC: “报告整体可以。图7里正式限发和其他减发几乎看不见，能把这两项单独画清楚吗？另外，三省负电价小时加在一起容易看成实际持续时间，请标注清楚。其他内容尽量保留，给我修改后的报告。” The user-facing reference control attached the saved report. Attempt `attempt_4e460a12fa1489ec`, native `pi-56b5b3008a1477e884e9752137d90c2129823e3dee67b99e174f37aff42221da`, then completed in the same work. No operator-written script or technical recovery prompt was supplied.

Revision completed at 06:51:47 UTC, about 3 minutes 50 seconds and 33 tools. The downloaded report is 101,989 bytes, SHA256 `77dc25213d4856d0ea69232583250cb57ebf51e6ada7aaa1f13c1aacee8d2632`. It has nine inline SVG charts, eleven tables, no external assets and no negative-size rectangles. Seven original SVGs are byte-identical; chart 3 changes its duration label and chart 7 is redrawn. Seven original tables are byte-identical. The other table changes concern duration wording and added province-hour/actual-window comparison; existing business-data rows remain. Independent browser rendering shows the small reduction series clearly.

The App adopted the revised saved file as version 2 of the same task delivery. Reload restored the title “两月现货与新能源分析报告 · 修订版”. Opening the display area selects v2; a new browser download has the same SHA256 as the revised file. Both attempts remain completed and the final thread cursor is 3238. Control graph verification passed: 30 nodes, 40 edges, no overlaps, crossings, through-node edges or viewport overflow. Source remains an unmerged local candidate; cloud-dev, demo and local-demo were not changed.

Remaining runtime quality issue: the isolated default Python lacks pandas/matplotlib. This run recovered with standard-library computation after an unsuccessful package-install attempt under the disabled external network policy. Do not count a prepared analysis-library environment as delivered. Task-process crash recovery and old-reader rollback also remain unverified. This successful run lasted less than 600 seconds, so the live test confirms config wiring but does not prove execution beyond the former deadline; 7200-second admission is covered by the real HTTP regression.

## Earlier checkpoint: control-plane packet loss

### Third live outcome and remaining lifecycle defects

`attempt_24d61c76261245a0` failed at 05:28:34 UTC when the application’s 600-second deadline expired. It retained 28 process files, including a 105,618-byte `report.html`; this is not completed report delivery. Publication and cancellation retention now work, but the research chain has not passed acceptance.

During this run, terminal nft reject counters also observed packets to TCP port 443 after the socket-UID exemption. An exact existing root-owned Provider connection was temporarily allowed for diagnosis. This did not establish that the run would finish; do not attribute the entire delay to that rule. Source now marks only connections originated by trusted service UIDs and permits subsequent packets with that mark. Task-originated connections cannot acquire that mark from this rule. Control-service reply handling remains explicit. A root-service 524,288-byte HTTP transfer passed three times in 29 ms, and the network-policy/publication tests passed (14). The final service-mark source rebuild is in progress in `/tmp/capstone-service-connections-rebuild.log`; no research task is active.

Inspection found a separate confirmed black-box defect: `GeneralPiHost.emit` stops appending after 128 projected events or 64 KiB, while assistant token deltas consume that same budget. `HttpGeneralPiExecutor` also caps cumulative seen events at 128. Later tools and progress can therefore disappear despite ongoing file generation. This requires durable cursor-based progress pages, not another larger fixed lifetime count. It is not fixed by the transport patch.

The remaining delivery work is task lifecycle: a normal long research task must not fail merely because it crosses the generic application deadline. Explicit resource budgets must have a visible, recoverable disposition with saved work. Communication deadlines remain retry signals; user cancellation remains authoritative. Persisted progress pagination, task checkpoints/resume, and early candidate-product publication must be implemented and verified before claiming long-research acceptance. Do not solve this by replacing 600 with another unexplained constant or by supplying an operator-written recovery prompt.

Final source rebuild is ready: API/worker image `sha256:6ba8c13658797164299430a774e4b540fbd44d325ca7b3a31b6b656e323dba23`. Fresh browser thread `thr_26465ef36b60f46b9d60` uploaded the four original files. Rebuild invalidated the previously selected skill catalog version; the UI preserved all draft files and required reselecting explore-data. After reselecting, the same ordinary report request was accepted at 05:18:32 UTC as `attempt_24d61c76261245a0`, native `pi-3b0880cf816b2fce97c580ac419ad9f5a95660efef3f6813918032fa0be531f3`. This run is still under observation; do not count artifact generation as delivered until App completion/download passes. No technical recovery prompt has been submitted.

Environment recovery: the host had about 120 MiB free when OrbStack stopped. `uv cache prune` removed 5.7 GiB of regenerable cache; no task data, uploaded resources, volumes or reports were removed. OrbStack is running again and the canonical rebuild is active. Final combined checks now pass: 160 tests, two PostgreSQL cases excluded. Cancellation cleanup retains process files without entering the ordinary publication retry loop. The control graph browser check has 30 nodes, 40 edges, no overlaps, crossings or overflow.

The second live attempt `attempt_2f81194ef82d5ec3` did not pass delivery. Its native task completed with a 115,018-byte standalone report, ten charts and fourteen artifacts. Status transport recovered at 04:48:44 UTC without restarting research. Artifact download then failed; the App recorded failure at 04:48:49. Preserve this failure history.

Large control responses stalled at 126,976 of 128,336 bytes, including on executor loopback. Adding an established control-service reply rule immediately restored status and report reads in 2–3 ms. The committed source candidate now permits only `tcp sport 8790 ct direction reply ct state established` before the socket-UID filter. It does not allow established outbound task connections. An unprivileged task still failed to connect to the public Internet with external access disabled. Missing socket identity on kernel-generated packets is the suspected packet-level mechanism; the rule-level before/after result is confirmed.

Artifact publication now retries typed transport interruptions against the same receipt and content hash under the existing task control. It never restarts research. Permanent response/content errors remain fatal. Publication failures retain an explicit `native_artifact_persistence_failed` category and the native executor status. Focused delegation, publication and network-policy tests: 135 passed. The first canonical rebuild failed when the local OrbStack Docker daemon exited. Recovery and a final rebuilt user-path acceptance are still required; the new source must not be described as deployed or accepted yet.

## Scope

Finish the compact composer popovers, then return to execution reliability. Do not expand cosmetic work. The user requires actual file upload and ordinary business feedback, without operator-written recovery instructions.

## Confirmed defects

1. Research tools return structured `isError: true` on rejection. Pi 0.84.4 derives its initial error flag from thrown exceptions and ignores that return field. A rejected research read or update could therefore appear successful in model context and execution events. The research extension now uses the public `tool_result` hook to set the error flag from its own failed receipt. It preserves content and structured details and does not change unrelated tools. A managed SDK session test exercises the real AgentSession hook bridge without a Provider call.
2. Status polling and research-channel exchanges used a 250 ms transport timeout. A real HTTP regression with a valid response delayed by 400 ms failed and caused remote cancellation before the repair. These exchanges now allow five seconds, bounded by the existing task deadline. The transport still checks user cancellation every 25 ms. Mutation requests are not automatically replayed. Cancellation cleanup limits stay unchanged.

These are confirmed defects. The older 98-second failure did not preserve its original parent exception, so it cannot be attributed conclusively to either defect. Earlier cancellation-reason instrumentation remains in place.

## Composer cleanup

Skill and context popovers share a compact 340 px layout and typography. Original skill names remain visible. Context uses one “会话资料” list instead of storage-oriented categories. Draft attachments remain in the composer until the user sends the message. Existing historical selection/removal behavior is retained. The context list measured 340 × 133.5 CSS px in the real browser, with one submitted CSV.

## Verification

- App input and work-execution tests: 23 passed; TypeScript check passed.
- Delegation transport and runtime tests: 119 passed, including the slow-valid-status regression and existing cancellation/deadline tests.
- Research tools: 19 passed, including the managed Pi SDK failure-hook contract test.
- Research bridge suite: 10 passed (PostgreSQL case excluded), including delayed bootstrap, pending, and acknowledgement exchanges and terminal replay.
- `make doctor` and `git diff --check` passed.
- Canonical local rebuild is ready. API and worker image: `sha256:39af3734309eddede5864b614e83bb5cb4b0d3693e6bd748d94eac32dc3fc30d`. The deployed native container contains the research result hook.

## Live user path

Browser-created enterprise session: `thr_62d2e11e125b2833be02`. Four files were selected through the actual upload input: README.md (5538 bytes), spot-prices.csv (1473876), interprovincial-flows.csv (1545038), renewable-generation.csv (2265749). The composer showed four removable draft cards before submission. The accepted command binds all four stored resource IDs.

Selected the original `explore-data` skill and sent: “请根据这几份模拟资料，分析两个月的现货价格、负电价时段外送通道利用和新能源消纳情况，做一份有图表、能直接打开汇报的中文报告。资料不足的地方请说明。”

Attempt `attempt_7f6fa94f7002f40b`, native task `pi-d0acfba4a7d5d845283f0b941f8f99dc6e216c3e4bb3a76939f06bf3469f0f6b`. Accepted 04:26:43 UTC. At 04:26:50 a rejected `agent_task_progress` call was recorded with `is_error: true`; at 04:26:51 the agent corrected it and received success without a user repair prompt. CSV structure/coverage output arrived at 04:26:54. The report is still running; do not count it as a completed delivery yet.

### Failed live result and corrected direction

The attempt failed at 04:30:36 UTC after about 233 seconds with `native_transport_timeout`. The original request allowed 600 seconds. The native receipt later confirmed cancellation and retained seven process artifacts; no report was delivered. Increasing a per-exchange timeout did not solve the lifecycle defect. Do not mark this run passed.

The user explicitly rejected seconds-based communication limits as a reason to stop deep research. Connection health and task lifetime are now separate: transient timeout/connection loss keeps the same task alive and retries with bounded backoff until connection recovery, user cancellation, or the independently configured task budget. Task admission uses the same ID and frozen request; bootstrap/acknowledgement replay uses the same owner, revision and receipt. No model task or business tool is restarted. Protocol/authorization errors remain fatal. Diagnostic interruption/restoration events identify the affected operation and safe transport phase without URLs, credentials or raw exception messages.

Verification of this second repair: 131 delegation/runtime/research bridge checks passed (one PostgreSQL case excluded). Eight additional parameterized real HTTP bridge checks cover delayed exchanges and lost admission/bootstrap/acknowledgement responses; research revision remains exactly one and the task runner executes once. Existing user cancellation and task deadline behavior remains covered. A new canonical rebuild is in progress; fresh live report acceptance remains outstanding.

Budget audit: `CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS` is supplied by the hosted application, currently defaulting to 600 seconds, and frozen in the admitted task. This is distinct from connection polling. Explicit, resumable long-research budgeting remains a product requirement; this change does not claim unlimited-duration execution or restart-resume of a lost native process.

Second canonical rebuild is ready: `sha256:0540d241bfcef9719ff40ee0d71806e9c475477a94e53fb00ef3ab89f838c604`. Combined final backend suite: 137 passed, one PostgreSQL case excluded. Fresh browser session `thr_4a5f82035f79affd96c6` again uploaded the four files, selected explore-data and sent the same ordinary request. Attempt `attempt_2f81194ef82d5ec3` is running. No operator recovery prompt was sent.

Implementation remains in `.worktrees/model-decision`, uncommitted. No cloud or demo deployment changed.
