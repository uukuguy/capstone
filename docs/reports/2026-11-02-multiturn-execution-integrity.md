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
files passed 44 checks; TypeScript passed. Subsequent diagnostic changes passed
their direct consumers (198 and 84 checks). A final combined rerun is required
after the last edits. Pytest also reports pre-existing temporary-directory cleanup
warnings; these are not execution test failures.

This is not whole-chain acceptance. Local canonical rebuild, durable-store
multi-turn verification and a short live continuation remain required. The full
summer request must not be replayed just to verify historical-file transport.
Review of other exception boundaries remains active. No CI was started. Intranet
services remain unchanged until the agreed batch is fixed and verified together.
