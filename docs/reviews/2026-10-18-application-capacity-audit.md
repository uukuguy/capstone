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

The normative local rebuild and the next actual browser upload/research task
remain required. No dev merge, cloud deployment or demo promotion is claimed.

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
