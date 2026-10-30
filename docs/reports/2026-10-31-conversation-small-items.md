# Conversation control repairs

The user approved four remaining repairs and confirmed delete-popover manual
acceptance. No session deletion was performed.

## Behavior

- Before receipt delivery, a pending instruction now precedes its Thinking.
  Admitted events replace both pending rows; reload reconstructs their ownership.
- Escape outside menus and dialogs sends the same active Work cancellation as
  Stop. Held Escape is ignored. Actual cancellation remains server-owned.
  Once cancelled, the status notice confirms that the task stopped.
- Revision conflicts state that the request did not execute, retain the draft,
  and refresh the Work snapshot before another submission.
- Tool errors unwrap JSON messages, MCP text content and gateway gaps. Invalid
  or incomplete JSON gets a short fallback. Original diagnostic data is retained.

## Verification

- Four affected App suites: 172 passed in 7.25s. Type check passed.
- App gate: 1419 passed in 20.97s; build passed. After the final notice repair,
  all 22 adapter tests passed in 7.93s and types passed.
- Regression tests first failed for pending instruction ownership, global Escape,
  JSON extraction, conflict copy and cancellation-terminal notice.
- Actual Vivaldi thread `thr_78654f76240fe97ce61a`: a real model request was
  cancelled with Escape. A subsequent instruction completed in 2.4s with answer5.
  Refresh retained the cancelled and completed records, each under its instruction.
  This is scoped control verification, not grid/research business acceptance.
- First canonical rebuild passed readiness and API/worker image identity
  `701ab0425999cdcf2bb2ed23d4c116b7dbd65fee7cc0753df1030663bddaf5d5`;
  scoped cache maintenance completed. Final notice-only rebuild is pending.

Local evidence: `runs/conversation-small-items-20261031/`.
Logs: `/tmp/capstone-small-tests.log`, `/tmp/capstone-small-app-all.log`,
`/tmp/capstone-small-rebuild.log`, `/tmp/capstone-small-rebuild-final.log`.

## Delivery boundary

Implementation is on `fix/conversation-small-items-20261031`; dev PR integration
and final actual-dev control-graph inspection remain pending. Cloud, demo and
main are unchanged. No release gate is required.
