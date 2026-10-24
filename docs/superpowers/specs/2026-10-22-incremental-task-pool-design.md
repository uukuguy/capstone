# Incremental isolated task execution

## Cohesive task scope and truthful execution groups — 2026-10-23 17:08

User correction supersedes earlier diagnostic-cutoff notes: 300 seconds is a
progress review reminder, never an automatic cancellation rule. Previous 300s
stops were operator test-watchdog cancellations, not application timeouts or
user-authorized hard deadlines. The observer now writes review-due.json and
continues; manual interruption requires actual abnormal work or user cancellation.

The 151946 sequential run was cancelled by that old watchdog at its fourth node.
Completed nodes: data audit72.434s (LLM70.699s), price73.134s (LLM69.138s),
negative price60.256s (LLM56.102s). Native tools took1.730/4.034/4.229s.
First result to next child took48.427s. Four analysis tasks were appended in one
revision after discovery, then scheduled sequentially. Price produced241 metric
rows and4 charts, hit2 script errors, attempted unsupported image reads and did
extra font/consistency checks. The fourth task spent25.188s generating a script.
This shows scope and generated-output overhead; it does not show slow numerical
execution. The saved trace reports peak concurrency1 and zero overlap.

The UI incorrectly grouped adjacent delegated nodes with equal dependencies.
It now requires actual overlapping execution intervals; incomplete timing cannot
establish parallelism. Sequential tasks retain individual rails and metrics.
Planning guidance now keeps related questions sharing calculation/interpretation
in one cohesive task. Executors reuse calculations for tables/charts and avoid
unrequested metric inventories or font diagnostics. Necessary context remains.
Advisory continuation/finish guidance no longer requires a separate quality
assessment. The whole-goal tool description now states its exclusive payload and
finish reference; no source-admission or evidence boundary was weakened.

192 execution JS tests,185 related App tests,App typecheck and10 SDK-chain tests
pass. Canonical rebuild and114 runtime hash/readiness/App checks pass: backend
c1af7c1148218a81168788fcae553fd1a7b1df39129fcbf630dd6901e60458c2,
native f00dd8c04bfd628d91f53413628899705355b97c94b361046bb72db922eb9301.
Source freeze: cohesive-grouping-hashes.json (101 files); receipt:
model-cohesive-grouping-deployment.json. Browser and next real sequential trial
remain pending. Baseline145.914727s is unchanged; no speed acceptance or parallel
comparison. Changes remain in model-decision, uncommitted; no cloud/demo change.


## Non-blocking research turns and reduced parent protocol — 2026-10-23

120343 sequential diagnostic stopped by the user-authorized300s watchdog;terminal
observed307.3s. Profile108.987s/12LLM104.772s/14852output tokens/13tools4.554s
native. Parent transition67.301s. Scope-only guidance was insufficient; no speed
acceptance or parallel trial. Diagnostic cancellation is external testing policy,
not an application failure rule.

User instruction: ordinary tool, analytical, missing-optional-input or unchecked
results should preserve the full instruction path and deliver useful work with
limitations. Unsafe ownership/authorization state or unconfirmed required
persistence remains fatal. Explicit user cancellation is respected. This does
not certify unfinished work or invent evidence. Remaining fatal-code paths still
need review; do not claim all faults are now recoverable.

Implemented optional lightweight record.assessment: one parent model submission
records and assesses a return, retaining separate checkpoints and original
issued identities. An invalid assessment preserves an already saved record.
Replay stays bound to the original execution after rerun; legacy schema unchanged.
New app-selected turnGuidance restores baseline240s draft target/60s integration
reserve as ADVICE ONLY. Parent and child see shared elapsed time; child gets
updated advice after successful tools. No cancellation, closure or scheduler
gate is derived from this guidance; tests prove post-target tasks still start.
The advisory origin is persisted across controller restore. Ordinary research
problem guidance retains related context and favors useful turn delivery.

187JS tests pass;10SDK chain tests passed before the final replay fix (rerun pending).
First build failed because new task-turn-guidance.mjs was absent from the native
Docker COPY list; fixed before model tests. Last build source then received a
replay correction and canonical rebuild47491 is active. Frozen101files in
nonblocking-turn-hashes.json. No model task active; readiness/hash verification
required before the next sequential300s diagnostic. Baseline145.914727s unchanged.


## Scope and depth, not excessive context compression — 2026-10-23

