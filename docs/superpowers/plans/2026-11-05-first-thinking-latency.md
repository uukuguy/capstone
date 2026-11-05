# First Thinking latency investigation and correction

User approved continuing measured optimization of the6.2s first-preview interval.
Runtime baseline367374aa; intranet overlay255c8855. Preserve direct native entry,
stage-local credentials, frozen models/resources and actual Authority boundaries.

1. Inspect worker/database calls and native/Provider relay startup independently.
   Use existing task/thread identities and monotonic durations. Diagnostic records
   contain only phase names, counts and timing, never prompts, text, URLs or secrets.
   Reuse existing logging mechanisms. No per-token database writes or new UI stages.
2. TDD minimal host timing: task/resource setup, process launch, first Provider
   request, response headers/bytes, first semantic Thinking/text. Distinguish
   application request start from actual network-send guarantees. Bound memory,
   clean up per-task timers, and preserve cancellation/failure behavior.
3. Identify a measured avoidable startup cost and correct only that cost. Do not
   reuse mutable agent contexts or UIDs between tasks, bypass permissions, assume
   model latency, or add a classification model. Test direct consumers and review.
4. Canonical local rebuild and bounded real ordinary trial; correlate private
   timing with SSE/browser observations. Verify no independent recognition and
   Thinking persistence/refresh. Deploy the verified source to three stages with
   idle guards/backups. Run one63 real ordinary check and compare measured phases.
5. Record exact deployed source/config, improvement and remaining model time in
   report/journal/baton/register/overview; inspect graph and save scoped recovery
   commits. No CI/push/merge or repeated broad/solver benchmark calls.
