# Agent Goal Mode Implementation Plan

> For agentic workers: use the approved design and implement each acceptance unit
> with local tests and review. Execute inline unless delegation is selected.

**Goal:** A standalone Capstone Agent can pursue an explicit Work objective across
bounded Attempts, stop safely, retain products and recover from durable state.

**Architecture:** Add an opt-in goal-mode lifecycle to the existing Work and Thread
ledger. Agent owns continuation; Harness still executes one claimed Attempt.
Control delegation, task boards and external triggers are later dependent stages.

**Tech Stack:** Existing Python services, PostgreSQL, native executor transport,
TypeScript App and existing test runners. No additional service or database.

**Status:** Design approved; implementation not started. Destination dev through
a scoped branch/PR. This document is the stage-A plan, not a second active worklist.
Design: [Capstone Control](../specs/2026-11-16-capstone-control-design.md).

## Global constraints

- Ordinary messages do not enable autonomous continuation.
- Keep historical snapshots and ordinary conversation behavior compatible.
- Keep one active Attempt per Thread; do not bypass native ownership fencing.
- Existing Authority, current-run evidence, resource and credential boundaries apply.
- Never automatically replay an unknown external effect.
- No new implementation branch is claimed by this planning document. At execution,
  record its owner, destination, acceptance and next step in the canonical register.
- Preserve the accepted enterprise UI and reuse conversation components.
- CI requires explicit per-run approval; focused local checks do not require it.
- No cloud deployment or full release suite is included.

## Source findings that constrain implementation

`thread_work.py::transition_work` currently maps Attempt terminal state to Work
status and consumes message input. Preserve that legacy projection. Goal mode needs
its own state and cannot infer success from Work.status == completed.
`create_attempt` binds an explicit start to the existing Attempt ledger; reuse this
admission path instead of creating a second executor queue.
`thread_worker.py::serve_thread_attempts` already has idle maintenance and wake
handling. Durable continuation must survive lost wake notifications and restart.
`task_steps.py` treats agent_task_progress as narrative/step tracking; it is not
a goal completion attestation. Do not repurpose old progress events as authority.

## Shared contracts

Create `packages/capstone-agent/src/capstone_agent/goal_mode.py` for pure contracts
and transition checks. Public Work projection adds optional `goal_mode`; absent
means legacy execution. Within it store schema `capstone-work-goal/1`, objective,
objective_revision, generation, state, reason, max_attempts, attempts_admitted,
deadline_at, last_settled_attempt_id and bounded progress/product references.
Use exact integer validation: booleans are not valid revisions or budgets.
`deadline_at` is a server-validated UTC instant; retries never reset budget.

Commands: `start_goal`, `pause_goal`, `resume_goal`, `revise_goal_objective`,
`cancel_goal`. Reuse command_id, idempotency_key, Work expected_revision and workspace
authorization. start requires objective, positive max_attempts and deadline_at.
Resume preserves budget; increasing budget requires an explicit versioned request.
No slash text is sent as a hidden ordinary instruction: App maps explicit `/goal`
interaction to this command contract. Literal text remains available as ordinary input.

The trusted host binds a model proposal to `capstone-work-goal-receipt/1`:
thread_id, work_id, objective_revision, generation, attempt_id, disposition
(`continue`, `wait`, `complete`), summary, next_instruction, waiting_reason and
product_refs. The host supplies identity; the model cannot select another Work.
`continue` requires a non-empty next instruction; `wait` requires a reason;
`complete` requires persisted delivery plus the applicable validation results.
Text-only tasks may complete with a saved answer rather than a fabricated artifact.
Missing or malformed receipts pause the goal with a typed reason and retain products.

Proposed pure API:

```python
def parse_goal_mode(value: object) -> dict: ...
def parse_goal_receipt(value: object) -> dict: ...
def decide_goal_boundary(goal: dict, receipt: dict, *, now: datetime) -> dict: ...
```