User correction: retain enough relevant context; control task scope and depth.
SDK organization guidance now explicitly retains needed definitions, caveats and
goal context. Select related versioned inputs/return slots, not unrelated sibling
results. Discovery stops when the next planning decision is supported, and does
not precompute downstream business analyses or hand-author narrative profiles via
large scripts. This is model guidance, not a proven hard scope boundary.
Vendor explore-data was read and remains unchanged. It covers structure, grain,
keys, coverage and quality, but defaults to comprehensive profiling, correlations
and follow-up suggestions. Its relevant subset is sufficient for initial discovery;
not every skill section is an assigned task. Baseline public events show direct
README/CSV reads and Python analysis, with no explicit explore-data read/invocation
found; availability does not prove use, and truncated events cannot establish
complete absence. Do not claim the baseline only called that skill.
A further baseline difference: actual-work-envelope.json records usable_draft
with240s soft target/60s integration reserve. Current lightweight execution has
no equivalent envelope. This is a scope-control difference to address separately
from cancelling capacity or truncating context, not proof of sole causation.
180JS tests pass; canonical rebuild72617 and112 runtime hash/readiness/App checks
pass. Backend ecaabce18317/native1218e1e9b497. Cleanup114259-56680 completed.
Frozen task-scope-hashes.json,receipt model-task-scope-deployment.json.
No model task active. Scope behavior and speed remain unverified after this change;
no repeat full trial or parallel run.300s diagnostic cutoff remains required.


## Task grain and research assessment correction — 2026-10-23

Completion persistence has a separate bounded budget after model return. Reuse
the existing configured task timeout for transfer, retain cancellation and lease
checks, and do not renew model execution. Regression covers transfer after
execution deadline, cancellation, and transfer-budget expiry (71 runtime/chain
tests passed). Lightweight assessment now records actual completed work with
unmet checks/outputs as limited, while preserving invalid-reference rejection
and strict legacy contracts (180 JS tests passed).

Task scope follows an independently useful outcome. Shared source files or a
common final report do not merge independent questions into one executor task.
Worker capacity belongs to the scheduler and must not alter semantic planning.
The model-facing execution contract is identical at concurrency one and three.
After returned findings, plan only the next justified task or batch.

Real trial 080526 first planned source profiling, then three independent analyses,
then report synthesis. This verifies incremental task grain in that run, not
performance acceptance. Profiling took 121.776s; price 284.964s, channel 192.475s,
renewable 342.001s. Model output and script corrections dominate the durations.
There is still no valid paired speed comparison with the 145.914727s baseline.

Pending correction, reproduced by a failing regression: a lightweight research
assessment requesting success with unchecked declared checks is rejected by the
legacy all-checks-passed gate. Record such useful work as limited with exact
unmet checks, rather than requiring another model call or recomputation. Do not
change invalid-reference rejection, native-failure identity, file admission or
legacy strict contracts. User review across turns remains the acceptance model.

Status: user accepted the execution model and incremental planning requirement.
Local candidate implementation and a small real-model protocol check passed.
Full business delivery, parallel performance and independent review remain open.
No merge or cloud/demo release has occurred.

## Accepted research-turn clarification — 2026-10-23

Each user instruction is one research turn in a continuing conversation. The user
judges analytical adequacy and may correct or extend prior results. Preserve useful
work and explain uncertainty; internal assessment is not a precision certification
or user acceptance. This supersedes automatic producer-return repair and the rule
that missing planned work can never accompany limited delivery.

A task may return incomplete findings or checks. Retain its actual files and
findings, admit only support that binds to authorized observations, and mark missing
or unsupported checks honestly. Do not retry an entire task or regenerate its
whole return automatically. The organizer may request a focused follow-up for a
specific gap necessary to the current instruction.

The goal review can choose limited. It must retain every original requirement,
identify unmet requests, cite actual assessed results and finish explicitly as
limited with stated limitations. Complete still requires fulfilled requests and
actual promised products. Do not label a missing product as delivered. A useful
partial answer may be returned for user feedback without forcing further work
until every internal check passes. Real permission, source/version, file safety,
required persistence and Authority evidence rules remain strict.

The local candidate selects new exact publications App1.18/Pack1.15/shared1.5;
old publications remain unchanged. Implementation/unit-chain verification and real
model acceptance are separate. See the current lightweight-node review and plan.

Input-selection correction: node source_refs remains a required explicit choice.
Only empty dependency/result-input arrays may be omitted. Goal-level source refs
are not inherited by executors. A missing required source is reported to the
organizer, never recovered by searching task metadata or parent directories.
This is distinct from tolerant analytical returns and does not certify per-node
OS filesystem isolation.

Synthesis-role correction (local candidate): mode is part of the executor's
assignment. An execute task investigates sources or performs new analysis. A
synthesis task composes retained results/products and formats their aggregates
into the requested response or document. It does not reopen original-input
investigations. Known original_input source grants are rejected for lightweight
synthesis before commit or restored dispatch; retained previous_product and
selected_context sources remain usable. Missing substantive work returns to the
organizer for a focused execute task. Missing optional values or incomplete checks
do not prevent saving a useful draft with stated gaps. Source refs and origins
remain explicit alongside exact paths; filenames must not be guessed. This is a
neutral role/input contract, not a domain workflow or per-node filesystem sandbox.

