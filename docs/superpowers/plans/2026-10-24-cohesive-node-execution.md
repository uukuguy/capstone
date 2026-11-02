# Cohesive Node Execution Implementation Plan

**Goal:** Execute a known read/write/run/process intent without unnecessary model round trips.

**Architecture:** Reuse the current Pi loop and isolated native tools. Carry descriptive metadata beside existing immutable input handles, provide exact report source errors, and guide the executor to compose known dependent work in code until new judgment is needed. No second scheduler or model gate.

**Accepted design:** [31-round investigation](../../reviews/2026-10-24-report-call-granularity.md).

## Constraints

- Preserve unrelated work, source grants, immutable versions, explicit returns and Authority boundaries.
- No new quality refusal, automatic retry loop, hard300s timeout or fixed model-round quota.
- Keep runtime metadata neutral. No power-market metric or example-specific task plan.
- Existing worktree is the implementation lane; no commit/merge/cloud/demo changes in this slice.

## 1. Consumable sealed inputs

Files: `native_graph_context.py`, `resources/task-node-return.mjs`, their focused tests.

- [x] Add a failing host-context test: resolve a frozen named artifact and assert readable `file_name`, `media_type`, `size_bytes`, `sha256`, roles accompany the same immutable handle.
- [x] Add a failing node-return test proving descriptive metadata reaches assignment files without inventing original filenames or changing read-only paths.
- [x] Populate metadata from the admitted product path and bytes; clone only supported optional fields in the model-facing projection. Legacy handles remain readable.
- [x] Run Python context and Node return-contract checks, including existing foreign-reference and immutability cases.

## 2. Exact report diagnostics

Files: `tools/native_report.py`, `tools/tests/test_native_report.py`.

- [x] Add a failing real CLI test with an absent Chinese image: diagnostic must identify `source_missing`, relative filename and section/block field; stdout and output file remain absent.
- [x] Implement bounded error metadata at source read; retain stdout success receipt and workspace confinement. Do not expose resolved host paths.
- [x] Run existing renderer tests covering embedding, Unicode, CSV preservation and symlink refusal.

## 3. Execution intent guidance

Files: `resources/general-sdk.mjs`, SDK execution fixture/tests.

- [x] Extend guidance to distinguish data dependencies from judgment dependencies: compose known read/transform/write/execute/check operations in one program, rather than assuming independent batches are the only option.
- [x] Keep unexpected analytical findings and unknown failures as model decision points. Preserve progress, cancellation, limits and concise explicit return.
- [x] Verify a real SDK tool call can read a file, generate a program, execute it and save processed output in one model response; no extra LLM review is added by the host.

## 4. Local and real-model verification

- [x] Run scoped backend/SDK/renderer gates, doctor and diff checks; freeze exact sources.
- [x] Canonical local rebuild and exact API/worker/native source verification; scoped build cache maintenance.
- [x] Use fixed saved upstream metrics/figures/findings as explicitly granted inputs for one report-only real-model task. Measure rounds, model/tool durations, products and limitations. Keep the146s baseline distinct and avoid a new full task until this experiment is understood.
- [x] Record source/runtime/experiment states separately in review, durable state and canonical dev register/overview; inspect the actual control page.

## Verification outcome

R1 report-only real request:215.132095s/19responses across2nodes, not a controlled baseline win. R2 one-intent real request:48.997602s/7responses, generation/execution/verification combined in one bash call, all CSV cells preserved. R3 fixes output-annotation rejection and adds a stopping rule;227Python/218JS checks and116runtime identity checks pass. R3 not rebenchmarked with a full report.

## Parallel planning refinement (accepted 2026-10-24)

- [x] Replace the over-broad merge preference with independently useful outcome boundaries. Shared read-only sources do not require merging; genuine joint interpretation may.
- [x] Require one batch for all currently justified independent work after discovery. Keep incremental planning, real dependencies and no fixed branch count.
- [x] Verify the organization prompt through the actual SDK loader. Keep execution capacity independent from semantic planning.
- [x] Remove a simple leading shell workspace change from visible tool summaries; preserve the exact operation in details and tooltip.
- [x] Rebuild the local candidate, verify frozen runtime identity, then run one complete original parallel request and record actual branches, overlap, calls, products and time.

The preceding two-branch run completed in412.363329s versus544.609189s for the sequential reference. Planning and admission fixes also changed; this is not a concurrency-only experiment. The historical145.914727s baseline remains unmet.

- [x] Record the original three-branch run336.512660s/59 model responses/59 tool records; report and indicators saved and hash checked.
- [x] Add neutral foldable startup/finalization records and current parent model timing. A temporarily empty incremental pool remains orchestration, not finalization.
- [x] Extract a leading action comment before truncating native command metadata.
- [x] Fix idle-graph continuation forcing direct answers into planning; actual simple enterprise request4.182780s/one response/no tools/no graph.

Known remaining work: locate16.6s parent pre-request gap; reduce manual record/review/finish round trips without changing explicit grants/persistence; a graph-free isolated single-operation entrypoint is not implemented.
