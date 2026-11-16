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

Latest implementation fix0a510e1e adds expired unbound-intent revocation,
concurrent API/worker schema locks and stable Goal selection. This checkpoint/
control draft is being committed next. Rebuild that fixed source before more
real trials. User permits direct focused macOS CI. No new CI or PR exists yet.

## Current runtime and live handles

Canonical rebuild2 source995c06a8, image
d08481461e7d4c74190f72e6b4c102eb0af321c507b610172de3bbc8b0cd1fb6
passed readiness, API/three-worker image identity and scoped cache maintenance.
Root App5173 remains dev4f511d46; candidate App5174 uses the feature worktree.
The actual dev graph live sidecar records that temporary mixed-source state;
the committed dev register has not yet received stageB.

Candidate Vite5174: shell session97706. Browser: existing Vivaldi window355034,
App tab5174 and actualdev file control tab. Do not create more tabs.
Observer59171 completed0. Rebuild2 session15394 reached completion.
Rebuild3 log: /tmp/capstone-control-rebuild-3.log. Once started, its exact source/
session is in root runs/control-delegation-20261117/active-operations.json.
Inspect that file and poll its confirmed handle before any replacement.
Do not edit package/backend source while a canonical build copies it.

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

1. Canonical rebuild3 of fixed source; readiness and same-image check. Goal2
   accepted state/products/pins must survive. No cloud/demo changes.
2. Create a fresh two-stage Goal through the existing App. Before creation start
   an observer. Restart native worker only at the durable boundary: first Task
   verified, second Task dispatching, its deterministic target Thread not yet
   admitted. Check no other active native attempts before disrupting the worker.
   Prove exactly one successor and original-byte handoff after restart.
3. Real active pause/resume/revise/cancel. Use a bounded synthetic goal-mode Task
   that saves a partial file and waits in a private tool. Confirm pause acknowledgement,
   resume keeps Work/budget, revision revokes old generation before a new Thread,
   and cancel stops new execution without deleting products.
4. Real delegation-budget stop: two phases with max_delegations1; first saves
   declared product, second never admits. Deadline/lost-binding paths have unit
   coverage; verify latest runtime deadline state as needed.
5. Browser refresh and delegated Work navigation must restore actual bound Work,
   existing conversation and products. Do not replace the conversation UI.
6. Review task-owned code, run focused gate, create dev PR and authorized focused
   macOS CI, integrate dev, rebuild actual dev and verify5173. No release/Linux
   scope. Record acceptance and exact sources in canonical worklist/register/
   graph. Final self-merge receipts stay ignored to prevent endless commit cycles.

Current fixes have passing local tests but not final runtime acceptance.
No independent stageB code review has run. Do not mark the goal complete yet.

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
