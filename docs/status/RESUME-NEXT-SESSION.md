# Live Session Checkpoint

## Control persistent events — local candidate, 2026-11-17

Owner capstone-control; HTTP adapter capstone-agent. Branch
feat/control-events-20261117 at product 4db1fb1a in initialized worktree
.worktrees/historical-input-receipts. Targets actualdev a7fb27d4.
Atomic Control event rows, per-Goal sequence, scoped bounded reads and legacy
coverage gaps are implemented. No UI consumer or deployment in this package yet.

Focused gate tools/test_control_events.sh: 65 passed, no skips, 1.91 seconds.
Real disposable database capstone_control_events_20261117 uses existing test
container capstone-review-tests-20261113 at localhost25439; not application data.
PostgreSQL restart, concurrent command replay, failed event INSERT rollback,
HTTP workspace/auth/page boundaries, old binding/new revision links pass.
Scope regression checks: 125 passed, 3.92 seconds. Existing Starlette warning only.

Next: finish candidate control/graph checks; request one macOS control-events CI
run (Control, adapter, event scope, disposable PostgreSQL), then PR to dev.
No new CI approval exists. Do not push or create a PR that starts CI beforehand.
After integration, canonical actualdev rebuild and read-only events smoke precede
any deployed acceptance claim. Runtime lanes and diagnostic links follow this API.

## Prior accepted task board

PR135 tested5ad60982/macOS CI44073188596 passed, merged a7fb27d4.
Product3ff3f515. Actualdev canonical rebuild and5173 Goal/Thread navigation passed;
API/three-worker image f9fb8763; zero execution commands in browser acceptance.
Branch closed; candidate5174 stopped. Cloud/demo unchanged.
Final receipts: root ignored runs/control-workspace-design-20261117/.
Preserve task-owned receipt stash769ab633 and unrelated stash2eefdda7.
Root actualdev and current candidate have distinct sources until PR integration.
