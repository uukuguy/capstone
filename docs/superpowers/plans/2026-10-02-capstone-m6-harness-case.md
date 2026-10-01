# Capstone M6 Harness and Case Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `capstone-agent` the durable owner of Thread-native Case execution with one sequential strategy and shared Web/CLI/TUI interaction semantics.

**Architecture:** CaseDefinition, CaseExecution, and strategy selection live in the Capstone application. A neutral Thread application-transition port atomically stores bounded application state, public events, and command receipts; it does not interpret Case fields. The Case service uses ordinary Thread commands for each Turn and reconciles terminal Attempts after crashes. Legacy `grid-agent` and `pypsa-agent` remain assembly/compatibility adapters.

**Tech Stack:** Python 3, pytest, PostgreSQL/psycopg, FastAPI, React/TypeScript, Vitest, assistant-ui, SSE.

## Global Constraints

- Follow [the approved M6 design](../specs/2026-10-02-capstone-m6-harness-case-design.md) and [the framework architecture](../../architecture/capstone-framework.md).
- Preserve `Application -> Domain Pack -> Kernel -> registered Authority`; no raw Authority object or direct Pi/DSH call in Case execution.
- M6 strategy identity is `sequential_batch`, version `1`; one active Case step and one active Attempt at most.
- A failed, cancelled, or interrupted Attempt is immutable. Retry creates a new Attempt under the same Turn.
- Case commands use `capstone-command/1`, expected event sequence, idempotency key, and stable receipts.
- `ThreadSnapshot` and `EventPage` carry user-readable Case status, actions, disabled reasons, and provenance; internal IDs are details.
- `grid-agent` and `pypsa-agent` are temporary adapters, not new orchestration owners. Do not add Case state or runtime routing to them.
- Preserve unrelated `.gitignore` edits and append-only `docs/status/JOURNAL.md`; stage only task-owned files.
- After backend/App edits, run `make capstone-local-rebuild`; full integration claims require `make doctor`, `make test`, `make test-e2e`, `make validate`, and `make check-release`.
- M6 closes only after an independent code review with no Important/Critical findings.

## File Map

| File | Responsibility |
| --- | --- |
| `packages/capstone-agent/src/capstone_agent/case_definition.py` | Trusted, versioned Case definitions and bounded catalog projection |
| `packages/capstone-agent/src/capstone_agent/case_execution.py` | CaseExecution state, sequential strategy, public interaction projection |
| `packages/capstone-agent/src/capstone_agent/case_service.py` | Application command admission, Turn dispatch, terminal reconciliation |
| `packages/capstone-agent/src/capstone_agent/thread_application_transition.py` | Neutral, bounded transition request and validation |
| `packages/capstone-agent/src/capstone_agent/harness.py` | Public Capstone Harness coordinator and Pi/DSH runtime seam |
| `packages/capstone-agent/src/capstone_agent/thread_application.py` | Application-owned runtime selection into the Harness seam |
| `packages/capstone-agent/src/capstone_agent/thread_service.py` | In-memory/Postgres atomic transition port and snapshot storage |
| `packages/capstone-agent/src/capstone_agent/thread_protocol.py` | Typed optional application projection on ThreadSnapshot |
| `packages/capstone-agent/src/capstone_agent/thread_commands.py` | Case command builders |
| `packages/capstone-agent/src/capstone_agent/thread_worker.py` | Reconciliation tick around existing Attempt worker |
| `packages/capstone-agent/src/capstone_agent/host_api.py` | Case catalog and command dispatch through Capstone service |
| `packages/capstone-app/src/threadProtocol.ts` | Strict TypeScript Case projection parser |
| `packages/capstone-app/src/threadClient.ts` | Typed Case command methods |
| `packages/capstone-app/src/ThreadLiveEntry.tsx` | Thread-native Case entry and actions |
| `packages/capstone-app/src/CapstoneAssistantThread.tsx` | Compact per-Case progress in conversation |
| `packages/capstone-agent/tests/test_case_*.py` | Pure, command, persistence, recovery, HTTP, and boundary tests |
| `packages/capstone-app/src/*Case*.test.tsx` | Shared projection and interaction tests |

---

### Task 1: Trusted CaseDefinition and catalog

**Files:** Create `case_definition.py`, `tests/test_case_definition.py`; modify `catalog.py` only to reuse its trusted registration parsing.

