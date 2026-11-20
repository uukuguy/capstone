# Live Session Checkpoint

Updated 2026-11-20. Active work continues on the managed enterprise execution plan.

## Shared task-state foundation

PR #178 merged to `dev` at `36380406`. Commit `848426b8` saves ordinary execution outcomes in versioned
Work state. New instructions bind the exact prior revision at admission.
The original messages and answers stay in the Thread ledger. User
acceptance remains undecided. The real two-instruction check passed with
the rebuilt local API and worker. See `runs/task-state-continuation/live.json`.

Commit `1a0a87b8` records structured completed items, open items, defects
and blockers in ordinary enterprise replies. It retains the prior report
and source when the next reply omits it. A real two-instruction check kept
the signed-source blocker after the user changed direction. See
`runs/task-state-continuation/business-live.json`. Commit `3750dcc4` adds
version-bound user decisions, a task-state section in the existing
conversation, and state persistence after a recorded worker exit.
PostgreSQL tests cover replay, stale revisions, restart and exact
continuation after interruption. Scoped macOS CI `44702425603` passed.
The browser confirmed acceptance against the original revision while
the missing approval form remained open.
Goal and Mission adapters and authorized cross-session handoff remain open.

## Mission organizer recovery

PR #176 merged at `01f7a07c`; scoped macOS CI `44674377200` passed.
A live model review recovered after a fault before the terminal write.
Control settled it under the original binding and kept the interruption.
See `runs/mission-organizer-recovery/live.json`. PostgreSQL cases cover
pause, cancel and concurrent receipt processing.

The task-context agreement is in the canonical worklist. Shared task
revisions and authorized cross-session handoff remain separate delivery work.

## Current baseline

PR #174 merged to dev `db141b0a`. The workbench has one instruction path
alongside Goal and Mission. The separate research rollout is closed. A real
legacy request saved the expected file and returned the ordinary result.

PR #172 merged to dev `0c6a68fc`. Mission verified the original child
answer and file after a test fault interrupted the native terminal write.
No replacement execution was admitted. See
`runs/mission-child-delivery-recovery/live.json`.

PR #170 merged to dev `6ca5d471`. The file delivery loop tries independent
files before retrying unavailable transfers. A failed Attempt with saved files
returns a partial response and keeps the files downloadable. The real model
and isolated read fault check passed; see
`runs/independent-artifact-delivery/live.json`.

Use the `dev` checkout at `.worktrees/dev-integration-152`. PR #168 merged at
`49444e8d`. The native briefing renderer tries alternate table layouts in
the same template when the original layout cannot fit. It preserves the
source rows, visible explanation, font sizes and page count. The receipt
records the adjusted layout. An unsatisfied physical fit still returns a
specific overflow diagnostic for that operation.

The exact saved content and assets from the reported benchmark session
reproduced the 3.27-inch table in a 3.25-inch frame. The repaired standard
renderer exported ten slides, validated page eight visually, and returned
a successful PDF receipt. See `runs/presentation-layout-recovery/`.
The local verification passed 95 checks and focused macOS CI 44516985397 passed.

## Next work

1. Project Goal plan and review state into the shared task contract.
   Keep execution completion and user acceptance independent.
2. Preserve the root checkout's unrelated files and other environment
   sources. Use focused development gates.

[Canonical worklist](../superpowers/plans/2026-10-16-enterprise-unified-execution.md).
