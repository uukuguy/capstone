# Harness reference continuity

Scope includes a later instruction in one Work, automatic Goal iterations,
and Mission task handoffs. Acceptance requires the consumer to resolve and
read the exact prior product or result under its current grant. A successful
producer, a matching reference string and a persisted conversation are
separate checks.

| Path | Observed behavior | Status |
| --- | --- | --- |
| Native Domain Pack result to a later instruction | IEEE 39 tool execution produced a result. The first Attempt ended with empty admitted result and evidence arrays. The later Attempt received the reference in history text, then the Authority returned `unknown_result` in its task workspace. | The host freezes an isolated Thread, Run and Work scope for model-free native execution. The Domain Pack verifies result and evidence content. The native host forwards the verified receipt to Harness, which stores it in the completed Attempt. The next native instruction reads receipts in its frozen history and model scope. Older workspaces use the separate verified recovery below. |
| Native Domain Pack result across worker replacement | The hosted pandapower worker used the tool service's temporary directory. The confirmed result was outside the mounted run volume. | Hosted registration uses the existing run directory for the tool workspace unless an explicit path is configured. The local source directories were saved and copied to the existing run volume. |
| Previously admitted result to native main-chain context | The plan used an empty prior-result list even when the claim carried admitted results. Structural context also used a different visibility filter from the frozen list. | The plan now uses one visible set for both paths. Covered by a regression test. |
| Older native Attempt | Its completed terminal record has no admitted references. It has a producer execution receipt and an Attempt-scoped private artifact directory. | Recovery selects a completed predecessor in the same frozen Work. The registered worker matches the exact saved receipt, verifies the source artifacts, and issues scoped read inputs without changing the old record. |
| Gateway operation receipts | Job and preparation handles were lost when the native adapter revoked its task. | The host captures issued handles, stores them in the attempt ledger, and restores grants only under the same registered connection, instance, and catalog revision. Mission carries producer coordinates to dependent tasks and reviews. |
| Gateway view receipts | A ready view could remain in a connection cache, but later native tasks had no saved grant to read it. | The adapter admits a ready manifest or a successful preparation job's declared read action. It pins the known schema, model, revision, selection and source snapshot. A successful read checks and forwards the exact view identity. A locator may grant an explicit local-view read under the same source version. |
| Tool-open Domain Pack context | A model could open a context successfully with no calculation, and the terminal receipt dropped that handle. | The Pack verifies the stored context and its revision. Work and Goal can carry the context separately from results and evidence. A Mission grant lets a dependent stage the verified context and revision in a private read workspace. |
| Mission reference delivery | The background verifier could mark a saved answer or file as verified even when a task required an issued reference. | A task can declare required authority and gateway receipt sources. Missing required receipts fail the delivery, preserve its saved answer and products for review, and prevent dependent dispatch. |
| Goal product to the next iteration | Settlement checked the proposal's products, then the continuation saved the next instruction and dropped the checked references. Input preparation could select other historical files in the Work. | Newly persisted continuations retain product references. Admission freezes completed files from the exact predecessor and checks their manifests. Historical continuations keep their existing read path. |
| Goal result to the next iteration | A real automatic continuation carried the admitted result and evidence but received no Application catalog from the native worker. The model could only find gateway and general tools. | When current publication is unavailable, continuation uses the exact completed predecessor catalog from the same Work and model selection. Memory, PostgreSQL and real automatic continuation checks pass. |
| Mission files and Authority references to a child or review | The file grant freezes the producer, artifact descriptor and digest. The delivery carried only an answer receipt and file descriptors. | Control now carries exact terminal coordinates from verified dependencies to a child and from delivered or verified tasks to a reserved review. The application resolves the receipt in the producer ledger. The Pack checks the content and stages the admitted references in an isolated read workspace. |
| Mission Domain Pack selection | A real planner selected shell because the Mission equipment catalog omitted the registered Domain Pack. The child received a catalog and still lacked an admitted domain tool. | The equipment catalog now publishes exact registered Pack versions. The native host enforces selected and denied versions, plus the resolved tool allowlist. |
| Native final reply | A separate failure receipt pointed to the answer-envelope marker count after the tool succeeded. A later live attempt produced complete answer JSON followed by tool protocol closing markers. | Formal/core answer parsing accepts the single valid two-field JSON object with redundant envelope markers or the exact observed tool trailer. Ambiguous replies still fail validation. |

