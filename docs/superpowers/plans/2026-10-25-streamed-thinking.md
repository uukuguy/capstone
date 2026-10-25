# Streamed Thinking Implementation Plan

For agentic workers: use subagent-driven-development for the independent backend
and frontend tasks; coordinator owns integration and proportional verification.

**Goal:** Show thinking immediately after submission, stream supplied public text,
then fold or hand off to the actual execution process.

**Architecture:** Reuse Thread/Work/Attempt events, native model streaming and
existing conversation/process components. Add a typed attempt-bound thinking delta;
keep answer/diagnostic/Authority channels separate.

1. Backend: failing tests for admitted native thinking deltas, frame bounds and
   answer separation; implement host/delegated normalization. Preserve redaction.
2. Frontend: failing tests for queued/streaming thinking, task/tool takeover,
   lifecycle exclusion, terminal folding, manual reopening and refresh replay.
   Reuse current composer and message rows.
3. Integrate: focused tests/types, review, canonical local rebuild only for changed
   runtime, actual direct/tool entry observation, then scoped PR to dev. Update
   owning state/control at the coherent acceptance boundary, avoiding repeated
   unchanged suites and intermediate graph renders.

Contract: public event assistant_thinking_delta with payload.text and optional
task_id. Content is actual displayable model-interface text; never a diagnostic
string, reconstructed hidden reasoning, signature or tool-output substitute.
