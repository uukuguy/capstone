from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from validation.run import ScriptedApplicationTransport


def test_scripted_events_use_provider_observer_contract() -> None:
    from pandapower_application.scripted_execution import _emit_scripted_event

    events = []
    event = {'type': 'tool_result', 'ok': True}
    _emit_scripted_event(events.append, event, 1)
    assert events == [event]


def test_scripted_transport_rejects_native_binding() -> None:
    import pytest
    from capability_agent.application.native import PreparedNativeBinding

    binding = PreparedNativeBinding(SimpleNamespace(), SimpleNamespace(), SimpleNamespace())
    with pytest.raises(ValueError, match='professional binding'):
        ScriptedApplicationTransport({'run_id': 'native', 'questions': []},
            prepared=SimpleNamespace(bindings={'grid': binding}),
            catalog=SimpleNamespace(domain_tools=()))


def test_scripted_transport_rejects_invalid_question_collection() -> None:
    import pytest

    with pytest.raises(ValueError, match='questions must be a list'):
        ScriptedApplicationTransport({'run_id': 'invalid', 'questions': {}},
            prepared=SimpleNamespace(bindings={'grid': SimpleNamespace()}),
            catalog=SimpleNamespace(domain_tools=()))


def test_scripted_transport_delivers_prompt_heartbeat_without_creating_evidence() -> None:
    case = {
        "run_id": "scripted-heartbeat",
        "questions": [{"text": "Explain the workflow", "steps": []}],
    }
    prepared = SimpleNamespace(
        bindings={"grid": SimpleNamespace(runtime=SimpleNamespace(capability_documents=()))}
    )
    transport = ScriptedApplicationTransport(
        case, prepared=prepared, catalog=SimpleNamespace(domain_tools=())
    )
    pulses: list[str] = []

    answer = transport.prompt_and_wait(
        "Explain the workflow",
        correlation_id="turn-1",
        on_heartbeat=lambda: pulses.append("waiting"),
    )

    assert pulses == ["waiting"]
    assert answer == "本步已完成，结果与证据已写入当前运行。"
    assert transport.calls == []
    assert transport.current_result_refs == ()
    assert transport.current_evidence_refs == ()


def test_scripted_transport_returns_explicit_model_answer_without_creating_evidence() -> None:
    model_answer = "交流潮流用于求解稳态运行点的电压、相角和支路功率。"
    case = {
        "run_id": "scripted-model-answer",
        "questions": [{
            "text": "什么是交流潮流？",
            "steps": [],
            "answer": model_answer,
        }],
    }
    prepared = SimpleNamespace(
        bindings={"grid": SimpleNamespace(runtime=SimpleNamespace(capability_documents=()))}
    )
    transport = ScriptedApplicationTransport(
        case, prepared=prepared, catalog=SimpleNamespace(domain_tools=())
    )

    answer = transport.prompt_and_wait(
        "什么是交流潮流？",
        correlation_id="turn-1",
        on_heartbeat=lambda: None,
    )

    assert answer == model_answer
    assert transport.calls == []
    assert transport.current_result_refs == ()
    assert transport.current_evidence_refs == ()
