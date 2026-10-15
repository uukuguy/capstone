# PyPSA runtime follow-up verification — 2026-10-15

The two runtime findings from the [earlier handoff verification](2026-10-15-pypsa-handoff-verification.md)
are resolved on candidate `c638e0992e49d300e760e89d07aff63ef6eca1c5`:

- Operation projections now complete for baseline and derived models, with the
  correct model revision and verified evidence.
- AC validation uses the saved generator dispatch. Independent checks of the
  actual AC branch flows confirm the expected non-slack generation, including
  the third-snapshot 10 MW increase at southern-backup.

One arithmetic discrepancy remains in the model's final comparison text. It is
recorded below. This report accepts the tested runtime paths, not every generated
sentence or every PyPSA workflow.

## Candidate identity and isolation

| Role | Source | Image and platform |
| --- | --- | --- |
| API, pandapower worker, PyPSA worker | `c638e0992e49d300e760e89d07aff63ef6eca1c5` | Same image `sha256:8b57999259546c0da8712fb807e4a165d28273cacb98329e8f82d94a4c01aa30`, `linux/amd64` |
| App | `e2eaee2403cb6d780b3f7564da86e0d083890673` | `sha256:783efaf71898639fbfd6c4c33b272f4f977003f027a60ac5a1ba278c50c8eaf9`, `linux/amd64` |

The separate Compose project is `capstone-regional-residual-check`, on port
`29375`, with fresh volumes. The old handoff-check volumes and Thread data were
preserved. Backend identity was checked before submitting a Provider request.
The reused App has a different source; no same-source claim covers it.

Execution used AMD64 images under Docker emulation on Apple ARM. The Provider
was `openai`, model `deepseek-flash`, through the configured custom Chat
Completions endpoint. Credentials stayed in worker configuration. No credential
or endpoint value is included here.

The delivered `e2eaee2` artifact was not replaced. The user service on `19173`
and cloud deployments were not changed. This was a separate runtime candidate,
not a rebuilt offline distribution.

## Repair and deterministic verification

The AC repair writes the saved schedule to `generators_t.p_set`, which installed
PyPSA 1.3.0 reads before power flow. Writing `generators_t.p` had written an
output that power flow then replaced. The saved dispatch reference, source
model, immutable storage and evidence contracts are unchanged.

A real three-snapshot regional regression first failed, then passed after the
repair. It observes actual PyPSA power-flow output: non-slack generators follow
the saved schedule; the slack generator differs only by calculated transmission
losses. It also checks the southern-backup increment and preservation of the
baseline model. Wrong-model and tampered dispatch references are rejected before
power flow.

AC validation currently restores Generator schedules only. Store, StorageUnit,
Link and Process models now return `unsupported_dispatch_components` before
power flow and produce no successful AC artifact. Tests first reproduced the
missing rejection for all four component types. Their actual optimization still
succeeds; this restriction does not disable dispatch or extend AC algorithms.
The public contract, guide and policy state this boundary.

Focused checks observed during implementation:

- Authority `test_power_operations.py`: **12 passed**.
- Domain Pack `test_operations_profile.py`: **1 passed**.
- Owned-file `git diff --check`: passed.
- Independent product review: approved before candidate construction.

The projection repair resolves each result against its verified model lineage
and uses the appropriate base or descendant revision. The live checks below
exercise the resulting public contract.

## Original conversation and explicit AC follow-up

Fresh Thread: `thr_552d053d489c612a9389`. All commands used App-default
`send_auto` and the selected `pypsa-business-cases@1.0.0` profile. Next turns used
the current ledger cursor. No instruction was retried or rewritten to force a
particular tool call.

| Turn | Instruction | Actual result | Duration |
| --- | --- | --- | --- |
| 1 | 打开区域六母线模型，检查网络结构，并求解基准情景的固定容量调度。 | Registered model checked; `operations.dispatch` is `optimal`, objective 1300. | 43.70 s |
| 2 | 沿用刚才的模型，把 central-demand 在三个时段的负荷各增加 10 MW；保留基准情景，建立增长情景模型修订。 | central-demand is 30/35/40 MW; total demand 50/60/65 MW. Baseline remains unchanged. No solve was claimed in this modeling-only turn. | 91.02 s |
| 3 | 求解增长情景，比较两次求解状态、模型运行成本目标和发电安排，说明结论的适用边界，并给出本轮证据。 | Baseline and growth dispatch both `optimal`, objectives 1300 and 1900. The answer correctly states that AC validation was not performed in this turn. | 135.48 s |
| 4 | 分别对已保存的基准和增长调度执行交流校验并比较，不重新执行调度。 | Two `operations.ac_validate` calls converge. Records confirm no new dispatch call. | 142.45 s |

Turn 4 was the separately authorized generic follow-up because the original
three turns did not automatically request AC validation. It used the saved
baseline and growth dispatch references. No further turn was sent.

The operator verified persisted results, evidence and model documents through
the Authority's public verification functions. The growth model's parent is the
baseline model. The final dispatch answer's objectives and generation schedules
match those documents:

