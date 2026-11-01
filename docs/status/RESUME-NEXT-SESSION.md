# Live Session Checkpoint

> Updated: 2026-11-01. Active-session recovery point, not a final handoff.

## Current boundary

User priority is the lightweight execution main path. Business-content correctness
and PPT styling are deferred. No CI without explicit user approval. No push, PR,
merge, new browser tabs, historical business replay or frozen-snapshot changes.

Current product source3e9c8c8e is rebuilt on the main dev checkout. Ready200 and
API/all worker image parity passed:
6695620c1d567f43379dc2f09db7263a162175b85877cb6c9a4a4be15f039c48.
Scoped cleanup receipt155253-99654 completed. API8767, App5173.
App label fixc00bfb15 is active. Configured labels take precedence over reported
gateway names: 本机联调,本机研发,合成验证,内网联调.
Other deployments are unchanged.

## Implemented and verified

- 1253ae06: frozen-schema whole-batch preflight through the existing task grant;
  all completed-call references retained, bounded spill/paging, nested failure
  counts, and tools.inspect.53 focused Node and34 Python checks passed.
- cad400bb: mutable gateway publication no longer changes executor identity on
  restart.142 host/relay checks passed,32 environment-dependent skips,6.9s.
- d2ea0fd7: private SDK failure receipts retain bounded source locations and
  exception types, excluding messages, arguments and external paths.Three focused
  checks passed.
- 3e9c8c8e: per-model budgets stay in models.json/compaction settings instead of
  rewriting runtimeLimits and breaking frozen research/history bindings.
  All55 executor checks passed2.48s. DeepSeek1M/Qwen256K policies remain selected.

## Real-model acceptance

Existing session thr_08b2e2a77b034852bf43, work_7ab6e8a9c7202001235d.
Final attempt_1d4ae7f8970f548d completed40.705s. First model start0.999s.
Seven model responses,11 tools,zero tool errors. Four gateway metadata calls:
discovery twice, description once, lightweight check once.
First composition used tools.batch and tools.inspect. Second composition used
previous program-call references; host receipt calls=0,failed_call_count=0.
Final4642-byte gateway_ref_reuse_verification.json downloaded and SHA256 checked:
cc70514bb2dc10b738a01d5310ff9aa70209c72c6396e8f78734c2ff4ca54083.
Evidence: runs/lightweight-batch-20261101/final-records.json and artifact JSON.
No business data or SQL. Submitted via the same App API when existing Vivaldi AX
control was denied. No new tab; no claim of fresh visual acceptance.

Earlier attempts remain intact:
attempt_1a837c4b9359dca9 failed admission on cached executor identity.
attempt_b481f74f0d803ec2 passed admission but failed SDK capacity consistency.
Neither made a model or gateway business call.
A rejected new-work command returned conversation_work_exists and did not execute.

## Remaining work

The model performed three searches and a discovery before the requested batch.
Mechanisms are verified; optimal planning or fewer calls in real business tasks
are not established. Investigate redundant discovery/search from actual task
context and tool descriptions, without fixed business routing or mandatory gateway
calls for unrelated requests. Do not rerun the summer business task automatically.

Report: docs/reports/2026-11-01-lightweight-execution-recovery.md.
Gateway follow-up packet: runs/summer-session-audit-20261101-new/gateway-followup.json.
Two historical generic table rejections need gateway clarification if pursued;
no message was sent externally. Current startup fixes need no gateway change.
Keep concurrency4; no confirmed gateway cache defect.
Instance3db5bb96-2c27-4d97-8584-346bc4a18656 at127.0.0.1:18001/mcp.
Latest metadata task confirms contract_updated_at2026-11-01T10:43:16.267212+08:00.
Use that timestamp, not differently scoped contract hashes, for publication change.

## Recovery and ownership

Current implementation commits are local dev; no remote integration performed.
VERSION-CONTROL, INDEX, report and PROJECT-OVERVIEW now include the real acceptance
receipt. Generated graph was inspected in its existing Vivaldi tab: current HEAD,
verified ancestry and local-dev source are visible. User switched to another tab;
no further focus change or new tab was made. Task result itself is API-verified.
Preserve unrelated untracked docs/reports/2026-11-01-summer-session-audit.md.
Historical evidence remains under runs/summer-session-audit-20261101-new/.
Do not revisit UI count disagreement unless requested; user said to focus on the
lightweight main chain.
