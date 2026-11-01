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

## Next execution work

- Make whole-batch schema preflight use the same frozen contract and validation
  semantics as ordinary invocation; do not add business-name routing or silently
  drop parameters. Independent calls already in flight cannot be rolled back.
- Improve direct saved-result access so structure inspection does not require
  repeated shell/model turns. Keep references scoped and reads bounded.
- Review failure receipts: `completed_calls.slice(-8)` hides earlier handles
  for larger failed programs. Preserve a bounded, retrievable complete manifest
  rather than encouraging re-execution. This limit was not the cause of the
  seven-call failure in this attempt.
- Keep program completion separate from nested tool success. A program that
  intentionally handles a failed call may succeed, but its returned observation
  summary must preserve that failure for the next decision.

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
