from __future__ import annotations

from threading import Event

from capstone_agent.harness import HarnessAttemptResult
from capstone_agent.thread_service import InMemoryThreadService
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


def test_thread_worker_stops_when_requested() -> None:
    service = _service()
    stop = Event()
    stop.set()

    serve_thread_attempts(service, lambda _claim: _Runtime(), stop_event=stop)
    assert service.read_events("thr_worker", 0).events == ()


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
