# Live Session Checkpoint

Updated: 2026-11-17. Session remains active; stageB is not complete.

## Goal, owner and source

User goal: 完成阶段二. Branch feat/control-delegation-20261117 targets dev in
the initialized .worktrees/historical-input-receipts worktree. Canonical worklist:
docs/superpowers/plans/2026-10-16-enterprise-unified-execution.md.
StageB plan: docs/superpowers/plans/2026-11-17-control-delegation.md.
StageA completed through PR125/dev4f511d46. Rootdev is clean at that commit.

StageB implements an independent capstone-control package, strict Goal/Task
contracts and PostgreSQL state, public Agent idempotent delegation, per-Work
cross-Thread product grants, bound observations/controls, background maintenance,
saved-product verification and existing-workspace Goal panel. Goal.revision is
CAS; Delegation.goal_revision binds Goal.objective_revision. Final acceptance
is a separate user action naming exact products. StagesC/D are not active.

Latest implementation8d292962 extends expiry revocation to bound active execution;
84b789f4 adds the missing pyright package roots after a reproduced CI governance
failure. Focused gate183 backend/71App/types passed. PR126 is a draft todev.
User explicitly permits direct focused macOS CI without repeated approval.
CI43926983198 failed the now-fixed config; CI43927606440 passed84b789f4.
The deadline fix and verification docs have not yet been pushed. Latest stageB
evidence is docs/reviews/2026-11-17-control-delegation-local.md.

## Current runtime and live handles

Canonical rebuild3 source3770e892, image
34a60dea85d5c11c585c506af6e862cd300e2218d4d34ab534a7903203f67eff
passed readiness, API/three-worker image identity and scoped cache maintenance.
Rebuild4 source8d292962 completed0 in22594, log
/tmp/capstone-control-rebuild-4.log. API/three-worker identity and readiness,
scoped cache maintenance passed at image
ca5031fdaef4f12f79c083e4e169691a9f4ffa9e6e0cc5d6624cc22dcddf2c9a.
Root App5173 remains dev4f511d46; candidate App5174 uses the feature worktree.
The actual dev graph live sidecar records that temporary mixed-source state;
the committed dev register has not yet received stageB.

Candidate Vite5174: shell session97706. Browser: existing Vivaldi window355034,
App tab5174 and actualdev file control tab. Do not create more tabs.
Observers59171/65258/61200/5548 and rebuild315158/422594 completed0. Focused gate372426
completed0. Exact active operation pointers are in root
runs/control-delegation-20261117/active-operations.json. No live model trial now.

Rebuild from the feature worktree uses root deploy/local.env and root
.grid-agent/runtime/pypsa-models by explicit environment paths, plus
CAPSTONE_START_APP=0. Do not copy authentication state. Preserve rootvar/data.

## Verified evidence

Focused gate:181 backend/governance checks with disposable PostgreSQL,
71 App checks and TypeScript passed (18.40s/8.83s). Graph20 checks and doctor
passed. Root helper check_with_postgres.py --gate creates/removes an isolated
database on existing capstone-review-tests-20261113; it prints no credentials.

First real Goalgoal_d2cac0bb36baaec64a94a1c12f48f27b failed safely after one
single Work: native input snapshot missing. Stage2 stayed pending; no budget
reset or automatic retry. Fix8a89fdbf reproduced/red-greened this path.
Evidence: root runs/control-delegation-20261117/first-failed-events.json.

Successful real Goalgoal_b600ce4290e3d95cdb4dfae171f40925, source995c06a8:
- Draft Threadthr_8db6688ee693109eb582f6426010e080,
  Workwork_6c5a7185de2405c74ffb; one completed Attempt.
- Verify Threadthr_ac75f69657d6487d635fb4db19049fa6,
  Workwork_315fd5c278bf39adfd4f; one completed Attempt.
- control-draft.txt:181 bytes,
  SHA419f88114b5aadf2fdf9fc0cd9fa8a92a74253e4cca75484b91ce7f4d404b8e4.
