# Live Session Checkpoint

> Updated: 2026-11-15 22:08 CST. **Session remains active — not a final handoff.**

## Current boundary

User continued capstone-app/Harness execution-chain work. Existing cancellation/restoration contract verified without runtime code changes. Current evidence branch docs/harness-cancellation-acceptance-20261115 in .worktrees/historical-input-receipts, owner shared-agent, destination dev. It will carry the report and pending final control receipts. No CI has been approved or started for this new evidence package.

## Verified facts

- Real Thread thr_2b9e9d997f6ead5256f1: tool-running cancellation reachedcancelled in observed0.548s with0.5s polling. Old attempt attempt_bd0a0ba00f1df670 retained draft.md28bytes/statuscancelled; no final.md was published.
- New instruction in same Work completed separately as attempt_5b37cb44a5b6dd72, creating new-instruction.md100bytes. No cancelled-attempt completion event or replay was observed.
- API-only restart returned ready. Ledger and both exact file sizes/SHA256 survived. Existing Vivaldi window353260 reload restored oldcancelled/newcompleted; cancelled draft preview explicitly showed已取消/模拟初稿，尚未完成.
-24 focused tests passed with actual disposable PostgreSQL, zero skips,1.49s; one existing Starlette warning. Temporary database container capstone-historical-input-tests-20261115 was stopped. Earlier20pass/4skip run is not PostgreSQL acceptance.
- Report: docs/reviews/2026-11-15-harness-cancellation-restoration.md. Ignored receipts: runs/harness-cancellation-validation-20261115/, including commands, snapshots, terminal events, postrestart-verification.json and browser preview/refresh trees/screenshots.

## Immediate next action

Finish the docs-only evidence/control commit, verify Markdown links/symlink/whitespace/doctor and graph in actual dev, then request approval for one focused macOS docs CI before push/PR creation. Existing run approvals43704515136 and43708007107 are already exhausted. Worker abnormal exit and real expired-lease recovery remain separate acceptance work; this passing slice does not justify a runtime fix.

## Baseline and recovery

Actual dev/origin/devd718050c. Previous PR117/118 implementation and control integrated; both old source branches closed. Local runtime remains verified5798dad6, API/three workers image1cd6589b0c8b6194fab93f8c0412275bcecd7cf076ebee142eba6ecd1f7a8eb1. No new build/image; only API restarted. Main/cloud/demo unchanged.

Previous final control snapshot paths/backup: runs/historical-input-validation-20261115/final-owned-paths.json and final-control-snapshot-d718050c/. Root docs/control changes include those preserved postmerge receipts plus this new verification package; do not bulk-stage or discard them. Old stashes52561c4cfdc6c1c2ad38c66b5db3706866ea9007 and69739de9cdbfdc142b65148a7c520c9b5fb17ade contain already-merged code/docs: do not blindly reapply. Preserve root var, authentication, user data and unrelated worktrees.
