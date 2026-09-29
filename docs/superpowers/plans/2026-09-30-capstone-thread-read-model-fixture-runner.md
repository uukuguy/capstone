# Capstone Thread Read Model and Fixture Runner Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with TDD. The public contract is intentionally small; do not import legacy Case/session types into it.

**Goal:** Freeze the minimum `capstone-thread/1` read-model and receipt shapes, then validate the Web/TUI fixture states against one strict event projection.

**Architecture:** `capstone-agent` owns the first internal implementation of the public Thread contract. The contract validates JSON documents without exposing Pi/DSH native events, provider secrets, raw network objects, or Domain Pack internals. A fixture runner consumes verified `ThreadSnapshot` plus contiguous `EventPage` values and returns semantic action assertions; Web and TUI will later adapt the same JSON without duplicating business state.

**Tech Stack:** Python 3.12, frozen dataclasses, standard-library JSON/time validation, pytest, checked-in JSON fixtures.

## Global Constraints

- Public clients use one `capstone-thread/1` contract for `ThreadSnapshot`, `EventPage`, `CommandReceipt`, and event envelopes.
- Snapshot recovery is strict: `base_event_seq` is verified, event pages are contiguous, and gaps fail closed with `resync_required`.
- Public events contain bounded normalized payloads; Pi/DSH native events remain diagnostics and are not accepted as business state.
- The fixture runner validates semantic action sets, not DOM nodes, terminal escape sequences, hidden model reasoning, or provider output.
- Existing `grid-agent` compatibility output and legacy `SessionStatus` remain unchanged.
- Tests run without Provider credentials and must not read ignored runtime/authentication state.

---

### Task 1: Freeze the public Thread read-model types

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/thread_protocol.py`
- Test: `packages/capstone-agent/tests/test_thread_protocol.py`

**Interfaces:**
- Produces `THREAD_PROTOCOL = "capstone-thread/1"`.
- Produces frozen `ThreadSnapshot`, `EventEnvelope`, `EventPage`, and `CommandReceipt` dataclasses with `from_document()` and `to_document()` methods.
- Raises `ThreadProtocolError` for unknown fields, missing fields, invalid identifiers, non-contiguous event sequences, invalid `base_event_seq`, or non-JSON payloads.

- [x] **Step 1: Write the failing tests**

  Add tests that require:

  ```python
  def test_snapshot_round_trips_with_active_context_and_attempt() -> None:
      snapshot = ThreadSnapshot.from_document(valid_snapshot())
      assert snapshot.thread_id == "thr_demo_39"
      assert snapshot.active_model_context.model_revision == "7"
      assert snapshot.to_document()["schema"] == "capstone-thread-snapshot/1"

  def test_event_page_rejects_a_gap_after_the_snapshot() -> None:
      with pytest.raises(ThreadProtocolError, match="contiguous"):
          EventPage.from_document(valid_page(events=[event(181), event(183)]),
                                  expected_after_seq=180)

  def test_snapshot_rejects_provider_or_native_runtime_payload_fields() -> None:
      document = valid_snapshot()
      document["provider_token"] = "secret"
      with pytest.raises(ThreadProtocolError, match="unknown field"):
          ThreadSnapshot.from_document(document)

  def test_receipt_preserves_command_identity_and_status() -> None:
      receipt = CommandReceipt.from_document(valid_receipt())
      assert receipt.command_id == "cmd_switch_005"
      assert receipt.status == "accepted"
  ```

- [x] **Step 2: Run the focused tests and verify the expected RED failure**

  Run: `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_protocol.py -q`

  Expected: collection fails because `capstone_agent.thread_protocol` does not exist.

- [x] **Step 3: Implement the smallest strict contract**

  Define only the following public fields:

  ```text
  ThreadSnapshot:
    schema, thread_id, run, active_model_context, active_grid_page_id,
    current_attempt, last_event_seq, base_event_seq
  EventEnvelope:
    event_id, event_seq, event_type, event_version, thread_id, run_id,
    turn_id?, attempt_id?, model_context_id?, selection_revision?,
    occurred_at, visibility, payload
  EventPage:
    schema, thread_id, after_event_seq, next_event_seq, has_more, events
  CommandReceipt:
    schema, command_id, idempotency_key, thread_id, run_id?, status,
    accepted_event_seq?, rejection?, target?
  ```

  Use frozen dataclasses and explicit `frozenset` field allowlists. Validate IDs as bounded lowercase/number/dash identifiers, revisions as non-empty strings, sequences as non-negative integers, `visibility` as `public` or `diagnostic`, and payloads with `json.dumps(..., allow_nan=False)`. Keep nested `run`, `active_model_context`, and `current_attempt` as typed frozen values; allow `current_attempt` to be `None`.

- [x] **Step 4: Run the focused tests and verify GREEN**

  Run: `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_protocol.py -q`

  Expected: all protocol tests pass.

- [x] **Step 5: Commit the contract**

  ```bash
  git add packages/capstone-agent/src/capstone_agent/thread_protocol.py packages/capstone-agent/tests/test_thread_protocol.py
  git commit -m "feat: add capstone thread read model contract"
  ```

### Task 2: Add canonical fixture documents

**Files:**
- Create: `packages/capstone-agent/tests/fixtures/thread-ui/idle-ieee39.json`
- Create: `packages/capstone-agent/tests/fixtures/thread-ui/historical-live-attempt.json`
- Create: `packages/capstone-agent/tests/fixtures/thread-ui/resync-required.json`
- Create: `packages/capstone-agent/tests/fixtures/thread-ui/interrupted-attempt.json`
- Create: `packages/capstone-agent/tests/thread_fixtures.py`
- Test: `packages/capstone-agent/tests/test_thread_fixtures.py`

**Interfaces:**
- Each JSON file contains `fixture_id`, `snapshot`, `events`, `local_view`, and `assertions` as defined in `2026-09-30-capstone-ui-state-fixtures.md`.
- Test helper `packages/capstone-agent/tests/thread_fixtures.py:load_fixture(name)` returns a parsed mapping after validating `snapshot` and `events` through Task 1 types.

- [x] **Step 1: Write the failing fixture-loader tests**

  Require all four fixture files to load and require the historical fixture to expose `viewed_grid_page_id != active_grid_page_id` while preserving the active Attempt target.

- [x] **Step 2: Run the tests and verify RED**

  Run: `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_fixtures.py -q`

  Expected: failure because the fixture files and loader do not exist.

- [x] **Step 3: Add the smallest four JSON fixtures and test helper loader**

  Keep payloads bounded and deterministic. Use no provider output. The resync fixture must set `snapshot.base_event_seq` to the replacement sequence and include no event before that base. The interrupted fixture must include `retry_new_attempt` in its expected semantic actions.

- [x] **Step 4: Run the fixture tests and verify GREEN**

  Run: `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_fixtures.py -q`

- [x] **Step 5: Commit the fixtures**

  ```bash
  git add packages/capstone-agent/tests/fixtures/thread-ui packages/capstone-agent/tests/test_thread_fixtures.py
  git commit -m "test: add capstone thread ui fixtures"
  ```

### Task 3: Implement the semantic fixture runner

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/thread_fixture_runner.py`
- Test: `packages/capstone-agent/tests/test_thread_fixture_runner.py`
- Modify: `packages/capstone-agent/tests/test_thread_fixtures.py`

