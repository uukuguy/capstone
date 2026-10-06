from __future__ import annotations

from threading import Event, Thread

import pytest

from capstone_agent.harness import HarnessAttemptResult, HarnessAttemptRunner
from capstone_agent.thread_service import InMemoryThreadService, ThreadModelDescriptor
from capstone_agent.thread_protocol import ThreadSnapshot
from capstone_agent.thread_worker import run_pending_attempt, serve_thread_attempts


def _service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_worker",
        "run": {"run_id": "run_worker", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39",
            "model_revision": "revision:sha256:" + "a" * 64,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


class _Runtime:
    def start(self) -> None:
        return None

    def prompt(self, question: str, *, on_event, correlation_id=None, on_heartbeat=None) -> str:
        assert question == "inspect"
        return "done"

    def stop(self) -> None:
        return None


def _submit(service: InMemoryThreadService) -> None:
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_worker_001",
        "idempotency_key": "idem_worker_001", "thread_id": "thr_worker",
        "run_id": "run_worker", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "inspect"},
    })


def test_run_pending_attempt_claims_and_executes_without_http_affinity() -> None:
    service = _service()
    _submit(service)
    seen: list[str] = []

    def factory(claim):
        seen.append(claim.attempt.attempt_id)
        return _Runtime()

    result = run_pending_attempt(service, factory, worker_id="thread-worker")

    assert isinstance(result, HarnessAttemptResult)
    assert result.status == "completed"
    assert seen
    assert service.snapshot("thr_worker").current_attempt is None
    events = service.read_events("thr_worker", 0).events
    event_types = [event.event_type for event in events]
    assert event_types.index("turn_plan_created") < event_types.index("attempt_completed")
    assert event_types[event_types.index("turn_plan_created"):event_types.index("turn_plan_created") + 2] == [
        "turn_plan_created", "turn_route_selected",
    ]


def test_thread_worker_stops_when_requested() -> None:
    service = _service()
    stop = Event()
    stop.set()

    serve_thread_attempts(service, lambda _claim: _Runtime(), stop_event=stop)
    assert service.read_events("thr_worker", 0).events == ()


def test_thread_worker_keeps_polling_after_an_iteration_fails(monkeypatch, caplog) -> None:
    service = _service()
    _submit(service)
    stop = Event()
    calls: list[int] = []
    original = run_pending_attempt

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("ledger temporarily unavailable")
        result = original(*args, **kwargs)
        stop.set()
        return result

    monkeypatch.setattr("capstone_agent.thread_worker.run_pending_attempt", flaky)
    serve_thread_attempts(service, lambda _claim: _Runtime(), stop_event=stop, poll_seconds=0.001)
    assert len(calls) == 2
    assert service.read_events("thr_worker", 0).events[-1].event_type == "attempt_completed"
    assert "retrying after poll interval" in caplog.text


def test_worker_family_filter_leaves_other_family_attempt_unleased() -> None:
    service = _service()
    _submit(service)
    assert service.claim_attempt("pypsa-worker", 30, "pypsa") is None
    assert service.snapshot("thr_worker").current_attempt is not None
    claim = service.claim_attempt("grid-worker", 30, "pandapower")
    assert claim is not None


def test_thread_worker_reconciles_before_and_after_attempt() -> None:
    service = _service()
    _submit(service)
    stop = Event()
    calls: list[int] = []

    class _CaseService:
        def reconcile_active(self) -> int:
            calls.append(1)
            if len(calls) >= 2:
                stop.set()
            return 0

    # The stop event is set by the post-attempt reconciliation call.
    serve_thread_attempts(
        service, lambda _claim: _Runtime(), stop_event=stop,
        case_service=_CaseService(), poll_seconds=0.001,
    )
    assert calls[:2] == [1, 1]


def test_runtime_factory_failure_finishes_attempt_as_failed() -> None:
    service = _service()
    _submit(service)

    def factory(_claim):
        raise RuntimeError("runtime unavailable")

    result = run_pending_attempt(service, factory, worker_id="thread-worker")

    assert result is not None
    assert result.status == "failed"
    assert service.snapshot("thr_worker").current_attempt is None
    assert service.read_events("thr_worker", 0).events[-1].event_type == "attempt_failed"


