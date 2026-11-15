# Historical input delivery receipts

Status: approved by the user; implementation492b78e2 passed local real-task and Vivaldi restoration checks. Dev integration remains pending.
Owner: capstone-agent and capstone-app. Destination: dev.
Parent: Harness execution-chain baseline, approved by the user on 2026-11-15.

## Problem and evidence

Real continuation in Thread `thr_2a8a75f03e429abf90e0` opened two historical
files, generated doubled data and preserved the original bytes. Vivaldi restored
both instructions and the report after reload. The structured product-source
panel still displayed zero because `ProductSeriesService.sources` reads only
explicit `context_product_refs`. Report prose is not a trusted lineage record.

## Decision

Record host-confirmed historical input delivery separately from product sources.
Do not manufacture an explicit user selection, rewrite the submission snapshot,
or infer that each output derives from every available input. A successful open
may return only a leading preview and protected path. The public claim is
therefore “historical input delivered”, never “full file analysed”.

## Receipt boundary

The worker-side `pi_delegation.py` already validates requested manifests against
the frozen task grant and transfers exact bytes. After `stage_resources` has
completed its acknowledged transfer, persist a receipt through the existing
Thread service. Include schema version, consuming Thread/Work/attempt/task,
resource version and digest, and the exact original artifact identity from
`resource_origins`. Validate origin against the frozen `_continuation_artifacts`.

Use a deterministic identity from consuming attempt, task and immutable resource.
Retry of the same completed transfer reuses the receipt; changed identity fails.
Availability alone produces no receipt. Missing source, digest mismatch,
interrupted transfer or unknown final acknowledgement produces no successful
delivery receipt. Required persistence failure remains fatal. Keep file bodies,
protected paths and credentials out of public receipts.

## Projection and UI

Expose a bounded attempt-scoped historical-input projection from persisted
receipts. Use the existing API and source presentation mechanisms. Show source
file name, exact historical version and delivery status under the instruction's
execution details. Keep existing product-reference sources and upload range
receipts unchanged. Do not attach attempt-level delivery to a particular product
as a proven derivation edge. State that delivery does not certify full-file
analysis or current Authority evidence. Refresh rebuilds from durable records.

## Verification

First reproduce the missing receipt with an acknowledged historical transfer.
Then verify successful and repeated transfer, no-open availability, missing or
changed source, cross-Work and cross-attempt rejection, interrupted transfer and
persistence failure. Use actual PostgreSQL for durable/idempotent recovery.
Check the App projection with duplicate and out-of-order receipt delivery.

After focused tests, rebuild with `make capstone-local-rebuild`. Run a real
two-instruction task and independently download the old and new products. Reuse
the existing Vivaldi tab to inspect receipts and refresh restoration. Record
timing and model/tool counts. No CI without fresh explicit user approval.

## Explicit limits

This slice records file delivery. Product derivation, whole-file processing
coverage, generic host file monitoring, cancellation/restart acceptance and
remote scale acceptance require their own evidence. No Kernel or Authority
semantics change. Preserve all pre-existing closeout edits and recovery refs.
