# Shared intent analysis and goal-based answer design

Status: draft, paused pending development-lane discussion. The user approves
the need for semantic intent analysis but now prioritizes deciding controlled
development/release policy and rejects arbitrary parallel development. This
document does not authorize implementation, cloud deployment or paid replay.

## Problem and observed implementation

Manual local-demo acceptance fails. A baseline powerflow table does not answer
a generator-outage ranking or a changed-load question. The line7 result contains
valid violations but lacks a direct conclusion and includes unrelated baseline
detail. Generic partial diagnostics do not identify the unanswered goal. A basic
introduction is long and takes 1m14s; its timing cause remains unconfirmed.

Development has modules named `request_intent.py`, `pi_intent.py`, and
`intent_runtime.py`, with routing, execution-goal and resource-selection fields.
The user clarifies that the current intent function is ordinary/professional
question routing. These fields and names do not establish the semantic intent
analysis required here. Both lanes need a distinct task-understanding contract:
user purpose, subject/scenario, requested conclusions, coverage and completion
conditions, plus response scale. Portable demo source
3e3bbfb instead has the older `turn_router.py` route decision, without the newer
intent runtime. Adding a second incompatible intent system would increase drift.

The previous correction 0287c86 / 3e3bbfb preserves evidence and optional
presentation failures. Its generic projection renderer is a safe data view;
it is not acceptance of a goal-based formal answer. Keep those safety checks.

## Recommended approach and alternatives

Add one application-owned semantic intent-analysis node and task contract to both
lanes, separate from ordinary/professional routing and execution dispatch. Reuse
existing bounded node execution and decision-validation infrastructure where
compatible; do not treat the routing node as an already implemented semantic
intent analyzer. Give each lane a bounded adapter to its execution path. Do not copy development's native Pi,
skills, input-management or multi-goal delegation features into demo incidentally.

A prompt-only change is cheaper but cannot reliably bind the requested scenario
or certify coverage. Separate demo and development implementations are easier to
start but recreate the current drift. Promoting all development features into
demo is a separate product/release decision and is outside this repair.

## Ownership and information flow

Application owns intent, bounded user context, execution selection and reader
response policy. Domain Packs own semantic object resolution, feasible analysis,
scenario interpretation, requested coverage and supported conclusion contracts.
Authorities own calculations, revisions, values and evidence. Kernel transports
neutral lifecycle, bounded context and artifacts; it gains no grid semantics.

The flow is:

1. Freeze the accepted instruction, selected object versions and history cutoff.
2. Recognize a bounded semantic task intent without business execution tools.
   Routing and resource selection consume that understanding; they do not
   substitute for it. The implementation must give the semantic node an explicit
   input, output and trace identity, even where transport/session cost is shared.
3. Resolve and validate it against application grants and published Pack
   capabilities. Clarify ambiguous objects or unsupported requested scope.
4. Execute authorized goals with the validated target and scenario requirements.
5. Evaluate each requested conclusion using current-run admitted facts and
   Pack-owned coverage. Assess unsuccessful optional work separately.
6. Compose a concise direct answer, then admit its claims and reference links.
7. Persist the required answer/evidence. Offer result cards and audit detail as
   supporting material, with optional presentation failures kept separate.

An intent decision is a proposal about what the user wants. It is not authority
truth, permission to run a tool, a proof that a capability exists, or a completion
certificate. No keyword routing fallback or question-specific answer template.

## Shared task contract

Use a versioned contract with Thread/Turn/Attempt identity, immutable request
identity, history cutoff and recognizer identity. Each goal contains:

| Field | Meaning and validation |
| --- | --- |
| goal ID and operation | Stable goal identity and registered operation class; retain existing goal dependencies. |
| target object references | Host-issued selected/current/historical objects; no invented model references. |
| subject and requested scope | Pack-resolved object kinds and explicit subset/full scope; an unspecified scope cannot become exhaustive. |
| scenario requirement | Baseline, requested change or contingency, with required resolved object/version association. |
| desired conclusion | Description, impact, limit judgement, comparison or ranking, with requested measure when supplied. |
| completion obligations | Conclusions that must be supported; Pack resolves required result kinds and coverage checks. |
| answer policy | User language, concise/standard/detailed scale and output purpose. Default concise overview when no detail is requested. |
| missing requirements | Ambiguity, missing authorized objects or capability gaps; distinguish unsupported capability from missing input data. |

Free-form user descriptions may guide semantic resolution but do not establish
an executable contract. A bus display name and simulator index must be resolved
through the Pack; do not assume bus31 means index31. A requested generator
contingency cannot be silently replaced with branch contingency. An alternative
scope needs user acceptance before execution.

Contract size, goal/reference counts and depth stay bounded. New fields have
explicit schema/version compatibility. Existing accepted decisions remain fixed
for retry. Legacy records are readable but do not retroactively obtain certified
goal coverage. Recognition failure is explicit and retryable; it cannot silently
execute a guessed interpretation.