@pytest.mark.parametrize("phase", ["factory", "startup", "prompt", "admission", "projection"])
def test_attempt_lease_survives_blocked_work_without_runtime_heartbeats(phase: str) -> None:
    service = _service()
    _submit(service)
    blocked, release = Event(), Event()
    renewals: list[bool] = []
    original_renew = service.renew_attempt

    def renew(claim, lease_seconds):
        renewals.append(original_renew(claim, lease_seconds))
        return renewals[-1]

    service.renew_attempt = renew

    def block(name: str) -> None:
        if phase == name:
            blocked.set()
            assert release.wait(4)

    class Runtime(_Runtime):
        network_projection_enabled = True

        def start(self):
            block("startup")

        def prompt(self, *_args, **_kwargs):
            block("prompt")
            return "done"

        def admit_attempt(self, *_args):
            block("admission")
            return None

        def network_projection(self, *_args):
            block("projection")
            return None

    def factory(_claim):
        block("factory")
        return Runtime()

    results: list[HarnessAttemptResult | None] = []
    thread = Thread(target=lambda: results.append(run_pending_attempt(
        service, factory, worker_id="thread-worker", lease_seconds=1,
    )), daemon=True)
    thread.start()
    try:
        assert blocked.wait(1)
        assert not release.wait(1.25)  # Exceed the claimed lease while work is blocked.
        assert service.interrupt_expired_attempts() == 0
    finally:
        release.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert results and results[0] is not None and results[0].status == "completed"
    count = len(renewals)
    Event().wait(0.4)
    assert len(renewals) == count, "renewal must stop when the Attempt ends"


@pytest.mark.parametrize("lost_during", ["factory", "startup"])
def test_lost_attempt_lease_stops_runtime_before_prompt(lost_during: str) -> None:
    service = _service()
    _submit(service)
    blocked, release, lost = Event(), Event(), Event()
    prompted: list[bool] = []
    stopped: list[bool] = []
    errors: list[Exception] = []
    original_renew = service.renew_attempt

    def renew(claim, lease_seconds):
        if blocked.is_set():
            service.finish_attempt(claim, phase="interrupted", payload={"reason": "lease_expired"})
            lost.set()
            return False
        return original_renew(claim, lease_seconds)

    service.renew_attempt = renew

    def block(name: str) -> None:
        if lost_during == name:
            blocked.set()
            assert release.wait(4)

    class Runtime(_Runtime):
        def start(self):
            block("startup")

        def prompt(self, *_args, **_kwargs):
            prompted.append(True)
            return "must not be committed"

        def stop(self):
            stopped.append(True)

    def factory(_claim):
        block("factory")
        return Runtime()

    def execute():
        try:
            run_pending_attempt(service, factory, worker_id="thread-worker", lease_seconds=1)
        except Exception as exc:
            errors.append(exc)

    thread = Thread(target=execute, daemon=True)
    thread.start()
    try:
        assert blocked.wait(1) and lost.wait(1)
    finally:
        release.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert errors and stopped and not prompted
    assert service.read_events("thr_worker", 0).events[-1].event_type == "attempt_interrupted"


def test_direct_harness_entry_renews_attempt_without_worker_wrapper() -> None:
    service = _service()
    _submit(service)
    claim = service.claim_attempt("direct-harness", lease_seconds=1)
    assert claim is not None

    class Runtime(_Runtime):
        def prompt(self, *_args, **_kwargs):
            Event().wait(1.25)
            assert service.interrupt_expired_attempts() == 0
            return "done"

    result = HarnessAttemptRunner(service, Runtime(), lease_seconds=1).run(claim)
    assert result.status == "completed"


def test_cancel_control_interrupts_runtime_at_heartbeat_and_commits_cancelled() -> None:
    service = _service()
    _submit(service)

    class _CancellableRuntime(_Runtime):
        def prompt(self, question: str, *, on_event, correlation_id=None, on_heartbeat=None) -> str:
            del on_event, correlation_id
            assert question == "inspect"
            assert on_heartbeat is not None
            claim = service._snapshot.current_attempt
            assert claim is not None
            receipt = service.submit_command({
                "schema": "capstone-command/1", "command_id": "cmd_cancel_worker",
                "idempotency_key": "idem_cancel_worker", "thread_id": "thr_worker",
                "run_id": "run_worker", "kind": "cancel_live_attempt",
                "expected_event_seq": service._snapshot.last_event_seq,
                "payload": {"attempt_id": claim.attempt_id},
            })
            assert receipt.status == "accepted"
            on_heartbeat()
            return "unreachable"

    result = run_pending_attempt(
        service, lambda _claim: _CancellableRuntime(), worker_id="thread-worker",
    )

    assert result is not None
    assert result.status == "cancelled"
    assert result.error_code == "attempt_cancelled"
    assert service.snapshot("thr_worker").current_attempt is None
    assert service.read_events("thr_worker", 0).events[-1].event_type == "attempt_cancelled"


