from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from capstone_agent.protocol import Frame
from capstone_agent.worker import PreparedWorker, serve_application
from test_network_view import _view
from test_network_diagram import projection


@dataclass
class FakeOutcome:
    status: str
    rendered: object
    report_path: Path | None = None


class FakeApplication:
    def __init__(self, observer):
        self.observer = observer
        self.questions: list[str] = []
        self.response_mode = None

    def run_stream(self, request, instructions):
        assert request.questions == ()
        self.response_mode = request.response_mode
        for ordinal, instruction in enumerate(instructions, start=1):
            self.questions.append(instruction)
            self.observer({"type": "tool_execution_start", "toolName": "fixture_tool",
                           "args": {"instruction": instruction}})
            self.observer({"type": "application_report_checkpoint",
                           "completed_questions": ordinal, "total_questions": 2,
                           "report_path": "runs/run-fixture/output/report.md"})
            self.observer({
                "type": "application_turn_completed", "ordinal": ordinal,
                "turn_id": f"run-fixture-t{ordinal:03d}",
                "answer_output": instruction.upper(), "answer_ref": f"answer:{ordinal}",
                "answer_summary": f"摘要 {ordinal}",
                "result_refs": [], "evidence_refs": ["evidence:current"],
            })
        return FakeOutcome("completed", {"questions": self.questions},
                           Path("runs/run-fixture/output/report.md"))


def test_worker_processes_turns_then_serves_run_scoped_evidence() -> None:
    incoming = b"".join((
        Frame("session-1", 1, "open", {"application_id": "fixture-app", "mode": "provider"}).to_line(),
        Frame("session-1", 2, "turn", {"instruction": "first"}).to_line(),
        Frame("session-1", 3, "turn", {"instruction": "second"}).to_line(),
        Frame("session-1", 4, "close", {}).to_line(),
        Frame("session-1", 5, "evidence", {"ref": "evidence:current"}).to_line(),
        Frame("session-1", 6, "evidence", {"ref": "evidence:foreign"}).to_line(),
    ))
    output = io.BytesIO()

    prepared_apps: list[FakeApplication] = []

    def factory(_payload, observer):
        app = FakeApplication(observer)
        prepared_apps.append(app)
        return PreparedWorker(
            application=app,
            run_id="run-fixture",
            evidence_reader=lambda ref: {"ref": ref} if ref == "evidence:current" else None,
        )

    serve_application(
        factory,
        input_stream=io.BytesIO(incoming), output_stream=output,
    )

    frames = [Frame.from_line(line, expected_sequence=index)
              for index, line in enumerate(output.getvalue().splitlines(keepends=True), start=1)]
    assert [frame.kind for frame in frames] == [
        "ready", "progress", "progress", "answer_committed",
        "network_view_unavailable", "progress", "progress", "answer_committed",
        "network_view_unavailable", "completed", "evidence_result", "evidence_result",
    ]
    assert "fixture_tool" in frames[1].payload["message"]
    assert "report.md" in frames[2].payload["message"]
    assert frames[9].payload["result"] == {"questions": ["first", "second"]}
    assert frames[9].payload["report_path"] == "runs/run-fixture/output/report.md"
    assert frames[10].payload["value"] == {"ref": "evidence:current"}
    assert frames[11].payload["value"] is None
    assert all(
        isinstance(frame.payload.get("duration_ms"), int)
        and frame.payload["duration_ms"] >= 0
        for frame in frames if frame.kind == "answer_committed"
    )
    assert [frame.payload["answer_summary"] for frame in frames if frame.kind == "answer_committed"] == [
        "摘要 1", "摘要 2",
    ]
    assert prepared_apps[0].response_mode == "answer_bundle"


def test_worker_publishes_network_unavailable_when_no_projection_is_registered() -> None:
    incoming = b"".join((
        Frame("session-1", 1, "open", {"application_id": "fixture-app", "mode": "provider"}).to_line(),
        Frame("session-1", 2, "turn", {"instruction": "first"}).to_line(),
        Frame("session-1", 3, "close", {}).to_line(),
    ))
    output = io.BytesIO()

    serve_application(
        lambda _payload, observer: PreparedWorker(
            application=FakeApplication(observer), run_id="run-fixture",
            evidence_reader=lambda _ref: None,
        ), input_stream=io.BytesIO(incoming), output_stream=output,
    )

    frames = [Frame.from_line(line) for line in output.getvalue().splitlines(keepends=True)]
    kinds = [frame.kind for frame in frames]
    assert kinds.index("answer_committed") < kinds.index("network_view_unavailable")
    assert frames[kinds.index("network_view_unavailable")].payload["ordinal"] == 1


