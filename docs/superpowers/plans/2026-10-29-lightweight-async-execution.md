# Lightweight asynchronous execution implementation plan

Goal: publish useful versions during execution and reduce unnecessary model
round trips with bounded explicit composition and independent reasoning.

Architecture: existing host artifact ledger and safe collector own versions;
the Application selects a neutral asynchronous LLM pool. Neither subsystem
creates DR state or changes Authority facts. User approved direct implementation.

## Task1: Incremental products

- [ ] Add failing host/storage/controller tests: capture v1 before execution
  returns; v2 has distinct immutable bytes; parent failure preserves v1.
- [ ] Implement a serialized coalescing capture worker triggered by verified
  tool completion, not periodic scanning. Reuse artifact safety and size budgets.
- [ ] Admit host capture events in delegated runtime and publish the existing
  browser artifact event with running source status and no completion claim.
- [ ] Run focused pytest checks; commit task-owned paths after review.

Files: general_pi_server.py, general_pi_storage.py, delegated_runtime.py,
native_artifact_projection.py and focused tests owned by authority_import.

## Task2: Neutral pool and light model interface

- [ ] In resources/async-call-pool.mjs and its Node fixture tests, implement
  createAsyncCallPool({concurrency,maxJobs,signal,run,onState}) exposing submit,
  drainReady,snapshot,waitForCompletion,cancel,close. Test red before code.
- [ ] Add bounded submit/collect/cancel model tools. Submit explicit text jobs;
  collect returns only observed results and states, wait timeout is not failure.
- [ ] Wire separate no-tool managed sessions into general-sdk.mjs using the
  same protected runtime. Bind child IDs, usage and cleanup to the parent.
- [ ] Register exact application capability policy and package all new modules.
- [ ] Test real pinned SDK isolation and model tool admission; commit scoped code.

## Task3: Result ergonomics and model guidance

- [ ] Diagnose field visibility with exact representative result shapes. Add a
  failing fixture for a useful data field buried behind verbose metadata.
- [ ] Keep bounded summaries with data keys, array counts and source refs;
  preserve original bytes. Teach the model existing tools.describe/call and
  saveContext/loadContext composition for known dependencies and independent reads.
- [ ] Measure prefix stability separately; do not change budgets solely because
  smaller text looks cheaper. No fixed summer-study query sequence.

## Task4: Live validation and records

- [ ] Run affected Node/Python/App checks and review boundaries and cancellation.
- [ ] Canonical local rebuild; verify API/worker image equality and scoped cleanup.
- [ ] New Vivaldi test conversation in existing tab: explicit independent analysis,
  intermediate artifact, follow-up edit and refresh. Record first/final timings.
- [ ] Run same summer-study instruction only after a concrete verified change.
  Inspect model path, cache use, actual files and precise failures. Stop abnormal
  consumption rather than launch blind retries. Update journal and recovery.
