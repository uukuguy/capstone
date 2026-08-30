from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from capability_agent.application import AgentApplication, ApplicationWorkspace

import grid_agent.application.composition as grid_composition
from grid_agent.cli import app as cli_module
from grid_agent.cli.app import app
from grid_agent.application.profile import build_pandapower_application_profile


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


def test_analysis_generic_adapts_product_llm_configuration_for_generic_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instructions = tmp_path / "instructions.txt"
    instructions.write_text("question\n", encoding="utf-8")
    observed: dict[str, object] = {}

    def run_generic(*_args: object, **kwargs: object) -> object:
        observed.update(kwargs)
        return SimpleNamespace(status="completed", rendered="{}\n", result=object())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "run_generic_application", run_generic)
    monkeypatch.setattr(cli_module, "load_questions", lambda _path: ("question",))
    monkeypatch.setattr(
        cli_module,
        "GenericProviderCatalog",
        SimpleNamespace(load=lambda _path: object()),
    )
    monkeypatch.setattr(
        cli_module,
        "_runtime_environment",
        lambda _path: {
            "GRID_AGENT_LLM_PROVIDER": "deepseek",
            "GRID_AGENT_LLM_MODEL": "deepseek-v4-flash",
            "DEEPSEEK_API_KEY": "test-key",
        },
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

    assert result.exit_code == 0, result.stderr
    environment = observed["environment"]
    assert isinstance(environment, dict)
    assert environment["CAPABILITY_AGENT_LLM_PROVIDER"] == "deepseek"
    assert environment["CAPABILITY_AGENT_LLM_MODEL"] == "deepseek-v4-flash"


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


def test_analysis_generic_uses_the_real_runner_and_pandapower_output_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instructions = tmp_path / "instructions.txt"
    instructions.write_text("question one\nquestion two\n", encoding="utf-8")
    profile = build_pandapower_application_profile()
    binding = profile.domains[0]
    provider = SimpleNamespace(
        start=lambda: None,
        prompt_and_wait=lambda _question, **_kwargs: "validated answer",
        stop=lambda: None,
    )

    def build_application(_application_id: str, **kwargs: object) -> AgentApplication:
        workspace_root = kwargs["workspace_root"]
        assert isinstance(workspace_root, Path)
        workspace = ApplicationWorkspace.create(
            workspace_root,
            run_id="cli-near-real",
            binding_ids=("grid",),
        )
        prepared = SimpleNamespace(
            bindings={
                "grid": SimpleNamespace(
                    binding=binding,
                    endpoint=SimpleNamespace(close=lambda: None),
                    runtime=SimpleNamespace(),
                )
            }
        )
        return AgentApplication(
            profile=profile,
            prepared_application=prepared,
            provider=provider,
            workspace=workspace,
            catalog=object(),
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(grid_composition, "build_generic_application", build_application)
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

    assert result.exit_code == 0, result.stderr
    rendered = json.loads(result.stdout)
    assert rendered["schema"] == "capability-agent-output/1.0"
    assert rendered["core"]["run_id"] == "cli-near-real"
    domain = rendered["domains"]["grid"]
    assert domain["schema"] == "pandapower-static-analysis-output/1.0"
    assert domain["payload"] == {
        "mode": "continuous-static-analysis",
        "instruction_count": 2,
        "completed_count": 2,
        "failed_count": 0,
        "report_artifact_ref": rendered["core"]["report_ref"],
    }
    report_path = tmp_path / "runs/cli-near-real/output/report.md"
    assert report_path.is_file()
    assert "question_id" not in result.stdout
    assert "generic application failed" not in result.stderr