The organization engine retains the overall user goal, accepted result references
and unresolved requirements. It submits only the next evidence-supported task or
batch. It must not commit an unknown complete workflow before source discovery.
After accepting results it decides whether the goal is met, more work is needed,
or a precise blocker prevents completion. An empty ready queue is not completion.
Do not wait for unrelated active work when a new independent task is justified.

Every execution task, including discovery, computation, checking and synthesis,
uses the same independent subagent context. The organization engine performs
planning, acceptance and delivery decisions; it does not execute native analysis.
The current graph ledger is the durable task pool. The existing scheduler releases
ready tasks subject to dependency, grant, concurrency, cancellation and budget.
Do not add a second ledger or a fixed business workflow or branch count.

Task inputs are explicit authorized source versions and accepted result versions.
Global task/result state is read-only to executors. A child returns findings,
declared product associations, actual checks, limits and missing inputs. Only the
organization engine accepts returned values into its context through the existing
record/assess contracts. Tool traces remain diagnostic, not automatic global state.
Preserve settled definitions/results and append newly justified tasks with revise.
In the new isolated mode, revise accepts only added or changed unstarted tasks;
the host retains omitted existing definitions exactly. Explicit retrospective
changes still need the existing settled-rerun contract. Legacy revise remains a
complete-set operation. Replays retain the original submitted command identity.

Publish a new shared policy and application registration. Keep previous policies
and persisted parent-execution graphs recoverable. Enforce isolated-node selection
and remove native execution tools from the new planner's active tool set. Continue
using host-protected immutable source/result files and native child manifests.
The existing child process model is not a per-node OS filesystem sandbox; do not
claim that sibling workspace access has become impossible without implementing
and adversarially verifying that separate boundary.

Acceptance requires incremental initial discovery, result-driven task expansion,
independent contexts, actual concurrent independent tasks, explicit result
acceptance, saved final products and truthful timing versus145.914727seconds.
No runtime or performance acceptance follows from policy text alone.

## Decision-bounded discovery refinement

The132.4second discovery did full quality and grouped statistics before any
independent analysis could start. Refine the accepted incremental rule through
shared policy1.2 and Application1.15, retaining Pack1.12 unchanged. Preserve all
older exact publications. Discovery ends when evidence supports selecting the
next cohesive questions, inputs and dependencies, or identifies a concrete gap.
Inspect only the source structure, meaning and access needed for that decision.
Do not require complete profiling, normalization or downstream calculations as
universal prerequisites. A necessary full-source scan remains allowed when the
decision or safety/accuracy requirement actually needs it; make its reason clear.
Scope claims to what was inspected. Analysis tasks retain the relevant local
quality checks, so smaller discovery does not imply weaker final acceptance.

Prefer this shared guidance over a hard action/time/count gate, which cannot know
whether a general problem needs more inspection. Do not use fixed file formats,
domain stages or branch counts. Use the existing task ledger and grants. Verify
exact registration/legacy bytes offline, then rebuild and run one original-input
real trial. Measure first-task scope/time, result-driven additions, actual overlap,
delivery and errors; retain the145.914727second baseline unchanged.

The real small check045408 declared only readme-peek at9.139740seconds, accepted
its result at37.068178seconds and appended summary-write at48.066955seconds.
Both independent contexts succeeded. The310-byte,3-line summary.md was delivered
as a completed primary product and hash checked. It took126.172693seconds with
18parent/14child responses and9reference-read/finish errors. This is a protocol
check with baseline=None, not report generation or parallel speed acceptance.
The full original-input043956 run failed the overall goal at258.314437seconds:
discovery alone took132.421177seconds and the old complete-set revision interface
blocked later expansion. Its outputs and failed acceptance remain preserved.

## Research-turn scope: implementation feedback (2026-10-23)

The user judges analytical adequacy across turns. A task defines its outcome,
explicit input selections and required returns. It need not carry a new check
inventory or a detailed execution recipe. Do not add file formats, fixed chart
counts, chapter inventories or numerical sampling quotas absent user needs or
a concrete downstream consumer. Ordinary uncertainty is a limitation, not a
reason to repeat completed analysis. Host permission, version binding and safe
file persistence checks remain mandatory and do not imply analytical acceptance.

The App owns the available source catalog. Each task explicitly selects its own
inputs. The initial batch does not freeze later batches to its source subset;
new batches may select other host-authorized references. Lightweight graph root
sources are derived from node selections. Historical products can supply a
standalone synthesis task without a current-run producer dependency. These are
general task contracts; no application, domain or fixed branch count is encoded.

173 scoped JS checks pass. Real saved-product composition completed595.066225s
with a three-topic report, but remains an abnormal performance result. The next
outcome-focused candidate is building; unchanged-request sequential/parallel
comparison and integration acceptance remain open.

