# Architecture improvement implementation

User approved the review proposals on 2026-11-13. This plan refines the accepted
enterprise execution worklist. IG1 remains open. Existing uncommitted control
documents are preserved separately.

## Scope and order

- [ ] Resource transactions: reserve under the existing thread transaction, write
  immutable bytes outside the lock, confirm under a short transaction. Test slow
  storage, cancellation during write, duplicate requests and write-before-ack
  recovery. Preserve cancellation cleanup of late objects.
- [ ] Resource projections: remove repeated event scans; retain durable events as
  the source of truth. Measure long-session and greater-than-1GB behavior before
  claiming scale acceptance.
- [ ] Attachment lifecycle: cancel obsolete reads, coalesce requests, bound cached
  bytes and show download errors while collapsed. Keep the accepted layout.
- [ ] Extract one shared state transition with storage conformance tests.
- [ ] Record same-task model/tool/storage timing before optimizing connections.
- [ ] Consolidate current architecture entry contracts and migrate registered
  pandapower runtime ownership with output and replay checks.

## First slice

Progress: resource write/duplicate fixes are committed as 787aad8b/640b0baa;
attachment cancellation and release as f092e9b4. PostgreSQL projection and the
greater-than-1GB transport check are recorded in
[verification](../../reports/2026-11-13-resource-projection.md). These partial
results do not close runtime, browser, pagination or integration acceptance.

Files: `thread_resources.py`, `tests/test_thread_resources.py` in capstone-agent.
First add a blocking-store regression that requires another thread to cancel
while put is in progress. Run it and observe failure, implement lock-free I/O,
then run resource tests and their direct consumers. Check both in-memory and
PostgreSQL paths; skipped database tests are not acceptance.

Runtime changes require the canonical candidate-workspace local rebuild and
real submit/product/continue/refresh validation. Preserve user data. Integrate
through dev PR governance; CI needs separate explicit approval. Update the
canonical worklist, journal and control graph at the verified boundary.