**Interfaces:** Produce `CaseStepDefinition(ordinal: int, title: str, instruction: str, instruction_digest: str)`, `CaseDefinition(case_id, case_version, case_revision, display_name, description, model_ids, steps)`, and `CaseCatalog.get(case_id: str, version: str | None = None) -> CaseDefinition`. `CaseCatalog.from_registered_catalog(document: Mapping[str, object])` accepts only the server-built `capstone-catalog/1.0` document.

- [ ] **Step 1: Write failing tests** for pandapower and PyPSA registration, a stable SHA-256 Case revision, unique IDs, bounded non-empty instructions, and rejection of an unregistered case. In the same module define `registered_catalog_fixture() -> dict[str, object]` with one three-step `pandapower-scripted-task` entry and one three-step PyPSA entry. Example:

```python
def test_catalog_freezes_registered_case() -> None:
    catalog = CaseCatalog.from_registered_catalog(registered_catalog_fixture())
    case = catalog.get("pandapower-scripted-task")
    assert case.case_version == "1"
    assert [step.ordinal for step in case.steps] == [1, 2, 3]
    assert case.case_revision.startswith("case:sha256:")
```

- [ ] **Step 2: Run** `pytest packages/capstone-agent/tests/test_case_definition.py -q`; expect import failure.
- [ ] **Step 3: Implement** frozen dataclasses and deterministic revision from canonical UTF-8 JSON of ID, version, model constraints, and ordered step titles/instructions. Derive short user-readable step titles from trusted case metadata, never from an LLM response. Reject unknown keys, duplicates, >32 steps, and >4096 characters per instruction.
- [ ] **Step 4: Run** the focused test; expect pass. Commit `feat: add trusted application case definitions`.

### Task 2: Pure CaseExecution state and sequential strategy

**Files:** Create `case_execution.py`, `tests/test_case_execution.py`.

**Interfaces:** Produce `PinnedCaseContext(model_context_id, model_id, model_revision, selection_revision)`, `CaseStepState(ordinal, turn_id, latest_attempt_id, status, answer, result_refs, evidence_refs, duration_ms, error_code)`, `CaseExecution(case_execution_id, thread_id, run_id, case_id, case_revision, strategy_id, strategy_version, context, steps, status, current_step)`, `StepOutcome(status: Literal["running", "completed", "failed", "cancelled", "interrupted"], attempt_id: str, answer: str | None, result_refs: tuple[str, ...], evidence_refs: tuple[str, ...], duration_ms: int | None, error_code: str | None)`, `StrategyDecision(execution: CaseExecution, next_step: CaseStepDefinition | None)`, `CaseExecutionStrategy.advance(execution, outcome) -> StrategyDecision`, and `SequentialBatchExecutor`.

- [ ] **Step 1: Write failing tests** for initial step, successful advance, terminal completion, blocked failure/interruption, no failed partial answer handoff, and completed-step immutability. In the same module define `execution_fixture(status: str) -> CaseExecution` and use `StepOutcome.running()` only as a test factory that returns a `running` outcome without changing the execution. Example:

```python
def test_strategy_waits_for_committed_step() -> None:
    execution = execution_fixture(status="waiting_step")
    decision = SequentialBatchExecutor().advance(execution, StepOutcome.running())
    assert decision.next_step is None
    assert decision.execution == execution
```

- [ ] **Step 2: Run** `pytest packages/capstone-agent/tests/test_case_execution.py -q`; expect import failure.
- [ ] **Step 3: Implement** frozen models with `to_document`/`from_document` bounds and a pure `advance` function. `StepOutcome.completed` must carry the exact terminal `attempt_id`; `StepOutcome.failed`, `cancelled`, and `interrupted` never expose partial answer/refs to the next step. Do not add DAG, branch, or tool-level switches.
- [ ] **Step 4: Run** the focused test; expect pass. Commit `feat: model sequential case execution`.

### Task 3: Atomic neutral application transition port

**Files:** Create `thread_application_transition.py`, `tests/test_thread_application_transition.py`; modify `thread_protocol.py`, `thread_service.py`, `tests/test_thread_protocol.py`, `tests/test_thread_postgres.py`.

**Interfaces:** Add `ApplicationEvent(event_type: str, payload: Mapping[str, Any], visibility: Literal["public", "diagnostic"] = "public")` and `ThreadApplicationTransition(command: Mapping[str, Any], state: Mapping[str, Any] | None, events: tuple[ApplicationEvent, ...])`; add `ThreadService.apply_application_transition(transition: ThreadApplicationTransition) -> CommandReceipt`. The `state` is bounded JSON under `ThreadSnapshot.application_state`; storage remains domain-opaque, while `case_service.py` owns the typed public Case projection before serialization. The store enforces command identity, cursor, idempotency, event sequence, and one atomic update. Case semantics stay in `case_service.py`.

