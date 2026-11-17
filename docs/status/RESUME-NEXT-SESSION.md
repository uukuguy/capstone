# Live Session Checkpoint

## Active Mission workstream, 2026-11-18

This is an active-session recovery checkpoint, not a final handoff. Worktree
`.worktrees/historical-input-receipts` now uses `feat/mission-foundation-20261118`,
based on `bc3d065b`, with destination `dev`. Foundation `2a74299b`, origin association
`018c29ad`, native bridge `64d1cc76`, equipment `b9febd28`, host grant guard
`7328a157` and composer UI `ea24f485` are committed. Durable intervention PR140
merged into `dev` at `38a9e77f`. The current source merges that accepted development
source before the Mission candidate build. Do not rebase shared work.

The equipment and Mission UI changes are committed. Native tools are registered
and unit-tested, but actual Provider execution, local rebuild,
browser acceptance and scoped CI remain pending. Equipment must narrow current
grants; unsupported equipment must fail closed. Model Mission control permits
pause/resume/cancel, not final verification or acceptance.

Native transport verification: 225 Python checks passed with 36 platform/database
skips; the focused Control/origin/native set passed 76 checks with PostgreSQL.
Two Node transport checks passed. The equipment/origin/native set passed 99 checks
with PostgreSQL after integration. Later implementation changes need their own
focused verification before acceptance. Root deployment and source remain separate.

## Historical recovery notes

The entries below describe the earlier execution-details task. They are recovery
references, not the active Mission worklist or current verification receipt.
## Earlier intervention checkpoint, before PR140 merge

This preserved root checkpoint predates accepted `dev` revision `38a9e77f`.
Its execution instructions are historical; use the active Mission section above.

User explicitly requires continuous progress through main-conversation intervention
closure and then Mission intent/planning/equipment; do not stop at intermediate commits.
Root branch feat/durable-instruction-admission-20261118 from dev c8de9924. Product
queue78ba3ff1/f5535b58, frozen capability9e97e566, native+Appc1a53f2d,
transport10051518, SDK/capacityb5b42460, continuationbc3d065b, narrow0298f557,
focused gate34686054.401backend/123scope/194App checks pass. No CI yet.

Real browser owner intervention_ui: active queue changed final artifact successfully,
refresh retained admission; stop during delivery correctly reports delivery_unknown,
pending unaffected tests covered by PG. Final explicit continuation verification ongoing.
Evidence runs/durable-instruction-admission-20261118. Do not rebuild during its task.
Latest canonical build /tmp/durable-intervention-context-rebuild.log passed image4f71d588;
an earlier source copy may include uncommitted Mission foundation while it was relocated.
Need final clean-source rebuild after browser task before claiming exact runtime source.
Dedicated disposable PG capstone-intervention-tests-20261118 on25440, trust localhost,
database capstone_intervention_tests; preserve application data. Remove test container
only after acceptance ends. Native source tests242passed32platform skipped/8Node passed.

Mission work isolated .worktrees/historical-input-receipts branch
feat/mission-foundation-20261118, foundation2a74299b. native_steering owns Control
foundation and native model bridge; backend_queue owns Mission HTTP/origin association
and equipment delegation. Shared index: parent serializes root commits; Mission agents
coordinate commits in their worktree. Do not mix unverified Mission source into root.
Root control register/HTML are candidate drafts, need final graph/browser verification.
Lightweight CI needs no separate approval; heavy tens-of-minutes CI still does.

Final local acceptance: f1c4dc57 plus focused gate;189App/types and143scope checks
pass. Final canonical rebuild exited0, API/workers imagef25c7f8a, cleanup completed.
Post-rebuild5174 original record, product entry, tab navigation and narrow screenshots
passed. No CI or merge. Next request one macOS execution-details CI (3–5 minutes)
before push/PR; do not use release/full solver gates. The root recovery files and
runs/execution-details-20261117 preserve evidence. Temporary8878 graph server can stop;
5174 remains the candidate preview. Status strip and backend admission remain pending.