The declarations define new interfaces, not existing functions. The boundary result
contains state, reason and optional next_instruction; it performs no IO. It rejects
wrong objective revision/generation, checks deadlines/budget, and never makes a
new Attempt. The transactional service owns that mutation.

## Unit 1 — Persist and control an opt-in objective

Files: create goal_mode.py; modify thread_work.py, enterprise_context.py only where
new optional execution identity is required, thread_protocol.py, thread_service.py
and thread_http.py. Keep helpers out of the already large service where possible.
Tests: create tests/test_goal_mode.py and tests/test_goal_commands.py under
packages/capstone-agent; extend test_thread_work.py and test_thread_http_version.py.

- [ ] Write failing tests for exact schema validation, legacy snapshots without
  goal_mode, workspace isolation, stale revision, idempotent replay and conflicting
  aliases. Reuse InMemoryThreadService and the PostgreSQL fixtures.
- [ ] Implement the pure codec and command admission. Preserve old goal text and
  revision compatibility; reject incompatible duplicate field values.
- [ ] Implement pause/cancel intent before requesting runtime cancellation. An
  active goal remains visibly stopping until the Attempt has a terminal receipt.
  Revise stores a new generation; never mutate the active Attempt's frozen input.
- [ ] Run the unit selection below, review the owned diff and commit this unit.

Example mandatory schema test:

```python
@pytest.mark.parametrize('invalid', [True, 0, -1, 1.5, '2'])
def test_attempt_budget_requires_positive_integer(valid_goal, invalid):
    with pytest.raises(ValueError):
        parse_goal_mode({**valid_goal, 'max_attempts': invalid})
```

`valid_goal` is a local fixture containing every required field above, with an
aware fixed deadline; tests inject time rather than sleeping.

## Unit 2 — Bind structured execution receipts to admitted results

Files: create goal_receipts.py; modify harness.py, native_conversation.py,
general_pi_server.py and the selected native host tool registration only as needed.
Use the existing host-owned native research/control transport after inspecting its
registration contract; do not infer a fixed tool invocation order from availability.
Tests: create test_goal_receipts.py; extend test_harness.py and
test_general_pi_server.py for the transport and retained result behavior.

- [ ] Write failing tests for forged identity, mismatched revision, unpersisted
  products, malformed proposal, missing proposal, duplicate proposal and late receipt.
- [ ] Add a goal-only structured proposal channel. Publish it only for goal mode.
  The host attaches frozen Work/Attempt identity and validates referenced products.
  Model progress prose and agent_task_progress remain independent UI events.
- [ ] Persist the qualified goal receipt with the terminal Attempt transaction.
  Receipt persistence failure is fatal; never report goal completion without it.
- [ ] Verify normal conversation produces unchanged terminal answers and no goal
  continuation. Review and commit the focused changes.

## Unit 3 — Durable automatic continuation and recovery

Files: create goal_continuation.py; integrate thread_service.py, thread_worker.py
and thread_worker_capacity.py. Extend existing database initialization only if an
indexed durable pending marker cannot use the current ledger storage contract.
Tests: create test_goal_continuation.py and test_goal_postgres.py; extend
test_thread_recovery_reaper.py and test_worker_interruption_products.py.

- [ ] Write PostgreSQL race tests: duplicate terminal settlement, two maintenance
  workers, pause versus continuation, revise versus stale completion, cancellation
  versus admission, restart after terminal commit but before next admission.
- [ ] Under the existing Thread transaction lock, settle the exact prior Attempt,
  save the next-step intent, and count each newly admitted Attempt once. Key intent
  by thread/work/generation/predecessor_attempt_id. Admit through the same execution
  preparation path as explicit starts, with current permission checks and frozen input.
- [ ] Drain eligible durable intents through bounded worker maintenance and wake.
  A lost wake must delay work only until maintenance, never lose it. Deadline and
  budget checks run again at admission; waiting/paused goals consume no worker slot.
- [ ] Stop on unknown outcome or interrupted unsafe effects. Preserve products
  and require explicit reconciliation/resume; do not turn lease recovery into retry.
