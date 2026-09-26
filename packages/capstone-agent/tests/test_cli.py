from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from capstone_agent.cli import _request, main
from capstone_agent.session import WorkerRegistry, WorkerSpec
from test_session import _worker


@pytest.mark.parametrize(("name", "count"), (("task", 9), ("test", 7)))
def test_pandapower_analysis_request_matches_question_list(
    name: str, count: int, tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[3]
    request_path = root / f"validation/client/pandapower-analysis-{name}.json"
    request = _request(request_path)
    questions = [
        line.strip()
        for line in (root / f"validation/questions/{name}.md.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert request["application_id"] == "pandapower-static-analysis"
    assert request["mode"] == "provider"
    assert "case_id" not in request
    assert len(request["instructions"]) == count
    assert request["instructions"] == questions

    registry = WorkerRegistry((WorkerSpec(
        "pandapower-static-analysis", _worker(tmp_path),
        scripted_cases=("pandapower-scripted-task",),
    ),))
    output = io.StringIO()
    assert main(
        ["run", "--request", str(request_path)], registry=registry,
        output_stream=output, error_stream=io.StringIO(),
    ) == 0
    assert json.loads(output.getvalue())["result"]["turns"] == questions


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


def test_headless_cli_prints_final_report_path(tmp_path: Path) -> None:
    command = _worker(tmp_path)
    script = Path(command[-1])
    source = script.read_text(encoding="utf-8")
    script.write_text(source.replace(
        '"result": {"turns": turns}',
        '"result": {"turns": turns}, "report_path": "/tmp/run-fixture/output/report.md"',
    ), encoding="utf-8")
    registry = WorkerRegistry((WorkerSpec("fixture-app", command),))
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "schema": "capstone-client-request/1.0", "application_id": "fixture-app",
        "mode": "scripted-demo", "instructions": ["first"],
    }), encoding="utf-8")
    errors = io.StringIO()
    assert main(["run", "--request", str(request)], registry=registry,
                output_stream=io.StringIO(), error_stream=errors) == 0
    assert errors.getvalue().splitlines()[-1] == "报告文件：/tmp/run-fixture/output/report.md"


def test_headless_cli_uses_human_output_on_terminal(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "schema": "capstone-client-request/1.0", "application_id": "fixture-app",
        "mode": "scripted-demo", "instructions": ["first"],
    }), encoding="utf-8")

    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    output, errors = Terminal(), io.StringIO()
    assert main(["run", "--request", str(request)], registry=registry,
                output_stream=output, error_stream=errors) == 0
    assert "capstone-client-result/1.0" not in output.getvalue()
    assert "answer:sha256:" not in output.getvalue()
    assert "运行完成" in output.getvalue()


def test_chat_summarizes_evidence_references(tmp_path: Path) -> None:
    command = _worker(tmp_path)
    script = Path(command[-1])
    source = script.read_text(encoding="utf-8")
    script.write_text(source.replace(
        '"result_refs": [], "evidence_refs": []',
        '"result_refs": ["result:sha256:' + 'a' * 64 + '"], '
        '"evidence_refs": ["evidence:sha256:' + 'b' * 64 + '"]',
    ), encoding="utf-8")
    registry = WorkerRegistry((WorkerSpec("fixture-app", command),))
    output = io.StringIO()
    assert main(
        ["chat", "--application", "fixture-app", "--mode", "scripted-demo"],
        registry=registry, input_stream=io.StringIO("first\n/exit\n"),
        output_stream=output, error_stream=io.StringIO(),
    ) == 0
    assert "结果 1 项、证据 1 项" in output.getvalue()
    assert "sha256:" not in output.getvalue()
