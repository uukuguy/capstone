from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from validation.run import ScriptedApplicationTransport


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