The general continuation path must preserve the producing Attempt, Work,
workspace, owner, product kind and immutable version. It must authorize the
consumer before resolving content. Reuse the existing Harness admission and
the owning reader for each kind. Domain Packs and registered Authorities
retain result and evidence resolution. Product storage retains file
resolution. Text from an earlier answer supplies context and does not grant
access to a referenced object.

## Local checks

- 259 focused agent tests passed. A separate disposable PostgreSQL run
  passed 155 Goal, Mission continuation and Work tests. Ten hosted and
  Domain Pack lifecycle tests passed.
- A real Goal published `draft.md` and `decoy.md` in its first Attempt.
  The next Attempt had a single historical input receipt for `draft.md`
  and read its exact bytes. The original and final downloads matched their
  recorded digests. The final file contained the marker that appeared
  only in the original file.
- A regression check covers pausing an active Goal iteration without
  discarding its prior input references. Resume uses the same frozen
  predecessor as automatic continuation.
- After a local worker rebuild, a registered `gridctl` read of the
  original result returned the same line ranking from the mounted run
  volume. This was an operator read. The original Thread's native
  continuation still lacks the admitted read grant.
- A new model-free enterprise Thread completed two real Attempts in a
  single Work. The first ran AC power flow once. The second returned the
  same result reference after a successful branch ranking and made zero
  replacement power-flow calls. A different Work could not read that
  result in a registered tool check. Both terminal records still have
  empty typed result and evidence arrays. The reply also added a limit
  assessment without executing the limit check. This validates stored
  result access and sorting only.
- Focused regression checks cover the missing-content case and the full
  Harness route with a synthetic Authority owner in memory and PostgreSQL.
  The first Attempt commits both references. The next Attempt receives them
  in structured context. A different reference in the answer text receives
  no admission. The Domain Pack excludes missing or mismatched evidence.
- The local Compose candidate with backend image `9f89bd44…` verified
  both native model modes with real model calls. Model-free Thread
  `thr_5b6d275e17f982c14df3` and open-model Thread
  `thr_c145277b0ea73df2c25a` each committed the exact same result and
  evidence references in both Attempts. Each second Attempt ran the branch
  ranking tool and made zero replacement power-flow calls. The top line
  indices were 21, 11 and 26, with 73.37%, 67.15% and 65.73% loading.
  The replies added a limit conclusion without reading the model's limits.
  A fresh canonical rebuild with backend image `44a06b36…` retained
  the open-model Thread. Attempt `attempt_409a574337a87466` read the same
  result and evidence after worker replacement and made zero replacement
  calculations. Its formal answer and core summary both withheld a limit
  assessment and explained that the relevant limits were unavailable.
- After rebuilding `a43f2819` with backend image `aa0b05ce…`, real Goal
  `thr_90578a87fde437ac5c86` reached completed through two Attempts.
  The producer `attempt_b7af5889e9007cdc` omitted result references from
  both its answer and its next instruction. The consumer
  `attempt_091a986f1bfa3093` had two structured handles and the saved
  domain catalog in its frozen input. It read and committed the exact
  result and evidence with zero replacement power-flow calls. The local
  memory and disposable PostgreSQL verification suite passed 33 checks.
- Commit `99b79856` adds named Goal handle selection and Mission authority
  grants. Focused tests passed 388 Control and Agent checks against memory
  and disposable PostgreSQL, plus 17 Domain Pack checks. They cover
  producer identity, exact reference selection, isolated solver reads,
  rejection of an ungranted reference, and denial of write tools on a read grant.
- The real Mission `goal_4d7c17c1472b1d5bd15909c2bc8a51fe` reached
  delivered on local image `6da6ba2b…`. Task A produced the AC power-flow
  result in `attempt_026643aa364455d1`. Dependent Task B
  `attempt_e0cf08ba27238f8c` persisted the same result and evidence.
  Both organizer reviews ran the Authority branch ranking successfully.
  B and the reviews made zero replacement power-flow calls.
- The first review's direct evidence read exposed a digest mismatch after
  staging JSON. Commit `64489e1b` now writes the Authority's canonical
  bytes. A real isolated `gridctl` evidence read verified the original
  digest and linked result with that fix.