## Limited-result deadlock and structured returns — 2026-10-23 06:18

054012 ended FAILED885.600273s, native_continuation_no_progress. Four nodes had
finished and retained their work: audit138.309s/15LLM/15tools; price231.137s/
28LLM/28tools; flow178.191s/18LLM/18tools; renewable167.172s/16LLM/17tools.
The report node was committed but pending because all producers were assessed
limited and future-slot selection still required a second limited-acceptance
protocol. Nothing was running, then the no-progress guard ended the turn. The
900s observer auto-cancel was removed by replacing only its polling process;
this failure was not an observer cancellation.7admitted CSV/Markdown products
were downloaded; image artifacts remain in saved API events. No report from this
attempt. This is not a completed sequential benchmark or a paired comparison.

Root correction: the App selects a host-only selected_limited_inputs policy for
lightweight research. Explicitly selected current completed limited returns can
be consumed without another model-authored acceptance form. Missing selected
slots still block; stale/cancelled/failed/unknown producers are not admitted.
Canonical assessment, unmet checks and record limitations pass to the consumer,
including directly selected producer limits that the compact assignment had
omitted. Later output manifests retain them. Python sealed-handle admission
supports this protected checkpoint policy and still checks exact provenance.
Legacy fixed-quality and professional behavior stays unchanged. No check is
promoted to passed and no general output becomes Authority evidence.

Known return overhead was structural: model writes protocol JSON, then parses
and repairs it. A new child-only agent_task_return tool takes concise statements,
slots and relative file selections. Host-owned metadata is encoded and saved
atomically; the actual native submission is a producer-statement observation,
not independent analytical verification. Omitted checks remain not_run. Actual
file freezing and permission checks remain separate. Legacy returns still work.
178JS and64Python checks pass, including10actual fixed-SDK/cross-language cases.
The new fixed-SDK case uses a scripted offline provider with actual tools:3model
turns,2nativecalls (write + return), quotes/newlines round-trip; it is conformance,
not real-model acceptance. Doctor/diff checks pass.98files frozen in
task-selected-limits-return-tool-hashes.json; canonical rebuild50288 is active.
No model task is active. Last verified backend7dc8e8d7/native3d178a07.
Next: compose the failed Work's already saved outputs without reanalysis; verify
real return-tool use and report persistence. Then unchanged-request sequential
and parallel on the same corrected code. Baseline145.914727s remains unchanged.

## Return host admission repair — 2026-10-23 07:05

062221 failed501.791752s at agent_task_return start/end boundary. Native private
receipt: ValueError, reason observation_source_invalid. The SDK tool had been
added without the outer GeneralPiHost observation allowlist. This was an
implementation omission; SDK-only conformance did not cover that host boundary.
No artifacts were admitted by this attempt. The450s operator backup retained
report.html2325735bytes and key_metrics.csv46080bytes. Duplicate archive members
have identical hashes; exact files were extracted under unadmitted-recovery with
recovery-extraction.json. They are unadmitted process drafts, not Authority or
accepted delivery. Never regenerate these contents just to register them.

Host now admits agent_task_return only on an exact tracked child lease; the
parent and unknown tools remain rejected. New real-host tests reproduce the
old observation_source_invalid rejection and verify source admission. The return
tool now freezes selected safe file versions through the protected context port
BEFORE publishing its return observation. Host tests prove these files survive
a later observation rejection, without being promoted to accepted delivery.
Question/expected-output duplicates derive from purpose/declared outputs when
omitted or empty. Task source_refs remains explicit. The synthesis source-origin
veto was removed: work mode is scope guidance, host grants are the permission
boundary. Unknown sources and version/owner checks remain enforced. This
supersedes earlier candidate notes saying original_input was forbidden for all
synthesis, which incorrectly rejected needed context as a quality rule.
The engine now sees protected max_concurrency, independent/read-only contexts,
incremental/dependency scheduling and explicit return updates. It is guided to a
useful first pass, not exhaustive metric/check/presentation inventories.

178JS and148Python pass; the first broad Python run had two localhost HTTP tests
routed to a proxy(502); with NO_PROXY set for localhost the full148pass in12.01s.
Doctor/diff pass. Independent review was attempted twice but the tool router
requested unavailable gpt-6.1-luna; no reviewer ran.99files frozen in
task-return-host-admission-hashes.json; canonical rebuild99430 is active.
No model task is active. Last verified deployment923c246f/native88eb7ef6.
Next: register_recovered_report.py explicitly uploads these UNADMITTED recovered
files as new resources and requests byte-identical output copies in the same Work.
Do not silently call the backup admitted history. Then verify the real return
host/persistence path, before unchanged-request sequential/parallel comparison.
Baseline145.914727s remains unchanged; no valid completed paired comparison.

