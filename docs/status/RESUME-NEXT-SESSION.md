# Live Session Checkpoint

Updated: 2026-11-17. Active task: fix the sidebar jumping on session selection.

## Current state

Owner capstone-app. Branch fix/session-sidebar-stability-20261117 in initialized
.worktrees/historical-input-receipts targets dev. Rootdev remains clean7531bc1f.
Prior stageB is complete through PR126/127; its final ignored receipt is
runs/control-delegation-20261117/closeout-receipt.json. Do not reopen that goal.

Existing5173 reproduced10 pinned rows becoming3 immediately after switching,
then returning to10. Pin IDs remain durable. SessionNavigation lost component-local
older-row descriptors on remount. Source501c90fd moves resolved row metadata to
the exact access-scoped session catalog and invalidates earlier history replies
on archive/delete/restore. It does not change pin authority, permissions or UI design.

Two regression tests failed first (cold-remount rows/position, stale removed-row
reply), then a concurrent-page overwrite regression failed and was fixed in
399f90f3.125 tests across10 direct App consumers and TypeScript pass;145
scope/governance checks pass. New session-navigation gate
runs only those consumers plus types and its scope test, on macOS. No solver or
release gate. Independent reviewer dispatch failed Unknown model gpt-6.1-luna;
direct source review performed; no independent pass exists.

## Live operations

Canonical candidate rebuilds63980/5024 completed0. Latest399f90f3/image731d93bf
passed readiness, API/three-worker identity and scoped cache maintenance;
/tmp/capstone-sidebar-rebuild-2.log. Candidate Vite session74642 serves5174.
Five real cold/warm switches retained10 pins/order and correct selected headings;
intermediate screenshots inspected. Root5173 still uses dev7531bc1f App;
record this temporary split accurately. No new tabs. No model trial is active.
Root ignored operation pointer: runs/session-sidebar-stability-20261117/active-operations.json.
Initial failing browser AX evidence is retained in the same directory.

## Next actions

1. Candidate browser is accepted locally. Do not interpret transient missing AX
   rows as visual failure: original root screenshot genuinely shows3; candidate
   AX9/AX0 screenshots still showed10. Concurrent overwrite has red/green proof.
2. Finish acceptance/control checkpoint, generate/re-layout and inspect graph via
   ignored live observation, using ui-ux-pro-max. Current dirty paths are task-owned
   status docs/graph/review/plan only. Verify links/symlink/diff/doctor and graph checks.
3. Commit verification/control checkpoint, push one final head, create dev PR and
   run authorized macOS session-navigation gate. CI requires no new user approval.
   Integrate, rebuild actualdev, verify real5173, original10 exact pin IDs and
   stable list. Stop only owned candidate Vite after5173 is accepted.
4. Integrate canonical final control acceptance through a finite docs PR if needed,
   refresh actualdev live graph, close verified task branches and keep both task
   worktrees clean. Final own receipts stay ignored; preserve all other work/data.

Plan: docs/superpowers/plans/2026-11-17-session-sidebar-stability.md.
Canonical worklist: docs/superpowers/plans/2026-10-16-enterprise-unified-execution.md.
GitHub uses process-scoped Clash127.0.0.1:7897. Preserve rootvar, ignored auth,
other worktrees and recovery2eefdda714845605f7aef5c8a450aa982770ca4f.
