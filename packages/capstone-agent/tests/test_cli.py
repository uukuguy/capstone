from __future__ import annotations

import io
import json
from pathlib import Path

from capstone_agent.cli import main
from capstone_agent.session import WorkerRegistry, WorkerSpec
from test_session import _worker


def test_headless_cli_writes_one_result_object(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "schema": "capstone-client-request/1.0", "application_id": "fixture-app",
        "mode": "scripted-demo", "instructions": ["first", "second"],
    }), encoding="utf-8")
    output, errors = io.StringIO(), io.StringIO()

    status = main(["run", "--request", str(request)], registry=registry,
                  output_stream=output, error_stream=errors)

    assert status == 0
    payload = json.loads(output.getvalue())
    assert payload["schema"] == "capstone-client-result/1.0"
    assert payload["result"] == {"turns": ["first", "second"]}
    assert len(output.getvalue().splitlines()) == 1
    assert "FIRST" in errors.getvalue()


def test_headless_cli_runs_provider_instruction_file_in_one_session(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path), scripted_cases=()),))
    instructions = tmp_path / "questions.md.txt"
    instructions.write_text("first\n\nsecond\n", encoding="utf-8")
    output, errors = io.StringIO(), io.StringIO()

    status = main(
        ["run", "--application", "fixture-app", "--instructions", str(instructions)],
        registry=registry, output_stream=output, error_stream=errors,
    )

    assert status == 0
    payload = json.loads(output.getvalue())
    assert payload["result"] == {"turns": ["first", "second"]}
    assert len(output.getvalue().splitlines()) == 1


def test_chat_answers_before_it_reads_next_instruction(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    output, errors = io.StringIO(), io.StringIO()

    class Input:
        index = 0

        def readline(self) -> str:
            self.index += 1
            if self.index == 1:
                return "first\n"
            if self.index == 2:
                assert "FIRST" in output.getvalue()
                return "second\n"
            return "/exit\n"

    status = main(["chat", "--application", "fixture-app", "--mode", "scripted-demo"],
                  registry=registry, input_stream=Input(),
                  output_stream=output, error_stream=errors)

    assert status == 0
    assert "FIRST" in output.getvalue()
    assert "SECOND" in output.getvalue()
    assert "run-fixture" in errors.getvalue()


def test_headless_cli_streams_worker_progress_to_stderr(tmp_path: Path) -> None:
    command = _worker(tmp_path)
    script = Path(command[-1])
    source = script.read_text(encoding="utf-8")
    script.write_text(source.replace('turns.append(instruction)\n',
                                     'turns.append(instruction)\n'
                                     '        send("progress", {"event": "capability_started", '
                                     '"message": "Working on current turn"})\n'),
                      encoding="utf-8")
    registry = WorkerRegistry((WorkerSpec("fixture-app", command),))
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "schema": "capstone-client-request/1.0", "application_id": "fixture-app",
        "mode": "scripted-demo", "instructions": ["first"],
    }), encoding="utf-8")
    errors = io.StringIO()
    assert main(["run", "--request", str(request)], registry=registry,
                output_stream=io.StringIO(), error_stream=errors) == 0
    assert "Working on current turn" in errors.getvalue()
