from __future__ import annotations

from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.session import WorkerRegistry
from capstone_agent.thread_application import ApplicationPiRuntimeFactory
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_service import AttemptClaim
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt


class _Session:
    def start(self) -> None:
        return None

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        del question, kwargs
        return "answer"

    def stop(self) -> None:
        return None


class _CreatorService:
    def __init__(self) -> None:
        self.snapshot = None

    def create_thread(self, snapshot):
        self.snapshot = snapshot
        return snapshot


class _Ledger:
    def ping(self) -> bool:
        return True


def _runtime_service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_runtime",
        "run": {"run_id": "run_runtime", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39",
            "model_revision": "revision:sha256:" + "d" * 64,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


def _claim() -> AttemptClaim:
    return AttemptClaim(
        thread_id="thr_application", run_id="run_application",
        attempt=AttemptSnapshot("turn_1", "attempt_1", "running", "ctx_ieee39"),
        kind="send_ordinary", instruction="inspect", model_context_id="ctx_ieee39",
        selection_revision="sel_0", lease_token="lease_1",
        model_context=ModelContextSnapshot(
            "ctx_ieee39", "ieee39", "revision:sha256:" + "a" * 64, "pandapower", "sel_0",
        ),
    )


def test_application_factory_wraps_injected_session_as_harness_runtime() -> None:
    received: list[AttemptClaim] = []
    factory = ApplicationPiRuntimeFactory(
        lambda claim: received.append(claim) or _Session(), runtime_mode="capstone",
    )

    runtime = factory(_claim())
    runtime.start()
    assert runtime.prompt("inspect", on_event=lambda _event: None) == "answer"
    runtime.stop()
    assert received[0].attempt.attempt_id == "attempt_1"


def test_application_assembly_binds_authority_catalog_and_pi_factory() -> None:
    service = _CreatorService()
    sessions: list[AttemptClaim] = []
    assembly = ThreadApplicationAssembly.from_authority(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "b" * 64,
            "implementation_family": "pandapower",
        },
        session_factory=lambda claim: sessions.append(claim) or _Session(),
    )

    created = assembly.thread_creator(service).create()
    assert created.active_model_context.model_revision == "revision:sha256:" + "b" * 64
    runtime = assembly.runtime_factory(_claim())
    runtime.start()
    assert runtime.prompt("inspect", on_event=lambda _event: None) == "answer"
    runtime.stop()
    assert sessions[0].attempt.attempt_id == "attempt_1"


def test_application_assembly_requires_catalog_and_runtime_together() -> None:
    try:
        ThreadApplicationAssembly(catalog=object(), runtime_factory=None)  # type: ignore[arg-type]
    except TypeError:
        return
    raise AssertionError("invalid assembly must fail closed")


def test_host_app_can_accept_the_complete_application_assembly() -> None:
    service = _CreatorService()
    assembly = ThreadApplicationAssembly.from_authority(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "c" * 64,
            "implementation_family": "pandapower",
        },
        session_factory=lambda _claim: _Session(),
    )
    app = create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service, thread_application=assembly,
    )

    with TestClient(app, base_url="http://localhost") as client:
        response = client.post(
            "/api/v1/threads",
            headers={"Authorization": "Bearer hosted-secret"},
            json={},
        )

    assert response.status_code == 201
    assert response.json()["active_model_context"]["model_revision"] == (
        "revision:sha256:" + "c" * 64
    )


def test_assembly_runtime_worker_and_sse_share_one_thread_contract() -> None:
    service = _runtime_service()
    assembly = ThreadApplicationAssembly.from_authority(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "d" * 64,
            "implementation_family": "pandapower",
        },
        session_factory=lambda _claim: _Session(),
    )
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_runtime_001",
        "idempotency_key": "idem_runtime_001", "thread_id": "thr_runtime",
        "run_id": "run_runtime", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "inspect"},
    })

    result = run_pending_attempt(
        service, assembly.runtime_factory, worker_id="assembly-worker",
    )
    assert result is not None and result.status == "completed"

    app = create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service, thread_application=assembly,
    )
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/v1/threads/thr_runtime").status_code == 401
        stream = client.get(
            "/api/v1/threads/thr_runtime/events/stream?after=0",
            headers={"Authorization": "Bearer hosted-secret"},
        )

    assert stream.status_code == 200
    assert "event: command_accepted" in stream.text
    assert "event: attempt_started" in stream.text
    assert "event: attempt_completed" in stream.text