- [ ] **Step 1: Write failing in-memory and PostgreSQL tests**: same key/same payload returns the first receipt; same key/different payload rejects; stale sequence rejects without side effects; event/state/receipt commit together; a fresh Postgres service reconstructs state. In the same module define `transition_fixture(expected_event_seq: int) -> ThreadApplicationTransition` with command `case_execution_created` and a bounded `case_execution` state. Example:

```python
def test_application_transition_is_atomic(service: InMemoryThreadService) -> None:
    transition = transition_fixture(expected_event_seq=0)
    receipt = service.apply_application_transition(transition)
    assert receipt.status == "accepted"
    assert service.snapshot("thr_case").application_state == transition.state
    assert service.read_events("thr_case", 0).events[-1].event_type == "case_execution_created"
```

- [ ] **Step 2: Run** `pytest packages/capstone-agent/tests/test_thread_application_transition.py packages/capstone-agent/tests/test_thread_protocol.py -q`; expect failures.
- [ ] **Step 3: Implement** validation and in-memory transaction under the existing lock. Add a nullable JSONB `application_state` column to `capstone_threads`, then Postgres transaction under `SELECT ... FOR UPDATE` with the same admission order as `submit_command`. Bound state to 64 KiB, each event to 64 KiB, and at most 8 events per transition. Ensure existing snapshot documents without `application_state` still parse.
- [ ] **Step 4: Run** focused tests both without and with `CAPSTONE_TEST_DATABASE_URL`; expect pass. Commit `feat: persist atomic application transitions in Thread ledger`.

### Task 4: CapstoneHarness runtime registry and convergence

**Files:** Modify `packages/capstone-agent/src/capstone_agent/harness.py`, `packages/capstone-agent/src/capstone_agent/thread_application.py`, and `packages/capstone-agent/tests/test_harness.py`, `packages/capstone-agent/tests/test_thread_application.py`.

**Interfaces:** Add `HarnessRuntimeRegistry.register(runtime_name: str, factory: Callable[[AttemptClaim], HarnessRuntime])`, `HarnessRuntimeRegistry.resolve(runtime_name: str) -> RuntimeFactory`, and `CapstoneHarness.run_attempt(service: ThreadExecutionService, claim: AttemptClaim, runtime: HarnessRuntime) -> HarnessAttemptResult`. `HarnessPiClient` remains the production Pi adapter; `HarnessDSHClient` remains an explicit unavailable adapter. No Case code may import either concrete client.

- [ ] **Step 1: Write failing tests** for duplicate runtime registration, Pi event normalization/provenance, DSH returning `HarnessRuntimeUnavailable`, and `CapstoneHarness` using only the existing public `HarnessRuntime` and `ThreadExecutionService` protocols.
- [ ] **Step 2: Run** `pytest packages/capstone-agent/tests/test_harness.py packages/capstone-agent/tests/test_thread_application.py -q`; expect failures for the new registry/facade.
- [ ] **Step 3: Implement** the small registry/facade by delegating to `HarnessAttemptRunner`; do not copy admission, ledger, or Domain Pack logic. Wire `ThreadApplicationAssembly` to accept the registry while preserving existing `from_authority` and `from_prepared_authority` constructors. Keep `runtime_mode` and runtime event normalization at the Harness boundary.
- [ ] **Step 4: Run** focused tests; expect pass. Commit `feat: converge runtime selection behind Capstone Harness`.

### Task 5: Case command admission and Turn dispatch

**Files:** Create `case_service.py`, `tests/test_case_service.py`; modify `thread_commands.py`, `host_api.py`, `tests/test_thread_commands.py`, `tests/test_thread_http_api.py`.

**Interfaces:** `CaseExecutionService(catalog: CaseCatalog, thread_service: ThreadExecutionService)` exposes `submit_command(command: Mapping[str, Any]) -> CommandReceipt`, `catalog(thread_id: str) -> dict[str, object]`, and `reconcile(thread_id: str) -> CaseExecution | None`. Add `start_case_execution`, `retry_case_step`, `cancel_case_execution`, `resume_case_execution` builders. HTTP uses the Case service for those four kinds and the existing service for all other commands.

- [ ] **Step 1: Write failing tests** for start with a pinned model/selection, duplicate idempotent start, wrong model, busy Thread, stale cursor, Profile/model switch lock, retry target mismatch, and operator-only HTTP access. In the same module define `case_service` with an `InMemoryThreadService` and `start_command(case_id: str, seq: int) -> Mapping[str, object]`. Example:

