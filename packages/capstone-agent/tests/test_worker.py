from __future__ import annotations

import io
from dataclasses import dataclass

from capstone_agent.protocol import Frame
from capstone_agent.worker import PreparedWorker, serve_application


@dataclass
class FakeOutcome:
    status: str
    rendered: object


class FakeApplication:
    def __init__(self, observer):
        self.observer = observer
        self.questions: list[str] = []

    def run_stream(self, request, instructions):
        assert request.questions == ()
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
                "result_refs": [], "evidence_refs": ["evidence:current"],
            })
        return FakeOutcome("completed", {"questions": self.questions})


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

    serve_application(
        lambda _payload, observer: PreparedWorker(
            application=FakeApplication(observer),
            run_id="run-fixture",
            evidence_reader=lambda ref: {"ref": ref} if ref == "evidence:current" else None,
        ),
        input_stream=io.BytesIO(incoming), output_stream=output,
    )

    frames = [Frame.from_line(line, expected_sequence=index)
              for index, line in enumerate(output.getvalue().splitlines(keepends=True), start=1)]
    assert [frame.kind for frame in frames] == [
        "ready", "progress", "progress", "answer_committed",
        "progress", "progress", "answer_committed", "completed",
        "evidence_result", "evidence_result",
    ]
    assert "fixture_tool" in frames[1].payload["message"]
    assert "report.md" in frames[2].payload["message"]
    assert frames[7].payload["result"] == {"questions": ["first", "second"]}
    assert frames[8].payload["value"] == {"ref": "evidence:current"}
    assert frames[9].payload["value"] is None