## Current: execution details candidate, 2026-11-17

Implementation branch feat/execution-details-20261117 in initialized worktree
.worktrees/historical-input-receipts, target dev4e81c5f6. Product a521f020 plus
2ac777f9 mainline product-access fix and focused execution-details gate.
189 App tests/typecheck and143 scope/graph checks pass. Real saved record on5174
shows process and answer in one right tab; files stay accessible in mainline.
Refresh, tab switching, desktop/narrow screenshots checked. First canonical rebuild
passed image28239bbf; final candidate rebuild log /tmp/execution-details-final-rebuild.log.
Do not call it accepted until that command and post-rebuild read complete.
Candidate Vite session62217 on5174 and temporary graph server95959 on8878 are active.
Default5173 App retains prior product UI. Cloud/demo untouched; no new CI approval.
Independent reviewer unavailable (configured model gpt-6.1-luna); manual review only.
Next: finish rebuild/read verification, commit control records, request one macOS
execution-details CI before push/PR; integrate through dev if approved.
Durable intervention, status strip and Mission runtime work remain unimplemented.
Root docs/conversation-intervention-20261117 has preserved JOURNAL/RESUME drafts.
Earlier PR137 candidate notes below are historical: it was accepted at dev4e81c5f6.

## Control runtime views — local candidate, 2026-11-17

Owner capstone-app. feat/control-runtime-views-20261117 in initialized worktree
.worktrees/historical-input-receipts targets dev dc6ada7b. Product a85c870c plus
focus/state-label fix71f6ef6e. No CI approval exists for this package.

Task/runtime/diagnosis perspectives reuse the Control sheet and original Thread
navigation. Board DOM/selection persist; runtime current states and fixed event
prefix remain separate; diagnosis links exact recorded bindings and restores
source focus/scroll.50 per page,500 cached maximum; refresh is explicit.
Full shell, Agent event correlation, as-of reconstruction and replay are not implemented.

86 App tests/types and123 scope checks pass; existing pytest plugin warning only.
Independent reviewer could not start (configured gpt-6.1-luna unavailable twice);
manual review completed, no independent verdict claimed.

Candidate Vite5174 session89524 is running; actual5173 remains accepted App.
Root canonical backend rebuild session2599 completed; imagef99d6129, readiness,
API/three-worker identity and scoped cache maintenance passed. Backend source is
accepted dev dc6ada7b. No cloud/demo update.

Real bounded Goal goal_eaed24d1e8bd9b2e9a7518c7cd2112ef (one delegation) delivered
six events and runtime-view-check.md,124 bytes, hash
07c0a85dcca099ac386739ed4fd21eb3470411eafbec5e5d5505163aa5e44cfc.
Task verified; Goal delivered, not finally accepted. It remains as real evidence.
Thread thr_0445095546f546e174f83ac9f41c7541 / Work work_29a64bc48ee1be62efff.
Desktop/narrow, source event identity, return DOM/focus and original Thread passed.
Evidence root runs/control-runtime-views-20261117/browser.log and screenshots.

Graph/browser ancestry and layout,21 graph/scope checks,doctor,new links and
shared symlink checks pass. Three existing ignored-artifact links are absent only
in this isolated worktree; no new missing link was introduced.
Next request one macOS control-task-board CI
(App/types/direct consumers, no solver/PG) and integrate through dev PR. Rebuild
actualdev and verify its real5173 entry before claiming deployed UI acceptance.

## Prior accepted event layer

PR136 tested41db18f5, merged dc6ada7b; CI44080297410 passed135seconds.
Actualdev six old Goal scoped event reads passed with zero execution commands.
Source branch closed; final receipts root runs/control-events-20261117/closeout.json.
Preserve receipt stashes8fc1da81,769ab633 and unrelated2eefdda7.