- Four Goal checks cover named selection in automatic dispatch and manual
  pause and resume with memory and a reopened PostgreSQL ledger. The live
  named Goal read both selected handles and preserved the original result
  and evidence. Its initial final reply included irrelevant context and
  revision handles in the continuation field. Terminal dispositions now
  discard that unused field. After rebuilding `64489e1b` on image
  `d49a1ce5…`, the named Goal completed in `attempt_2b3cd64c3d6cde4d`.
  It reused the exact result and original evidence with zero replacement
  power-flow calls. Three registered topology reads added separate
  evidence references for line endpoints.
- In live Goal `thr_76e9c178457d3a957cd0`, execution paused the
  in-progress consumer `attempt_bd4caa3f6380cdc2`. After the native
  worker restarted, `attempt_b2d27b67c1140626` resumed from the selected
  producer receipt, read the same result and evidence, and completed
  without replacing the computation.
- After rebuilding `70a2d97f` on image `acbfa63d…`, real Work
  `thr_0356c35b1e4952d3a264` contained model constraint evidence and no
  result reference. Its first answer omitted the handle. The next Attempt
  received that independent handle from the ledger and used `grid_evidence_get`
  successfully. Both terminal records contain the same evidence digest.

## Remaining acceptance

Each result-only continuation must make zero replacement calculation calls.

The old native host has a completed task receipt with zero saved observations.
Commit `1648b7be` reconstructs the typed handle list from the owning
Pack's verified artifacts after matching the exact stored worker receipt.
The real original Thread's receipt reproduced all three line rankings with
the same original result and evidence. The negative proof changed the call
identity and recovery rejected it. The original Thread's event cursor stayed
the same. A separate memory and PostgreSQL fixture exercised freezing the
old producer receipt for a later Attempt in the same Work.

The relay covers verified context, result and evidence handles, plus
registered gateway job, preparation and ready view handles. Model selection
has its existing frozen management record. Other owner-issued identifiers
need a registered reader and an admission contract before the relay can
transfer them. The registered issuer establishes ownership, and the grant
establishes permission.

The real local-integration gateway issued a preparation handle in
`attempt_c6630f9cedba96c0`. The next Attempt used that admitted handle
for a single source status read. The source reported `region_root_missing`
for the original operation. No second view creation took place. Focused
regressions cover native adapter restart, all three owner changes, and
Mission dependent and review grant propagation. In live Mission
`goal_5c7f4158883406be5c8cbcb63d038559`, the producer's two open requests
failed with `invalid_view_request` because the source required an exact
grid object reference. The source issued no preparation handle. The
organizer still marked the producer verified. The new delivery contract
closes this path when the plan requires a source-issued receipt. The original
run did not exercise a successful cross-Work gateway admission.

- A real two-instruction Work in `thr_96d0b341e0d34fe89754` opened IEEE 39
  in `attempt_cce011593caba12f` and saved a context-only receipt.
  `attempt_6ddddf1c57b00df5` read the dataset catalog through
  `grid_model_dataset_list` using the exact same digest. The first reply
  omitted the handle. The second Attempt did not reopen the model or run
  a calculation.
- Live Mission `goal_777b9f927ec666f51598c9eeacfcfbd0` declared a required
  gateway receipt. The real upstream returned the cached failed preparation
  and issued no usable handle. Control kept the saved answer and recorded
  `required_reference_receipt_missing`. The dependent tasks stayed pending.
- Live Mission `goal_551e5dae1b1724acda8d847e9b671091` delivered after A
  saved a preparation handle and B reused it. The frozen B Attempt
  `attempt_06be933addd421c4` and organizer review
  `attempt_mission_d9aaa46b82ebdc60cd38ae4e0a5b01b7` contain the exact
  same gateway receipt issued by `attempt_e5a6524226a1e226`. Each made
  one source status call and zero replacement view opens. The upstream
  preparation failed with `region_root_missing`. This verifies the live
  cross-Work handle handoff and source read; the source produced no ready view.
