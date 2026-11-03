# Execution reliability and session capacity implementation plan

> Execute inline, one bounded test/implementation/commit cycle at a time.

**Goal:** Complete the existing observation-to-product path and permit isolated
native conversations to execute with bounded capacity and truthful waiting state.

**Architecture:** Keep the PostgreSQL ledger as claim authority. Reuse native
observation, composition and reporting contracts. No second scheduler or cache.

**Stack:** Python Thread worker/PostgreSQL, native JavaScript SDK, React App.

## Constraints

- Accepted design: ../specs/2026-11-03-execution-reliability-and-session-capacity-design.md.
- Library capacity default1; local candidate2; no remote-server access/deployment.
- No business-name routing, automatic retries, altered gateway concurrency or
  automatic sampling. Existing grants, source versions and evidence rules remain.
- No CI or CI-triggering push until separately approved. Preserve root dev data.

## A: observation and product reliability

Files: resources/tool-composition{,-worker}.mjs, resources/observation-data.mjs,
owning gateway adapter, tools/native_report.py; existing focused tests
test_native_tool_composition.py, test_data_gateway_mcp.py, test_native_report.py.

- [ ] Run existing focused baseline; inspect exact adapter and worker contracts.
- [ ] Reproduce a failed processing/read-budget path retaining completed call
  refs, then repair from those refs with no new upstream read. Add a failing
  regression at the boundary where reproduction finds missing wiring.
- [ ] Exercise tools.plan rejection with zero upstream calls, exact reuse,
  refresh invalidation and live polling using existing fixtures.
- [ ] Exercise malformed/null tables and report check-only; retain precise source
  errors and prevent partial output publication. Patch only reproduced defects.
- [ ] Run focused regression files and commit verified corrections. Record
  existing passing behavior separately from newly repaired behavior.

## B: native slots and queue state

Files: thread_worker.py, native_hosted_worker.py, owning runtime-factory cleanup,
thread_service.py claim contracts if required; ThinkingProcess.tsx and owning
message projection only where accepted/start/snapshot tests reproduce a defect.

- [ ] Add worker test with two blocking attempts and third pending; assert both
  start, third is unclaimed, and next starts only after cleanup. Initially fail
  on absent max_concurrent_attempts parameter or serial behavior.
- [ ] Implement validated positive capacity, default1. Reuse run_pending_attempt
  and ledger claims; use at most one active execution per slot without submitting
  unbounded queued futures. Preserve wake behavior, per-attempt leases and family.
- [ ] Test cancellation, failure, shutdown and shared factory lifecycle. Review
  idle caches/locks; do not sweep or close resources still used by active attempts.
- [ ] Expose native setting in native_hosted_worker and checked-in configuration
  contract, test invalid values and default1. Use2 only in local candidate config.
- [ ] Test real PostgreSQL claim races, same-thread exclusion and cancelled queue.
- [ ] Reproduce accepted-only UI with live events and restored snapshot; preserve
  waiting until actual start, terminal cancellation and existing conversation UI.
- [ ] Run focused worker/native/App checks, type checks for changed modules, and
  commit verified implementation units with journal/checkpoint updates.

## Acceptance and integration

- [ ] Initialize isolated runtimes with make setup, make install-pi, make doctor.
- [ ] Canonical local rebuild; record temporary candidate source and preserve data.
- [ ] Real model: three sessions, two running and one waiting, queued cancellation,
  continuation, product download and refresh. Record any unavailable dependency.
- [ ] Measure comparable calls/rounds/time without promising speedup from fixtures.
- [ ] Run scoped cache maintenance after local build use.
- [ ] Update canonical unified worklist, version register, graph and recovery.
- [ ] Prepare reviewable dev PR; request one scoped CI approval only when ready.
  Merge accepted work into actual dev after its approved gate succeeds.
