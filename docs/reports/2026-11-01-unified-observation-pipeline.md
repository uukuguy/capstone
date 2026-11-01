# Unified lightweight observation pipeline

The user requested one coordinated main-path correction, not separate patches for
individual business tools. This extends the earlier composition-only reuse fix.
No tool, provider, object, table, year or measurement name determines this flow.

## Shared execution contract

1. `tools.plan(calls,{purpose,output,basis_refs})` checks the frozen schemas and
   successful task-owned basis references without executing or reserving calls.
   It exposes request counts, identical arguments and available local observations.
   `tools.batch` applies the same checks, reserves capacity and records the plan.
   These are executable facts; the purpose text does not certify business coverage.
2. The task-bound gateway adapter applies exact successful readonly/idempotent
   observation reuse to both direct calls and composition. Concurrent duplicates
   share the first successful read. Each logical call still has a host-verified
   receipt; reused_from and the original observed_at distinguish reuse from new
   upstream execution. Explicit refresh bypasses reuse and is recorded. Failed
   refresh invalidates the old entry; failures and partial results are not reused.
   Live operation references and returned-action following do not freeze polling.
3. `tools.read/inspect` expose the same structured root for observation aliases
   and issued saved-file handles. Legacy transport-prefixed pointers still work.
   Root metadata is part of reference identity. Original bytes remain unchanged;
   cached direct calls can share those bytes while retaining separate call IDs.
4. `tools.table` projects declared row fields from successful task-owned arrays.
   It checks every row for missing fields, exact primitive types, nullability,
   valid dates and timestamps, duplicate source slices, minimum rows and the
   existing bounded processing budget. It collects bounded diagnostics before
   writing. It does not coerce values, invent fields, drop invalid rows, change
   units, or publish a partially valid table. Success publishes CSV plus a source
   manifest with hashes, original references and retained gaps. The output remains
   an observation product, not Authority evidence.
5. Processing failure retains completed call manifests and original observations.
   Repair can plan, reuse and prepare the table in one program without new reads.
   Model transport diagnostics retain only registered error categories; a known
   connection failure or read timeout reaches the existing failure-delivery path
   instead of being reduced to an unexplained incomplete model turn.

## Boundaries

The adapter remains responsible for grants, frozen catalogs, exact receipts and
instance isolation. The native executor owns generic processing and recovery.
There is no new planner service, semantic registry, business routing table or
automatic whole-task retry. Concurrency remains unchanged.

Scope and statistical judgement remain model responsibilities: code cannot infer
which provinces are relevant or whether hourly statistics can be combined into
daily statistics. A declared plan is inspectable but is not proof of optimal
scope. Arbitrary user-requested scripts remain possible; this pipeline supplies
the validated route for standard data access and table construction rather than
claiming all possible generated scripts are correct.

## Verification

73 focused Node checks passed in 2.9 seconds. 94 focused Python/worker checks passed in 13.4 seconds.
Additional targeted host checks verified persisted model connection-failure codes.
The new regression joins planning, a real worker call, failed mapping, observation
reuse and successful CSV preparation. Other checks cover 35-call recovery, concurrent
direct/composed reuse, refresh, polling, task isolation, malformed policy,
immutable file roots, invalid dates, missing fields and output-directory links.
The canonical rebuild of `2b347fc6` completed. API and workers share image
`f96b8e7fb2fbf0c56c152916cc84dd0760d44d2e0984a8873d4335caa603aeeb`.
Scoped cleanup receipt: `.capstone-agent/cache-maintenance-20261101-180419-53195.log`.
No CI or automatic summer replay was used.

## Real metadata trial

Thread `thr_06440e24643ca2748769`, work `work_7f30351c628edbf7ab39`, attempt
`attempt_696255a1871bc668` completed in 26.030 seconds. First model start was
1.037 seconds after attempt start. It used 7 model responses and 8 tool executions
(6 top-level, 2 nested), with no tool errors. Evidence is saved under
`runs/unified-pipeline-validation-20261101/`.

The model selected the published contract-check tool. Its direct read and later
batch read have the same original request ID `aca0471f51844a178bb06841ab1aed37`;
the host reports the batch call as reused. Explicit refresh produced request ID
`5cac253737aa40a592d11b85514c79d5`. Thus the three logical checks made two upstream
reads. Publication remained `2026-11-01T16:34:18.989104+08:00` in the same instance.
Names are evidence from this publication, not permanent execution rules.

One composition performed plan, batch, refresh, inspect, read and typed table
preparation. The CSV has one provider row, 82 bytes, SHA256
`a4dc85d1e5b2aefd5a850ddcf3a54485a4233cfb8dc05b78adc2c3201e8930c7`.
The 665-byte source manifest and both CSV copies were downloaded and hash-checked.
The model made one successful shell call to copy/mark the primary artifact; it did
not use shell to discover source JSON paths. The existing browser tab showed the
completed execution and the CSV preview. No new tab was opened.

The model's custom intermediate summary still guessed some optional helper fields
and reported nulls; the host's completed-call manifest supplied the actual reuse
metadata for the final answer. This trial proves shared execution and typed export,
not that arbitrary model-written summaries are fully validated. Plan availability
currently lists composition-local observations; direct observations can still be
reused at the shared relay. Business scope selection and full summer-task retrieval
counts remain unaccepted; the short trial does not certify those outcomes.