```python
def test_start_case_pins_current_context(case_service: CaseExecutionService) -> None:
    receipt = case_service.submit_command(start_command("pandapower-scripted-task", seq=0))
    assert receipt.status == "accepted"
    execution = case_service.reconcile("thr_case")
    assert execution is not None
    assert execution.context.model_revision == case_service.thread_service.snapshot("thr_case").active_model_context.model_revision
```

- [ ] **Step 2: Run** `pytest packages/capstone-agent/tests/test_case_service.py packages/capstone-agent/tests/test_thread_commands.py -q`; expect failures.
- [ ] **Step 3: Implement** strict payload parsing, typed rejections, frozen Case revision, and `case_execution_created`/`case_execution_started` events through Task 3's transition port. Dispatch a step with `send_auto` using a deterministic command/idempotency identity derived from execution ID and ordinal. Attach `case_execution_id`, ordinal, and frozen context to the accepted step event. While a Case has a nonterminal step, reject new non-Case `send_*` commands with `case_execution_active` to prevent interleaving; after blocked, cancelled, or completed Case state, the Run accepts ordinary Turns again. Read-only Thread access remains available. Add a narrow context-lock query to `ThreadService` admission; do not fork profile/model logic in the Case service.
- [ ] **Step 4: Run** focused tests; expect pass. Commit `feat: admit Thread-native case commands`.

### Task 6: Terminal reconciliation, strict recovery, and worker tick

**Files:** Modify `case_service.py`, `thread_worker.py`, `cli.py`; create `tests/test_case_recovery.py`; modify `tests/test_thread_worker.py`, `tests/test_thread_postgres.py`.

**Interfaces:** `CaseExecutionService.reconcile(thread_id) -> CaseExecution` reads the trusted snapshot and contiguous events, then performs at most one idempotent transition while always returning the current typed execution. `CaseExecutionService.reconcile_active(limit: int = 32) -> int` enumerates active Case Threads through a public `ThreadService.active_application_threads(limit: int) -> tuple[str, ...]` port. `serve_thread_attempts(..., case_service: CaseExecutionService | None = None)` calls reconciliation before claiming and after completing an Attempt.

- [ ] **Step 1: Write failing tests** for successful three-step advancement, failed/cancelled/interrupted block, explicit retry creating a new Attempt under the same Turn, post-commit crash before next-step dispatch, restart from fresh Postgres service, and no half-resumed Attempt. In the same module define `start_and_finish_step(service: CaseExecutionService, phase: str) -> CaseExecution`, `case_service_from_same_postgres() -> CaseExecutionService`, and `count_step_turns(service: CaseExecutionService, ordinal: int) -> int`. Example:

```python
def test_restart_advances_only_after_committed_terminal_attempt(case_service: CaseExecutionService) -> None:
    first = start_and_finish_step(case_service, phase="completed")
    restarted = case_service_from_same_postgres()
    restarted.reconcile(first.thread_id)
    assert restarted.reconcile(first.thread_id).steps[1].status == "running"
    assert count_step_turns(restarted, ordinal=2) == 1
```

- [ ] **Step 2: Run** `pytest packages/capstone-agent/tests/test_case_recovery.py -q`; expect failures.
- [ ] **Step 3: Implement** idempotent terminal-event consumption, `case_step_completed`/`case_execution_blocked`/`case_execution_completed` transitions, explicit `case_retry_created`, and `case_execution_cancelled`. A missing event page, context mismatch, or uncertain terminal result blocks with a precise code and never dispatches the next step. `resume_case_execution` validates a committed successful step and creates only the next Turn. Reconciliation uses no runtime internals.
- [ ] **Step 4: Run** focused recovery/Postgres tests; expect pass. Commit `feat: reconcile case steps with strict recovery`.

### Task 7: Shared public interaction projection and clients

**Files:** Modify `thread_protocol.py`, `thread_service.py`, `thread_http.py`, `thread_tui.py`, `thread_fixture_runner.py`, `packages/capstone-app/src/threadProtocol.ts`, `threadClient.ts`; create `tests/test_case_projection.py`, `packages/capstone-app/src/threadCaseProjection.test.ts`.

**Interfaces:** `ThreadSnapshot.application_state` projects `CaseExecutionSnapshot` with `display_name`, `status`, `completed_steps`, `total_steps`, `current_step`, `steps`, `actions`, and `disabled_reasons`; each step projects title, status, duration, and Turn/Attempt/result/evidence refs for details. TypeScript `parseThreadSnapshot` rejects malformed Case state. Python HTTP and TUI clients reuse the same typed shape.

