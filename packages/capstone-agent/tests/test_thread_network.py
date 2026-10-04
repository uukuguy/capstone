from __future__ import annotations

import pytest

from capstone_agent.harness import HarnessPiClient
from capstone_agent.thread_service import AttemptClaim, InMemoryThreadService


class _Session:
    def start(self) -> None:
        return None

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        del question, kwargs
        return "answer"

    def stop(self) -> None:
        return None


def _projection(claim: AttemptClaim, *, revision: str | None = None) -> dict[str, object]:
    model_revision = revision or claim.model_context.model_revision
    return {
        "schema": "capstone-network-view/2.0",
        "ordinal": 1,
        "diagram": {
            "schema": "capstone-network-diagram/1.0",
            "model": {
                "id": claim.model_context.model_id,
                "revision": model_revision,
                "source": "pypsamodelctl",
            },
            "coordinate_system": "schematic",
            "buses": [
                {"id": "bus-1", "label": "Bus 1", "x": 0.0, "y": 0.0, "vn_kv": 110.0},
                {"id": "bus-2", "label": "Bus 2", "x": 1.0, "y": 0.0, "vn_kv": 110.0},
            ],
            "branches": [{
                "id": "line-1", "kind": "line", "label": "Line 1",
                "from_bus": "bus-1", "to_bus": "bus-2",
            }],
        },
        "layer": {"focus_ids": [], "next_focus_ids": [], "overlay": None},
    }


class _Provider:
    def __init__(self, factory):
        self.factory = factory

    def project(self, claim, result_refs, evidence_refs, tool_events):
        return self.factory(claim, result_refs, evidence_refs, tool_events)


@pytest.fixture
def claim() -> AttemptClaim:
    service = InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_network",
        "run": {"run_id": "run_network", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39",
            "model_revision": "revision:sha256:" + "a" * 64,
            "implementation_family": "pypsa", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_network",
        "idempotency_key": "idem_network", "thread_id": "thr_network",
        "run_id": "run_network", "kind": "send_ordinary",
        "expected_event_seq": 0, "payload": {"text": "hello"},
    })
    leased = service.claim_attempt("network-worker", lease_seconds=30)
    assert leased is not None
    return leased


def test_harness_pi_client_exposes_bounded_network_projection(claim: AttemptClaim) -> None:
    provider = _Provider(lambda claim, *_args: _projection(claim))
    client = HarnessPiClient(_Session(), network_projection_provider=provider)

    projection = client.network_projection(
        claim, ("result:sha256:" + "a" * 64,), (), (),
    )

    assert projection is not None
    assert projection["schema"] == "capstone-network-view/2.0"
    assert projection["diagram"]["model"]["revision"] == claim.model_context.model_revision


def test_network_projection_rejects_foreign_revision_and_returns_none(claim: AttemptClaim) -> None:
    foreign_revision = "revision:sha256:" + "b" * 64
    provider = _Provider(lambda claim, *_args: _projection(claim, revision=foreign_revision))
    client = HarnessPiClient(_Session(), network_projection_provider=provider)

    assert client.network_projection(claim, (), (), ()) is None
