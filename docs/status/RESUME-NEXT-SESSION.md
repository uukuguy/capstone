# Live Session Checkpoint

Updated 2026-11-19. Active work continues on the managed enterprise execution plan.

## Current baseline

Use the `dev` checkout at `.worktrees/dev-integration-152`. PR #162 merged at
`561df5ee`. The authenticated Pi status read can use a retained native terminal
receipt when no live record exists. It validates the task and executor identity
from the stored request and checks the request hash. The worker checks the frozen
parent Attempt. A read does not start execution or rebuild a live event cursor.

The configured Provider and tools completed test Attempt
`attempt_fff6b0339cb43271` on Thread `thr_56b699ccd5589b8087d7`.
The real executor process restarted with the same configuration. The client read
the original reply and 19-byte file. Both hashes matched. The separate cross-build
check reached the executor identity boundary. Local evidence lives in
`runs/native-durable-receipt/after-restart.json`.
Scoped macOS CI 44495574558 passed. See [the version register](VERSION-CONTROL.md).

PR #160 already verified the complete path after a confirmed parent exit. The
worker appends one delivery under the original instruction after file
verification. The ledger retains the interruption.

## Next work

1. Add Goal and Mission delivery recovery through their existing review and
   acceptance contracts. Keep ordinary native delivery independent.
2. Recover Authority-backed cases through application admission and current-run
   evidence checks.
3. Preserve the root checkout's unrelated files, test data and other environment
   sources. Use the focused development gate.

[Canonical worklist](../superpowers/plans/2026-10-16-enterprise-unified-execution.md).
