# Session LLM selection: local validation

Date: 2026-10-28. Scope: enterprise workbench session models and native task routing.

## Implemented

The application registry owns model options and local/intranet startup defaults.
The public catalog exposes admitted IDs, labels, model names, availability and icons.
Provider credentials and routing remain protected by the backend. Composer selection
persists per session. Submission freezes the exact registered model identity; omitted
selections also freeze the deployment default at admission. DR remains next-instruction-only.

The compact menu uses the DeepSeek brand for the commercial option and server icons
for internal models. Each item shows one name, or IP:port plus model. Keyboard focus
starts on the selected model, skips unavailable items and returns on Escape.
The source-grid header shortcut was removed. Cache settings use aligned compact controls.

## Verified

- 125 focused App checks and TypeScript passed; two additional icon/keyboard interaction
  checks passed. Vivaldi showed the correct DeepSeek icon and no source-grid header button.
- Combined backend registry/admission/catalog/execution/relay checks: 81 passed,
  18 unrelated version combinations skipped, 3.86 seconds.
- Omitted-default admission regression failed before the fix and passed afterward.
  Changing the startup preset cannot change an already accepted selection.
- The selective native Docker projection reproduced a missing gateway_diagnostics import.
  The image now includes it, checks the import during build and includes it in executor
  identity. Seven packaging checks passed; the actual rebuilt container import passed.
- Commercial model test through a new conversation in the existing Vivaldi tab:
  thread thr_fab1ac9870cddc90b83e, attempt attempt_4ddb08977604b40e.
  Actual tool execution calculated 137 × 29; answer 3973. Total execution 2.985 seconds,
  two model responses, one bash call, no gateway call. Admission and private runtime
  receipt both identify commercial-deepseek-flash / deepseek-flash.

## Deferred or incomplete

The user confirmed the development server is disconnected. The submitted 18804 test
attempt_61073af59d9b5c90 was cancelled in Vivaldi; the ledger confirms cancelled.
The session was restored to commercial DeepSeek. This is not intranet model acceptance.
Do not probe internal models or remote gateway until connectivity returns.

Real intranet tool calling, two-session refresh persistence and an intranet server
deployment remain unaccepted. Earlier direct connectivity/generation probes are historical.
Current lightweight-chain performance and failed summer-PPT recovery remain separate
open tasks. Do not infer business acceptance from unit checks or readiness alone.

## Same-session recovery verification

After restoring commercial DeepSeek, the failed summer thread
thr_4932d0b2b8e4d1a2105a continued as attempt_58c55b5ad6cf8d22.
It reused admitted saved files, fixed two script defects and a table-width issue,
and delivered a 15-slide PPT plus metrics_core.csv and source notes.
The original attempt remains failed. The recovery took 69.330 seconds,
16 model responses and 18 tool calls (16 bash, one write, one diagnosis record).
There were zero gateway calls. Tool-level failures were recorded and repaired
without turning this recovery into a whole-task failure.

Downloaded PPT: 564490 bytes, SHA256
`e4b7e8afbf1fdecf32446eb99b66caba903b13714205ad89bdeaeca5073b07de`.
The API hash, zip integrity and 15 slide XML parts passed. Metrics and source CSV
hashes also matched published descriptors. Vivaldi displayed the cover and advanced
to page 2 in the right pane. This is structural and limited visual verification,
not a full numerical or all-slide review.

The trace still shows avoidable calls: probing an empty output directory before
using staged inputs, then coping with read-only permissions inherited by a working
copy. The next optimization should improve generic staged-input guidance and
combine related local operations. It must not encode this business script or
weaken the read-only source boundary.

## Scoped review and root-loop follow-up

Independent review of a81f1820..98c7d33a found no new Critical/Important issues.
The omitted-default issue is closed for the current Work send_message path;
the historical non-Work bare-message compatibility path was not accepted by this review.
The reviewer ran 11 Python and eight UI checks without provider or remote requests.

5723947c found and fixed a concrete lightweight wiring omission: nativeExecutionGuidance
was available to research children but absent from the normal root loader append.
The new loader regression failed before this fix. It now includes the same generic
execution grouping and read-only input working-copy advice; organization-only parents
still do not receive native execution guidance. 28 graph and23 error-path checks passed.
No end-to-end speed claim is based on this prompt wiring check alone.

## Full fresh-generation attempt and gateway repair

The latest root optimization was tested from a new Vivaldi conversation with the
unchanged 1311-byte full summer instruction (SHA256 d3f126381daf74a6d46cd9a3fb1aa8b9cde84813702c305c73ddea0c7ab2e03f).
Thread thr_ff8c3c7c95d8967a5a1c / attempt_0fca8bbb5cb5b180 used commercial DeepSeek,
DR off and zero inherited materials. It failed after115.420s,10model responses,
14bash calls and one progress call; no gateway business call was made. It is not
full-generation acceptance and not a valid timing improvement over data-backed trials.