| Generator | Baseline MW | Growth MW |
| --- | --- | --- |
| coastal-wind | 20 / 10 / 0 | 20 / 10 / 0 |
| northwest-supply | 20 / 40 / 50 | 30 / 50 / 50 |
| southern-backup | 0 / 0 / 5 | 0 / 0 / 15 |

## Operation projection evidence

All **five operation projections** are `completed`: baseline dispatch in turns
1 and 3, growth dispatch in turn 3, and the two AC results in turn 4. Each has
source Domain Pack `pypsa-power-operations`, the correct capability, and evidence
verified against that result. Checks require a projection for the producing
attempt, not merely an older successful projection of the same result.

- Baseline revision:
  `revision:sha256:062d4fbd54bc4b45f0d53a84a9739b798adeb1e71de8b678a878492b2ee538cf`.
- Growth revision:
  `revision:sha256:1526e49e97be17c457c49c646a56acc7ee92059ea3a4198a3f21934d7822ea1f`.

The 24 source-modeling projection entries without dedicated structured projectors
remain `unavailable`, outside this acceptance. Their actual status is retained
in the receipt; this report does not describe every Domain Pack projection as
supported.

## AC schedule consistency, beyond convergence

The live AC result does not publish actual generator output. The checker
therefore independently uses its signed branch active-power results and the
verified model's load, endpoint and generator data. For each non-slack generator
bus in this registered model, it estimates generation as local demand plus
outgoing `p0` minus incoming `p0`. Incoming-line losses are the omitted term;
the explicit per-bus tolerance is **0.01 MW**. This is a bounded active-power
consistency check, not an exact loss calculation or full security assessment.

Across all three snapshots, coastal-wind and southern-backup match the saved
dispatch within approximately **0.00004649 MW**, well below that tolerance. In snapshot 3,
the inferred southern-backup output changes from **4.999994834 MW** to
**14.999979337 MW**, an increase of **9.999984503 MW**. The old behavior, which
shifted the increment to the northwest slack supply, fails the same checker on
the preserved old artifacts.

The changed third-snapshot flow pattern therefore agrees with the southern
dispatch increment. Slack loss balancing remains allowed. Neither convergence
alone nor the model's prose was used as evidence that the schedule entered AC.

## Answer review and limits

The final answer correctly separates linear dispatch costs from AC validation,
states that no new dispatch was run in turn 4, and describes the Generator-only
scope and slack-loss adjustment. It does not claim voltage-limit, capacity,
stability or N−1 acceptance from convergence.

One comparison-table cell is arithmetically wrong: south-center changes from
approximately −12.5 MW to −5.0 MW in snapshot 3, but the difference cell says
`+5.000 MW`; it should say approximately **+7.500 MW**. The same cell's magnitude
change and later prose correctly say 7.5 MW. The Authority values and projection
data are correct. This model-generated arithmetic discrepancy is retained in the
receipt and is not relabeled as a runtime repair failure or a fully correct
answer.

No all-profile AC correctness, all-README-sample acceptance, native-AMD64 timing,
offline-package upgrade or cloud deployment is claimed. The coordinating operator
stopped the candidate successfully: zero running project containers and data
preserved. The validation script did not control its lifecycle.

## Preserved receipts

PR #28 passed required Linux and macOS CI run38723131332 and merged normally
into dev as `f300d1f375ef20af005840a60af47b5e33ea62e8`. The merged `packages/`
tree matches the tested c638e09 source. This merge does not upgrade the delivered
e2eaee2 archive or its user's installation.

The root dev checkout fast-forwarded to that merge and completed
`make capstone-local-rebuild`. API and both workers are healthy and share image
`sha256:6c616058e6432cedcb1cd628a6292921c962e4d1bb87872724119036167d2a0a`.
The canonical image label remains `development`; source identity was checked by
matching SHA256 for 1060 tracked backend files in each role to the clean f300d1f
checkout. API readiness passed. App5173 reports f300d1f, dirty=false, local-dev.
Existing data was retained; other deployment stages and user installation19173
were not changed. The root operator receipt is
`.capstone-agent/pr28-local-dev-identity.json`. The first two builds timed out
at registry authentication; the existing proxy restored access for the successful
canonical build, logged in `.capstone-agent/pr28-dev-local-rebuild-proxy.log`.

The earlier report and raw artifacts remain unchanged. New ignored evidence is
stored separately:

- `.capstone-agent/regional-residual-integration-c638e09.json`: identity,
  checkpoints, Authority checks, projection checks, AC residuals and answer review.
- `.capstone-agent/regional-residual-integration-c638e09/turn-{1,2,3,4}-records.json`:
  complete persisted attempt/tool records.
- The same directory's `turn-*-snapshot.json` and `turn-*-authority.json`:
  public projections and verified Authority documents.
- `.capstone-agent/regional-residual-candidate-c638e09/identity.json`:
  candidate operator identity receipt.
- `.capstone-agent/verify_regional_integration_candidate.py`: operator runner.

The runner checks source and platform before sending a Provider-backed turn,
requires a new receipt path, and does not start or stop the candidate. This run
had no operator-checker error.
