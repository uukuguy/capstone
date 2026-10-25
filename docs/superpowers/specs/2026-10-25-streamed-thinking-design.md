# Streamed thinking and execution handoff

Status: user specified the interaction on2026-10-25; implementation follows that
instruction. Reuse the shared conversation and its event ledger.

- Every accepted/submitting instruction has an initial thinking view, including
  queued work. Queue state must not claim the model has already produced text.
- Append actual model-interface thinking text incrementally when supplied. Keep
  it separate from answer text, diagnostic logs, tool results and Authority facts.
  Do not reconstruct hidden/redacted content, emit signatures or invent thinking.
- A real visible tool or business-task process replaces the initial thinking
  view. Generic host preparation/execution/finalization does not trigger handoff.
- A direct answer retains thinking until completion, then folds it. Failure and
  cancellation fold with their actual status. Retained text can be opened again.
- Replay uses the same ordered, attempt-bound records. A later instruction gets
  a fresh thinking phase. Completed old phases must not resume or absorb new text.
- Models that supply no displayable thinking retain a truthful status indicator.
  This change does not force unsupported reasoning or add another model call.

Publish bounded typed thinking deltas through the existing native host/application
event path. Preserve trajectory redaction and all professional Authority boundaries.
Keep initial-thinking selection distinct from the tool/business process projection.

Verify native delta admission and separation, queued thinking, streaming, actual
task handoff, lifecycle exclusion, completion/cancellation folding and replay.
Use focused backend/SDK/App checks and a local real entry check. Reuse unchanged
professional results; no solver suites or release gate.