**Interfaces:**
- Produces `FixtureProjection` with `active_model_context_id`, `active_grid_page_id`, `viewed_grid_page_id`, `current_attempt_id`, `authority_labels`, and `enabled_commands`.
- Produces `run_fixture(document) -> FixtureProjection`.
- Produces `expected_commands(document, surface) -> frozenset[str]` for `web`, `tui`, and `cli`.

- [x] **Step 1: Write failing runner tests**

  Cover these assertions:

  ```python
  def test_historical_page_keeps_live_cancel_target() -> None:
      projection = run_fixture(load_fixture("historical-live-attempt"))
      assert projection.active_grid_page_id == "page_ieee39"
      assert projection.viewed_grid_page_id == "page_scigrid_2"
      assert "cancel_live_attempt" in projection.enabled_commands
      assert "send_professional" not in projection.enabled_commands

  def test_gap_fixture_is_resync_required_and_has_no_business_commands() -> None:
      projection = run_fixture(load_fixture("resync-required"))
      assert projection.transport_state == "resync_required"
      assert projection.enabled_commands == frozenset({"reconnect", "resync", "help", "exit"})

  def test_all_surfaces_share_the_same_semantic_command_set() -> None:
      fixture = load_fixture("interrupted-attempt")
      assert expected_commands(fixture, "web") == expected_commands(fixture, "tui")
      assert expected_commands(fixture, "tui") == expected_commands(fixture, "cli")
  ```

- [x] **Step 2: Run the tests and verify RED**

  Run: `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_fixture_runner.py -q`

  Expected: failure because the runner module does not exist.

- [x] **Step 3: Implement a projection-only runner**

  Apply only state events needed by the fixtures: `model_context_activated`, `attempt_started`, `attempt_progress`, `approval_requested`, `attempt_cancelled`, `attempt_interrupted`, and `run_closed`. Treat `grid_page_viewed` as local view state from `local_view`; do not mutate the active context. Derive the action set from transport, execution, view, and context axes in the wireframes. Do not classify user text and do not infer authority from answer prose.

- [x] **Step 4: Run the focused runner tests and the existing capstone-agent tests**

  Run: `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_fixture_runner.py packages/capstone-agent/tests/test_thread_fixtures.py -q` and then `make test`.

  Expected: focused tests and the repository suite pass without Provider credentials.

- [x] **Step 5: Commit the runner**

  ```bash
  git add packages/capstone-agent/src/capstone_agent/thread_fixture_runner.py packages/capstone-agent/tests/test_thread_fixture_runner.py packages/capstone-agent/tests/test_thread_fixtures.py
  git commit -m "test: validate shared thread ui projections"
  ```

## Plan self-review

- The plan freezes read-model and receipt names before any Web/TUI component work.
- The four fixture files are intentionally a first slice; the remaining six named fixture states can be added without changing the contract.
- The runner does not own persistence, transport, Pi/DSH sessions, Domain Pack semantics, or Authority truth.
- Existing compatibility `SessionStatus` and `grid-agent` output remain outside this plan.
- No provider credentials or ignored runtime state are needed for any task.