- [ ] Verify process-restart and concurrent-worker tests, review and commit.

Required assertions include: successor count == 1 for concurrent drainage;
attempts_admitted is unchanged by duplicate command replay; no successor after
pause/revise/cancel; old-generation receipts cannot complete the current objective.

## Unit 4 — Existing conversation entry and controls

Files: add goalMode.ts and goalMode.test.ts in packages/capstone-app/src; modify
threadWorkProtocol.ts, its tests, ThreadCommandMenu.tsx and the existing composer
and Work projection consumers located from their imports. Do not create a new chat.

- [ ] Add protocol tests for explicit start, budget validation, pause/resume/cancel,
  version conflicts and rendering a legacy snapshot.
- [ ] Add `/goal` to the existing command interaction. Show objective and bounded
  execution settings before submission; backend remains authoritative for limits.
- [ ] Render goal status separately from the current Attempt. Expose pause, resume,
  cancel and revise through existing controls. Preserve pending user text on conflict.
  Ordinary input while a goal runs must visibly steer/pause it before subsequent
  execution; it must not silently create concurrent work or disappear.
- [ ] Verify refresh restores state from the backend; remove/reconnect UI during
  execution without stopping the backend loop. Run focused tests and type checks.
- [ ] Rebuild with the canonical local command and inspect the existing Vivaldi
  tab against the accepted enterprise design before claiming UI acceptance.

## Unit 5 — Real acceptance, delivery and recovery baton

- [ ] Prepare a real model task that requires successive saved products. Check at
  least two qualified Attempts, actual tool execution and downloadable final content;
  if the model completes in one Attempt, that run does not prove continuation.
- [ ] During execution test pause, objective revision and cancellation. Prove no old
  successor executes; retain and reuse the saved partial product in a later Work.
- [ ] Restart API/worker at a durable boundary, reconnect the existing App tab, and
  prove exactly one successor plus original product retention. Test budget exhaustion.
- [ ] Review task-owned changes and record failures separately from accepted results.
  Update canonical worklist, register, journal and overview with implementation and
  local acceptance only. Use the required graph skill/browser checks for graph edits.
- [ ] Request one focused macOS CI approval only after changes and local evidence
  are ready. Merge through dev PR rules after approval; no automatic CI beforehand.
- [ ] Verify the actual dev entry point and use finite ignored closeout receipts;
  do not start a self-referential control-commit loop.

## Focused check commands

Run only tests whose files have been introduced by the current unit:

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_goal_mode.py packages/capstone-agent/tests/test_goal_commands.py packages/capstone-agent/tests/test_thread_work.py packages/capstone-agent/tests/test_thread_http_version.py -q
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_goal_receipts.py packages/capstone-agent/tests/test_harness.py packages/capstone-agent/tests/test_general_pi_server.py -q
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_goal_continuation.py packages/capstone-agent/tests/test_goal_postgres.py packages/capstone-agent/tests/test_thread_recovery_reaper.py packages/capstone-agent/tests/test_worker_interruption_products.py -q
npm run check --prefix packages/capstone-app
npm test --prefix packages/capstone-app -- src/goalMode.test.ts src/threadWorkProtocol.test.ts
git diff --check
```

PostgreSQL tests require an isolated disposable database using the existing test
fixture configuration; skipped database tests are not concurrency acceptance.
Real runtime acceptance uses `make capstone-local-rebuild`, protected existing
Provider settings and saved receipts under ignored runs/. Scoped cache maintenance
follows the repository rebuild rules. Record measured durations and actual outcomes.

## Plan review

Coverage: Unit 1 owns identity/compatibility/control; Unit 2 owns trustworthy
completion proposals; Unit 3 owns durable continuation/budgets/fencing; Unit 4 owns
the real user entry; Unit 5 owns real acceptance and integration. Long-term Goal,
cross-session delegation, task boards and event triggers are explicitly stages B–D,
not missing stage-A implementation. No runtime capability is claimed by this plan.
