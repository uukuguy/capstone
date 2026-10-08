from __future__ import annotations

import hashlib

import pytest

from fastapi.testclient import TestClient

from capstone_agent.case_definition import CaseCatalog, CaseDefinition, CaseStepDefinition
from capstone_agent.case_service import CaseExecutionService
from capstone_agent.host_api import create_host_app
from capstone_agent.session import WorkerRegistry
from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_service import InMemoryThreadService, PostgresThreadService
from capstone_agent.thread_catalog import CompositeThreadModelCatalog, ThreadModelCatalogEntry


class _ModelCatalog:
    default_model_id = "ieee39"

    def resolve(self, model_id: str | None):
        raise AssertionError(f"resolve is not needed for catalog projection: {model_id}")

    def list_entries(self):
        return (
            ThreadModelCatalogEntry("ieee39", "gridctl:ieee39", "IEEE-39", "pandapower", "pandapower"),
            ThreadModelCatalogEntry("pypsa-example/scigrid_de", "pypsa:scigrid_de", "SciGrid-DE", "pypsa", "pypsa"),
        )


class _Profile:
    def __init__(self, profile_id: str, version: str, name: str, families: tuple[str, ...]):
        self.descriptor = type("Descriptor", (), {"profile_id": profile_id, "profile_version": version})()
        self.display_name = name
        self.implementation_families = families


class _CapabilityCatalog:
    def resolve(self, model, selection=None):
        return selection

    def profiles_for_family(self, family: str):
        return {
            "pandapower": (_Profile("pandapower-static-analysis", "1.0.1", "Pandapower Static Analysis", ("pandapower",)),),
            "pypsa": (_Profile("pypsa-business-cases", "1.0.0", "PyPSA Business Cases", ("pypsa",)),),
        }.get(family, ())


def _service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1",
        "thread_id": "thr_demo_39",
        "run": {"run_id": "run_001", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39_7", "model_id": "ieee39", "model_revision": "7",
            "implementation_family": "pandapower", "selection_revision": "sel_2",
        },
        "active_grid_page_id": "page_ieee39",
        "current_attempt": None,
        "last_event_seq": 0,
        "base_event_seq": 0,
    })


class _Ledger:
    def ping(self) -> bool:
        return True


def _app(service: InMemoryThreadService, wake_worker=None, prepare_workers=None):
    return create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service,
        wake_worker=wake_worker,
        prepare_workers=prepare_workers,
    )


def _case_app(service: InMemoryThreadService):
    catalog = CaseCatalog(
        (
            CaseDefinition(
                case_id="case_demo",
                case_version="1",
                case_revision="case:sha256:demo",
                display_name="Demo case",
                description="A case for the HTTP command boundary.",
                model_ids=("ieee39",),
                steps=(
                    CaseStepDefinition(
                        1,
                        "First",
                        "inspect the network",
                        hashlib.sha256(b"inspect the network").hexdigest(),
                    ),
                ),
            ),
        ),
    )
    return create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service,
        case_service=CaseExecutionService(catalog, service),
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer hosted-secret", "Origin": "http://localhost:5173"}


def test_opened_model_projection_uses_the_private_thread_boundary():
    service = _service()
    with TestClient(_app(service), base_url="http://localhost") as client:
        path = "/api/v1/threads/thr_demo_39/models"
        assert client.get(path).status_code == 401
        response = client.get(path, headers=_auth())
    assert response.status_code == 200
    workspace = response.json()
    assert workspace["thread_id"] == "thr_demo_39"
    assert len(workspace["models"]) == 1
    assert workspace["models"][0]["model_id"] == "ieee39"
    assert workspace["current_entry_id"] == workspace["models"][0]["entry_id"]


@pytest.mark.parametrize("kind", ["switch_model", "reopen_model_context"])
def test_unregistered_model_command_returns_a_rejection_without_changing_thread(kind) -> None:
    service = _service()
    service.set_model_catalog(CompositeThreadModelCatalog(default_model_id="ieee39"))
    before = service.snapshot("thr_demo_39")
    command = getattr(ThreadCommandFactory("thr_demo_39"), kind)(
        "missing-model", expected_event_seq=0,
        command_id="cmd_missing", idempotency_key="idem_missing",
    )
    with TestClient(_app(service), base_url="http://localhost") as client:
        response = client.post(
            "/api/v1/threads/thr_demo_39/commands", headers=_auth(), json=command,
        )
    assert response.status_code == 202
    assert response.json()["status"] == "rejected"
    assert response.json()["rejection"] == "model_unavailable"
    assert service.snapshot("thr_demo_39") == before


