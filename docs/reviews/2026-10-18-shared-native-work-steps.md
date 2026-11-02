# Shared native work-step records

## Accepted requirement

General chat, enterprise research and grid analysis use one Harness step and replay mechanism. The visible process describes actual work, tool ownership, public observations, method changes and failures. It does not expose private model reasoning or invent business steps from tool names. Simple conversation needs no mandatory research plan.

## Confirmed gaps

The professional Pi path maps turn_start, assistant message_end and turn_end to runtime actions and applies RuntimeStepTracker. The isolated general executor discarded those boundaries. Its adapter forwarded tools without step ownership. The App also selected a native-only tool list and omitted task_step_id while projecting native tools. Existing research progress could therefore remain separate from its real execution turn.

## Repair

- Extract the existing neutral turn-boundary projection into public project_runtime_action and use it in both transports. Only phase, response kind and bounded usage counts cross the native host boundary; message content, reasoning and arguments are excluded.
- Forward native lifecycle events through the existing receipt stream. Adapt native tool receipts and successful validated progress records to the existing RuntimeStepTracker.
- Scope step IDs to each native task. Preserve failed-tool links to subsequent turns. Mark an unfinished observed turn interrupted when execution exits; do not invent missing starts.
- Keep native tools as runtime observations, never semantic Authority results or evidence.
- Preserve native tool step ownership in the App and use the shared step component when ownership exists. Old unframed records retain the legacy tool-list view.

## Verification

107 focused backend checks and 23 shared RPC checks passed. App type check and 110 focused UI checks passed. Coverage includes transport field bounds, no private reasoning leakage, native process forwarding, shared step persistence, failed-tool continuation, successful progress purpose, rejected progress, native UI grouping and replay projections. Doctor and scoped diff checks passed.

Local canonical rebuild and real user-path checks are in progress. Implementation remains in model-decision, unmerged. No cloud or demo deployment is part of this change. This repair does not establish a latency improvement or complete lost-process recovery.

## Isolated-image correction

The first rebuilt research check, attempt_a9c63c6374d7fed7 in thr_b222c50e04f74d5a56b5, failed before any model turn. The general executor image intentionally excludes the full capability_agent package, so importing its RPC module raised ModuleNotFoundError. Preserve that failed attempt.

The shared boundary projection is now a dependency-free Kernel module. The isolated Dockerfile copies that exact source as capstone_runtime_events, while the full runtime imports it through the Kernel package. The worker still owns RuntimeStepTracker and persistence. An isolated Python subprocess with site packages disabled verifies that the projection requires only the standard library. Backend checks now total 108 passed; shared RPC remains 23 passed. A corrected canonical rebuild is in progress.

## Failure feedback correction

The user correctly rejected the generic error message and the fabricated completed verification phase in that failed startup. Missing runtime modules now have a bounded public failure code, native_runtime_dependency_missing. The answer explains that an executor component is missing, directs maintenance to repair the service environment, and tells the user that rewriting the instruction or uploading the same files again is unnecessary. Arbitrary exception messages and private paths remain excluded from the public receipt.

Failure and cancellation no longer start a synthetic finalization phase. An active recorded step ends with finish_reason=interrupted; already completed steps remain completed. Verification appears only when the normal flow actually entered verification. The failed acceptance record is preserved, not rewritten.

151 focused backend tests passed, including host failure persistence across restart and an end-to-end Harness error-delivery regression. The App type check and 110 focused tests passed. These checks do not replace the pending rebuilt-image and real-upload acceptance.

## Local acceptance

The final canonical rebuild passed readiness and API/worker image identity checks: sha256:75cdcaaf916d24cf138f9702f8af21b4af0607459da5dbfa4b78f9b8457229db. Log: /tmp/capstone-failure-feedback-rebuild.log. The isolated running container imports the dependency-free projector and contains the new failure classifier. An additional 26 worker tests passed.

- General chat, attempt_5247aeae39857735 in thr_59625f3e3d01e1771a9f: three-sentence answer completed. Native response step 6.351 seconds, first text 1.690 seconds after native turn start; no tools. Refresh restored preparation, native response and actual finalization.
- Enterprise research, attempt_d94eae6eb4ec4b35 in thr_b222c50e04f74d5a56b5: the user-path continuation was only “请继续完成这份备忘录。” The prior browser-uploaded meeting note was retained. The task completed in 43.8 seconds, produced memo-2026-10-19-energy-activity.html, and persisted six native turns. All five tools have step ownership. Refresh restored those steps and tool operation/result summaries. The original failed attempt remains unchanged.

This run emitted no public task-progress observations. Its tool-step titles therefore remain “组织工具调用”. Transport and grouping now work, but useful research method/observation reporting is not yet accepted. No latency improvement is claimed. Browser keyboard activation opened the details. The initial automated mouse check did not reveal the hover-only action strip and hit its own reply footer; this was not composer obstruction. A follow-up test moved the pointer into the reply footer and clicked the control normally, which passed. No layout change is needed for that observation. No cloud/demo update or dev integration is claimed.

