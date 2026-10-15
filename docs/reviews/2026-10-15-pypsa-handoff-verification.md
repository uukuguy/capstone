# PyPSA application handoff verification — 2026-10-15

The shared tool-schema defect is fixed and verified on an independent candidate.
The original regional six-bus three-turn conversation now executes baseline and
growth dispatch. Authority-verified objectives are **1300** and **1900**, both
`optimal`. This is acceptance of the handoff and dispatch path. It is not complete
acceptance of result presentation or AC-validation consistency; both have open
findings below.

## Source and isolation

- Runtime source: `28020aa24dd387f63ef6163b544b274b77ce328d`.
- API, pandapower worker and PyPSA worker use the same backend image:
  `sha256:a4d57f1619a1a11bf47e67bd15db20850ad9a43273d0cb0372b10da86e5b6d91`.
- All three roles report `linux/amd64`; execution used Docker emulation on Apple
  ARM. This is not native AMD64 performance evidence.
- Independent Compose project: `capstone-regional-handoff-check`, port `29375`,
  with separate data volumes. App assets remain source
  `7c1976659a46fdf3f19abd565a0198bb60a0b8cd`; no same-source claim covers the App.
- Real Provider configuration: `PROVIDER=openai`, `OPENAI_MODEL=deepseek-flash`,
  custom OpenAI-compatible endpoint, Chat Completions. Credentials stay in worker
  configuration and are absent from this report.
- The delivered `7c19766` archive was not replaced. The user installation on
  `19173` was not changed or tested by this verification.

Identity receipt: `.capstone-agent/regional-candidate/identity.json`.

## Reproduced defect and bounded change

The failed `7c19766` regional conversation loaded both `source` and `operations`
bindings. The application had already issued handoffs for the baseline and
derived models. Missing capability selection or an absent application grant did
not explain the failure.

The published tool schema required `handoff_ref`, but the extension supplied it
from the private application index only inside `execute`. Pi validates public
tool arguments before `execute`. A call with the model reference alone therefore
failed before injection. The old test called `execute` directly and missed that
boundary. The model instead reported missing authorization without trying
dispatch.

The standalone diagnostic first produced **1 failed, 2 passed**: public Pi
validation rejected the missing receipt, direct execution injected it correctly,
and an ungranted reference still failed internal validation. The formal test then
reproduced the same public-validation failure before implementation.

The fix changes only the shared Pi extension. When a private handoff index is
configured and the contract declares both `reference` and `handoff_ref`, the
model-facing schema omits the receipt field. The tool description states that
the runtime supplies it for application-authorized references. Internal
validation still uses the unchanged canonical contract after injection.
Authority verification and application grants are unchanged. With no handoff
index, the original public contract remains intact.

Verification commands, from `packages/pi-capability-tools`:

```sh
npm test
npm run check
```

Results: **82 passed**, syntax checks passed, and `git diff --check` passed.
Parameterized tests load all **16** actual handoff contracts: operations 6,
planning 5, sector 5. They check public validation, unchanged internal schemas,
injection, rejection of model-supplied receipts, missing authorization, malformed
receipts, wrong target/family/reference, and unchanged behavior without an index.
Other business parameters, including outage sets and predecessor dispatch
references, remain required. Independent review approved the change.

One earlier full run hit an unrelated short-timeout research-receipt test. That
test passed in isolation and the subsequent full suite passed; no research code
was changed.

## Provider-schema comparison

The installed Pi `streamSimple` transport sent the same original dispatch tool
to a loopback SSE capture server with providers `openai` and `deepseek`, API
`openai-completions`, and model ID `deepseek-flash`. Both actual wire payloads
contained identical tool schemas, including the original required receipt.
The probe used a synthetic key and made no external Provider request.

This rules out a provider-specific schema transformation as the cause of this
particular mismatch. It does not certify every OpenAI-compatible server feature.

Probe and receipt:

- `.capstone-agent/compare_regional_provider_schemas.mjs`
- `.capstone-agent/regional-dispatch-diagnostic/provider-wire-schema-comparison.json`

## Original three-turn live verification

Fresh Thread: `thr_d81d23a12360de2cd322`. All commands used App-default
`send_auto`, with the selected `pypsa-business-cases@1.0.0` profile. Each next turn
used the current ledger cursor. No failed business instruction was resubmitted.