def test_postgres_model_admission_handles_the_composite_catalog_lookup_error() -> None:
    service = PostgresThreadService("postgresql://unused")
    service.set_model_catalog(CompositeThreadModelCatalog(default_model_id="ieee39"))
    command = ThreadCommandFactory("thr_demo_39").switch_model(
        "missing-model", expected_event_seq=0,
        command_id="cmd_missing", idempotency_key="idem_missing",
    )
    assert service._model_switch_for_command(
        _service().snapshot("thr_demo_39"), command,
    ) == (None, "model_unavailable")


def test_thread_snapshot_and_event_page_are_exposed_as_capstone_protocol() -> None:
    service = _service()
    with TestClient(_app(service), base_url="http://localhost") as client:
        snapshot = client.get("/api/v1/threads/thr_demo_39", headers=_auth())
        assert snapshot.status_code == 200
        assert snapshot.json()["schema"] == "capstone-thread-snapshot/1"

        events = client.get("/api/v1/threads/thr_demo_39/events", headers=_auth())
        assert events.status_code == 200
        assert events.json() == {
            "schema": "capstone-thread-events/1",
            "thread_id": "thr_demo_39",
            "after_event_seq": 0,
            "next_event_seq": 0,
            "has_more": False,
            "events": [],
        }


def test_thread_catalog_projects_registered_models_and_profiles() -> None:
    service = _service()
    service.set_model_catalog(_ModelCatalog())
    service.set_capability_catalog(_CapabilityCatalog())

    catalog = service.catalog("thr_demo_39")

    assert catalog["schema"] == "capstone-thread-catalog/1"
    assert [entry["model_id"] for entry in catalog["models"]] == [
        "ieee39", "pypsa-example/scigrid_de",
    ]
    assert catalog["profiles"] == [
        {
            "profile_id": "pandapower-static-analysis",
            "profile_version": "1.0.1",
            "display_name": "Pandapower Static Analysis",
            "implementation_families": ["pandapower"],
        },
        {
            "profile_id": "pypsa-business-cases",
            "profile_version": "1.0.0",
            "display_name": "PyPSA Business Cases",
            "implementation_families": ["pypsa"],
        },
    ]


def test_thread_catalog_marks_family_without_a_ready_worker_unavailable() -> None:
    service = _service()
    service.set_model_catalog(_ModelCatalog())
    service.set_available_families(frozenset({"pandapower"}))

    models = {entry["model_id"]: entry for entry in service.catalog("thr_demo_39")["models"]}

    assert models["ieee39"]["available"] is True
    assert models["pypsa-example/scigrid_de"]["available"] is False
    assert models["pypsa-example/scigrid_de"]["unavailable_reason"] == "worker_unavailable"


@pytest.mark.parametrize("backend", ["memory", "postgres"])
def test_thread_catalog_and_family_gate_follow_worker_recovery_without_api_restart(backend, monkeypatch) -> None:
    service = _service() if backend == "memory" else PostgresThreadService("postgresql://fixture")
    if backend == "postgres":
        monkeypatch.setattr(service, "snapshot", lambda _thread_id: _service().snapshot("thr_demo_39"))
    service.set_model_catalog(_ModelCatalog())
    ready = {"pandapower"}
    service.set_available_families(lambda: frozenset(ready))

    def available():
        return {m["model_id"]: m["available"] for m in service.catalog("thr_demo_39")["models"]}

    assert available()["pypsa-example/scigrid_de"] is False
    assert not service.is_family_available("pypsa")
    ready.add("pypsa")
    assert available()["pypsa-example/scigrid_de"] is True
    assert service.is_family_available("pypsa")
    ready.remove("pypsa")
    assert available()["pypsa-example/scigrid_de"] is False
    assert not service.is_family_available("pypsa")


def test_worker_availability_callback_rejects_invalid_projection() -> None:
    service = _service()
    service.set_available_families(lambda: frozenset({"unregistered/endpoint"}))
    with pytest.raises(ValueError, match="implementation families"):
        service.is_family_available("pypsa")


def test_thread_catalog_is_exposed_over_the_authenticated_thread_route() -> None:
    service = _service()
    service.set_model_catalog(_ModelCatalog())
    service.set_capability_catalog(_CapabilityCatalog())

    with TestClient(_app(service), base_url="http://localhost") as client:
        response = client.get("/api/v1/threads/thr_demo_39/catalog", headers=_auth())

    assert response.status_code == 200
    assert response.json()["schema"] == "capstone-thread-catalog/1"
    assert response.json()["models"][1]["display_name"] == "SciGrid-DE"