- [ ] **Step 1: Write failing cross-client fixtures** for idle, running, blocked, cancelled, completed, and resync with exact labels, action availability, and disabled reasons. Include one fixture where a raw internal ID changes but user-visible text does not.
- [ ] **Step 2: Run** `pytest packages/capstone-agent/tests/test_case_projection.py -q` and `npm --prefix packages/capstone-app test -- --run src/threadCaseProjection.test.ts`; expect failures.
- [ ] **Step 3: Implement** bounded, strict Python and TypeScript parsing and projection; put internal identities only in detail fields. Preserve existing Thread documents lacking Case state. CLI/TUI show the same status/actions without creating a second Case state machine.
- [ ] **Step 4: Run** focused Python/App tests; expect pass. Commit `feat: project shared case interaction state`.

### Task 8: Thread-native Web Case interaction

**Files:** Modify `ThreadLiveEntry.tsx`, `CapstoneAssistantThread.tsx`, `threadHttpTransport.ts`, `styles-light.css`; create `ThreadCaseInteraction.test.tsx`; modify existing `CapstoneAssistantThread.test.tsx`.

**Interfaces:** A compact Case picker starts a registered Case in the current Thread; conversation renders the Case progress adjacent to its current step; blocked step offers retry/stop; completed Case exposes process details. All actions use `CapstoneThreadClient` and current verified event cursor. The old `App.tsx` Case workspace stays hidden as historical reference in M6.

- [ ] **Step 1: Write failing interaction tests** for start, 1/3 progress, running duration, blocked retry, stop, disabled reason, and SSE resync. Example:

```tsx
it('shows a blocked step beside its retry action', () => {
  render(<ThreadCaseProgress execution={blockedCaseFixture} onAction={vi.fn()} />)
  expect(screen.getByText('步骤 2 未完成')).toBeVisible()
  expect(screen.getByRole('button', { name: '重试此步骤' })).toBeEnabled()
})
```

- [ ] **Step 2: Run** `npm --prefix packages/capstone-app test -- --run src/ThreadCaseInteraction.test.tsx`; expect failure.
- [ ] **Step 3: Implement** the approved compact layout; use existing assistant-ui message/runtime and existing left model pane. Do not render raw Case/Attempt IDs in normal UI. Keep actions stable with disabled reasons and keyboard labels; preserve composer focus and draft during Case progress.
- [ ] **Step 4: Run** focused App tests and `npm --prefix packages/capstone-app run build`; expect pass. Commit `feat: add Thread-native case controls to Web workspace`.

### Task 9: Boundary assertions, integration gates, and independent review

**Files:** Create `tests/test_case_architecture_boundary.py`; update `docs/RUNBOOK.md`, `README.md`, `README.zh-CN.md`, `docs/status/CURRENT-STATE.md`, `docs/status/RESUME-NEXT-SESSION.md`, and `docs/status/INDEX.md` only where facts or indexed status change. Keep JOURNAL append-only and uncommitted.

- [ ] **Step 1: Write boundary tests** that scan new Case/Harness implementation imports and reject `grid_agent`/`pypsa_agent` Case ownership, direct Authority/Pi calls from Case service, and compatibility package imports of `case_execution` internals. Assert the old stdout envelope remains one JSON object.
- [ ] **Step 2: Run** focused boundary tests; expect failure until all application roots use `capstone-agent` Case service.
- [ ] **Step 3: Finish** service wiring in the Capstone API/worker root, update reader-facing commands and recovery notes, then run `make capstone-local-rebuild`, `make doctor`, `make test`, `make test-e2e`, `make validate`, and `make check-release`. Record exact counts and API/worker image identity. Provider-billed validation remains separately authorized.
- [ ] **Step 4: Run** an independent M6 code review against the approved spec, fix every Important/Critical finding, rerun affected tests, and commit the review record with the final gate evidence. Commit `docs: close M6 verification and independent review` only after the evidence is complete.

## Execution Order and Stop Conditions

Tasks 1–3 establish trusted definitions, pure state, and atomic storage. Task 4 converges runtime selection behind the Harness; Task 5 admits commands; Task 6 makes execution crash-safe; Tasks 7–8 expose one shared interaction model; Task 9 closes the architecture and release gates. Each task must end with passing focused tests and a scoped commit. If an Attempt or Case cannot be proven continuous, block it with a recorded reason and require explicit retry or clean restart.
