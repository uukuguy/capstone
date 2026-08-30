# Formal Application Report Parity Implementation Plan

> **For implementation:** Execute this plan in the current workspace, task by task. Preserve unrelated changes and do not change simulator-truth boundaries.

**Goal:** Make `make application` expose v1.0.1-quality live execution visibility and a rich pandapower report, while retaining the generic application kernel and its final immutable-artifact contract.

**Architecture:** Add a generic, optional checkpoint/report-observation seam to the kernel. It atomically rewrites the mutable working `output/report.md` after each finalized turn, then performs the existing final report registration unchanged. The grid product supplies a pandapower report shell/adapter that reuses the established v1.0.1 report renderer and maps generic run objects into its stable presentation inputs. CLI progress is forwarded to stderr only.

**Stack:** Python 3.12, capability-agent-kernel, grid-agent, pytest, GNU Make.

---

## Task 1: Add a generic live-report checkpoint lifecycle

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runner.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/reporting.py`
- Test: `packages/capability-agent-kernel/tests/application/test_runner.py`

1. Write failing kernel tests that run two questions and assert that a checkpoint is rendered after each completed turn, uses only completed answers, and is atomically written to `output/report.md` before finalization.
2. Introduce a narrowly typed optional checkpoint callback or shell method; its inputs must be generic application records, current completed answers, trajectories, references, context, and preparation data.
3. In `AgentApplication.run`, call the checkpoint immediately after each successfully finalized answer. Do not checkpoint failed/unfinalized answers as completed.
4. Retain the existing end-of-run `_write_report` and immutable artifact registration as the sole final-admission path. A checkpoint must never register/overwrite a final immutable reference.
5. Run `pytest packages/capability-agent-kernel/tests/application/test_runner.py -q` and verify both red-to-green coverage and existing lifecycle tests pass.

## Task 2: Restore generic-run stderr progress without contaminating stdout

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runner.py`
- Modify: `packages/grid-agent/src/grid_agent/cli/app.py`
- Test: `packages/grid-agent/tests/cli/test_run_command.py`

1. Add a generic-run semantic-event observer that fans out events already sent to projection; do not create a second execution path or alter stored event semantics.
2. Wire `analysis-generic` to the existing `_ProgressReporter`, including prompt, tool, heartbeat, turn-completion, and report-checkpoint progress messages.
3. Write a CLI regression test that captures streams during an `analysis-generic` run: stdout is exactly the one JSON answer envelope, while progress is observable on stderr.
4. Run `pytest packages/grid-agent/tests/cli/test_run_command.py -q` and confirm all v1 and generic stream-separation tests pass.

## Task 3: Supply a pandapower rich report shell by reusing v1.0.1 reporting

**Files:**
- Add or modify: `packages/grid-agent/src/grid_agent/application/` (product report adapter/shell)
- Modify: `packages/grid-agent/src/grid_agent/application/profile.py`
- Reuse: `packages/grid-agent/src/grid_agent/analysis/report.py`
- Test: `packages/grid-agent/tests/application/test_generic_entrypoint.py`
- Test: `packages/grid-agent/tests/analysis/test_report.py`

1. Characterize the required v1.0.1 report sections with focused tests: question/result status, answer text, tool trajectory, evidence/result references, runtime/validation details, and graceful partial-run rendering.
2. Build a product-owned adapter that translates generic application records into the inputs expected by the established analysis report renderer. Reuse report helpers and atomic write behavior; do not copy a simplified report implementation.
3. Make `build_pandapower_application_profile` use this shell instead of `GenericReportShell`; leave the Kernel default shell domain-neutral for other products.
4. Ensure every network-specific claim remains tied to current-run simulator evidence. Checkpoint output may contain only finalized turns and must survive a later interrupted turn.
5. Extend the generic application integration test to assert rich report sections, turn-by-turn checkpoint behavior, and final report availability.
6. Run `pytest packages/grid-agent/tests/application/test_generic_entrypoint.py packages/grid-agent/tests/analysis/test_report.py -q`.

## Task 4: Document operation and prove the supported flow

**Files:**
- Modify: `docs/PANDAPOWER-APPLICATION.md`
- Modify: `docs/MANUAL-VALIDATION.md`
- Modify if shared command facts change: `README.md`, `README.zh-CN.md`, `docs/RUNBOOK.md`
- Test: `tools/test_makefile_application.sh`

1. Document that `make application` is the formal pandapower application entry, stderr contains live progress, `runs/<run-id>/output/report.md` refreshes after finalized answers, and the final report is registered only on successful completion.
2. Include concise interruption inspection guidance: view the mutable report and per-turn artifacts; distinguish an interrupted run from a completed final artifact.
3. Preserve the short Makefile contract and add/adjust its contract test only if new invocation or inspection behavior needs it.
4. Run focused tests, then required gates: `make doctor`, `make test`, `make test-e2e`, and `make validate`.
5. With the already authorized provider billing, run a real multi-question `make application` using the configured provider. Observe stderr and `output/report.md` during execution; retain the run path and outcome as validation evidence.

## Review checklist

- `output/report.md` is atomically refreshed after each finalized answer.
- A long-running generic application emits meaningful stderr progress while stdout remains one JSON object.
- The formal pandapower report reuses v1.0.1 report richness rather than a new reduced format.
- Kernel remains generic; no pandapower objects, raw internals, or product-specific claims cross into it.
- Final immutable report registration happens only in normal finalization.
- Documentation and Makefile references use `make application` consistently.