def test_thread_command_is_idempotent_and_emits_a_replayable_event() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1",
        "command_id": "cmd_turn_001",
        "idempotency_key": "idem_turn_001",
        "thread_id": "thr_demo_39",
        "run_id": "run_001",
        "kind": "send_ordinary",
        "expected_event_seq": 0,
        "payload": {"text": "hello"},
    }
    with TestClient(_app(service), base_url="http://localhost") as client:
        first = client.post("/api/v1/threads/thr_demo_39/commands", headers=_auth(), json=command)
        second = client.post("/api/v1/threads/thr_demo_39/commands", headers=_auth(), json=command)
        assert first.status_code == second.status_code == 202
        assert first.json() == second.json()
        assert first.json()["status"] == "accepted"
        assert first.json()["accepted_event_seq"] == 1

        events = client.get("/api/v1/threads/thr_demo_39/events", headers=_auth()).json()
        assert events["next_event_seq"] == 1
        assert events["events"][0]["event_type"] == "command_accepted"


def test_accepted_thread_command_wakes_worker_but_rejected_command_does_not():
    service = _service()
    wakes = []
    with TestClient(_app(service, wake_worker=lambda: wakes.append(1)), base_url='http://localhost') as client:
        rejected = client.post('/api/v1/threads/thr_demo_39/commands', headers=_auth(), json={
            'schema': 'capstone-command/1', 'command_id': 'cmd_bad', 'idempotency_key': 'idem_bad',
            'thread_id': 'thr_demo_39', 'run_id': 'run_001', 'kind': 'not_registered', 'expected_event_seq': 0, 'payload': {},
        })
        assert rejected.json()['status'] == 'rejected'
        assert wakes == []
        accepted = client.post('/api/v1/threads/thr_demo_39/commands', headers=_auth(), json={
            'schema': 'capstone-command/1', 'command_id': 'cmd_wake', 'idempotency_key': 'idem_wake',
            'thread_id': 'thr_demo_39', 'run_id': 'run_001', 'kind': 'send_ordinary', 'expected_event_seq': service.snapshot('thr_demo_39').last_event_seq,
            'payload': {'text': 'inspect'},
        })
        assert accepted.json()['status'] == 'accepted'
        assert wakes == [1]
        # Each accepted receipt must wake the scheduler, even inside the
        # legacy read throttle window. The worker may already have drained.
        replay = client.post('/api/v1/threads/thr_demo_39/commands', headers=_auth(), json={
            'schema': 'capstone-command/1', 'command_id': 'cmd_wake', 'idempotency_key': 'idem_wake',
            'thread_id': 'thr_demo_39', 'run_id': 'run_001', 'kind': 'send_ordinary',
            'expected_event_seq': 0, 'payload': {'text': 'inspect'},
        })
        assert replay.json()['status'] == 'accepted'
        assert wakes == [1, 1]


def test_thread_entry_waits_for_database_and_all_worker_wakes():
    ready = False
    with TestClient(_app(_service(), wake_worker=lambda: ready), base_url='http://localhost') as client:
        assert client.get('/api/v1/thread-access').status_code == 503
        ready = True
        response = client.get('/api/v1/thread-access')
        assert response.status_code == 200
        assert response.json()['mode'] == 'operator'


def test_workbench_preparation_streams_actual_component_readiness():
    import json
    def workers():
        yield {'component': 'worker:pandapower', 'status': 'preparing'}
        yield {'component': 'worker:pandapower', 'status': 'ready'}
    with TestClient(_app(_service(), prepare_workers=workers), base_url='http://localhost') as client:
        response = client.get('/api/v1/workbench-preparation')
        assert response.status_code == 200
        updates = [json.loads(line) for line in response.text.splitlines()]
        assert [(item['component'], item['status']) for item in updates] == [
            ('api', 'ready'), ('database', 'preparing'), ('database', 'ready'),
            ('worker:pandapower', 'preparing'), ('worker:pandapower', 'ready'), ('workbench', 'ready'),
        ]
        assert updates[-1]['complete'] is True
        assert response.headers['cache-control'] == 'no-store'


def test_failed_component_never_admits_workbench():
    import json
    def workers():
        yield {'component': 'worker:pypsa', 'status': 'failed'}
    with TestClient(_app(_service(), prepare_workers=workers), base_url='http://localhost') as client:
        response = client.get('/api/v1/workbench-preparation')
        updates = [json.loads(line) for line in response.text.splitlines()]
        assert updates[-1]['status'] == 'failed'
        assert not any(item.get('complete') for item in updates)


