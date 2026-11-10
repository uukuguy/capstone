# Tool execution lifecycle implementation plan

> Execute in the current isolated workspace using subagent-driven-development.

Goal: record actual execution and enforce configurable rolling queues while grouping
all same-response calls without false concurrency claims.

## Constraints

Use the accepted lifecycle design. Default capacity eight. No semantic name routing.
Keep existing authority ownership, output contracts, data and credentials protected.
Do not run CI or push. Preserve pre-existing dirty status files.

## Tasks

- [x] Backend: map native relay, domain service, gridctl subprocess and composition
  paths. Define a validated execution receipt contract propagated through existing
  result details and runtime events. Add neutral owner-side scheduling and actual
  process start/exit records. Add failing tests for sixteen/eight rolling refill,
  cross-entry scope, conflicts, errors, cancellation and persistence before code.
  Verify focused tests and commit only owned backend paths.
- [x] App: consume validated execution receipts; group same-response calls using
  admitted ownership, never time overlap. Label batch count, capacity and known peak
  distinctly. Use owner timing for queue/execution; legacy actual execution remains
  unknown. Add failing projection/render tests, run focused tests/types and commit.
- [x] Review and local validation: inspect both diffs for contract agreement, cancellation
  and unknown-state handling. Run focused consumer checks. Rebuild local-dev through
  the canonical entry; verify real calls, saved receipts/products and refresh. Update
  journal/checkpoint and version register/control overview.
- [ ] Dev integration: obtain separately approved focused macOS CI, then use a dev
  PR and refresh the actual dev control graph. Continue is not CI approval.
