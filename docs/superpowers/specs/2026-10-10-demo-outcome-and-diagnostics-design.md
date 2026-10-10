# Demo task outcomes and failure diagnostics

> Status: High-level and written design approved on 2026-10-10. Implementation and local verification pass on main and demo baseline; remote acceptance pending.

## Purpose and immediate priority

Fix the demo failure without treating every answer-admission problem as loss of
all work. Preserve valid Authority results, identify unsupported conclusions,
and give users a confirmed cause or an explicit unknown cause.

The immediate target is the current demo baseline `ed2524f`. Local main was
`e9aca89` at investigation. A demo fix must remain portable to local main;
unrelated local features must not enter the demo incident release implicitly.

The user also requests a future demo trial/fix lane and a local-development to
cloud-dev lane, aligned at a common point before parallel work. Record this
intent only. Do not change release topology, branches, triggers or environments
in this package. Existing release and stage-isolation rules still apply.

## Verified incident and remaining uncertainty

- Request: generator N−1 checks and a severity ranking on IEEE-39.
- Thread: `thr_2e32a4cb4ec67eaf2611`.
- Attempt: `attempt_dadf4642048eef59`, accepted at 01:36 UTC on 2026-10-10.
- Event 85 reports successful `model.revision.derive` with a new context and revision.
- Event 91 reports `answer_admission_failed`.
- Offline replay of the actual successful tool events raises
  `tool identity does not match the bound model context` in
  `_verify_bound_attempt_references`. The deployed source has the same check.
- AC powerflow has a start event and no recorded completion. No complete
  generator contingency scan or ranking evidence is present for this Attempt.
- RPC can discard a tool end without standard capability details. Harness
  projections omit tool error reasons. These are verified diagnostic gaps;
  they do not establish the missing powerflow's actual cause.
- There is no evidence that missing input data caused this incident. Do not
  state that it did. Absence of an event does not establish failure to execute.
- Read-only Railway metadata confirms demo source `ed2524f`. No Provider request
  or cloud mutation was made during investigation. Recorded public events are
  retained under ignored `runs/demo-n1-debug/events.json`.

## Ownership

Authority verifies model lineage, input validity, calculation status and result
evidence. Domain Packs define task coverage and reusable domain failure meaning.
The Kernel transports neutral tool lifecycle and bounded diagnostic contracts.
The application binds these to the Attempt and selects presentation and recovery
actions. The App displays bounded projections and receives no raw artifacts,
credentials, internal paths, network objects or DataFrames.

Do not classify by question keywords, exceptions guessed from prose, or the
model's assertion that an error was caused by missing data.

## Three separate dimensions

1. Execution lifecycle: keep current completed, failed, cancelled and interrupted
   Attempt states, with existing lease, retry and persistence rules.
2. Task completion: `complete`, `partial` or `unavailable`, with independently
   supported completed work, blocked work and scope coverage.
3. Assurance: only admitted results and observations can support a conclusion.
   A task can be partial even when every retained result is valid. A finished
   model response does not prove task completion.

The task outcome is an optional additive projection on terminal events and
restored history. Existing records without it keep their current truthful
fallback. Do not reinterpret old failures as successful partial work.

The bounded `capstone-task-outcome/1` projection contains status, confirmed work,
blocked work, admitted reference links, optional domain-owned coverage and
diagnostics. Each diagnostic contains a stable code, category, stage,
confirmation (`confirmed` or `unknown`), safe reader summary, affected work
identity and an allowlisted recovery action. Correlation uses Thread/Attempt
and tool-call identities; model identity remains explicit.

Cap at 32 work entries and 32 diagnostics, 512 characters per summary and the
existing 64 KiB terminal-event payload limit. Reject invalid or oversized
documents before persistence; do not silently discard required evidence.

## Failure attribution

| Category | Required source | Allowed explanation |
| --- | --- | --- |
| Input data | Authority input validation | Name the missing/invalid field or precondition. |
| Calculation | Authority solver status | Distinguish non-convergence from a solver/runtime exception. |
| Capability | Registered contract or explicit capability response | State the unsupported operation or bounded scope. |
| Tool invocation | Typed parameter/contract error | State which call needs correction; do not blame model data. |
| Service | Confirmed connection, deadline or lease diagnostic | State interruption and whether execution outcome is known. |
| Admission | Typed lineage/reference/admission diagnostic | Distinguish foreign evidence from a host implementation defect. |
| Storage | Required result/evidence/terminal persistence diagnostic | Mark persistence failure; do not claim safely saved work. |
| Unknown | Missing or insufficient diagnostics | State that the cause is unknown and needs investigation. |

Several blockers can coexist. Preserve both an initial tool failure and a later
admission failure. Do not replace the first cause with the last exception.
Non-convergence is not automatically insufficient data or a software defect.

