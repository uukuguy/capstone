# Bounded investigation repair

Candidate code:0147f0af, following2c4c3ac7,59077bf0,0cc404af and99f10a3a.
Design approved by the user; dev integration, CI and remote deployment remain
separate. This change does not guarantee a hard investigation budget.

## Diagnosis

Original threadthr_4d2e08d5cbea2b23ac1f ended without its requested measurements.
The model expanded selected windows and inferred global absence from empty
samples. It did not repeatedly send exactly the same observed request.124 saved
gateway receipts contain no matching tool/catalog/full-argument-hash group;
this is not a full semantic-repeat audit of132 client gateway calls.

The sibling data-gateway repair guide dated2026-11-09 confirms that accurate
source replay still returns60 points. It also distinguishes bounded retrieval
from locating a nonempty record without known keys. New sample discovery is a
gateway capability, not a tool hardcoded by this Capstone patch.

## Implemented behavior

- Preserve finite instruction scope and source/evidence boundaries in lightweight
  guidance. Loaded skills do not expand the user request.
- Coalesce advisory scope reminders at the next model context after12 completed
  leaf tool callbacks by default. Configuration can change the interval.
- Count stable SDK call IDs once; use Host composition counts to exclude wrapper,
  reuse and local processing overhead. These are local tool counts, not source
  request counts. Existing request_id/span_id correlation remains separate.
- Keep a pending reminder across model errors; acknowledge it only on a successful
  assistant response. Saved tool observations and user messages remain unchanged.
- Validate and persist context_prepared/response_received checkpoints through the
  executor and application event projection. A live probe exposed the missing
  application projection, repaired in0147f0af with a failing regression test.
- Keep counters attempt-local. Durable events retain delivery history; a new
  session begins a new interval, without claiming cumulative budget recovery.

Existing execution statuses, vendor skill text, Kernel and business routing are
unchanged. Semantic progress and scope decisions remain model responsibilities.

## Verification

56 focused Node/SDK tests pass. The pinned SDK test inspects actual outgoing
messages and confirms no added user request or persisted source modification.
Retry/error and composition reuse/failure cases pass. Targeted Python receipt and
composition checks pass. Application/delegation/server/executor checks pass283
with32 environment skips; these overlap the smaller checks and must not be added
as distinct coverage counts. Four stale concurrency assertions were reproduced
on parent5f6a5d92, then updated to use the existing published eight-slot policy.

Business checks ran through new public local-dev sessions on99f10a3a:

| Independent track | Thread | Remote calls | Duration | Source comparison |
| --- | --- | --- | --- | --- |
| Exact query reference | thr_fcc8d069dbc405f6d7b4 | 2 |33.46s | All10 final time/value pairs match the20 source rows read |
| Zero-seed discovery | thr_4cc4ab034b3149cd8e68 | 6 |85.54s | All10 final time/value pairs match the60 source rows read |

The exact-reference task did not search devices or expand dates. Its source
response lacked a readable device name; the answer reports that limit rather
than inventing one. The zero-seed task used current discovery, source-backed
samples, key_ref preparation, fetch and read. Its saved answer includes the
device name with stale local-directory provenance, inferred unit basis, local
time semantics, unknown global loading and unverified source quality.
Only the exact-reference track received an explicit query_ref. The zero-seed
track received no known device/date, attachments or private historical seed.

An earlier zero-seed check on2c4c3ac7 used8 remote calls/25 model responses and
matched10 final values. These trials also use a newly published gateway sample
capability: improved results cannot be attributed solely to the reminder patch.
0147f0af changes only public receipt projection after the business checks. Its
final live checkthr_86923cee2033ea8aa691 completed13 native calls in6.23s;
the saved public events contain exactly one context_prepared/response_received
pair with the same checkpoint ID and completed count13. No gateway was called.
The earlier missing-projection probe is retained as delivery-preprojection files.

Canonical local rebuild passed. API and all three workers share backend image
f28ec483e4461822ab39758659c8875900084a17e865876113ea8d00d55030dc;
native imagef6ace2f14797ebf90dede40f2f9eb7b3febbd5753fa15c0c2aa10c16feb1b588
still has37 layers. Changed runtime file hashes match0147f0af in both roles;
the image's existing development label is not used as source proof. App code is
unchanged. After the rebuild the earlier60-row CSV downloads with the same
SHA-256, confirming retained data and artifact access. Scoped cache maintenance
uses the checked-in helper; its receipt is cache-maintenance-20261109-135005-2166.log.

Private full arguments, references, source values, saved answers and verification
receipts remain in ignored runs/local-chain-20261109/. Production keys and expected
source values were not added to runtime code or fixtures.

Real-model negative fixture controlthr_b916867af28478affe04 completed in13.38s.
It actually read the uploaded fixture and distinguished empty-page/unknown load,
timeout/unknown effects, invalid unissued reference and out-of-year samples.
It did not call a gateway or treat the fixture as Authority evidence. One summary
phrase inaccurately calls the point-count-only sample a value-bearing case;
the source fixture contains a count, not actual measurement values. Retain this
as a nonblocking semantic precision gap, not a fully passed negative gate.
This control is not a live gateway fault/empty-source test.

## Remaining scope

- A reminder is not a hard call/time/token/cost budget and does not prove long
  loops impossible. Source budget admission and semantic strategy accounting need
  separate contracts.
- Live empty-page, source-timeout, invalid-reference and out-of-partition negative
  cases remain separate acceptance items; unit/SDK checks do not replace them.
- App owns the follow-up objective_status/terminal wording inspection. A finished
  execution must not imply business acceptance; UI is outside this patch.
- The independent review agent could not start because its model was unavailable.
  Inline review is not an independent review receipt.
- Canonical dev register and overview are refreshed; graph browser inspection
  remains unavailable and is not claimed as visual acceptance.
- No CI, push, merge or intranet/cloud/demo update was performed for this patch.
  Existing unrelated dirty state in both checkouts is preserved.
