# Tool execution lifecycle and queue verification

## Scope and source

Candidate branch: `feat/gateway-contract-context-reuse-20261107`, based on dev
`8da7dc76`. Design and plan are in the 2026-11-08 lifecycle documents.
Final runtime source: `b473fe0d`; focused CI preparation: `ed253613`. Backend image:
`sha256:f8956f62ae54c0f5516b2088cab7c62f316195bcd88938b96646ae8193df375d`.
No CI, push, dev integration or remote deployment is claimed.
Final source-byte checks match nineteen backend/native files; all four backend roles
are healthy on the same image. The selected gateway is connected with its contract
available. The actual dev control graph was regenerated and inspected in readable
and full views; its dev HEAD and local deployment source are separate Git nodes.

The original sixteen-call observation was a host invocation overlap, not a recorded
Authority execution peak. Its host durations ranged from 819 to 3657 ms. The old
Authority did not persist process timing; this historical gap cannot be reconstructed.

## Implemented

- Neutral Kernel owner queue, configurable default eight, rolling refill and
  contract-declared resource conflicts. No business-name scheduling.
- Source adapter budget shared by formal applications and hosted direct/composed
  calls. Opaque, resource-bound borrowed leases prevent double acquisition.
  Authority observer
  records actual process start and confirmed exit, including failure/timeout cleanup.
- Gateway dispatch budget shared by access objects/tasks in one host process.
  Host transport receipts do not assert remote source execution.
- Application leaves share one eight-slot dispatcher, including mixed direct and
  composed calls. Host-declared orchestration containers do not hold leaf slots.
- Private relay connection budgets are also eight, globally and per task. The
  packaged capacity resource remains a link to its canonical configuration.
- Validated task/call-bound receipts retained through native event normalization,
  public events and replay. Native image stages the neutral primitive and validator.
- Whole-response batch connectors, distinct batch count/capacity/observed peak,
  owner-clock durations and explicit unknown actual execution for legacy records.

## Focused checks

- App: 399 tests and TypeScript passed in the prepared gate.
- Host/delegated runtime/receipt: 201 passed, 32 environment skips, 5.81 seconds.
- Gateway relay/delegated/receipt consumer set: 129 passed, 3.34 seconds.
- Domain service: 6 passed; Authority executor: 21 passed; neutral queue: 10 passed.
- SDK consumers: 141 passed, including shared leaf dispatch. Native packaging
  and image-layer checks passed.
- Doctor and diff whitespace checks passed.
- Independent review accepted the queue/receipt/cleanup boundaries. The initial
  regex finding was retracted after source-byte and production-ID verification.

The prepared focused development gate passed locally in 55.85 seconds: 1316 tests
passed, 35 skipped, with scoped typing and package boundaries. Later relay-default
changes passed 44 direct checks; the owner-queue label passed 212 App checks/types.
The exact branch diff selects `execution-lifecycle`; 189 scope/governance checks
pass. The CI job remains unstarted and requires separate approval.

## Live acceptance

The sixteen-call real-model tests ran on `2b45bc49`. The final source adds the
reviewed partial-result no-replay correction; its source adapter and shared SDK
queue are unchanged. Final rebuild, live source directory probe and gateway
connection/contract checks pass on `b473fe0d`. The correction passed 146 focused
checks and scoped typing; the final reviewer found no remaining material blocker.

- Canonical final rebuild passed readiness, same-image API/three-worker checks,
  App reachability and scoped cache maintenance. Other deployments were unchanged.
- Sixteen real Authority metadata reads completed in 4.466 seconds with actual
  process peak eight. The ninth call started before the slowest initial call ended.
  Nineteen private owner receipts ended in `released` and survived container recreation
  on the existing worker volume.
- Real browser Thread `thr_43b3ae851174f4ea2dd4`, first attempt
  `attempt_1abd48c6a0dc63d7`: 35.874 seconds, 19 tools, zero errors, 18 public owner
  receipts. Sixteen describes formed one native turn batch. Actual process peak four
  exposed the old intermediate relay budget; it was corrected to eight.
- Continuation `attempt_3f255ae859e6dc0a`: 29.176 seconds, 20 tools, zero errors,
  sixteen fresh source reads, actual process peak eight. No numerical calculation
  or business data retrieval was requested. These are observations, not a general
  performance comparison between the two attempts.
- Saved products: first Markdown 4857 bytes, SHA256
  `e94c80fee8e2e3cbe0bd83f131b4db7038c4f82d535eeb1d710789bb36c6381d`;
  second Markdown 2929 bytes, SHA256
  `29e11eb26839acb423412c64bb70b719b28896624dd09c52d0329fff343e34e3`.
  Both downloads matched their published hashes before the successful refresh;
  the second product preview and both measured batch records restored afterward.
- The existing browser tab displays full native-turn groups. The historical
  sixteen-call batch remains actual-execution-unknown; fresh records distinguish
  capacity and observed peak. Original 324 ledger attempts were retained.

Private receipts: `.capstone-agent/execution-lifecycle-20261108/` in the root
checkout. Native packaging omissions, layer-depth failure and failed replacement
container conflicts were corrected without removing persistent volumes. The omitted
native event bridge was reproduced by a failing host test and fixed before acceptance.

## Explicit boundaries

Budgets belong to execution owners, not a distributed fleet semaphore. Separate
worker replicas do not share an in-memory queue. Formal and hosted source paths
share their adapter's process budget, not a distributed coordinator.
Gateway metadata preparation and exact-contract publication reads are outside the
source-call dispatch budget. Transport cancellation does not prove that a remote
source stopped. Active local Authority work retains its slot until process exit or
timeout; transport-disconnect cancellation is not a new Authority cancellation API.
No global source-concurrency or performance acceptance is claimed from host traces.
