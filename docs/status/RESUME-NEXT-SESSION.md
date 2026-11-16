# Live Session Checkpoint

> Updated: 2026-11-15 23:55 CST. **Session remains active — not a final handoff.**

## Active scope

User approved real worker-loss/lease recovery verification. Actual baseline dev/origin/devfffc881e, runtime5798dad6. Current fix branch fix/worker-interruption-products-20261115 in .worktrees/historical-input-receipts targets dev, owner capstone-agent. Product candidatef0976baf is committed; no CI approval or remote push/PR for this package.

Real baseline uncovered two issues. Ledger fencing works: the old lease cannot renew, append events or finish after interruption. But expired-lease reaper did not seal running captures, and _process_files excluded interrupted attempts; real new instruction could not read retained draft. Candidate repairs only that admitted-file recovery using existing incomplete seals and transaction. Independent native task continued after parent-worker SIGKILL; that separate lifecycle gap is open in KNOWN-ISSUES. Do not claim overall worker-loss execution stop accepted.

## Durable evidence

Baseline real Thread thr_1f5fe57105d8c6667941, old attempt_1759f3983b73d252. A ledger guard confirmed only this probe active, then SIGKILL/restart only capstone-worker-native-1. API-container monitor held lease only in RAM; all stale writes/renew rejected after lease_expired. Native taskpi-4d5aaa15a34a126be5c24f9b407a79c0341c69cc476232eedfdfdcfca751b647 independently completed with private final.md/draft.md; final.md never entered Thread products. No native work remained running when checked. Baseline public draft stayedrunning; actual follow-up acknowledged unreadable source. No baseline history rewritten.

Report docs/reviews/2026-11-15-worker-loss-product-recovery.md. Receipts/scripts under runs/harness-worker-loss-validation-20261115/: thread/commands, loss.json, fence-result.json, native-after-loss.json, before/after/settled snapshots and follow-up events. Lease tokens were never serialized. Initial wrong container Python lacked psycopg; owning /app/packages/capstone-agent/.venv/bin/python corrected setup only.

## Candidate verification and immediate next action

Four new memory/PostgreSQL tests first failed for both root causes. Candidate passes exact incomplete sealing before terminal, idempotence, stale renew/event/completion rejection, new frozen historical grant and protected byte read. PostgreSQL rollback on terminal persistence failure is covered. Python3.12 direct-consumer115 checks passed; focused worker-interruption gate116 passed21.96s; classifier123 passed3.58s. Added exact-byte assertions then four cases passed again. Test PostgreSQL capstone-historical-input-tests-20261115 on25445 is stopped.

Root temporarily holds the exact three package-file changes from f0976baf. Canonical rebuild completed; API and three workers share image sha256:8952043d0e6a2268237c93c3a8a2f1c78ecfb0059bcda1bc6866c948e4bf9987. Readiness and scoped cache cleanup passed.

Fresh Thread thr_20784dcce6ac2fe4156a: old attempt attempt_5c7c2a5eb2f62c10 interrupted, captured draft sealed incomplete. Distinct attempt attempt_38138f9991b21f68 read the original 28 bytes and saved recovery-check.md (1588 bytes). Download hashes and existing Vivaldi tab refresh verified. Receipts: runs/harness-worker-loss-fixed-20261115/. Native orphan cleanup was manual; automatic stop is still open. No active probe remains.

Next: finish the local evidence/control commit, then request one focused macOS worker-interruption CI (not yet approved). No remote push or PR until that approval. Independent reviewer dispatch failed due an unavailable configured model; no independent review result exists. Product diff self-review found no further change needed. Whole worker-loss acceptance remains partial.

## Ownership and recovery

Root pre-existing final docs/control receipts from PR119 remain; backups runs/harness-cancellation-validation-20261115/final-control-snapshot-fffc881e/ and earlier snapshots/stashesbcde2615,52561c4c,69739de9 preserved. Do not bulk-stage or blindly apply stashes: prior code/docs already merged. Current root adds this package's docs, KNOWN-ISSUES (INDEX updated), canonical worklist and temporary three-file product patch. Preserve var, authentication, user data and unrelated worktrees. Main/cloud/demo unchanged. No new Kernel/Authority/UI contract or Dockerfile change.