## Tool lifecycle diagnostics

Each observed tool start must have a terminal receipt: success, reported failure,
cancelled, interrupted, or unknown outcome. A missing receipt becomes unknown;
it must not become a fabricated tool failure or success.

Keep tool-call identity when Pi emits a nonstandard error. The neutral RPC
adapter emits a bounded failure receipt even without an Authority capability
envelope. This receipt carries no fabricated capability or Authority result.
Known tools are associated through host-owned start metadata.

Carry typed errors through Harness normalization and durable terminal/history
projections. Persist stable codes and sanitized summaries, not raw exceptions.
Private diagnostics must exclude secrets, internal endpoints, filesystem paths
and arbitrary Provider/tool output. Raw trace retention and access must be
bounded and separate from public projections.

## Derived model admission

Keep the selected base model unchanged in the Thread. A derived scenario belongs
to its calculation; it does not implicitly switch the active model or camera.

The registered pandapower Authority verifies the child context and revision,
their current-run content identities, and the lineage chain back to the exact
bound base context/revision. The application consumes that verified relationship
through a typed binding contract. A successful derive event alone is insufficient.

Reject foreign roots, missing parents, cycles, mismatched revisions, tampered
documents and incomplete identity. Bound lineage traversal must stop after 64
ancestors. Keep existing PyPSA verified-reference semantics and tests.

Results and evidence must match their verified calculation context and owner.
Do not rewrite child identities to the base revision. Result cards and topology
overlays must preserve scenario identity; omit an unsupported overlay with a
specific reason rather than attach child values to the base diagram implicitly.

## Partial results and coverage

Independently admitted results can survive failure elsewhere. Construct partial
output from those results and trusted execution receipts. Do not publish the
entire rejected model answer as a partial answer. General guidance must be
visibly separate from current-model calculation conclusions.

Domain-owned coverage for batch studies includes the confirmed requested scope,
completed scenarios, unsuccessful scenarios and unknown/unexecuted scenarios.
Counts and identities come from registered models and execution receipts.
The model cannot assert exhaustive coverage. A scenario with a confirmed solver
status can be assessed as unsuccessful; one with no terminal receipt is unknown.

A full ranking requires complete assessed scope, compatible scenario metrics
and admitted evidence. A subset ranking must say which subset it covers.
Missing coverage blocks an exhaustive ranking but does not erase baseline
calculations or independent scenario results. Reading a model or creating a
scenario alone is confirmed progress, not a completed N−1 analysis result.

Required evidence or terminal persistence failures remain fatal. Only previously
durable verified records can be displayed in that case; do not claim that this
Attempt successfully saved new partial work.

## User presentation and recovery

Show the outcome summary in the answer area: completed work, blocked objective,
confirmed cause or unknown cause, and the applicable next action. Put technical
details behind the existing run-process view. An error code alone is insufficient.

For this incident, report the confirmed revision-admission defect and separately
state that the powerflow outcome is unknown. Do not promise a severity ranking
or ask the user to supply data without an input-validation finding.

Recovery actions are `retry`, `provide_input`, `change_scope`, `wait_for_service`,
`report_issue` or `none`, selected from host/Domain Pack policy. Do not automatically
rerun an unknown prior calculation, mutation or billed Provider request. Retry
creates a new immutable Attempt and preserves all prior history.

## Verification and delivery

- Replay the incident through the same admission path on the demo baseline.
- Verify legitimate one-step and multi-step descendants with real Authority
  documents; reject foreign roots, tampering, missing parents and cycles.
- Verify typed tool errors and unstructured Pi failures retain terminal receipts,
  correlation, safe causes and no false Authority evidence.
- Verify start-without-end yields unknown, including when the model returns text.
- Verify input validation, non-convergence, timeout and admission errors remain
  distinct, and a later error preserves the earlier cause.
- Verify independent admitted work remains visible while unsupported full
  rankings and rejected answer text remain excluded.
- Verify coverage counts, subset labels and empty-result behavior.
- Verify required persistence failure remains fatal, history replay matches live
  presentation, and existing CLI stdout envelopes remain unchanged.
- Verify App desktop/mobile rendering and legacy-record fallback.
- Run focused gates, then full integration/release gates and the canonical
  current-source local rebuild before remote validation.
- Compare demo-baseline and local-main behavior without bringing unrelated
  workspace/resource features into the incident patch. Remote verification and
  any Provider execution need their applicable authorization. Follow existing
  exact-source promotion, rollback and stage-specific acceptance-tag rules.

The incident fix is not accepted until remote demo verification passes. Local
tests alone do not prove the deployed issue is resolved. Release-lane redesign
remains deferred and is not an acceptance condition for this repair.