- The canonical rebuild for `b5e95f2f` ran API and all three workers
  on image `848c98645da0…`. All 17 changed runtime files matched the
  checkout. Readiness and scoped image/cache maintenance passed. A separate
  live `grid:north` probe reached the job reader once and also returned
  `region_root_missing` before the source issued a ready view.
- An explicit source-issued grid object succeeded where the regional alias
  failed. The first live run prepared a view, then found a transport defect.
  Generic Pi result validation rejected the view receipt's model revision.
  Commit `96b131ae` validates the typed source receipt in the transport and
  keeps the protected field rejection for ordinary source metadata.
- After the exact rebuild on image `e34b51eec4c4…`, real Work
  `thr_7132481de90b52f9e3d0` persisted the ready view and its executable
  graph descriptor in `attempt_aa75702f8aac8391`. The next Attempt
  `attempt_374efffbb61a56f6` read `summary_nodes` with the same admitted
  view and source version. There were zero replacement opens.
- The dedicated Harness gate passed 1,166 Agent and Control tests, 26
  Pack tests, and 14 Application tests on the local macOS checkout.
  Thirty-five conditional cases were skipped. The gate runs with disposable
  PostgreSQL and keeps the development branch out of the full product suite.
- Real Goal `thr_dcdbd391d7895b2668c8` continued from
  `attempt_cd53472aa5a45ba7` to `attempt_9830984951852596`. The first
  Attempt selected only its context receipt. The second read the original
  context with the registered dataset tool and completed the Goal.
- Real Mission `goal_99bf18dca4665624f7698461eb503c0f` delivered after its
  dependent Work and organizer review each read one page from the ready
  view. Both frozen inputs matched the producer's complete view receipt.
  Each read succeeded and neither consumer reopened the view.
- The focused run with disposable PostgreSQL passed 441 tests and skipped
  32 unavailable cases. The Pack authority and execution check passed
  26 tests. The focused gateway relay rerun passed 54 tests and checked
  ready manifests, job completion, locator outputs, wrong versions and
  another connection's grant.

The Mission file grant in `delegation_resources.py` verifies a completed
producer record and binds the saved artifact version to a consumer Work.
The analogous authority grant in `delegation_authority.py` resolves the
producer's exact terminal event and frozen owner configuration. The
receiving Pack stages the authorized immutable closure and removes it
after each read.

## Live instruction reply recovery

In Thread `thr_00da33eafdfec87fefb4`, the worker admitted the additional
power-flow instruction. The tools completed, then reply presentation
rejected the separate formal and summary envelopes. The original saved
stream restores the complete answer and summary without replacing the
calculation. Malformed supplemental content now leaves the readable formal
answer visible with a warning. The parser also repairs literal line breaks
inside the known answer-and-summary JSON object.

A separate live Work admitted its added instruction in
`attempt_62963243b9ab6d62`, ran power flow, and completed with one result and
two evidence references. Replay of both saved responses verifies that the
parser retains the formal text and the model-written summary.

The final local image `7f52be531d78…` completed a fresh live run
`attempt_b7c3aca64e1c9fae`. It admitted the queued instruction and saved
the formal answer, a separate 132-character core summary, one result and
two evidence references. The focused suite passed 268 tests.

## Enterprise answer layout and associated topology

The enterprise conversation shows one full process record below the formal
answer. The CAPSTONE header and completion time precede the core summary.
Status, duration and actions sit above the closed formal answer. The
summary and formal body use the same font size and line height. Browser
measurement confirmed that expanding the answer leaves the toolbar at the
same vertical position.

A native answer can publish a diagram from its verified Authority context.
The application reads the exact model revision through the registered
operator diagram capability without reopening the model or running a
calculation. Older completed Attempts can read their frozen diagram on
demand when the required receipt remains available. Existing work and model
selection remain intact.

Native Attempt `attempt_0269ef131b02d844` published its IEEE 39 diagram.
The original completed Attempt `attempt_97c0ed64814465e6` resolved its
saved diagram with 39 buses and 46 branches on image `f827f36f9c68…`.
The same URL from a different workspace returned 404.
## Instruction topology focus

The instruction diagram now carries a verified view layer for the saved
revision. The browser fits the area around focus elements and their terminal
buses. Fitting the full diagram remains a manual action. Opening the same
instruction again restores its focus.

