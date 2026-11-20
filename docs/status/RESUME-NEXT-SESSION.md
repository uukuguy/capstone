# Live Session Checkpoint

Updated 2026-11-20. Active work continues on the managed enterprise execution plan.

## Mission organizer recovery candidate

Branch `fix/mission-organizer-recovery-20261120` targets `dev`. Candidate
`08ebc478` settles a saved native review on its original Control binding.
The focused run passed 86 tests. Three cases skipped the PostgreSQL-only
recovery path in the memory fixture. A follow-up run passed seven recovery
cases, including concurrent processing of the same saved receipt.
The canonical local rebuild completed and the API is ready. Next, verify
a real model review with an interruption before terminal write, then run
scoped CI and integrate through a dev PR.

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

1. Verify the Mission organizer recovery candidate with a real model review
   and the original Control binding. Preserve Authority admission and user stop.
2. Preserve the root checkout's unrelated files and other environment
   sources. Use focused development gates.

[Canonical worklist](../superpowers/plans/2026-10-16-enterprise-unified-execution.md).