- control-final.md:3369 bytes,
  SHA3d51f627ae820864778a20a0202101ae854265f815889ec8c956a221d7a10b60.
- Downloaded bytes, hash, size and original random marker match the final report.
  Exactly one host-qualified delegation_input_delivered binds the source.
- Goal reached delivered11 with acceptance null, then explicit Vivaldi click
  accepted12 with actorworkspace:open and exact products. Real acceptance remains
  distinct from Agent completion and Task verification.

Receipts/products/browser JSON are in root runs/control-delegation-20261117/:
real-two-stage-byte-receipt-2.json, real-accepted-goal-2.json, real-products-2/,
real-events-draft-2.json, real-events-verify-2.json, browser-accepted-goal-2.json.
Do not relabel the failed first run as success.

## Remaining acceptance and integration

Completed real probes under source3770e892:
- Browser-created restart Goalgoal_e19b58506e67d464cfdd28e3a4a0a5fa: native worker
  restarted at verified pre-admission phase boundary; API restarted afterward;
  two Threads/one completed Attempt each, original33bytes/report1846bytes and
  one input receipt match. Browser refresh and open-stage2 restore existing
  conversation/products. Explicit browser acceptance persisted with exact products
  and actorworkspace:open after rebuild4; restart-accepted-goal-3.json is saved.
- Goalgoal_dea8ead1fde03c75d11d6289313a3945 controls61200 completed0: real pause
  stopped Attempt; resume kept Work and attempts1→2; revision2 stopped old
  Thread before new one; cancel stopped new execution; all4 exact replays equal.
  controls-result-3.json and full snapshots saved. No active trial remains.
- Budget Goalgoal_d7bd3c46b320c864a587ac14dd50fbe2 paused after1 delegation and
  verified15-byte product; second Task pending with no delegation.

Real active-single deadline Goalgoal_48bb4df10d239d2f4ae6998741bf1d4a passed:
running before55-second expiry, then deadline_exhausted/one delegation/no late
delivery/no active Attempt. deadline-result-4.json is saved. Graph regenerated
after recording exact8d source/image;22 Python/3Node graph checks, doctor,
symlink and diff passed. Added Markdown links resolve; old ignored-delivery
links are absent in this worktree and are not changed. Existing root graph
live sidecar and screenshot show actualdev4f node and candidate8d source edge;
canonical dev register remains unmerged. ui-ux-pro-max network-chart guidance
and visual source-edge check applied. Node tests live in
tools/project_overview/live_snapshot.test.cjs; Python tests in same directory.

Next: finish docs/graph checkpoint commit, push final task-owned commits once,
await current-head focused macOS CI,
ready/merge PR126 into dev, rebuild actualdev and verify5173 original products,
accepted Goal, paused budget/control states and pins. Canonical graph/register
must reach actualdev. Final self-merge/source/clean receipts remain ignored.
Independent reviewer dispatch failed with Unknown model gpt-6.1-luna. Direct
source review found/fixed active expiry; do not claim independent review passed.
StageB is not complete; cloud/demo and stagesC/D are unchanged.

## Recovery and operational rules

Rootdev/source stashes are preserved, notably
2eefdda714845605f7aef5c8a450aa982770ca4f. Do not reapply the whole old stash:
stageA content is merged. Preserve other worktrees, ignored auth and user data.
No permanent branch writes without PR. GitHub uses process-scoped Clash proxy
127.0.0.1:7897; read remote state before retrying failed writes.

Reuse browser tabs. Cmd+E selects existing Capstone tabs; Cmd+L then set address
and Return with confirmed focus. Up is supported, ArrowUp is not. Native menu
indexes are short-lived. Write large Orca JSON to a temporary file and print
filtered tree/path; direct JSON parsing can fail if command output truncates.
Inspect screenshots before frontend acceptance. The real control graph remains
owned by dev; a feature snapshot alone is not integrated control alignment.
