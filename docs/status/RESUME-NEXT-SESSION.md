# Live Session Checkpoint

Updated 2026-11-19. Active work continues on the managed enterprise execution plan.

## Current baseline

Use the actual `dev` checkout at `.worktrees/dev-integration-152`. PR #160
merged at `cef82ba4`. The worker can recover a completed ordinary native reply
and its files after the current owner's exit is recorded. The Attempt row lock
protects the write. Timing alone does not stop a running Attempt or change
ownership. The original interruption stays in the ledger.

The configured Provider and tools completed test Attempt
`attempt_871a3b662da37d32` on Thread `thr_bf48a7c3ef559325b08c`. A test-scoped
database trigger blocked the normal reply write and initial file publication.
Recovery returned the formal reply and published `native-delivery-proof.md`.
The 21 bytes match the expected content and receipt hash. The trigger was
removed. Local evidence lives in `runs/native-delivery-recovery/live.json`.
Scoped macOS CI 44462572461 passed. The source and runtime records are in
[the version register](VERSION-CONTROL.md).

## Next work

1. Verify a protected read-only lookup of the same completed receipt after
   native executor restart. Keep immutable binding and exact artifact bytes.
2. Add a recovery path for Goal/Mission and Authority-backed cases through
   their own delivery and evidence gates. They must retain their review,
   acceptance, and evidence admission contracts.
3. Keep the root checkout's unrelated work and test data intact. Deployment
   history for other environments is unchanged. Use focused checks for dev.

[Canonical worklist](../superpowers/plans/2026-10-16-enterprise-unified-execution.md).