def test_worker_publishes_network_view_only_after_committed_answer() -> None:
    incoming = b"".join((
        Frame("session-1", 1, "open", {"application_id": "fixture-app", "mode": "provider"}).to_line(),
        Frame("session-1", 2, "turn", {"instruction": "first"}).to_line(),
        Frame("session-1", 3, "close", {}).to_line(),
    ))
    output = io.BytesIO()
    serve_application(
        lambda _payload, observer: PreparedWorker(
            application=FakeApplication(observer), run_id="run-fixture",
            evidence_reader=lambda _ref: None,
            network_reader=lambda ordinal: {**_view(), "ordinal": ordinal},
        ), input_stream=io.BytesIO(incoming), output_stream=output,
    )
    frames = [Frame.from_line(line) for line in output.getvalue().splitlines(keepends=True)]
    kinds = [frame.kind for frame in frames]
    assert kinds.index("answer_committed") < kinds.index("network_view") < kinds.index("completed")
    assert frames[kinds.index("network_view")].payload["ordinal"] == 1


def test_worker_skips_network_projection_when_step_link_is_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CAPSTONE_ENABLE_NETWORK_STEP_LINK", "false")
    incoming = b"".join((
        Frame("session-1", 1, "open", {"application_id": "fixture-app", "mode": "provider"}).to_line(),
        Frame("session-1", 2, "turn", {"instruction": "first"}).to_line(),
        Frame("session-1", 3, "close", {}).to_line(),
    ))
    output = io.BytesIO()
    serve_application(
        lambda _payload, observer: PreparedWorker(
            application=FakeApplication(observer), run_id="run-fixture",
            evidence_reader=lambda _ref: None,
            network_reader=lambda ordinal: {**_view(), "ordinal": ordinal},
        ), input_stream=io.BytesIO(incoming), output_stream=output,
    )
    kinds = [Frame.from_line(line).kind for line in output.getvalue().splitlines(keepends=True)]
    assert "answer_committed" in kinds
    assert not any(kind.startswith("network_") for kind in kinds)


def test_network_projection_failure_does_not_erase_answer() -> None:
    incoming = b"".join((
        Frame("session-1", 1, "open", {"application_id": "fixture-app", "mode": "provider"}).to_line(),
        Frame("session-1", 2, "turn", {"instruction": "first"}).to_line(),
        Frame("session-1", 3, "close", {}).to_line(),
    ))
    output = io.BytesIO()

    def unavailable(_ordinal):
        raise ValueError("projection is unavailable")

    serve_application(
        lambda _payload, observer: PreparedWorker(
            application=FakeApplication(observer), run_id="run-fixture",
            evidence_reader=lambda _ref: None, network_reader=unavailable,
        ), input_stream=io.BytesIO(incoming), output_stream=output,
    )
    kinds = [Frame.from_line(line).kind for line in output.getvalue().splitlines(keepends=True)]
    assert "answer_committed" in kinds
    assert "network_view" not in kinds
    assert "network_view_unavailable" in kinds
    assert "completed" in kinds


def test_worker_publishes_one_base_and_two_historical_layers() -> None:
    incoming = b"".join((
        Frame("session-1", 1, "open", {"application_id": "fixture-app", "mode": "provider"}).to_line(),
        Frame("session-1", 2, "turn", {"instruction": "first"}).to_line(),
        Frame("session-1", 3, "turn", {"instruction": "second"}).to_line(),
        Frame("session-1", 4, "close", {}).to_line(),
    ))
    output = io.BytesIO()
    serve_application(
        lambda _payload, observer: PreparedWorker(
            application=FakeApplication(observer), run_id="run-fixture",
            evidence_reader=lambda _ref: None,
            network_reader=lambda ordinal: projection(ordinal),
        ), input_stream=io.BytesIO(incoming), output_stream=output,
    )
    frames = [Frame.from_line(line) for line in output.getvalue().splitlines(keepends=True)]
    network = [frame for frame in frames if frame.kind.startswith("network_")]
    assert [frame.kind for frame in network] == [
        "network_diagram", "network_layer", "network_layer",
    ]
    assert [frame.payload["ordinal"] for frame in network[1:]] == [1, 2]
