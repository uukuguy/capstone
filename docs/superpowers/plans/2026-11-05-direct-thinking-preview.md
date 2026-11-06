# Implementation plan

1. Add failing focused tests for bounded preview storage, duplicate batches,
   asynchronous persistence, barriers and required write failure.
2. Add a per-attempt writer with an explicit append_thinking observer seam.
   Preserve synchronous append_runtime_event return contracts.
3. Add a private authenticated API publish endpoint and SSE preview frames.
4. Frontend worker owns transport/store reconciliation and existing Thinking UI.
5. Run focused tests. Parent owns local rebuild, real trial, deployment and
   project control records. No CI is authorized by this plan.