The research HTML opened in the App preview and downloaded through its real download control. The downloaded file is 9,724 bytes, SHA256 29df08bd1ff016561bbb7b56d1ad65b529b367303cd60753c9e18f6ec3383cac. The root workspace retains it at outputs/shared-step-acceptance/memo.html. The visible report preserves the named owners, unassigned venue booking, unconfirmed Friday deadline, unapproved budget and unknown vendor delivery date from the uploaded note.

## Public research checkpoints

On user continuation, investigation found the reminder waited for eight execution calls, while the actual task used only five. The existing instruction alone produced no public progress records. The accepted shared-work-record requirement remains the design: the Domain Pack asks for a business purpose before substantive source/file work, then actual observations, limitations and adjustments. Simple conversation stays direct. These records do not reveal private reasoning, certify results, force a research graph or block delivery.

The native reminder now runs before work, after the first execution result, and after a failed tool. It does not repeat after every successful call or impose a tool-count threshold. A confirmed successful progress receipt clears the pending reminder; a rejected progress receipt does not. The generic event adapter supplies timing only; the Domain Pack owns all research wording. Three reminder tests passed after first reproducing two failures. 86 focused backend tests and 16 research bridge tests passed (one PostgreSQL configuration-dependent case skipped); the bridge set includes the real managed SDK in memory. Canonical rebuild and fresh upload acceptance are pending.

### Fresh-upload observation and follow-up

Image 1b7eb7fa5037 passed canonical readiness. Through the actual App controls, a new enterprise-research thread thr_eb5cfa79d33ca27c1d90 was created and the original meeting note selected in the file chooser. Upload overlapped the planned restart and showed HTTP 502; reselecting the same file through the resume control succeeded, leaving one pending draft attachment. The ordinary request asked for owners, dates, unresolved items and a short downloadable HTML, using only the uploaded material.

Attempt_77107fa502be803e completed and produced the HTML. It recorded a public goal and a source/output consistency observation; the latter titled its execution step “核对备忘录与源文件的一致性”. Ten tool calls retained step ownership. However, three early progress calls were rejected with only invalid_arguments. The exact rejected arguments were not retained in the public projection, so do not assert which field caused those calls to fail.

The shared progress tool now explains the step_id/phase pairing rule and gives safe schema repair guidance for validation rejection, without reflecting received values or arbitrary exception text. The Domain Pack reminder asks for the minimal kind/purpose/text record, with purpose as the short step title. Both the canonical tool source and the isolated packaged copy are aligned. The 19 shared research-tool tests passed; the first run also saw an unrelated receipt test fail transiently, and it passed on the subsequent full run without a production change to that path. The 18 bridge/step checks passed with one PostgreSQL case skipped. Final rebuild and natural revision verification remain pending.

### Final local verification

The final canonical rebuild passed: image sha256:643d6534905d1331c54d6fd14dc32aef909fb0f0bd4200128415b54b57f572e1, log /tmp/capstone-research-checkpoints-final-rebuild.log. API and workers share that image. The browser then submitted the ordinary feedback “备忘录再短一些，只保留待办和待确认事项，方便发给同事。请给我修改后的HTML。” in the same fresh-upload thread.

Attempt_3b9b9264bcfc39f2 completed in 23.9 seconds. Its first native step is titled “精简备忘录：仅保留待办与待确认事项”, with a persisted public goal. All five native calls (including progress) succeeded and have step ownership; the App counts four work tools separately. The task read the retained original uploaded note and generated 节能宣传活动_待办与待确认.html. Refresh retained both versions and the step record. No progress argument repair was needed this time.

This is a verified improvement, not a guarantee of complete public research narration: the revision recorded a goal but no separate observation; two native turns kept generic titles. The first full task did record a source/output consistency observation. General-chat latency and broader research stability remain open. The previous alleged composer obstruction was disproved by a normal hover-then-click test. No UI CSS change, dev merge, or cloud/demo release occurred.

### Second ordinary feedback and document access

The downloaded short version omitted the simulation notice. An ordinary user feedback asked to add one sentence and retain all other content. Attempt_76c5811bb937bfe2 completed in 24.7 seconds with public purpose and comparison observations, six native calls and five actual model turns. It retrieved the prior HTML and changed it rather than reconstructing it from a reply. Independent comparison of the two App downloads confirmed only the added notice and its CSS rule. The final file is 3,312 bytes, SHA256 6089b84d3b9a4ceb4e67076d06fd77dc09a63610a6a6953148536442bcf93410; root copy outputs/shared-step-acceptance/memo-short-notice.html. The previous 3,032-byte revision remains available separately.

