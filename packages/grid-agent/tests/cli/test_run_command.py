from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from grid_agent.cli import app as cli_module
from grid_agent.cli.app import app


def test_analysis_generic_requires_application_and_instructions() -> None:
    result = CliRunner().invoke(app, ["analysis-generic", "--application", "pandapower-static-analysis"])

    assert result.exit_code == 2
    assert "--instructions" in result.output


def test_analysis_generic_emits_the_validated_composite_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instructions = tmp_path / "instructions.txt"
    instructions.write_text("question one\nquestion two\n", encoding="utf-8")
    rendered = (
        '{"schema":"capability-agent-output/1.0",'
        '"core":{"status":"completed"},"domains":{"grid":{}}}\n'
    )
    observed: dict[str, object] = {}

    def run_generic(application_id: str, questions: tuple[str, ...], **kwargs: object) -> object:
        observed.update(application_id=application_id, questions=questions, kwargs=kwargs)
        return SimpleNamespace(status="completed", rendered=rendered, result=object())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "run_generic_application", run_generic)
    monkeypatch.setattr(
        cli_module,
        "load_questions",
        lambda _path: ("question one", "question two"),
    )
    generic_catalog = object()
    monkeypatch.setattr(
        cli_module,
        "GenericProviderCatalog",
        SimpleNamespace(load=lambda _path: generic_catalog),
    )

    result = CliRunner().invoke(
        app,
        [
            "analysis-generic",
            "--application",
            "pandapower-static-analysis",
            "--instructions",
            str(instructions),
            "--provider",
            "fixture-provider",
            "--model",
            "fixture-model",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {
        "schema": "capability-agent-output/1.0",
        "core": {"status": "completed"},
        "domains": {"grid": {}},
    }
    assert observed["application_id"] == "pandapower-static-analysis"
    assert observed["questions"] == ("question one", "question two")
    kwargs = observed["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["provider"] == "fixture-provider"
    assert kwargs["model"] == "fixture-model"
    assert kwargs["provider_catalog"] is generic_catalog
    assert "question_id" not in result.stdout
    assert "analysis-generic" in result.stderr


def test_analysis_generic_never_projects_failed_run_to_legacy_envelope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instructions = tmp_path / "instructions.txt"
    instructions.write_text("question\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli_module,
        "run_generic_application",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="failed",
            rendered=None,
            error="ApplicationConfigurationError: application execution failed",
        ),
    )
    monkeypatch.setattr(cli_module, "load_questions", lambda _path: ("question",))
    monkeypatch.setattr(
        cli_module,
        "GenericProviderCatalog",
        SimpleNamespace(load=lambda _path: object()),
    )

    result = CliRunner().invoke(
        app,
        [
            "analysis-generic",
            "--application",
            "pandapower-static-analysis",
            "--instructions",
            str(instructions),
        ],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "question_id" not in result.stdout
    assert "generic application failed" in result.stderr
