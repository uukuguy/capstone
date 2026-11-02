# Lightweight task nodes implementation plan

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


## Task grain and research assessment correction — 2026-10-23

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

**Goal:** Remove mechanical model work and repeated context while preserving
independent execution, evidence admission and complete delivery.

**Architecture:** A neutral compact-return adapter builds existing proposals;
the dispatcher selects it through a trusted publication flag. Compact model
projections omit recoverable duplicate lineage. The durable graph is unchanged.

**Tech Stack:** JavaScript runtime and tests; Python publication/host adapters.

Execution is inline in the existing model-decision checkout. Preserve unrelated
work. No Git index/ref, cloud or demo changes. User approved implementation.

- [x] Add failing compact-return and dispatcher tests. Implement
  `task-node-return.mjs` and integrate `general-sdk.mjs`. Test local observation
  aliases, immutable binding, numbered checks, actual selected products, rejected
  references and old return behavior. Run `node --test` on the focused fixtures.
- [x] Add a compact graph regression in `enterprise-graph-runtime.test.mjs`.
  Remove repeated lineage only from compact projections; verify exact full-state
  preservation and recoverability. Replay the saved capacity failure if available.
- [x] Register App 1.17 / Pack 1.14 / shared policy 1.4 and trusted flag. Retain
  prior catalog bytes, add the module to Docker/runtime inventory, run focused
  publication, host, consumer and image tests.
- [x] Add bounded summary windows and overview pagination in DEBUG mode, per
  user correction. Real failure-state replay preserves all 14 result refs and
  full state while reducing compact context from 72356 to 44638 characters.
- [ ] Freeze sources, canonical rebuild, verify runtime hashes/readiness and
  scoped cache cleanup. Verify a real bounded task chain and inspect returned
  files, call counts and errors before a complete full-task acceptance run.
- [ ] Record measured outcomes, update recovery and canonical control. Distinguish
  implemented, locally verified, real acceptance and deployment states.

## 2026-10-23 correction and comparison

- [x] Recovery043222 retained three corridor products but hit its diagnostic stop
  before a report. Confirm synthesis had raw-input grants and reopened analyses.
- [x] Make task mode explicit. Separate synthesis composition from execute/source
  investigation; original_input grants are not synthesis inputs. Preserve products,
  aggregate-based charting, useful drafts and exact source identities.143JS and
  29focused Python checks pass; no per-node OS isolation claim.
- [ ] Rebuild task-cohesive-synthesis-hashes.json, verify source identity/cleanup,
  and produce a saved-input report draft without reopening raw-source analysis.

- [x] Diagnose034025 failure at859.119629s: flow role validation rejected files;
  DEBUG queue saturation then aborted the whole task.15admitted CSV/Markdown files
  are downloaded; the later private archive was empty and is not retained data.
- [x] Freeze safe files independently of semantic association checks, normalize
  presentation roles conservatively, retain incomplete associations without child
  repetition, and allow explicit limited file omission. Keep truth boundaries.
- [x] Make goal coverage incremental with current-reference checks. Replace fatal
  temporary buffer fullness with bounded backpressure.140JS/74Python/6actual Linux
  process checks pass. No buffer quota increase or critical-frame dropping.
- [x] Rebuild97frozen files: backend8d791b98/native16d1e8ce,112runtime source checks,
  readiness/App HTTP and cleanup043051-90579 pass.
- [ ] Complete saved-report-recovery-20261023-043222 from real prior files and
  inspect the report/metrics. This changed continuation prompt is not a146s trial.

Accepted clarification: this is a continuing research conversation. Each user
instruction produces a useful current-turn response; the user judges adequacy and
can request revisions. Preserve uncertainty and partial work instead of enforcing
perfect task acceptance through automatic whole-return rewrites. This supersedes
the former rule that every planned product must exist before any limited delivery.

- [x] Real two-turn README check delivered5141/4123byte files in118.529/158.104s,
  exposing invented length quotas and incorrect prior-source selection. Fix granted
  source catalog and editorial scope; retained third turn52.119s preserves all4090
  body bytes while changing only its title. This is no full-report speed claim.
- [x] Stop032707 original-input diagnostic after omitted source_refs produced a
  source-less child that searched parent inputs. Keep node source_refs required;
  only depends_on/inputs default empty.135JS checks pass; no implicit grants.
- [ ] Rebuild task-explicit-source-hashes.json and verify actual source selection
  before treating any subsequent run as a valid sequential/parallel comparison.

- [x] Preserve021714 failure (289.147s, no products) and diagnose return rejection
  plus unaccepted discovery. Do not claim a completed sequential comparison.
- [x] Retain imperfect returns and safe products, omit unverified evidence, mark
  unsupported/missing checks honestly and remove automatic lightweight rewriting.
- [x] Add explicit limited whole-turn review/finish with unresolved requirements
  retained. Publish App1.18/Pack1.15/shared1.5; preserve all prior publications.
- [x] Verify135JS and137host/publication checks; one host check skips. Actual
  reducer integration retains limited results with one child and one file save.
- [ ] Rebuild95 frozen files, check deployed identity and scoped cleanup, then
  verify a real two-turn research/correction path before further full trials.

- [x] Preserve failed/cancelled full trials and the146s baseline. Verify outbound
  task traffic is blocked and probe preinstalled imports/fonts without a model.
- [x] Pass trusted runtime capabilities to independent contexts; keep unrelated
  parent context excluded. Normalize omitted lightweight empty arrays without
  granting sources or inferring dependencies.
- [x] Reproduce sequential invocation growth before parallel execution. Retain
  the015900 assignment, call metrics, actual node files and cancellation result.
- [x] Correct the isolated organizer's coding-role fallback and preserve selected
  App/Pack rules. Repair execution_ms through the worker/Thread-history boundary.
  125JS/145Python/9cross-language checks pass;169App/42resource checks also pass.
- [ ] Rebuild frozen role/projection source with concurrency1 and verify identities.
  Inspect the next real first task's scope and native/observed timings before
  continuing the full sequential original-input trial.
- [ ] After corrected sequential behavior is understood, compare concurrency3
  using the same source/model/input bytes/prompt. Record model-generated graph
  differences and actual delivery quality; no fixed domain or branch count.

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
