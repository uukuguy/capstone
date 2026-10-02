from __future__ import annotations

import pytest

from capstone_agent.thread_application_transition import ApplicationEvent, ThreadApplicationTransition
from capstone_agent.thread_protocol import ThreadProtocolError, ThreadSnapshot
from capstone_agent.thread_service import InMemoryThreadService


def snapshot() -> ThreadSnapshot:
    return ThreadSnapshot.from_document({
        "schema": "capstone-thread-snapshot/1",
        "thread_id": "thr_case",
        "run": {"run_id": "run_case", "state": "open"},
        "active_model_context": {
            "id": "ctx_case", "model_id": "ieee39", "model_revision": "1",
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


def transition_fixture(expected_event_seq: int) -> ThreadApplicationTransition:
    return ThreadApplicationTransition(
        command={
            "schema": "capstone-command/1", "command_id": "cmd_case_1",
            "idempotency_key": "idem_case_1", "thread_id": "thr_case",
            "run_id": "run_case", "kind": "case_execution_created",
            "expected_event_seq": expected_event_seq,
            "payload": {"case_id": "demo"},
        },
        state={"case_execution": {"case_id": "demo", "status": "running"}},
        events=(ApplicationEvent("case_execution_created", {"case_id": "demo"}),),
    )


@pytest.fixture
def service() -> InMemoryThreadService:
    return InMemoryThreadService(snapshot())


def test_application_transition_is_atomic(service: InMemoryThreadService) -> None:
    transition = transition_fixture(expected_event_seq=0)
    receipt = service.apply_application_transition(transition)
    assert receipt.status == "accepted"
    assert service.snapshot("thr_case").application_state == transition.state
    assert service.read_events("thr_case", 0).events[-1].event_type == "case_execution_created"


def test_application_transition_idempotency_and_cursor(service: InMemoryThreadService) -> None:
    transition = transition_fixture(expected_event_seq=0)
    receipt = service.apply_application_transition(transition)
    assert service.apply_application_transition(transition) == receipt

    conflict = transition_fixture(expected_event_seq=0)
    conflict = ThreadApplicationTransition(
        command={**conflict.command, "payload": {"case_id": "different"}},
        state=conflict.state, events=conflict.events,
    )
    assert service.apply_application_transition(conflict).rejection == "idempotency_conflict"

    state_conflict = ThreadApplicationTransition(
        command=transition.command,
        state={"case_execution": {"case_id": "demo", "status": "completed"}},
        events=transition.events,
    )
    assert service.apply_application_transition(state_conflict).rejection == "idempotency_conflict"

    events_conflict = ThreadApplicationTransition(
        command=transition.command,
        state=transition.state,
        events=(ApplicationEvent("case_execution_changed", {"case_id": "demo"}),),
    )
    assert service.apply_application_transition(events_conflict).rejection == "idempotency_conflict"

    stale = ThreadApplicationTransition(
        command={**transition.command, "command_id": "cmd_case_2", "idempotency_key": "idem_case_2"},
        state={"case_execution": {"status": "changed"}}, events=(ApplicationEvent("case_execution_changed", {}),),
    )
    rejected = service.apply_application_transition(stale)
    assert rejected.rejection == "stale_event_seq"
    assert service.snapshot("thr_case").application_state == transition.state
    assert service.read_events("thr_case", 0).next_event_seq == 1


def test_transition_validates_bounds() -> None:
    with pytest.raises(ThreadProtocolError):
        ApplicationEvent("case_execution_created", {"large": "x" * (64 * 1024)})
    with pytest.raises(ThreadProtocolError):
        ThreadApplicationTransition(
            command=transition_fixture(0).command,
            state={"large": "x" * (64 * 1024)}, events=(),
        )
    with pytest.raises(ThreadProtocolError):
        ThreadApplicationTransition(
            command=transition_fixture(0).command, state=None,
            events=tuple(ApplicationEvent(f"event_{i}", {}) for i in range(9)),
        )
