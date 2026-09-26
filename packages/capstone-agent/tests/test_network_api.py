"""Authenticated network diagram replay from persisted session events."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.network_diagram import normalize_network_projection
from capstone_agent.session import WorkerRegistry, WorkerSpec
from test_network_diagram import projection


class StoredNetworkLedger:
    def __init__(self) -> None:
        first = normalize_network_projection(projection(), admitted_refs=())
        second = normalize_network_projection(projection(2), admitted_refs=())
        self.events = [
            SimpleNamespace(kind="answer_committed", payload={"ordinal": 1,
                "result_refs": []}, sequence=1),
            SimpleNamespace(kind="network_diagram", payload={"diagram": first["diagram"]}, sequence=2),
            SimpleNamespace(kind="network_layer", payload={"ordinal": 1,
                "layer": first["layer"]}, sequence=3),
            SimpleNamespace(kind="answer_committed", payload={"ordinal": 2,
                "result_refs": []}, sequence=4),
            SimpleNamespace(kind="network_layer", payload={"ordinal": 2,
                "layer": second["layer"]}, sequence=5),
        ]

    def get_session(self, session_id: str):
        if session_id != "session-one":
            return None
        return SimpleNamespace(completed_turns=2)

    def events_after(self, session_id: str, after: int):
        assert session_id == "session-one"
        return [event for event in self.events if event.sequence > after]


def test_network_route_reconstructs_historical_layer_without_repeating_base() -> None:
    root = Path(__file__).resolve().parents[3]
    registry = WorkerRegistry((WorkerSpec("pandapower-static-analysis", ("unused",),
                                  scripted_cases=("pandapower-scripted-task",)),))
    ledger = StoredNetworkLedger()
    app = create_host_app(ledger, registry, operator_token="hosted-secret",
                          allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
                          repo_root=root)
    with TestClient(app, base_url="http://localhost") as client:
        route = "/api/v1/sessions/session-one/network"
        assert client.get(route, params={"ordinal": 1}).status_code == 401
        headers = {"Authorization": "Bearer hosted-secret"}
        first = client.get(route, params={"ordinal": 1}, headers=headers)
        second = client.get(route, params={"ordinal": 2}, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["diagram"]["ref"] == second.json()["diagram"]["ref"]
        assert first.json()["layer"]["ordinal"] == 1
        assert second.json()["layer"]["ordinal"] == 2
        assert client.get(route, params={"ordinal": 3}, headers=headers).status_code == 404


def test_registered_case_diagram_is_available_without_creating_a_run() -> None:
    root = Path(__file__).resolve().parents[3]
    registry = WorkerRegistry((WorkerSpec("pandapower-static-analysis", ("unused",),
                                  scripted_cases=("pandapower-scripted-task",)),))
    ledger = StoredNetworkLedger()
    diagram = normalize_network_projection(projection(), admitted_refs=())["diagram"]
    calls = []

    def load(spec, case_id):
        calls.append((spec.application_id, case_id))
        return diagram

    app = create_host_app(ledger, registry, operator_token="hosted-secret",
                          allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
                          repo_root=root, preview_loader=load)
    route = "/api/v1/cases/pandapower-static-analysis/pandapower-scripted-task/diagram"
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get(route).status_code == 401
        headers = {"Authorization": "Bearer hosted-secret"}
        first = client.get(route, headers=headers)
        second = client.get(route, headers=headers)
        assert first.status_code == second.status_code == 200
        assert first.json() == diagram
        assert len(calls) == 1
        assert client.get(route.replace("pandapower-scripted-task", "foreign"), headers=headers).status_code == 404