Native branch endpoint reads use the saved network fact to identify the
branch. Native ranking calls store the ordered assets returned by the
registered tool. The projection confirms membership in the admitted result
and reads its loading values. A historical ranking can recover complete
arguments from a successful owner receipt for the same Attempt. It reads the
saved result through the same published ranking capability. It does not
rerun power flow. A view without a saved focus identifies itself as a full
diagram.

The original endpoint Attempt `attempt_0cb9460732a43f5f` highlighted line 11
in the browser. Changing to the full diagram and reopening the Attempt
returned to the same focus area. Focused application, agent, App and scope
checks passed with 16, 111, 202 and 123 tests respectively. The agent suite
skipped four conditional tests.

A fresh Provider session saved two separate views. Attempt
`attempt_06d8f01feef6966f` focused line 11. Attempt
`attempt_5fc947015044ad45` focused the three lines returned by the registered
loading rank in order: lines 21, 11 and 26. The saved layer carried a loading
value for each of the three lines.

The final local image `83d5c5b3edc4…` runs source `3fc01073` in the API and
all three workers. The read endpoint restored the original line 11 view and
the two original five-branch ranking views from the same saved Thread. The
new three-line view also passed the browser camera, highlight and reopen
checks.

## Completion navigation and answer summaries

A new completed instruction with a saved network layer opens the right-hand
grid tab. The App uses the admitted event data directly. A historical view
opens its tab immediately, shows loading when required and reuses a bounded
session cache.

The saved narrow loading query determines the view when it follows a broader
exploratory rank. Historical Attempts `attempt_97c0ed64814465e6` and
`attempt_4602b9986422f21a` now show just lines 21, 11 and 26. The separate
mixed-branch Attempt `attempt_e6ca56fca197e013` retains its five branches.
The local read endpoint returned the two corrected views in 1.145 s and
1.223 s on image `a1981a8ecd8a…`.

A real Provider run, `attempt_0838ef4d153159b3`, automatically selected the
grid tab, highlighted all three requested lines and made zero follow-up
diagram requests. The App rendered the model's summary as three list items,
with separate conclusion and limitation paragraphs. Browser replay of
`attempt_4602b9986422f21a` also showed exactly three highlights. The focused
App suite passed 300 tests. The focused Agent suite passed 147 tests and
the application lifecycle suite passed 16 tests.

## Dynamic instructions and workspace layout

The composer displays pending supplements as rows. It hides the empty buffer
and removes the persistent stopped row. The desktop browser measured a 56 px
single-row header, an 8 px composer inset, one composer divider and no
horizontal overflow at 1289 px. The enterprise workspace uses the original
60/40 default split. Existing resize controls still adjust and reset it.

Enter submits plain input while tool selection is locked. Keyboard
composition and Shift+Enter retain their own behavior. The default send
mode inserts a question into the active execution. Explicit interruption
settles the former Attempt and admits the replacement under the same Work
in one transaction. The replacement receives the frozen grants and the
available conversation context.

A real browser Enter submission cancelled `attempt_43e258f6a6de1c75` and
completed its successor `attempt_52103c3f68927c9c` with a separate answer.
A real inserted question stayed in `attempt_0a6af820a71bed8f` while its
registered grid tools continued. The attempt completed and answered the
inserted question. Focused checks passed 201 App tests and 119 backend
tests, with PostgreSQL enabled for the ledger cases.

## Paired answer summaries and long replies

The execution path saves the formal answer and its corresponding summary
together. If the initial model response omits the summary, the execution
asks its selected model to summarize the admitted formal answer. The
fallback has no tools. It preserves the saved answer when a summary request
fails.

The original gateway Attempt `attempt_db29bab16f9bd102` retained its
4115-character formal answer. Its original completion event had no summary.
The recovery used the stored model selection and appended a summary event
for that Attempt. It did not change the formal answer. The full expanded
answer uses the conversation viewport. User scroll input clears pending
reading-position restoration. Browser testing reached the final paragraph
with End on the conversation viewport and confirmed that the reply has
no inner scrollbar.

A fresh gateway execution, `attempt_0ccae9013f741b80`, used real tools and
saved both its 4370-character formal answer and its distinct 253-character
summary in a single completion event. Focused checks passed 211 App tests
and 81 Agent tests. Four conditional Agent tests were skipped.