That last run omitted its optional product-purpose manifest, so the file appeared under collapsed process files. The App now directly shows the open control for an otherwise unclassified sole HTML/PDF, labelled “生成文档”. It does not assign a persisted purpose or certify delivery. Explicit roles and multiple process files keep their existing grouping. Type checking and 112 focused App checks passed. The same canonical rebuild is used for this presentation change; final readiness and browser checks are recorded below.

Final local readiness passed with API/worker image sha256:dbc5abf08dbdfaaf6700c3603bcf722b3953f2df836b192d07c3cea0d539d893 (log /tmp/capstone-research-document-entry-rebuild.log). Browser refresh showed the final file as “生成文档 · 4 KB”, outside any collapsed details, with no horizontal page overflow. Doctor and diff checks passed. No active test task remains.


### Source-observation reminder ordering

Continuation found a reproducible ordering defect in the soft reminder: a successful goal receipt could clear a pending source-result or failure reminder from the same tool batch. A regression test failed before the fix. The reminder now distinguishes the initial goal prompt from result feedback. A goal can acknowledge only the initial prompt; an observation, limitation or adjustment can acknowledge result feedback. It still never invokes tools, blocks completion or fabricates a work record.

Five focused reminder checks passed. The shared bridge/step checks passed (18 passed, one PostgreSQL variant skipped). The real managed SDK fixture now executes the source read before the goal receipt and asserts that the next model request contains the source-observation reminder; this passed in memory (one PostgreSQL variant skipped). The first assertion used JSON stringification for multiline content and failed because it escaped newlines; the fixture now inspects text blocks directly. Doctor and diff checks passed. Local rebuild and actual CSV upload acceptance are in progress; no acceptance or timing claim yet.


Actual source-file acceptance uses a fresh UI thread, thr_de0d0d76457de53c00d9. The file chooser uploaded the original spot-prices.csv (about 1.4 MB); it remained in the draft through the planned restart. The ordinary prompt asked to compare three provinces' August/September mean price and negative-price duration in a Chinese HTML brief, using only the upload and stating that it is simulated. After canonical rebuild to sha256:18f11b7062e016ff0b61e2c7e2f6b8ccb66dc890828cf0b9474e1e439fcf916b, attempt_6a46ee4241454c72 completed in 148.4 seconds. The first progress tool was rejected with the safe pairing hint, and the agent corrected it without an extra user prompt. The accepted source inspection, monthly calculation, chart preparation, HTML generation, correction and delivery records were visible. It caught its own wrong claim that negative prices occurred overnight, recorded the correction and changed the output to noon (11–15).

The actual App download is saved as root outputs/shared-step-acceptance/spot-brief-v1.html, 24,631 bytes, SHA256 bf7c91b4e39615d983977c64e4e3ab7de48c5adb2b13261b8f846725c646c306. Independent standard-library Decimal aggregation agrees with all six monthly mean prices and negative-price durations; the expected results are saved beside it. Four SVG charts are inline. Reading found a wrong fixed monthly sample-count label (2,976 applies to August but September has 2,880), excessive length and unsupported causal language about the main reason for a price change. An ordinary feedback asks to correct the count, keep the monthly comparison and two or three points, and avoid unsupported reasons. Revision acceptance is pending. This first result is imperfect; do not call it fully verified or evidence of latency improvement.

### Natural revision and independent download checks

The feedback was: “9月只有30天，页头每省每月2976个时段好像不对。另外这份有点长，保留月度对比和两三个要点就好，原因没有证据就别下结论。” No technical repair instructions were added. Attempt_60aba68310c9e2b8 completed in about 97 seconds. The revised HTML has the correct monthly counts, a monthly table, two inline bar charts and three points. Unsupported causal assertions were removed, with the source/coverage limitations retained. Both the goal and final observation are public; the observation has two source references. All 19 native calls have step ownership and no tool failed. The first attempt had 30 calls including six accepted progress records and two failed calls; the App excludes progress from its displayed work-tool count.

The actual revised App download is root outputs/shared-step-acceptance/spot-brief-revised.html, 10,157 bytes, SHA256 612c1b946cab28fea22f09ec9550a73d3ab9f24b39a216acae2c64fd538df619. The HTML table was parsed and all six month/province pairs checked against independent Decimal aggregation for mean price and negative-price duration. Verification explicitly requires six matches (province names are header cells). Evidence is in spot-brief-expected.json and spot-brief-verification.json beside the report. The displayed expanded document was visually inspected: table, labels and two charts are readable. Screenshot: /tmp/capstone-spot-brief-revised.png. Refresh retained both versions; reopening the latest version showed the corrected September count and no page overflow. No active test task remains.

This demonstrates real upload, autonomous calculation/correction, file delivery and natural revision. It does not establish optimal latency or complete step narration. Several intermediate turns still use generic titles, and final messages repeat much of the document. Follow-up work should use the measured event timings to reduce avoidable work and response duplication, without imposing a short research timeout. The final local image is 18f11b7062e0; dev integration and cloud/demo releases have not occurred.
