from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from grid_agent.analysis.runner import AnalysisOutcome
from grid_agent.cli import app as cli_module
from grid_agent.cli.app import app
from grid_agent.contracts import AnswerEnvelope
from grid_agent.domain.authority import VerifiedArtifact, VerifiedReferenceSet
from grid_agent.domain.manifest import DomainManifestError


ROOT = Path(__file__).resolve().parents[4]
CLI_APP_SOURCE = ROOT / "packages/grid-agent/src/grid_agent/cli/app.py"


@dataclass
class _FakeAuthority:
    workspace_root: Path
    authority_id: str = "fake-authority"
    admissions: list[tuple[str, dict[str, object], tuple[str, ...]]] = field(
        default_factory=list
    )

    def admit(
        self,
        capability: str,
        result: dict[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet:
        self.admissions.append((capability, result, evidence_refs))
        return cast(VerifiedReferenceSet, object())

    def verify_result(self, reference: str) -> VerifiedArtifact:
        return cast(VerifiedArtifact, object())

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[object, ...]:
        return ()


class _FakeRpcClient:
    starts = 0

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def start(self) -> None:
        type(self).starts += 1

    def prompt_and_wait(self, *_args: object, **kwargs: object) -> str:
        on_event = cast(Any, kwargs["on_event"])
        on_event(
            {
                "type": "tool_result",
                "capability": "model.list",
                "ok": True,
                "result": {"items": []},
                "evidence_refs": ["artifact:evidence/model-list.json"],
            }
        )
        return "prepared answer"

    def stop(self) -> None:
        pass


def _profile(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        manifest=SimpleNamespace(
            executable_name="gridctl",
            system_policy_path=tmp_path / "policy.md",
        ),
        projector_registry=object(),
    )


def _prepared_runtime(
    tmp_path: Path, authority: _FakeAuthority
) -> SimpleNamespace:
    return SimpleNamespace(
        executor=SimpleNamespace(invoke=lambda capability, arguments: {}),
        authority=authority,
        environment_description={
            "protocol_version": "1.0",
            "pandapower_version": "3.4.0-test",
            "executable_capabilities": [],
        },
        capability_documents=(),
        tool_catalog_path=tmp_path / "tool-catalog.prepared.json",
        guide_index_path=tmp_path / "guide-index.prepared.json",
    )


def _patch_live_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    rpc_type: type[_FakeRpcClient] = _FakeRpcClient,
) -> SimpleNamespace:
    resolved = SimpleNamespace(
        config=SimpleNamespace(
            provider="test-provider",
            model="test-model",
            timeout_seconds=12.0,
            max_retries=0,
        ),
        secret=None,
    )
    monkeypatch.setattr(cli_module, "resolve_llm", lambda **_kwargs: resolved)
    monkeypatch.setattr(cli_module, "_runtime_environment", lambda _path: {})
    monkeypatch.setattr(
        cli_module.PiRuntimeLock, "load", lambda _path: SimpleNamespace()
    )
    monkeypatch.setattr(
        cli_module,
        "PiRuntimeLocator",
        lambda *_args, **_kwargs: SimpleNamespace(resolve=lambda: tmp_path / "pi"),
    )
    monkeypatch.setattr(
        cli_module,
        "PiRuntimeInstaller",
        lambda *_args, **_kwargs: SimpleNamespace(ensure=lambda: tmp_path / "pi"),
    )
    monkeypatch.setattr(cli_module, "_install_gridctl", lambda _workspace: None)

    class FakePiConfigMaterializer:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def materialize(self, _resolved: object) -> None:
            return None

        def materialize_domain_runtime(
            self,
            _manifest: object,
            *,
            workspace: Path,
        ) -> Path:
            return workspace / "domain-runtime.json"

    monkeypatch.setattr(
        cli_module,
        "PiConfigMaterializer",
        FakePiConfigMaterializer,
    )
    monkeypatch.setattr(cli_module, "build_pi_launch", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli_module, "PiRpcClient", rpc_type)
    return resolved


@pytest.fixture
def cli_harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[CliRunner, Path]:
    instructions = tmp_path / "task.md.txt"
    instructions.write_text("运行交流潮流\n筛选负载率最高的5条线路\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return CliRunner(), instructions


def _fake_execute_analysis(*, instructions: Path, artifact_root: Path | None, provider: str | None, model: str | None) -> AnalysisOutcome:
    project_root = Path.cwd()
    root = artifact_root or project_root / "runs"
    analysis_id = "analysis-test"
    analysis_root = root / analysis_id
    (analysis_root / "input").mkdir(parents=True)
    (analysis_root / "output").mkdir()
    (analysis_root / "context").mkdir()
    (analysis_root / "input/instructions.md.txt").write_text(instructions.read_text(encoding="utf-8"), encoding="utf-8")
    (analysis_root / "output/answers.jsonl").write_text("", encoding="utf-8")
    (analysis_root / "context/analysis-context.json").write_text("{}", encoding="utf-8")
    (analysis_root / "report.md").write_text("# report\n", encoding="utf-8")
    return AnalysisOutcome(
        analysis_id=analysis_id,
        status="completed",
        report_path=analysis_root / "report.md",
        completed_turns=2,
        total_turns=2,
    )


def _fail_if_called(*_args: Any, **_kwargs: Any) -> subprocess.Popen[str]:
    raise AssertionError("report must not launch child grid-agent run subprocesses")


def test_cli_assembles_runtime_from_extracted_package_owners() -> None:
    tree = ast.parse(CLI_APP_SOURCE.read_text(encoding="utf-8"))
    imports = {
        (node.module, tuple(alias.name for alias in node.names))
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert ("capability_agent.application", ("prepare_domain_runtime",)) in imports
    assert ("pandapower_domain", ("build_pandapower_profile",)) in imports
    assert ("grid_agent.application.composition", ("prepare_domain_runtime",)) not in imports
    assert ("grid_agent.domains", ("build_pandapower_profile",)) not in imports


def test_run_selects_builtin_profile_before_pi_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _FakeRpcClient.starts = 0
    _patch_live_runtime(monkeypatch, tmp_path)
    profile = _profile(tmp_path)
    authority = _FakeAuthority(tmp_path / "runs/run")
    prepared = _prepared_runtime(tmp_path, authority)
    selected: list[bool] = []
    preparation_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        cli_module,
        "build_pandapower_profile",
        lambda: selected.append(True) or profile,
        raising=False,
    )

    def prepare(selected_profile: object, **kwargs: object) -> SimpleNamespace:
        assert selected_profile is profile
        preparation_calls.append(kwargs)
        return prepared

    monkeypatch.setattr(
        cli_module, "prepare_domain_runtime", prepare, raising=False
    )

    result = CliRunner().invoke(app, ["run", "列出可用网络"])

    assert result.exit_code == 0, result.stderr
    assert len(selected) == 1
    assert preparation_calls == [
        {
            "executable": cast(Path, preparation_calls[0]["workspace"])
            / "bin/gridctl",
            "workspace": preparation_calls[0]["workspace"],
            "tool_catalog_path": cast(Path, preparation_calls[0]["workspace"])
            / "tool-catalog.json",
            "guide_index_path": cast(Path, preparation_calls[0]["workspace"])
            / "guide-index.json",
        }
    ]
    assert authority.admissions == [
        (
            "model.list",
            {"items": []},
            ("artifact:evidence/model-list.json",),
        )
    ]
    assert _FakeRpcClient.starts == 1
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}
    assert AnswerEnvelope.model_validate_json(result.stdout).answer_output == (
        "prepared answer"
    )


def test_analysis_uses_prepared_runtime_for_all_domain_resources(
    cli_harness: tuple[CliRunner, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, instructions = cli_harness
    tmp_path = instructions.parent
    _patch_live_runtime(monkeypatch, tmp_path)
    profile = _profile(tmp_path)
    authority = _FakeAuthority(tmp_path / "runs/analysis-test")
    prepared = _prepared_runtime(tmp_path, authority)
    selected: list[bool] = []
    preparation_calls: list[dict[str, object]] = []
    launch_paths: list[object] = []
    runner_arguments: dict[str, object] = {}
    monkeypatch.setattr(
        cli_module,
        "build_pandapower_profile",
        lambda: selected.append(True) or profile,
        raising=False,
    )

    def prepare(selected_profile: object, **kwargs: object) -> SimpleNamespace:
        assert selected_profile is profile
        preparation_calls.append(kwargs)
        prepared.authority.workspace_root = cast(Path, kwargs["workspace"])
        return prepared

    monkeypatch.setattr(
        cli_module, "prepare_domain_runtime", prepare, raising=False
    )

    def fake_launch(_resolved: object, runtime_paths: object, **_kwargs: object) -> object:
        launch_paths.append(runtime_paths)
        return object()

    monkeypatch.setattr(cli_module, "build_pi_launch", fake_launch)

    class FakeAnalysisRunner:
        def __init__(self, **kwargs: object) -> None:
            runner_arguments.update(kwargs)

        def run(self, request: object) -> AnalysisOutcome:
            workspace = cast(Any, runner_arguments["workspace"])
            workspace.report_path.write_text("# report\n", encoding="utf-8")
            return AnalysisOutcome(
                analysis_id=workspace.analysis_id,
                status="completed",
                report_path=workspace.report_path,
                completed_turns=2,
                total_turns=2,
            )

    monkeypatch.setattr(cli_module, "AnalysisRunner", FakeAnalysisRunner)

    result = runner.invoke(
        app, ["analysis", "--instructions", str(instructions)]
    )

    assert result.exit_code == 0, result.stderr
    assert len(selected) == 1
    assert len(preparation_calls) == 1
    workspace_root = cast(Path, preparation_calls[0]["workspace"])
    assert preparation_calls[0] == {
        "executable": workspace_root / "bin/gridctl",
        "workspace": workspace_root,
        "tool_catalog_path": workspace_root / "tool-catalog.json",
        "guide_index_path": workspace_root / "guide-index.json",
    }
    runtime_paths = cast(Any, launch_paths[0])
    assert runtime_paths.tool_catalog_path == prepared.tool_catalog_path
    assert runtime_paths.guide_index_path == prepared.guide_index_path
    assert runtime_paths.system_policy_path == profile.manifest.system_policy_path
    assert runtime_paths.domain_runtime_descriptor_path == (
        workspace_root / "domain-runtime.json"
    )
    projector = cast(Any, runner_arguments["projector"])
    assert projector._authority is authority
    assert projector._projector_registry is profile.projector_registry
    assert runner_arguments["environment"] == {
        "provider": "test-provider",
        "model": "test-model",
        "pandapower": "3.4.0-test",
        "gridctl": str(workspace_root / "bin/gridctl"),
    }
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}


def test_run_manifest_mismatch_fails_before_pi_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _FakeRpcClient.starts = 0
    _patch_live_runtime(monkeypatch, tmp_path)
    profile = _profile(tmp_path)
    monkeypatch.setattr(
        cli_module, "build_pandapower_profile", lambda: profile, raising=False
    )
    monkeypatch.setattr(
        cli_module,
        "prepare_domain_runtime",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            DomainManifestError("protocol_version mismatch")
        ),
        raising=False,
    )

    result = CliRunner().invoke(app, ["run", "列出可用网络"])

    assert result.exit_code == 1
    assert _FakeRpcClient.starts == 0
    assert "DomainManifestError" in result.stdout
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}