## Result relevance, coverage and failure handling

Each admitted fact carries a goal association, model/context revision, scenario
role and result/evidence links. Packs supply typed relevance and coverage checks.
Do not associate facts merely by model name, tool order or successful-call count.

A baseline observation can support background, not a conclusion about changed
load or an outage. Comparison requires admitted facts for the relevant scenarios.
A full ranking requires verified requested coverage and a defined ordering
measure. Non-converged cases remain visible; do not drop them to claim full scope.

Evaluate goal completion independently of the historical tool error list. A
failed redundant query does not erase a supported conclusion; a successful
baseline calculation does not satisfy an uncomputed changed scenario. Mark a
failed obligation recovered only when its required evidence/coverage is actually
satisfied. Model declarations are insufficient.

The outcome says which user question is answered, which is not, the confirmed
reason and a useful next action. Unknown causes stay unknown. Raw tool messages,
private paths and credentials remain outside public answers. Detailed tool-call
diagnostics are available in the run view rather than repeated in the answer.

## Formal response and safe recovery

Retain supported conclusions even if other conclusions are rejected. Formal
response synthesis consumes only the goal contract and admitted typed facts,
with claim-level bindings validated by the application and Pack. It cannot cite
foreign or historical evidence without new current-run admission. A model may
compose prose, but it may not decide its own assurance or completion status.

If model synthesis fails, a trusted renderer uses the same Pack-owned supported
conclusion records. Generic result cards alone are insufficient for this fallback.
Where no requested conclusion is supported, say so directly and distinguish any
baseline/background observations. Never present baseline data under an implied
changed-scenario answer. Required formal-answer/evidence persistence stays fatal.

Default structure: direct conclusion, brief supporting facts, and any unresolved
requested scope with an actionable explanation. Large tables, full numerical
datasets and technical diagnostics belong in expandable result/run views.
Detailed output is used when requested or required for the task. The answer
scale affects planning too: a model/capability overview does not automatically
require a powerflow calculation. Add separate timing for intent, preparation,
model reasoning, Authority work and finalization; set latency budgets only after
measurement. Avoid another recognition call where an existing intent call can
produce the richer decision.

## Public repair and two-lane delivery

The user requires common foundational fixes to take effect in development and
demo. This includes intent contracts, completion/admission, evidence linkage,
diagnostics and response policy. There is one canonical implementation and one
shared regression suite for each common change, with application adapters where
existing feature sets differ.

Record a patch identity, dependency closure, target commit in each lane, shared
contract/module source identity and validation receipt. Port compatible changes
with dependencies; do not mechanically cherry-pick an intent feature that depends
on an absent scheduler. If adapters cannot preserve the same semantics, the
common repair remains incomplete until the shared foundation is reconciled.

Local execution remains separate: local-dev5173/API8767 and local-demo15173/
API18767. Rebuild both real entrypoints after accepted source changes. A common
repair is delivered locally only when both run the verified common semantics;
one passing branch or a passing source-only test is insufficient.

Cloud-dev and cloud-demo retain independent data, credentials, origins, release
verification and acceptance tags. Public source propagation does not authorize
simultaneous cloud deployment. Current scope remains local-only. Future release
metadata shows local-dev/local-demo/cloud-dev/cloud-demo alongside product/source
identity and common-patch acceptance. These display changes remain deferred.

The precise long-lived branch names, merge policy, CI automation and general
feature-promotion schedule require the separate two-lane discussion. This repair
establishes the common-change rule without implementing that whole workflow.

## Acceptance in both lanes

Run the same contract and product cases through both application entrypoints:

- Basic overview: concise relevant facts and published capability boundaries;
  no unrequested calculation or full inventory dump.
- Unsupported generator N−1: explicit capability boundary before irrelevant
  baseline/ranking work; proposed alternative retains the requested distinction.
- Single branch outage: direct supported impact conclusion; optional query
  failure does not hide it; no unrelated baseline table dominates the answer.
- Changed load: resolve the bus identity and verify the changed revision/result;
  baseline-only evidence cannot answer the changed-scenario question.
- Full ranking: incomplete coverage never yields an exhaustive ordering claim.
- Multi-goal request: preserve each supported conclusion and explain specific
  remaining obligations, without generic repeated partial paragraphs.
- Invalid/ambiguous intent, unknown causes, legacy retry, foreign context/result,
  reference tampering, optional display overflow and required persistence failure.
- Language/scale selection, desktop/mobile presentation and both role identities.

Use deterministic controlled model decisions and real registered Authority
execution where possible. Read actual new failed Attempts before assigning their
root causes. Paid Provider acceptance is separate and is never repeated
automatically. Passing infrastructure checks alone cannot close manual answer
acceptance. No cloud release occurs during this design/implementation scope.
