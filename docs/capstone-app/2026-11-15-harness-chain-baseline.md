# Harness execution-chain baseline

Status: local mechanism verification; frontend acceptance remains open.
Source: actual dev e0fc951e; unchanged local runtime f185c080, as recorded by the preceding rebuild receipt. This probe did not independently attest the runtime image.
Owner: capstone-agent and capstone-app. Destination: dev. No runtime source change, CI or deployment.

## Accepted scope

Trace instruction submission, frozen context and grants, model/tool execution,
answer admission, durable products and App continuation/recovery. Reuse the
existing conversation. Do not revive archived execution implementations or
introduce fixed business stages. Authority evidence remains distinct from
general task products.

## Current source seams

- `thread_work.py:apply_work`: Work revision checks and continuation input.
- `harness.py:HarnessAttemptRunner._run`: lease ownership, runtime execution,
  answer admission, bounded correction and terminal commit.
- `harness.py:_persist_event`: public/diagnostic projection and persistence.
- `general_pi_executor.py:GeneralPiProcess.run`: bounded native event transport,
  cancellation, deadline, usage and answer extraction.
- `general_pi_server.py`: native process orchestration and artifact collection.
- `threadProjectionStore.ts:readSnapshotEvents`: contiguous event restoration;
  live loading also guards superseded snapshot requests.

These are source observations, not proof of every failure path.

## Measured local slice

Thread: `thr_2a8a75f03e429abf90e0`.
Attempt one: `attempt_ca4f56ac99825d04`; attempt two: `attempt_e861a90f234e0321`.

1. A real model created simulated CSV rows A=7, B=11, C=13, read the file and
   saved a Chinese report. Two main response records and one tool execution;
   host execution stage 8493 ms. This is not total end-to-end latency.
2. A new instruction in the same Work requested doubled values and preserved
   originals. The real model delivered new CSV and report, with total 62.
3. Six distinct attempt/file downloads passed byte size and SHA256 checks.
   Independent CSV parsing confirmed original total 31 and doubled total 62.
   Copied originals retained exactly the original file digests.
4. Both attempts have persisted completion events. Snapshot reads show the
   same Work completed at revision 6. API reads do not prove browser refresh.

Focused checks: Harness, task steps and research bridge: 139 passed, 1 skipped,
16.49 s. App projection store and progress: 72 passed, 1.07 s.
Skipped coverage is not accepted coverage.

Ignored operator receipts: `runs/harness-chain-20261115/`, including commands,
snapshots, event pages and `download-verification.json`. Credentials remain in
protected backend configuration and do not enter these receipts.

## Open verification and next step

The second attempt republishes copied original files with the second attempt's
producer identity. This observation alone does not prove a lineage defect.
Trace product-series admission and source references before changing behavior;
check whether App distinguishes retained source copies from new derived products.

The browser plugin found no browser, but the existing Vivaldi window is available
through Orca Computer Use. On 2026-11-15, the existing Capstone tab was reused to
open this Thread, inspect both answers, preview the doubled report and reload the
page. The same Thread, both completed instructions, totals31/62 and the report
returned after reload. No additional tab was created. Screenshots and UI trees
are recorded by `loaded-final.json` and `after-refresh.json` in the receipt folder.

The App displays two primary files and two supporting files for continuation;
copied originals are not presented as replacements for the old attempt. Both
attempt answers remain visible. The report's structured product-source count is
zero, despite its prose explaining the source relation. Source code confirms
`product_series_service.py:sources` reads only `submission.context_product_refs`.
This instruction contained no explicit product selections. Runtime observations
show protected historical-resource paths used by the successful processing tool;
the model selected and opened the historical inputs. Thus execution access and
file preservation work, while the structured product-source panel does not show
this implicit continuation consumption. This is a coverage gap, not evidence of
fabricated data or failed byte preservation.

Next slice: distinguish admitted historical availability, successful host file
opening, and asserted product derivation. Only host-verified access may populate
an access record; model prose or matching digests alone cannot prove derivation.
Reuse `resource_origins` and existing source contracts, with exact task/attempt
identity and idempotent persistence. Do not label all historical files as consumed
merely because the model could access them. A scoped design and regression case
must fix the distinction before extending the public source panel.

Cancellation, interrupted execution and service restart were not exercised by
this slice. This is not full-chain or release acceptance. Preserve existing seven
uncommitted closeout files. No runtime code has changed.
