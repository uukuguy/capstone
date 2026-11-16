# Live Session Checkpoint

> Current checkpoint: Agent goal mode, 2026-11-16. Session active, not final handoff.

Work in `.worktrees/historical-input-receipts`, branch
`feat/agent-goal-mode-20261116`, destination dev. Source4792b7d8 adds strict persisted
goal state, Work snapshot compatibility and refusal of legacy mutation bypass.
87 focused tests pass;14 database-dependent tests skipped. No goal commands,
structured completion receipts, automatic continuation or App entry exist yet.
Next: stage-A Unit1 transactional controls, then receipts and continuation; follow
`docs/superpowers/plans/2026-11-16-agent-goal-mode.md`. No CI approval exists.
Actual local-dev remains4834ebe3 with persistent pins. PR124 closeout is complete;
use `runs/session-pins-investigation-20261116/delivery-receipt.json`, not the old
checkpoint below, to determine pin status. No cloud/demo change.

Root dev contains task-owned design/worklist/control drafts copied to the feature
branch for integration. Preserve them until the scoped PR is accepted; do not
restore or stage unrelated files. Recovery snapshots and exact dirty-path records:
`runs/always-on-architecture-research-20261116/`. Generated graph shows4792b7d8
connected to actual dev by verified ancestry; live pin overlay remains receipt-backed.
Control update is locally prepared, not integrated into dev. Do not report full alignment.

## Prior checkpoint retained for recovery only

> Updated: 2026-11-16 21:03. **Session remains active — not a final handoff.**

Current correction: durable workspace pins. User explicitly requires persistence.
Owner capstone-agent/capstone-app, branch fix/durable-session-pins-20261116,
destination dev, initialized historical-input-receipts worktree. Source dbdb3202;
retry and focused gate correction981ddc3d. All ten old-origin pins migrated through
the App into PostgreSQL. Both localhost and127.0.0.1 show ten pin links. API restart
preserved exact state; focused86 backend/83 App checks and272 governance checks
passed (3 governance conditions skipped). Independent review found a write-retry
defect; fixed with an intended-value replay regression. Second review passed;
final canonical rebuild47cc7638 and source hashes passed, original pins retained.
No CI approval, push, PR or merge yet.

Immediate next action: request one focused macOS CI for dev integration after
acceptance/control documentation is frozen. Preserve original browser
records and ignored runs/session-pins-investigation-20261116 evidence. No cloud,
demo or main update. Existing runtime authentication and user data remain intact.

## Previous clean closeout recovery contract

Recoverable long-task capability: accepted in PR121/00999b8a and acceptance/control PR122/2cc689af. Real fault, cancellation, versioned continuation, hash/download, refresh and independent review evidence remains in docs/reviews/2026-11-16-recoverable-long-task-local.md and runs/recoverable-long-task-20261116/. The product runtime source remains00999b8a; API/three workers use46c1b66d and native usesda6d74ad. Cloud/demo/main unchanged.

This control-tool delivery fixes the9 tracked files left after the prior claimed closeout. Owner project-control tooling; source branch fix/project-control-clean-closeout-20261116, destination dev. User explicitly approved an ignored live-state sidecar. Scope: those9 docs, renderer/template, standard-library/Node tests and their macOS docs gate. No application or runtime rebuild is needed.

Static HTML is a committed, timestamped acceptance snapshot. For actual local Git state use:
    python3 tools/render_project_overview.py --live --no-probe
This writes only runs/project-overview/live-state.js, already ignored. The same existing HTML page selects valid fresh live state and labels it; missing/stale/malformed/future data falls back to its embedded snapshot. Do not regenerate the tracked HTML after the final merge merely to record that merge's own HEAD.

Finite completion contract:
1. Scope checked locally and independently reviewed; one explicit macOS control/docs CI approval is required before PR creation or a synchronizing push.
2. After that accepted PR merges, preserve any owned drafts, fast-forward actual dev and synchronize/detach the initialized worktree; retire the merged source branch after ancestry/PR checks.
3. Refresh --live on actual dev and inspect the existing Vivaldi graph: actual dev HEAD node, product source00999b8a and exact deployment edges must remain distinct.
4. Prove both root dev and .worktrees/historical-input-receipts clean with git status --porcelain, and actual dev equal origin/dev.
5. Write exact CI/PR/merge/source/cleanliness receipts and the final commit's journal line to ignored runs/project-overview/closeout-receipt.json and closeout-journal.jsonl. Do not edit this baton, tracked JOURNAL, VERSION-CONTROL or snapshot solely to record their own final commit/merge.
6. If those receipts and current Git/PR state prove completion, no follow-up work package or CI run exists for this closeout. If not, resume only the unresolved actual condition; no timeout-driven repeated faults or task submissions.

The committed control register records this branch's owner/destination/acceptance without guessing its future merge hash. Actual branch existence, HEAD, ancestry and PR state determine lifecycle. The final self-receipt is operator evidence, not a second worklist or an Authority result.

Recovery: old pending9-file state and original probes are preserved under runs/recoverable-long-task-20261116/final-delivery/, pre-dev-integration/, pre-docs-integration/, closed-docs-branch-recovery/ and their exact stash.txt refs. Never reapply the whole old source-overlay stash; runtime changes are merged. Preserve ignored auth, user var/data, all unrelated work and all failed-observer evidence.

Browser: reuse existing Vivaldi window355034/Capstone tabs. Confirm fresh URL before reload. Cmd+E + exact set-value selects existing tabs; use Cmd+L and verify address focus before URL paste/Return. Existing signed-in/operator/browser state stays private.

Provider/Authority boundaries and evidence contracts remain unchanged. Recovery is a new explicit attempt from a durable boundary, not RAM restoration or generic exactly-once external effects.
