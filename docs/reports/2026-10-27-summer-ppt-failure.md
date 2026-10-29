# Summer-peak PPT failure investigation

Status: implementation verified; real business recovery is running.

## Reported failure

Session title: 企业研究与分析 · 10-27 15:01:49. Thread `thr_d6a5d364641c974aea45`, attempt `attempt_4abd327e421a84db`.

The request asks for a June15–August15 summer-peak PPT using current/prior two years of grid load, weather and typhoon data, including national and selected provincial comparisons. The attempt ran15:02:10–15:20:34. It made40 parent model requests and no research children, then ended with `native_model_turn_incomplete`. Context repeatedly exceeded100k reported input/cache tokens per request. The last three model responses were errors. The exact provider reason was not retained; a specific context-limit rejection cannot be asserted retrospectively.

Confirmed amplification paths: gateway tool text included the full MCP response, including duplicated text and structured data; repeated tool loading returned full output schemas. Both remained in model history. Most gateway queries completed successfully. No PPT was delivered.

## Fix1d40a296

Large gateway and tool-load results are saved as complete task-local JSON. The model receives a clearly incomplete preview and file/hash/size reference, bounded to6000 characters. Parent and child sessions use their own private directories. The host event projection restores exact original result bytes for existing receipt verification; no Authority evidence or tool grants are invented. Small results retain their prior behavior. Directory links cannot redirect writes outside the task.

Model response boundaries now retain safe error classification and HTTP status when available. Neutral Kernel events pass bounded metadata; the application allowlists public categories and the App displays known categories. Raw provider error text is not exposed. Existing unclassified errors remain unknown.

Verification:21 JavaScript/actual pinned-SDK cases,115 backend/transport/packaging tests,148 App tests and TypeScript passed. Relevant regressions failed before implementation. Canonical local rebuild/readiness and scoped cleanup passed. Running source1d40a296, image`3a2e25d1c1a21bf86f29a8a867c16843cb6524522ceb53b02329e352bcbb0f24`.

## Real recovery trial

The exact original instruction was submitted in a new conversation in the existing Vivaldi Capstone tab at19:32:30. Thread `thr_4fed88ded08c8ef37b10`, attempt `attempt_4d9d65ecc575c476`. Browser window137137. Old failed records were preserved.

At19:37:17 the task remained active, with meaningful source/coverage queries and Python extraction from saved JSON.39 large results were retained,682224 bytes total, largest136783 bytes. No model failure had occurred. Source discovery found incomplete current-year coverage; any output must separate missing2026 summer evidence from2024/2025 historical analysis. No PPT has yet been accepted.

Remaining acceptance: inspect final saved PPT, supported numeric comparisons and date scope, explicit data gaps, task completion and final model accounting. Do not describe the reported failure as fully recovered until those checks pass.

## History display failure

The user supplied a screenshot at19:42:59 showing `event_buffer_count`4097/4096 at `history.trim`. The backend had already completed the trial at19:42:21, returning a progress report and10 CSV artifacts, not a PPT. The browser stopped before consuming its terminal record and continued displaying a running task.

`ThreadProjectionStore.trimHistory` checked temporary history size before applying its rolling-window eviction. Debug mode therefore threw before normal eviction could run. The corrected order trims the recoverable client window, then observes the retained size; the complete server ledger remains available for history paging.58 scoped store tests and TypeScript pass, including count and byte bounds in debug mode. The count regression failed before the correction.

A real browser reload restored the completed state, progress report and CSVs, with no capacity banner. A continuation was then submitted in the same new test conversation: reuse saved results, deliver an actual PPT, disclose missing years/windows/provinces/typhoon evidence, avoid full re-extraction and progress-only closure. It is pending verification. The original failure is still not marked as fully recovered.
