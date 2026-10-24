# Application capacity repair

The active prerequisite is reliable delivery. Do not compare research speed
until a real uploaded-data task reaches completion and its files can be opened.

## Confirmed failure

Attempt `attempt_e14a537c0fa29ee5` completed model work in 485.115 seconds,
with 71 recorded model responses and 86 tool calls. It then failed during file
persistence. The native store imposed an additional 8 MiB aggregate output cap;
57 already saved files occupied 8,381,618 bytes. This was separate from the
available disk and the global store quota. The old failure handler cleared
artifact descriptors and deleted the workspace. Preserve this attempt as failed.

## Implemented candidate

`configs/runtime/application-capacity.json` owns application defaults. Startup
accepts strict partial `CAPSTONE_CAPACITY_JSON`, a profile file, or programmatic
initialization. Immutable snapshots have fingerprints. The API publishes safe
effective values at runtime-capacity and thread-access. The App initializes its
validators before parsing data. API/worker/native processes receive the same
JSON override. Kernel and tools accept neutral limit mappings, without importing
Application modules.

Defaults distinguish uploaded source capacity from model context and outputs:
64 GiB per uploaded file, 256 GiB per session/staging, 64 MiB per output file,
256 output files and 4 GiB private native storage. These are configuration and
admission defaults, not a claim of a completed 64 GiB load test. Chunked source
staging does not put entire uploaded files into the model prompt.

The redundant 8 MiB output aggregate cap is removed. Files above a configured
output limit fail explicitly rather than disappearing from collection. A failed
save retains verified saved descriptors and the task workspace; normal retention
cleanup removes expired workspaces. Typed capacity failures carry dimension,
actual use, configured limit, unit and phase to shared user-facing messages.

Research schemas, native frame/HTTP/context/file limits, frontend parsers,
drafts, projections and history use initialized capacity. History working sets
remain bounded and marked; their complete ledger remains available. The native
workspace tmpfs also has an explicit deployment initialization setting.

## Verification before rebuild

- App: 691 tests, types and production build passed; capacity failure display:
  106 focused tests and types passed.
- Kernel: 649 tests passed; neutral Kernel source types passed.
- Pi tools: 88 tests passed, including an actual subprocess override.
- Application backend full pass attempt: 1,648 passed, 138 skipped, one failed
  asset-equality check while canonical assets were being updated. After asset
  freeze, that exact test passed. Do not describe this as a single clean full run.
- Focused native/upload/contracts: 141 passed, 15 environment skips. Partial
  persistence and an output set above the old aggregate limit passed.
- Independent PostgreSQL projection/history tests passed; temporary databases
  were stopped. No application database was used for test fixtures.
- Actual research bridge update above the old 1/2 MiB thresholds passed under
  non-default initialization values.

## Historical acceptance retained from dev — 2026-10-18

Final source regression after entry-point repairs: 1,658 backend tests passed,
138 environment skips. Five HTTP paging guards still used static Query maxima;
real browser entry exposed list128 being rejected by an old50-item guard. All
five routes now check initialized capacity at request time. Real TestClient
checks cover128-item lists,512-item history and changed quotas after app creation.
Native file transfer/status/cancel budgets also accept initialization settings.
Quota failure during final receipt saving settles the task as failed, retaining
verified file metadata and workspace; it does not strand the running state.
The matching34-store tests and110 transport/entry tests passed. Doctor passed.

## Real local entry-point verification

The final normative rebuild is ready. API and worker use image
`sha256:a8e6c4ca4ded5b03e51be3e12c25448cc1a7063b4ef8f59f88f8ca9ad25db6ec`.
API and native executor expose the same effective capacity fingerprint
`f60650a6778f1dd62a16d0625b9966d9ca1352a3d54b1962fe76b24db15dde73`.
The loaded native server file hash matches the current persistence repair.
Protocol2 list128 succeeds. Native pandas HTML-table parsing succeeds with the
pinned lxml installation. No dev merge, cloud/demo deployment is claimed.

New Thread `thr_33f695bb5cf5541602b3`, Work `work_d2e7694243bdfae2a6a5`,
Attempt `attempt_b010901da4e0be4f` used the original short question and actual
browser uploads of README plus three CSV files. Before submission the user-facing
draft held exactly four attachments; stored file bytes and SHA match each source.
The task completed normally in350.524s with41 recorded model responses,52 total
tool calls and6 tool-call failures repaired during execution. Files saved and
downloaded normally:23files/2,705,591bytes, including a1,477,640-byte primary HTML,
175-row key-metrics CSV and9embedded PNG charts. This output total does not itself
exercise the old8MiB threshold; the explicit9MiB persistence regression does.

Downloaded HTML SHA256:
`19a18f4fdff2a5794ff6943b95b62bde459e6f3ea43576e38075fd5177bc1472`.
It opens directly as a local file, with9/9images loaded, no external resources
and no page overflow.48core values in the generated raw metrics and44matching
published CSV values pass independent source-based checks. CSV rounding tolerance
is0.000051; raw metric tolerance is0.000001. The App iframe also displays9/9images.

Compared with the same-input baseline488.375s/77responses, this first successful
trial used28.23%less time and46.75%fewer model responses. This is one trial, not a
guaranteed speedup. Preserve the earlier failed attempts as failures. A separate
short human-style follow-up asks the report to distinguish cumulative province
hours from deduplicated clock hours and to clarify missing-data energy coverage;
that revision is not included in the first-run timing comparison.

Evidence: root `outputs/research-round-efficiency/capacity-first-run.json`,
`capacity-first-run-events.json`, `capacity-upload-verification.json`,
`capacity-quality.json`, `capacity-csv-quality.json`, `capacity-report.html`
and `capacity-report-standalone.png`.

## Remaining audit items

### 2026-10-19 debug interruption candidate

The accepted debug behavior is immediate task termination at the first exceeded
runtime bound. It must not retry, trim, return a normal tool error for model
repair, or finish as a limited result. Normal mode retains graded recovery.
Set `CAPSTONE_CAPACITY_MODE=debug` at application startup, or use
`initialize_capacity(..., mode='debug')`. The mode is included in the immutable
profile fingerprint and passed to API, worker, native SDK, and tool bindings.
The normal default is `normal`; startup configuration requires a rebuild or
process restart, not a per-message switch.

The source candidate provides `observe_capacity` for soft bounds and preserves
`require_capacity` for hard admission checks. Debug errors contain dimension,
actual use, effective limit, source and location, plus `mode=debug` and
`fatal=true`. The native SDK needs an explicit abort path because its normal
tool wrapper converts thrown exceptions into retryable model observations.
An actual pinned-SDK test now checks that no later model request or tool runs
after the first debug capacity failure.

Root-owned focused checks: application initialization and research bridge,
56 passed and one environment skip. These are source checks, not deployment
acceptance or proof that every third-party capacity has been migrated.
The active inventories also include transport wait windows, App cache and
preview trims, schema validation before tool execution, and deployment resource
ceilings. Their remaining rows must stay visible until verified.

The pinned SDK's native read/bash tool observation window is separately bounded
and explicitly reports truncation; it is not a file upload cap. Its own factory
configuration needs a separate integration check before claiming all third-party
defaults can be overridden. Model context metadata must stay within the selected
Provider model's supported capacity.

Model-workspace historical identity migration still has an existing bounded
window without an omitted-count projection. Full ledger data is retained. Do not
describe the entire repository audit as closed until this is accounted for.