def test_case_command_route_is_operator_only_and_uses_case_service() -> None:
    service = _service()
    command = ThreadCommandFactory("thr_demo_39", "run_001").start_case_execution(
        "case_demo",
        expected_event_seq=0,
        command_id="cmd_case_start",
        idempotency_key="idem_case_start",
    )
    with TestClient(_case_app(service), base_url="http://localhost") as client:
        unauthorized = client.post(
            "/api/v1/threads/thr_demo_39/commands",
            json=command,
        )
        accepted = client.post(
            "/api/v1/threads/thr_demo_39/commands",
            headers=_auth(),
            json=command,
        )

    assert unauthorized.status_code == 401
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "accepted"


def test_thread_command_with_unhashable_kind_returns_422() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1",
        "command_id": "cmd_bad_kind",
        "idempotency_key": "idem_bad_kind",
        "thread_id": "thr_demo_39",
        "run_id": "run_001",
        "kind": ["start_case_execution"],
        "expected_event_seq": 0,
        "payload": {"text": "hello"},
    }
    with TestClient(_case_app(service), base_url="http://localhost") as client:
        response = client.post(
            "/api/v1/threads/thr_demo_39/commands",
            headers=_auth(),
            json=command,
        )

    assert response.status_code == 422


def test_thread_cursor_gap_returns_verified_resync_snapshot() -> None:
    service = _service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_turn_001",
        "idempotency_key": "idem_turn_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    service.compact_before(1)
    with TestClient(_app(service), base_url="http://localhost") as client:
        response = client.get(
            "/api/v1/threads/thr_demo_39/events?after=0", headers=_auth(),
        )
        assert response.status_code == 409
        assert response.json()["error"] == "resync_required"
        assert response.json()["snapshot"]["schema"] == "capstone-thread-snapshot/1"


def test_thread_sse_reuses_the_same_event_cursor() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1", "command_id": "cmd_turn_001",
        "idempotency_key": "idem_turn_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    }
    with TestClient(_app(service), base_url="http://localhost") as client:
        client.post("/api/v1/threads/thr_demo_39/commands", headers=_auth(), json=command)
        stream = client.get("/api/v1/threads/thr_demo_39/events/stream?after=0", headers=_auth())
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "id: 1" in stream.text
        assert "event: command_accepted" in stream.text


def test_thread_sse_cursor_gap_returns_resync_snapshot() -> None:
    service = _service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_sse_gap_001",
        "idempotency_key": "idem_sse_gap_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    service.compact_before(1)

    with TestClient(_app(service), base_url="http://localhost") as client:
        response = client.get(
            "/api/v1/threads/thr_demo_39/events/stream?after=0", headers=_auth(),
        )

    assert response.status_code == 409
    assert response.json()["error"] == "resync_required"
    assert response.json()["snapshot"]["last_event_seq"] == 1


def test_thread_rejects_unknown_command_kind_without_emitting_an_acceptance_event() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1", "command_id": "cmd_unknown_001",
        "idempotency_key": "idem_unknown_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "execute_shell", "expected_event_seq": 0,
        "payload": {"command": "echo unsafe"},
    }
    receipt = service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "unsupported_command"
    assert service.snapshot("thr_demo_39").last_event_seq == 0


def test_thread_rejects_message_without_nonempty_text() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1", "command_id": "cmd_empty_001",
        "idempotency_key": "idem_empty_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "   "},
    }

    receipt = service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "message_text_required"
    assert service.read_events("thr_demo_39", 0).events == ()


def test_thread_accepts_multiline_message_text() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1",
        "command_id": "cmd_multiline_001",
        "idempotency_key": "idem_multiline_001",
        "thread_id": "thr_demo_39",
        "run_id": "run_001",
        "kind": "send_auto",
        "expected_event_seq": 0,
        "payload": {"text": "第一行\n第二行"},
    }

    receipt = service.submit_command(command)

    assert receipt.status == "accepted"
    assert service.read_events("thr_demo_39", 0).events[0].payload["payload"] == command["payload"]


def test_thread_rejects_non_json_command_payload_as_protocol_error() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1", "command_id": "cmd_bad_json_001",
        "idempotency_key": "idem_bad_json_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": object()},
    }

    from capstone_agent.thread_protocol import ThreadProtocolError

    import pytest
    with pytest.raises(ThreadProtocolError, match="not JSON"):
        service.submit_command(command)
