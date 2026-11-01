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

73 focused Node checks passed in2.9s.94 focused Python/worker checks passed in13.4s.
Additional targeted host checks verified persisted model connection-failure codes.
The new regression joins planning, a real worker call, failed mapping, observation
reuse and successful CSV preparation. Other checks cover35-call recovery, concurrent
direct/composed reuse, refresh, polling, task isolation, malformed policy,
immutable file roots, invalid dates, missing fields and output-directory links.
The live source is not yet accepted until the canonical rebuild and a short real
metadata-only pipeline trial finish. No CI or automatic summer replay is used.