def test_analysis_cli_emits_one_envelope_and_uses_self_contained_paths(
    cli_harness: tuple[CliRunner, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, instructions = cli_harness
    monkeypatch.setattr("grid_agent.cli.app._execute_analysis", _fake_execute_analysis)

    result = runner.invoke(app, ["analysis", "--instructions", str(instructions)])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert len(result.stdout.splitlines()) == 1
    envelope = AnswerEnvelope.model_validate_json(result.stdout)
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}
    assert "trajectory" not in result.stdout
    analysis_root = instructions.parent / "runs" / envelope.question_id
    assert envelope.answer_output == f"runs/{envelope.question_id}/report.md"
    assert (analysis_root / "input/instructions.md.txt").is_file()
    assert (analysis_root / "output/answers.jsonl").is_file()
    assert (analysis_root / "context/analysis-context.json").is_file()


def test_failed_analysis_envelope_points_to_partial_report(
    cli_harness: tuple[CliRunner, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, instructions = cli_harness

    def failed_analysis(**kwargs: Any) -> AnalysisOutcome:
        completed = _fake_execute_analysis(**kwargs)
        return AnalysisOutcome(
            analysis_id=completed.analysis_id,
            status="failed",
            report_path=completed.report_path,
            completed_turns=4,
            total_turns=9,
            error="PiProtocolError: Pi provider failure: terminated",
        )

    monkeypatch.setattr("grid_agent.cli.app._execute_analysis", failed_analysis)

    result = runner.invoke(app, ["analysis", "--instructions", str(instructions)])

    assert result.exit_code == 1
    envelope = AnswerEnvelope.model_validate_json(result.stdout)
    assert envelope.answer_output == "分析未完成；部分报告已保存：runs/analysis-test/report.md"
    assert "execution limitation" not in result.stdout


def test_report_command_delegates_to_analysis_without_child_run(
    cli_harness: tuple[CliRunner, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, instructions = cli_harness
    monkeypatch.setattr("grid_agent.cli.app._execute_analysis", _fake_execute_analysis)
    monkeypatch.setattr(subprocess, "Popen", _fail_if_called)

    result = runner.invoke(app, ["report", "--questions", str(instructions)])

    assert result.exit_code == 0
    assert AnswerEnvelope.model_validate_json(result.stdout).question_id.startswith("analysis-")


def test_trajectory_serve_delegates_without_answer_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, object] = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("grid_agent.cli.app.serve_trajectory", lambda **kwargs: observed.update(kwargs))

    result = CliRunner().invoke(app, ["trajectory", "serve", "--port", "9000"])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert observed["port"] == 9000
    assert observed["host"] == "127.0.0.1"
    assert observed["runs_root"] == Path("runs")


def test_trajectory_serve_reports_startup_errors_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "grid_agent.cli.app.serve_trajectory",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("missing assets")),
    )

    result = CliRunner().invoke(app, ["trajectory", "serve"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "grid-agent trajectory error: missing assets" in result.stderr
