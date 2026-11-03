# Capacity recovery audit — 2026-11-02

## Scope and result

The local summer task stopped at `provider_relay_task_requests: 17 > 16`.
The failed attempt is `attempt_6e437de48d8a3628` in
`thr_abe1ff30d63e4efbf93b`. Its last model turn issued about 28 gateway calls
in parallel. Model and gateway calls shared the same relay slots. In debug
mode, the seventeenth simultaneous call revoked the task.

This was a scheduling defect. Sixteen was an in-flight connection bound, not
a task call budget. Saved evidence is under the ignored
`runs/capacity-audit-20261102/`. No historical business request was replayed.

## Applied corrections

| Boundary | Protected resource | Applied behavior |
| --- | --- | --- |
| Provider relay | Model connections and relay memory | Wait for a slot; recheck task grant and deadline while waiting. |
| Gateway relay | Gateway connections and backend load | Separate from model slots; queue with concurrency four, as requested for gateway integration. |
| Provider stream completion | Occupied connection slots | Release after the SSE completion marker, even if the upstream socket stays open. |
| MCP total call count | Explicit operator task budget | Default zero disables the total-call ceiling. A configured positive budget still applies. Call receipts remain mandatory. |
| Single RPC batch | Parser and request memory | Check the existing batch limit of 128 before execution. Return actual, limit, `executed=false`, and a split-batch correction. Keep the task grant. |
| Soft context, preview and cache windows | Bounded working memory | Allow existing pagination, preview, trimming and completed-record eviction in normal and debug modes. |
| Hard per-call validation | Invalid input or oversized messages | Reject that call and let the SDK repair it. Debug emits bounded diagnostics without aborting the next model turn. |
| Required receipt and product persistence | Replay protection and durable outputs | Keep failure fatal. A missing required save is not successful execution. |

The gateway concurrency value is based on the existing integration instruction.
This change does not claim that all other numeric defaults have measured sizing
evidence. It does not increase database query time budgets or invent business
routes and tool names.

## One effective capacity contract

`configs/runtime/application-capacity.json` owns numeric defaults and operator
overrides. `configs/runtime/capacity-policy.json` classifies all 171 dimensions
once, with scope, unit, protected resource, abnormal condition, recovery policy
and a sizing review flag. Numeric values are not copied into the policy file.

Before the first model call, the task context lists every model-visible effective
limit. Its full `.runtime-capacity.json` includes all dimensions and the accepted
task deadline. The selected model profile supplies its actual context and output
windows and compression threshold. The application fallback is not presented as
the selected model's window. The file contains no credentials and is excluded
from generated product publication. Host validation uses protected configuration.

The model receives these distinctions explicitly:

- Concurrent requests queue; concurrency is not a total-call or turn ceiling.
- MCP zero means no total-call ceiling.
- Research-controller rounds are separate from native LLM turns.
- Storage quotas, read windows and model-context budgets have separate scopes.
- A recovery recommendation describes policy; it does not prove that each
  consumer already supports automatic recovery.

Contract coverage and effective override tests fail if a dimension is omitted,
duplicated or has no unit. Python, Kernel, JavaScript and App validators agree on
zero semantics. A new Kernel profile starts from defaults, not a prior task's
partial overrides.

## Focused verification

- Python application, relay, gateway, native bridge, artifact and Kernel checks:
  279 passed, 34 skipped, 33.69 seconds. Skips are not acceptance evidence.
- All-visible contract disclosure follow-up: 12 passed.
- Gateway JavaScript checks, including capacity preflight correction: 13 passed.
- App capacity, artifact windows and direct consumers: 116 passed; type check passed.
- Managed SDK, shell, child runtime and shared JavaScript capacity checks:
  nine passed. These use local SDK fixtures, not live business data.
- Regression: 28 direct parallel gateway calls complete in both normal and debug
  modes, with maximum gateway concurrency four and an independent model slot.
- Regression: an oversized preflight is rejected before execution; a corrected
  batch succeeds with the same task grant in both modes.
- Regression: oversized native tool input is corrected on the next SDK turn.
- Regression: old frozen artifact descriptors without the later `saved_at`
  display field remain readable. Ownership, version and digest checks stay exact.

No CI was started. No complete summer task was rerun for these changes.

## Remaining sizing and architecture work

The policy inventory covers 18 groups. Its `review_needed` flag deliberately
does not imply validated capacity. The following architecture gaps remain open:

| Boundary | Current constraint | Required follow-up |
| --- | --- | --- |
| Native generated products | 64 MiB per file, 256 files | Stream products through durable storage; do not raise an in-memory limit to GB scale. Upload quotas remain separate. |
| Durable receipt and record indexes | Finite lifetime indexes | Preserve replay protection while moving old records to a durable paged index. Do not delete tombstones to recover space. |
| Thread and work history | Finite persisted collections | Separate storage growth from bounded projections and page older history. |
| Native task admission | Eight simultaneous tasks | Add durable queuing where needed; current worker admission is not proof of multi-user capacity. |
| Catalog and material projections | Some consumers still truncate | Supply explicit continuation at every incomplete read boundary. |
| Execution budgets | Deployment deadlines and research-controller round cap | Expose accepted budgets accurately; implement resumable checkpoints before claiming long-task autonomy. |

These are recorded gaps, not evidence that an arbitrary higher default would be
safe. The relay failure and soft-recovery failures above have concrete fixes and
regression coverage. System-wide adequacy still requires workload and memory
measurements for the remaining consumers.
