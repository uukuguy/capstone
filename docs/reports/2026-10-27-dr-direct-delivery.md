# Deep Research direct delivery

## Implementation

The existing protected graph ledger still owns admission, task scheduling,
product versions and result registration. Validated advisory returns already
settle automatically and release dependent work. This change preserves that
path and removes a redundant model request after successful finish.

The finish tool sets the pinned SDK's terminate hint only after a successful or
limited delivery commit. An awaited tool-result hook confirms the same persisted
delivery. The RPC terminal carries that delivery separately from actual model
messages. The executor accepts its summary only when it matches the previously
observed successful finish result. No model response, usage or stop reason is
fabricated. Failed finishes and blocked goals do not gain successful delivery.

The new Application 1.20 / Research Pack 1.17 / shared planning policy 1.7
publication removes obsolete instructions to record and assess every return.
It calls for useful task batches, declared known dependencies, automatic handoff,
combined review/finish and proportional local revisions. Prior publications and
their hashes remain unchanged. Default adaptive execution remains available;
Deep Research is not mandatory for ordinary answers or local modifications.

The existing execution record now shows a compact admitted-business-task summary
by default. It reports actual active tasks, completed counts and recorded gaps.
Raw calls, model requests and diagnostics remain in expandable process details.
No estimated completion percentage is generated.

## Focused verification

- 133 backend tests passed, 2 skipped (17.33s).
- 143 JavaScript/controller/SDK tests passed (1.02s).
- The pinned SDK direct-delivery regression confirms one model request, a saved
  finish, and no second model request. Executor tests reject missing, changed
  and failed finish receipts, while preserving actual accounting.
- App process tests and TypeScript pass; final aggregate count is recorded in
  the live journal after the final UI run.
- 162 App process tests passed (6.77s); 91 protected host/progress tests passed
  after the gateway discovery grant fix (3.59s).
- Canonical local rebuild/readiness passed. API and worker image:
  `sha256:6e8b897a3c92cf163a07ccc786f405597cd68a8767766facc26689fb20197d99`.
  Scoped cache receipt: `.capstone-agent/cache-maintenance-20261027-214339-85159.log`.

## Real-model acceptance

First trial failed; acceptance remains pending. A new conversation was opened in the existing Vivaldi tab:
`thr_d9ad2d9b56a91ad85a5f`. The submitted summer-peak question explicitly requests
Deep Research for this acceptance case. It asks for actual gateway coverage,
2026 gaps, historical comparisons, selected provinces, weather and typhoon
limitations, PPTX and core CSV. Do not present historical 2025 data as current
2026 data. Retain first-action, handoff, final-delivery and total wall times.
No cloud deployment or integration into dev is claimed here.

Attempt `attempt_ac1864e024486d49` ran 21:48:20–21:51:38. Its first tool started
after 2.83s. The parent performed coverage discovery before activation. The first
plan failed schema validation at21:50:58; a corrected plan committed21:51:37.
The five-node graph then failed with private reason `observation_source_invalid`.
No report was delivered. This is not a successful performance result.

The real gateway application grant adds agent_tool_search/load to the SDK menu,
but the host's child observation validator previously checked only the original
native tool list. A host regression reproduces both legitimate discoveries being
rejected. Gateway SDK setup and receipt admission now share a task-scoped grant
function. An unavailable gateway and unpublished discovery tool remain rejected.
The previous explicit-grant tests alone did not cover this actual wiring.

Second trial `attempt_4c3cddcff6804d68` / `thr_79caf54fa728b80d4a9e`
started22:15:56 and failed22:18:07 on the first child discovery call. It also
had two plan corrections (extra node fields, then an omitted producer dependency).
The grant helper's first integration used a nonexistent host gateway attribute;
production owns the gateway on `NativeTaskRunner`, retained as `host._run`.
The corrected regression uses that actual ownership and the host now reads it.
Both trials remain failed, with no report delivery or accepted speed comparison.

Startup correction: a typed `inputs[].from` already selects an exact producer
and slot. The lightweight planner now derives that scheduler dependency rather
than requiring the model to repeat it in `depends_on`. The reducer still rejects
unknown producers, undeclared slots and cycles, and exact frozen source/input
grants remain required. This removes one observed redundant planning correction.
122 controller/direct-delivery tests passed after this change (0.97s).
