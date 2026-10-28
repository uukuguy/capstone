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
