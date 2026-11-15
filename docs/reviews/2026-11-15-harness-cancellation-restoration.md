# Harness cancellation and instruction restoration

Status: local verification of existing behavior passed. No runtime code change,
new image, CI or deployment. Repository source: devd718050c; local runtime source
remains verified5798dad6. Owner: capstone-agent/capstone-app. Evidence/control
delivery branch: docs/harness-cancellation-acceptance-20261115; destination dev.

## Existing acceptance boundary

The canonical enterprise plan requires the existing normal conversation to
support stop, follow-up, refresh and session state. Stop acceptance must not be
reported as terminal completion. This slice verifies that accepted contract;
it does not introduce pause/resume, retry cancelled work automatically, or use a
general task's files as Authority evidence.

## Real execution

Thread: `thr_2b9e9d997f6ead5256f1`.
Cancelled attempt: `attempt_bd0a0ba00f1df670`.
Follow-up attempt: `attempt_5b37cb44a5b6dd72`.

1. A real model was asked to save an explicitly incomplete simulated draft,
   perform a20-second wait, then create a separate final file. The probe waited
   for a host-observed tool start before sending `cancel_work` with the current
   Work revision. It did not cancel any pre-existing user task.
2. Cancellation was accepted and then reached a distinct `attempt_cancelled`
   event26. Observed cancellation-to-terminal elapsed time:0.548seconds, with
   polling every0.5seconds. This is one mechanism measurement, not a latency SLA.
3. `draft.md` was retained as source_status`cancelled`,28 bytes,
   SHA256`84b1d27e8b614ee4ddb67697d4345252320d4e7ce7ffce14e18b5a3e5d5596b6`.
   No published `final.md` exists in the complete event history.
4. A new instruction in the same Work explicitly excluded the cancelled wait
   and requested `new-instruction.md`. It completed as a separate attempt at
   event62. The saved100-byte file's SHA256 is
   `61b84fe7429feeaac6dada06e39004166dc6c574ddd4fc980af8864061a44ca4`.
   The cancelled attempt did not gain a completion event.
5. The local API container was restarted without changing source, image or
   storage. Readiness returned. Both terminal records and both downloadable
   files survived with exact byte sizes and hashes. The first instruction was
   not replayed by the restart or by the new instruction.
6. The existing Vivaldi Capstone tab was reused. After reload it showed the
   cancelled first attempt, completed second attempt and new product. Expanding
   the first attempt's process files opened `draft.md`; its preview displayed
   “已取消” and “模拟初稿，尚未完成”. No new browser tab was created.

## Focused checks and evidence

The incremental-artifact cancellation, terminal transition and worker capacity
checks passed:24 tests in1.49seconds with real disposable PostgreSQL, zero skips.
The earlier environment-only run had20 passes/four PostgreSQL skips and is not
used as PostgreSQL acceptance. One existing Starlette deprecation warning does
not change the result. The temporary test database container was stopped.

Ignored operator evidence: `runs/harness-cancellation-validation-20261115/`:
commands/receipts, `summary.json`, `cancel-events.json`, `postrestart-events.json`,
`postrestart-verification.json`, `browser-refreshed.json`,
`browser-draft-list.json`, `browser-draft-preview.json` and their screenshots.
Credentials remain in protected backend configuration and the existing private
operator client; none are stored in these receipts.

## Limits and next boundary

This validates cancellation of one real general task, preservation of its
incomplete file, a distinct new instruction, API restart and browser restoration.
It does not prove worker crash recovery, expired-lease fencing under real
process loss, arbitrary slow-tool cancellation or complete execution-chain
acceptance. Those need separate bounded experiments. No runtime fix is justified
by this passing slice. Any documentation PR requires a separately approved CI
run; none has been started for this evidence update.
