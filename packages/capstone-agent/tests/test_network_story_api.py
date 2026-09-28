from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.network_story import build_cumulative_story
from capstone_agent.session import WorkerRegistry, WorkerSpec
from test_network_story import diagram, steps


class StoryLedger:
    def __init__(self, story: dict[str, object], *, state: str = "completed") -> None:
        self.events = [
            SimpleNamespace(kind="answer_committed", payload={"ordinal": 1, "result_refs": ["result:step-1"]}, sequence=1),
            SimpleNamespace(kind="answer_committed", payload={"ordinal": 2, "result_refs": ["result:step-2"]}, sequence=2),
            SimpleNamespace(kind="answer_committed", payload={"ordinal": 3, "result_refs": []}, sequence=3),
            SimpleNamespace(kind="network_story", payload={"story": story}, sequence=4),
        ]
        self.state = state

    def get_session(self, session_id: str):
        if session_id != "session-story":
            return None
        return SimpleNamespace(state=self.state, completed_turns=3)

    def events_after(self, session_id: str, after: int):
        assert session_id == "session-story"
        return [event for event in self.events if event.sequence > after]


def _app(ledger: StoryLedger):
    root = Path(__file__).resolve().parents[3]
    registry = WorkerRegistry((WorkerSpec("pandapower-static-analysis", ("unused",)),))
    return create_host_app(
        ledger, registry, operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        repo_root=root,
    )


def test_network_story_endpoint_returns_persisted_story() -> None:
    story = build_cumulative_story(diagram(), steps(), None)
    with TestClient(_app(StoryLedger(story)), base_url="http://localhost") as client:
        response = client.get(
            "/api/v1/sessions/session-story/network-story",
            headers={"Authorization": "Bearer hosted-secret"},
        )
        repeated = client.get(
            "/api/v1/sessions/session-story/network-story",
            headers={"Authorization": "Bearer hosted-secret"},
        )
    assert response.status_code == repeated.status_code == 200
    assert response.json() == repeated.json()
    assert response.json()["schema"] == "capstone-network-story/1.0"


def test_network_story_endpoint_is_not_ready_before_completion() -> None:
    story = build_cumulative_story(diagram(), steps(), None)
    with TestClient(_app(StoryLedger(story, state="closing")), base_url="http://localhost") as client:
        response = client.get(
            "/api/v1/sessions/session-story/network-story",
            headers={"Authorization": "Bearer hosted-secret"},
        )
    assert response.status_code == 409
