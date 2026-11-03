# Multi-turn execution integrity audit

## Evidence and scope

The affected intranet Thread is `thr_52b7e926ea630d064f77`, on deployed
source `70c42dab`. Read-only evidence is retained under the ignored
`runs/multiturn-rejection-20261102/`. No historical business request was replayed.

Three failed Attempts follow successful earlier turns. The latest Attempt is
`attempt_18be896bbcd8e575`. Its raw events include model responses and successful
tool calls. Event 6399 starts `agent_resource_open`; no completion is recorded.
Event 6402 reports a parent execution failure and confirmed child cancellation.
The child receipt has status `cancelled`, with no native-host exception receipt.
The saved terminal incorrectly shows only cancelled task preparation.

The frozen submission contains the prior catalog file reference without
`saved_at`. Artifact listing enriches the same receipt with this display time.
Exact descriptor equality rejects it. The original reader raises `KeyError`,
which was not handled by the resource staging boundary. This failure path is
reproduced by focused tests. The old deployment did not retain the parent
traceback, so the historical exception cannot be proved from a saved stack.

## Corrections

- Reuse one frozen-descriptor comparison for direct historical reads and durable
  adoption reads. Permit only the absent legacy display timestamp. Keep ownership,
  source, reference, size and SHA-256 checks. Reject other descriptor changes.
- Translate the typed missing-artifact condition into a recoverable resource
  result. Do not catch arbitrary `KeyError` or turn programming bugs into success.
- Save resource-read diagnosis before returning the unavailable receipt. Preserve
  the original source coordinates and resource ID; do not copy exception text.
- Record parent failure coordinates and unsettled tool call IDs. Their effects
  remain unknown; cancellation does not assert that they were never executed.
- Preserve failure coordinates in the terminal Attempt, including chained causes.
- Recognize native model/tool events as execution. Report failed execution as
  failed, not cancelled preparation. User cancellation remains distinct.
- Preserve preparation and rollback failure coordinates separately. Record worker
  polling and runtime cleanup failures in service logs.
- Keep answer-admission causes rather than cutting them off with `from None`.
  Record shadow-router and partial-admission failures. Log failure-receipt storage
  failure while retaining the original fault coordinates.
- Show an LLM purpose only when explicitly retained or parsed from its opening
  comment. Do not substitute tool names, script operations or generic labels.

## Verification and remaining acceptance

The combined focused Python run passed 271 checks; 28 PostgreSQL-dependent cases
were skipped because no test database URL was supplied. The App's three focused
files passed 44 checks; TypeScript passed. Host/executor direct consumers passed
174 checks, with 32 cases skipped. Three local HTTP checks required bypassing the
host proxy; all three passed on rerun. No CI was started.

The canonical local rebuild succeeded after b4df210b. API and worker use the same
image, sha256:61aa2b1e7aa030732ed11d48523a65ec50a2b902fb519a578a4f8d1c5ce81664.
An isolated PostgreSQL check completed four turns: create a file, read its frozen
reference, record a failed business round, then read the historical file again.
Each terminal outcome released the current attempt. This check uses a deterministic
executor with real ledger and resource storage; it does not establish live-model
acceptance. Its dedicated database was removed after the check.

A short live continuation and review of other exception boundaries remain open.
The full summer request must not be replayed to verify historical-file transport.
The research server is unavailable. No further remote connections or deployment
will run until it is restored. Intranet services remain unchanged until the
agreed batch is fixed and verified together.

## Terminal fault precedence and receipt recovery

cbec0d59 prevents concurrent cancellation from replacing a classified runner
failure. 187a8ca8 logs both the initial result persistence fault and a subsequent
failure-receipt persistence fault using safe source coordinates and exception
classes, without private error messages. The host suite now passes 114 checks
(32 skipped), including a double persistence-failure case that verifies terminal
settlement, workspace preservation and no replay after host restart.

Further review found incremental capture retains only an exception class in an
internal field that no consumer reads. Final capture remains mandatory, but this
intermediate diagnostic gap is still open; do not claim the audit is complete.

## Consolidated exception-boundary review

Reviewed the main orchestration boundaries in thread_worker, harness,
delegated_runtime, pi_delegation, general_pi_server, continuation_resources,
and both incremental artifact workers. The inventory contains 103 catch sites.
Input rejection, typed transport recovery, reference integrity rejection and
unknown-outcome replay fences remain enforced. They are not converted into
successful business outcomes. c438fca6 adds shared cleanup handling: an active
execution exception remains primary; a secondary cleanup exception is logged
with safe coordinates. Cleanup failure without an active execution exception
still propagates. Session callbacks, business runtime stop, native process stop,
relay/gateway revocation and worker-factory close use this handling.

Cancellation failures and unexpected optional projection failures now retain
safe diagnostic origins. Normal optional absence remains optional; no retry or
fabricated success was added. Consolidated focused checks passed 462 cases,
with 33 skipped. Unified rebuild and a bounded live-model four-turn check are
in progress; these tests alone do not establish live acceptance.

## Local integrated acceptance

Unified rebuild passed with API/worker image
sha256:b79f2055b1aa9c4cfc2eb1c6920e1ffd760ee39e512a0d0e2fdb637d7ec28f7c.
Rebuild exposed and fixed a missing runtime_cleanup image COPY and the native
image layer limit; adjacent helper copies now share one layer. Isolated image
imports pass. Docker replacement debris was removed without removing volumes.

Live model thread thr_c2778f7072c571b40524 completed four HTTP command rounds:
1. Create verify.csv containing alpha,7 (6.2 seconds).
2. Read the admitted historical resource and confirm 7 (8.2 seconds).
3. Execute one deliberate bash exit3 and explain the failed tool outcome (8.2 seconds).
4. Read the same historical resource after that failed tool and confirm 7 (8.2 seconds).
Every round completed and released current_attempt. Each next command reloaded
the HTTP snapshot. This verifies API restore, not visual browser refresh. Saved
records are under runs/execution-integrity-20261102/live-multiturn. The separate
isolated PostgreSQL test covers continuation after a failed business terminal.
No summer business query, remote deployment or CI was run.

Scoped Docker cache maintenance reduced build-cache size from109.6GB to98.01GB.
Images, persistent volumes and running environments were preserved. Many orphan
historical validation volumes remain intentionally retained pending data review.