| Turn | Original instruction | Observed result |
| --- | --- | --- |
| 1 | 打开区域六母线模型，检查网络结构，并求解基准情景的固定容量调度。 | Model open/topology/inspect/validate and `operations.dispatch` succeeded; verified `optimal`, objective 1300. |
| 2 | 沿用刚才的模型，把 central-demand 在三个时段的负荷各增加 10 MW；保留基准情景，建立增长情景模型修订。 | Immutable growth model derived from baseline; load sequence 30/35/40 MW, total demand 50/60/65 MW. Baseline preserved. No dispatch claimed in this modeling-only turn. |
| 3 | 求解增长情景，比较两次求解状态、模型运行成本目标和发电安排，说明结论的适用边界，并给出本轮证据。 | Two successful dispatch calls, objectives 1300/1900, both `optimal`; two successful AC-validation calls, both `converged`. Final answer compares cost and generation and states limits. |

The operator verified persisted results and evidence through the Authority's
public `verify_operation_result`, `verify_operation_evidence` and `verify_model`
functions. This checks stored identity and lineage; terminal completion and
answer text alone were not used as proof of solving.

Verified generation schedules, in snapshot order:

| Generator | Baseline MW | Growth MW |
| --- | --- | --- |
| coastal-wind | 20 / 10 / 0 | 20 / 10 / 0 |
| northwest-supply | 20 / 40 / 50 | 30 / 50 / 50 |
| southern-backup | 0 / 0 / 5 | 0 / 0 / 15 |

The final answer's objectives, schedules and growth-parent relationship match
the verified Authority documents. Cost increases by 600. The raw artifacts and
their references are retained in the ignored evidence directory.

## Open findings and verification limits

1. **Result presentation remains incomplete.** The first-turn baseline projection
   is `completed`, with domain Pack `pypsa-power-operations`. Third-turn dispatch
   and AC-validation projections are `unavailable`, with fallback domain Pack
   identity `operations`, despite successful verified results. The snapshot
   preserves both the first baseline projection and later unavailable entries.
   An unavailable projection is not proof that a solve did not run.
2. **AC consistency needs separate investigation.** The final answer explicitly
   reports that the third-snapshot generation increment is not reflected in the
   AC-validation flow increment pattern. Stored AC results do show approximately
   the same incremental northwest flows across all three snapshots, while linear
   dispatch assigns the final extra 10 MW to southern-backup. Both AC calculations
   converge, but convergence does not establish that they validate the saved
   optimized schedule. No complete AC consistency acceptance is claimed.
3. No full offline archive was rebuilt or promoted by this verification. The
   delivered `7c19766` package still lacks this fix. Follow-up integration,
   acceptance and a new artifact require their own source and receipts.

## Operator failure, kept separate from business results

After the first successful dispatch, the first read-only checker used the base
container `python`, which could not import `pypsa_model_authority`. The script
stopped before sending turn 2. Raw turn-1 records and snapshot had already been
saved. The checker was corrected to use
`/app/packages/pypsa-agent/.venv/bin/python`, recovered the existing result without
resending turn 1, then continued turns 2 and 3 in the same Thread.

The initial operator-error receipt is retained separately. It is neither a
Provider failure nor a failed dispatch. The coordinating operator then stopped
the candidate: zero running project containers, with data retained.

## Receipts and reproduction

All paths below are ignored operator evidence, not shipped application files:

- `.capstone-agent/regional-handoff-candidate-live.json`: checkpoint receipt,
  Authority checks, manual answer review and open findings.
- `.capstone-agent/regional-handoff-candidate-live/turn-{1,2,3}-records.json`:
  complete persisted tool and attempt records.
- `.capstone-agent/regional-handoff-candidate-live/turn-{1,2,3}-snapshot.json`:
  public snapshots and projections.
- `.capstone-agent/regional-handoff-candidate-live/turn-{1,2,3}-authority.json`:
  verified operation documents, evidence and source models.
- `.capstone-agent/regional-handoff-candidate-live-operator-failed-first.json`:
  original checker failure.
- `.capstone-agent/verify_regional_handoff_candidate.py`: operator script; it
  submits Provider-backed requests only when explicitly run against an authorized
  independent fixture. It does not start or stop that fixture.

For a separately authorized repeat, select a fresh receipt path; do not overwrite
the receipts above:

```sh
python3 .capstone-agent/verify_regional_handoff_candidate.py \
  --origin http://127.0.0.1:29375 \
  --project capstone-regional-handoff-check \
  --receipt .capstone-agent/regional-handoff-repeat.json
```