def test_retry_control_reclaims_a_fresh_attempt_and_replays_the_instruction() -> None:
    service = _service()
    _submit(service)
    first = service.claim_attempt("thread-worker", lease_seconds=30)
    assert first is not None
    service.finish_attempt(first, phase="interrupted", payload={"reason": "lease_expired"})

    retry = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_retry_worker",
        "idempotency_key": "idem_retry_worker", "thread_id": "thr_worker",
        "run_id": "run_worker", "kind": "retry_new_attempt",
        "expected_event_seq": service.snapshot("thr_worker").last_event_seq,
        "payload": {"attempt_id": first.attempt.attempt_id},
    })
    assert retry.status == "accepted"
    assert retry.target is not None
    assert retry.target["attempt_id"] != first.attempt.attempt_id

    seen: list[str] = []

    class _RetryRuntime(_Runtime):
        def prompt(self, question: str, *, on_event, correlation_id=None, on_heartbeat=None) -> str:
            del on_event, correlation_id, on_heartbeat
            assert question == "inspect"
            return "retried"

    def factory(claim):
        seen.append(claim.attempt.attempt_id)
        return _RetryRuntime()

    result = run_pending_attempt(
        service, factory, worker_id="thread-worker",
    )

    assert result is not None
    assert result.status == "completed"
    assert seen == [retry.target["attempt_id"]]
    events = service.read_events("thr_worker", 0).events
    assert events[-1].event_type == "attempt_completed"
    assert events[-1].turn_id == first.attempt.turn_id
    assert events[-1].attempt_id == retry.target["attempt_id"]


def test_prepared_context_failure_rolls_back_new_selection_before_attempt_failure() -> None:
    service = _service()

    class _Catalog:
        def resolve(self, model, selection):
            return selection

    service.set_capability_catalog(_Catalog())
    staged = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_worker_profile",
        "idempotency_key": "idem_worker_profile", "thread_id": "thr_worker",
        "run_id": "run_worker", "kind": "enable_profile", "expected_event_seq": 0,
        "payload": {"profile_id": "static-analysis", "profile_version": "1.0.0"},
    })
    assert staged.status == "accepted"
    next_turn = service.submit_command({
        **{
            "schema": "capstone-command/1", "command_id": "cmd_worker_profile_turn",
            "idempotency_key": "idem_worker_profile_turn", "thread_id": "thr_worker",
            "run_id": "run_worker", "kind": "send_ordinary",
            "payload": {"text": "inspect"},
        },
        "expected_event_seq": service.snapshot("thr_worker").last_event_seq,
    })
    assert next_turn.status == "accepted"

    class _PreparationFailureFactory:
        rollback_selection_on_failure = True

        def __call__(self, _claim):
            raise RuntimeError("profile preparation failed")

    result = run_pending_attempt(
        service, _PreparationFailureFactory(), worker_id="thread-worker",
    )

    assert result is not None
    assert result.status == "failed"
    assert result.error_code == "capability_context_preparation_failed"
    snapshot = service.snapshot("thr_worker")
    assert snapshot.current_attempt is None
    assert snapshot.active_model_context.selection_revision == "sel_0"
    assert service.read_events("thr_worker", 0).events[-2].event_type == "selection_reverted"


def test_model_preparation_failure_commits_valid_snapshot_and_original_attempt_lineage() -> None:
    service = _service()

    class _Models:
        default_model_id = "ieee39"

        def resolve(self, model_id):
            assert model_id == "pypsa39"
            return ThreadModelDescriptor("pypsa39", "revision:sha256:" + "b" * 64, "pypsa")

    service.set_model_catalog(_Models())
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_worker_switch",
        "idempotency_key": "idem_worker_switch", "thread_id": "thr_worker",
        "run_id": "run_worker", "kind": "switch_model", "expected_event_seq": 0,
        "payload": {"model_id": "pypsa39"},
    })
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_worker_switch_turn",
        "idempotency_key": "idem_worker_switch_turn", "thread_id": "thr_worker",
        "run_id": "run_worker", "kind": "send_ordinary",
        "expected_event_seq": service.snapshot("thr_worker").last_event_seq,
        "payload": {"text": "inspect"},
    })

    class _PreparationFailureFactory:
        rollback_selection_on_failure = True

        def __call__(self, claim):
            assert claim.model_context.model_id == "pypsa39"
            raise RuntimeError("preparation failed")

    original_rollback = service.rollback_context_if_preparation_failed

    def observed_rollback(claim, *, error_code):
        result = original_rollback(claim, error_code=error_code)
        # Every snapshot visible after a public store operation must be valid.
        ThreadSnapshot.from_document(service.snapshot("thr_worker").to_document())
        return result

    service.rollback_context_if_preparation_failed = observed_rollback
    result = run_pending_attempt(service, _PreparationFailureFactory(), worker_id="thread-worker")
    assert result is not None and result.status == "failed"
    snapshot = ThreadSnapshot.from_document(service.snapshot("thr_worker").to_document())
    assert snapshot.active_model_context.model_id == "ieee39"
    events = service.read_events("thr_worker", 0).events
    assert [event.event_type for event in events[-2:]] == ["model_context_reverted", "attempt_failed"]
    activated = next(event for event in events if event.event_type == "model_context_activated")
    assert events[-1].model_context_id == activated.model_context_id
