# Structured Tool Batches Implementation Plan

> Execute inline, task by task, with focused red/green checks and recovery commits.

**Goal:** Make independent tool calls explicit without model-written control flow.

**Architecture:** Add a calls alternative to the existing composition tool and reuse
its batch preflight and observation pipeline. Share bounded scheduling across that
tool's programs; keep gateway-wide capacity outside this session-local mechanism.

**Tech Stack:** Node.js ESM, node:test, existing Pi tool schemas and local Compose.

## Global constraints

Preserve grants, exact schemas, current-run evidence, user data and normal Git index.
No CI, push, merge, intranet deployment or demo update. Concurrency remains at most 4.

## Task 1: Structured contract and independent scheduling

Files: `resources/tool-composition.mjs`, `resources/tool-composition-worker.mjs`,
`resources/tool-call-scheduler.mjs`, `tests/fixtures/tool-composition.test.mjs`,
`tests/fixtures/tool-call-scheduler.test.mjs` under `packages/capstone-agent`.

- [ ] Add failing tests using `execute('batch',{calls:[{id:'a',tool:'read',arguments:{n:1}}]})`.
- [ ] Run `node --test packages/capstone-agent/tests/fixtures/tool-composition.test.mjs`.
- [ ] Validate one input mode and unique IDs; derive tools and pass a host-owned
  batch program through the existing worker. Use settled per-item outcomes only
  for this explicit mode; retain legacy program behavior.
- [ ] Add a FIFO scheduler with `acquire({signal,exclusive})` returning an idempotent
  release function. Abort removes queued waiters; active entries release on settlement.
- [ ] Test max 4 across simultaneous programs, FIFO exclusive calls and cancellation.
- [ ] Run focused tests and inspect diffs; create an exact-path recovery commit.

## Task 2: Model-facing integration and verification

Files: `resources/general-sdk.mjs`, the design, report and status documents.

- [ ] Explain calls mode as the normal expression of known independent requests;
  retain program mode for processing and genuinely dependent operations.
- [ ] Run composition and direct SDK/schema consumer checks. Test source contract
  retention, independent out-of-order completion, failed item recovery and next stage.
- [ ] Rebuild exact candidate using `make capstone-local-rebuild`, verify API/worker
  identity, then run one bounded real-model trial if the configured gateway is usable.
- [ ] Record actual adoption, concurrency, timing and any connectivity limitation.
- [ ] Clean scoped build cache; update recovery state and canonical control overview.
