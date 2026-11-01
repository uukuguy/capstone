# Lightweight execution recovery diagnosis

Scope: execution mechanisms, not business-content acceptance or PPT styling.
Historical task: `work_53f7da1d73674ab2ff0e`, attempt
`attempt_3e66dab639f817b9`, thread `thr_52217df00e65ff16be59`.
Evidence is retained under `runs/summer-session-audit-20261101-new/`.
No historical requests were replayed. No CI was started.

## Main-path findings

1. Startup was not the bottleneck in this attempt. The first model request
   started 1.077 seconds after attempt start. Model response intervals total
   466.629 seconds of the 592.860-second attempt. These are wall intervals,
   not provider inference-only measurements.
2. Model rounds 1–31 took about 128 seconds. Discovery and metadata reads
   repeatedly alternated with bash extraction of saved JSON. The retained
   observations were usable, but many model turns only inspected structure or
   selected fields. This is a context/observation usability problem; it does
   not justify forcing one business tool or a fixed discovery route.
3. Rounds 32–37 took about 59 seconds, including a compaction. Seven nested
   calls completed before a context-save failure. Six returned data; one
   rejected a source table and returned null data. The dataset save error did
   not identify which source or pointer failed. The next program treated the
   direct return of `tools.read` as a `{value,ok}` wrapper and tried to read
   rows from the failed result. A later probe read `/data` successfully but
   inspected its nonexistent `.value`, so the model abandoned reuse.
4. Full saved argument hashes prove four unchanged requests were issued again
   in round 35: three successful reads and the table rejection. Similar-looking
   truncated previews elsewhere do not prove duplicate requests.
5. A later program passed a provenance `native-observation` identifier where
   `tools.read` requires an issued call reference or a saved `full_result`
   object. The reference namespaces are distinct. This is not evidence that
   compaction deleted the host's observation map.
6. Four calls in one program used unsupported `params`. The gateway rejected
   them. The current batch preflight checks capacity, argument-object shape
   and selected tool identity; full argument schemas are checked per call.
   Shared-error batch stopping remains guidance rather than an enforced
   scheduler rule. The frozen advertised schema still needs comparison with
   the rejection before assigning ownership of this validation discrepancy.
7. The largest individual gateway call took about 4.58 seconds. Three batch
   programs took about 11.94, 11.19 and 9.67 seconds. No cache-fault conclusion
   follows from these timings. Correcting query construction caused repeated
   extraction, which is a separate problem from upstream request latency.

## Implemented correction

Commit `a45bd3c8` uses one pointer-resolution function for observation reads
and semantic context saves. A missing field reports its requested pointer,
parent pointer and type, and a bounded list of actual keys. Dataset failures
also report the dataset index and source reference. Diagnostics explain the
direct read return shape and distinguish provenance identifiers from read
handles. They do not infer a replacement field, alter data or repeat a call.

38 focused Node checks passed, including recovery from a failed save and a
wrong pointer using the original observation with no additional upstream
call. Canonical local rebuild67650a8e passed readiness and API/worker image parity.
It also fixes the model-profile loader package identity found during the first
rebuild. Scoped cache cleanup completed. No historical business request was replayed;
reduced model/tool counts are not yet a measured acceptance result.

## Follow-up implementation and acceptance

Commit `1253ae06` implements these four changes:

- Whole-batch preflight uses the task's frozen schema and the same validator as
  ordinary invocation. Invalid batches make no upstream calls and do not consume
  reservations. Already running independent calls cannot be rolled back.
- `tools.inspect` provides bounded saved-result structure inspection. `tools.read`
  keeps its direct return shape and uses existing scoped references.
- Failure receipts retain every completed-call handle. Large manifests spill to
  saved storage for bounded paging. They no longer retain only the last eight.
- Successful programs report nested failure counts and references separately.

53 focused Node and34 Python checks passed, including the protected HTTP relay,
deep schema rejection, concurrent capacity reservation and large-manifest recovery.
The canonical rebuild passed readiness and image parity. This is mechanism
verification, not proof that a new business task uses fewer calls.

A new metadata-only validation then failed at task admission before any LLM or
tool call. The worker supplied executor config revision `e49c27a1`; after restart
the executor supplied `00a0512a`, with the same executable source revision. Startup
had hashed mutable gateway publication into executor identity. Commit `cad400bb`
removes that coupling; per-task gateway binding and catalog validation remain.
A startup regression reproduces the original failure and checks stable identity
across gateway publication changes while runtime changes still alter identity.
142 focused host/relay checks passed,32 environment-dependent cases skipped,6.9s.
The cad400bb rebuild passed readiness and image parity. Task admission then passed,
but the SDK rejected initialization before any model/tool call. The model-context
change had also overwritten the SDK's transport capacity snapshot. Research and
history bindings retained the application snapshot, so their strict capacity
equality checks failed. Commit `3e9c8c8e` keeps these contracts separate: selected
model budgets remain in models.json and compaction settings, while runtimeLimits
still matches the task bindings. All55 focused executor checks passed in2.48s.
Commit `d2ea0fd7` also retains bounded SDK module/line and exception-type diagnostics
in private failure receipts; exception text, parameters and external paths are
excluded. One Node and two Python focused checks passed.
The final canonical rebuild3e9c8c8e passed readiness and API/worker image parity
(`6695620c1d567f43379dc2f09db7263a162175b85877cb6c9a4a4be15f039c48`).
Scoped cleanup155253-99654 completed.
Failure evidence: `runs/lightweight-batch-20261101/page1.json` and
`validation-page1.json`. Neither failure reached a gateway business call.

## Real-model validation

Attempt `attempt_1d4ae7f8970f548d` completed in40.705s; first model start was0.999s
after attempt start. It used7 model responses and11 tool calls, with zero tool
errors. Four calls reached gateway metadata tools: discovery twice, one contract
description and one lightweight contract check. The other calls were three tool
searches, one tool load, two composition programs and one local JSON check.

The first composition used tools.batch for discovery and contract check, then
tools.inspect and field extraction. The second composition reused both returned
program-call references via tools.read; its host receipt reports calls=0 and
failed_call_count=0. No business data, SQL or historical query was executed.
The final4642-byte JSON artifact was downloaded through the App API and its SHA256
verified (`cc70514bb2dc10b738a01d5310ff9aa70209c72c6396e8f78734c2ff4ca54083`).
Evidence: `runs/lightweight-batch-20261101/final-records.json` and
`gateway_ref_reuse_verification.json`.

This validates startup, real batch execution and reference-only reuse. It does
not establish optimal task planning or business performance. The model searched
three times and performed discovery before the explicitly requested batch. Those
extra metadata steps remain a planning-efficiency finding; no provider-specific
route or mandatory first business tool was added to suppress them.

## Gateway coordination

The two source-table rejections returned empty `scope` objects and generic
`invalid_arguments` guidance. Request IDs are
`b415e99167604670bb4ae13e020571ba` and
`0e4bf43489f840a0a863fc97ca7dcb9c`. Raw replies and exact arguments are saved in
`runs/summer-session-audit-20261101-new/gateway-followup.json`.
Ask the gateway to check whether this SQL entry should provide the same
unreadable-table path, execution status and recovery action as its structured
query entry. Do not infer `executed=false` from the current generic message.
This follow-up has been prepared, not sent to an external service.