Container-side MCP initialize returned421 with the fixed response Invalid Host header.
URL and authentication matched the sibling local-integration-container configuration;
authenticated host access succeeded. Capstone did not alter the sibling repository.
The user asked the gateway owner to repair it. A later container MCP prepare succeeded
and discover_gateway returned isError=false with status/data/gaps/provenance/calculation.
The catalog contained51 tools at that probe; later publication may change.

The failed task also exposed NativeDiagnosis.handle envelope validation. A long-script
rejection reproduces that exact ValueError at the former hidden32KB limit. 9cb69245
uses actual compact UTF8 size and the existing native RPC capacity; it does not change
selection hashes or reset retry scope. The exact failing wire frame was not retained,
so this regression identifies a real failure path without claiming a complete forensic
proof for every earlier native_execution_error.39 diagnosis+failure-origin tests passed.
The independent reviewer ran37 diagnosis and4 safe-status tests, finding no Important
or Critical issue.137 MCP+host tests passed with NO_PROXY; two initial localhost502s
were caused by proxy use and are not product acceptance failures.

A rebuilt host must reload the restored gateway catalog before the next fresh full trial.
# 2026-10-29 lightweight progress correction

The current development stage keeps automatic DR escalation disabled. The user
may require DR for the next instruction with the composer switch. Longer term,
DR is a closed delegated operation of the lightweight reasoning loop, not a
replacement for that loop. This future integration is not accepted yet.

The 58.94-second attempt `attempt_c3463976741ad57a` did not start DR. Its
`agent_task_progress` receipt started `data_recon`; it did not settle that step.
The App nevertheless selected task presentation, and host finalization changed
the running step to completed. Regression tests reproduce both faults. Native
conversation progress now stays in the tool process unless an actual research
graph is admitted. An unsettled business step closes as limited; interruption
does not mark running work completed. Existing explicit terminal statuses remain.

A separate context fault was found: progress guidance was appended as a synthetic
user message after the real task. For explicitly lightweight instructions it now
stays in system guidance, without creating a new user request for a status answer.
This is a candidate fix for premature progress-only answers. The real full
PPTX/CSV task must still verify the effect; unit checks do not establish it.

## Full lightweight delivery — 2026-10-29

The same original instruction was submitted in a new Vivaldi conversation:
`thr_0eb9fcae6393c8022b89`, attempt `attempt_a44450618326822a`.
Instruction SHA256 remains `d3f126381daf74a6d46cd9a3fb1aa8b9cde84813702c305c73ddea0c7ab2e03f`.
Source `61feb331`, backend image `c56e9b228a5682f9f8efa1897e00055746b4fd1d16bc0d5af2dbadf81aecc602`.
Canonical rebuild and scoped cache maintenance completed. Commercial DeepSeek,
local integration gateway, DR false, no inherited materials or research children.

- Full run: 420.676 seconds, 64 model responses, 98 tool calls, 7 error receipts.
- First tool: 2.135 seconds. Last tool return to attempt completion: 8.643 seconds.
- Model response intervals sum to 336.62 seconds. Tool intervals sum to 54.09
  seconds, including overlaps; these sums must not be added as disjoint stages.
- Usage: 254,674 uncached input, 4,077,696 cache-read, 68,166 output tokens.
  The 47-second response wrote the PPT generation script. Repeated discovery,
  source-result parsing, data corrections, script construction and polishing
  remain optimization targets. This run does not establish a speed improvement.
- Actual primary PPTX downloaded: 715,648 bytes, 14 slides, 6 embedded media;
  ZIP passes and SHA256 `90c9607644552d28886241d78a8ffbf770dcf680971ed841ac7a701cae2be31a`.
- Actual core CSV downloaded: 2,044 bytes, 14 data rows, 21 columns;
  SHA256 `aa2a9050613ae3163e38537b0444a0102bf8f8d0d64d842f3937d06701368cf3`.
  Every row has the header column count. Download sizes and hashes match saved
  references. Vivaldi displayed the real PPT cover. Full slide visual and
  business-conclusion acceptance are not inferred from this check.
- Semantic title succeeded in 1.031 seconds, 11 completion tokens, with thinking
  disabled for naming only: “迎峰度夏电网数据PPT与CSV交付”.

Execution UI now shows each model response as a primary row with its measured
time. Native tools are grouped using explicit SDK turn boundaries and actual
call IDs within that turn, not timestamp adjacency. Tools use single-line,
closed-by-default details. Header counts and cumulative model time remain visible.
Observed Vivaldi header: 98 tools, 64 LLM calls, cumulative 5m37s, total 7m01s.
Overlap badges require the same response and overlapping recorded intervals.
145 App checks and TypeScript pass. Missing response boundaries preserve the old
request as incomplete and accept the next explicit start as a new request. A
response with no matching start cannot keep assigning tools to the old turn.
Cancelled tool receipts remain cancelled. Historical records without an admitted
native turn scope remain unassociated. No tool contents or evidence are changed.

Diagnostic evidence is retained under ignored `runs/light-full-20261029-stability/`,
including events, timing breakdown, download hashes and actual files. Historical
partial progress-only runs remain failed delivery comparisons, not successful baselines.
