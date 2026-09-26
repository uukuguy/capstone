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
from grid_agent.compat.single_run import SingleRunAdapter, _DeterministicDiagnosticTransport
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
    monkeypatch.setattr(
        cli_module,
        "PiExtensionLocator",
        lambda *_args, **_kwargs: SimpleNamespace(
            resolve=lambda: tmp_path / "node_modules/pi-grid-tools/domain-tools.mjs"
        ),
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
            **_kwargs: object,
        ) -> Path:
            return workspace / "pi/domain-runtime.json"

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


@pytest.mark.parametrize("sidecar_bytes", (None, b"not-json"), ids=("missing", "corrupt"))
def test_single_run_adapter_projects_committed_answer_when_admission_sidecar_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sidecar_bytes: bytes | None,
) -> None:
    """A presentation value returned by the application is never public truth."""
    workspace = tmp_path / "runs" / "committed-answer"
    turn = workspace / "turns" / "turn-001"
    core = workspace / "core"
    turn.mkdir(parents=True)
    core.mkdir()
    answer = {
        "schema": "capability-agent-answer/1.0",
        "run_id": "committed-answer",
        "turn_id": "turn-001",
        "submission_id": "submission-001",
        "answer_output": "committed reader text",
        "referenced_bindings": ["grid"],
        "result_refs": ["result:sha256:1"],
        "evidence_refs": ["artifact:evidence/1"],
        "claims": [],
    }
    from capability_agent.trajectory.canonical import canonical_json_bytes
    from hashlib import sha256

    answer_bytes = canonical_json_bytes(answer)
    answer_ref = "answer:sha256:" + sha256(answer_bytes).hexdigest()
    (turn / "answer.json").write_bytes(answer_bytes)
    if sidecar_bytes is not None:
        (turn / "answer-admission.json").write_bytes(sidecar_bytes)
    event = SimpleNamespace(
        event_type="answer.submitted",
        turn_id="turn-001",
        payload={
            "answer_ref": answer_ref,
            "answer_path": "turns/turn-001/answer.json",
            "answer_sha256": sha256(answer_bytes).hexdigest(),
        },
    )
    completed = SimpleNamespace(
        event_type="turn.completed",
        turn_id="turn-001",
        payload={
            "answer_ref": answer_ref,
            "answer_path": "turns/turn-001/answer.json",
            "answer_sha256": sha256(answer_bytes).hexdigest(),
        },
    )
    monkeypatch.setattr(
        "grid_agent.compat.single_run.ApplicationContextStore.replay_events",
        lambda _path: (SimpleNamespace(run_id="committed-answer"), (event, completed)),
    )
    outcome = SimpleNamespace(
        rendered="untrusted rendered value",
        result=SimpleNamespace(core=SimpleNamespace(run_id="committed-answer", answer_refs=(answer_ref,))),
    )

    assert SingleRunAdapter.read_committed_answer(workspace, outcome) == "committed reader text"


@pytest.mark.parametrize("defect", ("missing-submitted", "duplicate-submitted", "outside-turns", "missing-completed", "forged-ref"))
def test_single_run_adapter_rejects_untrusted_committed_answer_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    workspace = tmp_path / "runs" / "rejected-answer"
    workspace.mkdir(parents=True)
    answer_ref = "answer:sha256:trusted"
    admission_ref = "admission:sha256:trusted"
    submitted = SimpleNamespace(
        event_type="answer.submitted", turn_id="turn-001",
        payload={"answer_ref": answer_ref, "admission_ref": admission_ref,
                 "answer_path": "turns/turn-001/answer.json"},
    )
    completed = SimpleNamespace(
        event_type="turn.completed", turn_id="turn-001",
        payload={"answer_ref": answer_ref, "admission_ref": admission_ref},
    )
    events: tuple[object, ...] = (submitted, completed)
    if defect == "missing-submitted":
        events = (completed,)
    elif defect == "duplicate-submitted":
        events = (submitted, submitted, completed)
    elif defect == "outside-turns":
        submitted = SimpleNamespace(
            event_type="answer.submitted", turn_id="turn-001",
            payload={"answer_ref": answer_ref, "admission_ref": admission_ref,
                     "answer_path": "core/answer.json"},
        )
        events = (submitted, completed)
    elif defect == "missing-completed":
        events = (submitted,)
    elif defect == "forged-ref":
        events = (SimpleNamespace(
            event_type="answer.submitted", turn_id="turn-001",
            payload={"answer_ref": "answer:sha256:forged", "admission_ref": admission_ref,
                     "answer_path": "turns/turn-001/answer.json"},
        ), completed)
    monkeypatch.setattr(
        "grid_agent.compat.single_run.ApplicationContextStore.replay_events",
        lambda _path: (SimpleNamespace(run_id="rejected-answer"), events),
    )
    outcome = SimpleNamespace(result=SimpleNamespace(core=SimpleNamespace(run_id="rejected-answer", answer_refs=(answer_ref,))))

    with pytest.raises(RuntimeError):
        SingleRunAdapter.read_committed_answer(workspace, outcome)


def test_single_run_adapter_rejects_a_foreign_run_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "runs" / "current-run"
    workspace.mkdir(parents=True)
    outcome = SimpleNamespace(
        result=SimpleNamespace(core=SimpleNamespace(run_id="current-run", answer_refs=("answer:sha256:1",)))
    )
    monkeypatch.setattr(
        "grid_agent.compat.single_run.ApplicationContextStore.replay_events",
        lambda _path: (SimpleNamespace(run_id="foreign-run"), ()),
    )

    with pytest.raises(RuntimeError, match="another run"):
        SingleRunAdapter.read_committed_answer(workspace, outcome)


def test_run_forwards_legacy_provider_options_to_single_run_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}

    class FakeSingleRunAdapter:
        model_request_capture_status = "unavailable"

        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def run(self) -> str:
            return "committed only"

    monkeypatch.setattr(cli_module, "SingleRunAdapter", FakeSingleRunAdapter)
    result = CliRunner().invoke(
        app,
        [
            "run", "question", "--question-id", "forwarded-options",
            "--provider", "fixture", "--model", "fixture-model",
            "--base-url", "https://provider.invalid", "--api-key-env", "FIXTURE_KEY",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert captured["provider"] == "fixture"
    assert captured["model"] == "fixture-model"
    assert captured["base_url"] == "https://provider.invalid"
    assert captured["api_key_env"] == "FIXTURE_KEY"
    assert json.loads(result.stdout) == {
        "question_id": "forwarded-options", "answer_output": "committed only"
    }


@pytest.mark.parametrize("failure", ("provider interrupted", "workspace already exists"))
def test_run_preserves_error_envelope_for_provider_and_duplicate_run_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    monkeypatch.chdir(tmp_path)

    class FailingSingleRunAdapter:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(self) -> str:
            raise RuntimeError(failure)

    monkeypatch.setattr(cli_module, "SingleRunAdapter", FailingSingleRunAdapter)
    result = CliRunner().invoke(
        app, ["run", "question", "--question-id", "existing-run"]
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "question_id": "existing-run",
        "answer_output": "执行限制 / execution limitation: RuntimeError",
    }
    assert failure in result.stderr


def test_real_offline_single_run_rejects_duplicate_question_id() -> None:
    question_id = "cli-duplicate-single-run"
    run_root = ROOT / "runs" / question_id
    import shutil

    shutil.rmtree(run_root, ignore_errors=True)
    command = [
        "uv", "run", "--project", "packages/grid-agent", "grid-agent", "run",
        "--offline", "--question-id", question_id,
        "IEEE-39节点系统中线路11连接哪两个母线?",
    ]
    try:
        first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60)
        assert first.returncode == 0, first.stderr
        duplicate = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60)
        assert duplicate.returncode == 1
        assert json.loads(duplicate.stdout) == {
            "question_id": question_id,
            "answer_output": "执行限制 / execution limitation: WorkspaceError",
        }
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def test_deterministic_offline_transport_projects_real_executor_calls() -> None:
    events: list[dict[str, object]] = []

    class Executor:
        def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
            if capability == "context.open":
                assert arguments == {"model_id": "ieee39"}
                return {"context_ref": "context:real", "projector": "context.open"}
            assert capability == "analysis.powerflow.ac.run"
            assert arguments == {"context_ref": "context:real"}
            return {
                "result_ref": "result:real", "projector": "analysis.powerflow",
                "evidence_refs": ["evidence:real"],
                "total_active_loss": {"value": 1.0, "unit": "MW"},
            }

    catalog = SimpleNamespace(domain_tools=(
        SimpleNamespace(
            name="grid_context_open",
            projector_id="model.context.open",
            key=SimpleNamespace(binding_id="grid", capability_id="context.open"),
        ),
        SimpleNamespace(
            name="grid_analysis_powerflow_ac_run",
            projector_id="analysis.powerflow.ac.run",
            key=SimpleNamespace(binding_id="grid", capability_id="analysis.powerflow.ac.run"),
        ),
    ))
    transport = _DeterministicDiagnosticTransport(Executor(), catalog)
    answer = transport.prompt_and_wait(
        "IEEE-39节点系统运行交流潮流", on_semantic_event=lambda event, *_args: events.append(dict(event))
    )

    assert "context:real" not in answer
    assert [event["type"] for event in events] == ["tool_execution_start", "tool_result"] * 2
    assert events[1]["capability_key"] == {
        "binding_id": "grid", "capability_id": "context.open"
    }


def test_deterministic_offline_transport_rejects_unpublished_capability() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class Executor:
        def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
            calls.append((capability, arguments))
            return {}

    transport = _DeterministicDiagnosticTransport(Executor(), SimpleNamespace(domain_tools=()))
    with pytest.raises(RuntimeError, match="not published"):
        transport.prompt_and_wait(
            "IEEE-39节点系统运行交流潮流", on_semantic_event=lambda *_args: None
        )
    assert calls == []


def test_progress_reporter_renders_application_provider_and_waiting_events(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = cli_module._ProgressReporter("input question")
    reporter.on_event({
        "type": "application_provider_resolved", "run_id": "run-1",
        "provider": "fixture", "model": "fixture-model",
        "timeout_seconds": 12.0, "max_retries": 2,
    })
    reporter.on_event({"type": "application_waiting"})

    captured = capsys.readouterr()
    assert captured.out == ""
    stderr = captured.err
    assert "provider=fixture model=fixture-model" in stderr
    assert "12s SDK重试=2次" in stderr
    assert "调用输入: input question" in stderr
    assert "仍在等待模型或工具响应" in stderr


def test_run_selects_builtin_profile_before_pi_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The legacy CLI is now a thin projection over application execution."""
    monkeypatch.chdir(tmp_path)
    _FakeRpcClient.starts = 0
    captured: dict[str, object] = {}

    class FakeSingleRunAdapter:
        model_request_capture_status = "unavailable"

        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def run(self) -> str:
            return "application committed answer"

    monkeypatch.setattr(cli_module, "SingleRunAdapter", FakeSingleRunAdapter)

    result = CliRunner().invoke(
        app,
        ["run", "列出可用网络", "--question-id", "stdout-byte-contract"],
    )

    assert result.exit_code == 0, result.stderr
    assert captured["request"].question_id == "stdout-byte-contract"
    assert _FakeRpcClient.starts == 0
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}
    assert AnswerEnvelope.model_validate_json(result.stdout).answer_output == (
        "application committed answer"
    )
    assert result.stdout == (
        '{"question_id": "stdout-byte-contract", '
        '"answer_output": "application committed answer"}\n'
    )


@pytest.mark.parametrize(
    "question_id",
    (
        "../escape",
        "/tmp/escape",
        "nested/name",
        r"nested\name",
        "x" * 129,
    ),
)
def test_run_invalid_question_id_preserves_single_json_stdout_envelope(
    question_id: str,
) -> None:
    result = CliRunner().invoke(
        app,
        ["run", "列出可用网络", "--question-id", question_id],
    )

    assert result.exit_code == 1
    assert len(result.stdout.splitlines()) == 1
    payload = json.loads(result.stdout)
    assert set(payload) == {"question_id", "answer_output"}
    assert payload["question_id"] == question_id
    assert "execution limitation" in payload["answer_output"]
    assert "grid-agent error:" in result.stderr
    assert "Traceback" not in result.stderr


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
        workspace_root / "pi/domain-runtime.json"
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
    class FailingSingleRunAdapter:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(self) -> str:
            raise DomainManifestError("protocol_version mismatch")

    monkeypatch.setattr(cli_module, "SingleRunAdapter", FailingSingleRunAdapter)

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
    assert result.stderr == "model request capture: unavailable\n"
    assert len(result.stdout.splitlines()) == 1
    envelope = AnswerEnvelope.model_validate_json(result.stdout)
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}
    assert "trajectory" not in result.stdout
    analysis_root = instructions.parent / "runs" / envelope.question_id
    assert envelope.answer_output == f"runs/{envelope.question_id}/report.md"
    assert (analysis_root / "input/instructions.md.txt").is_file()
    assert (analysis_root / "output/answers.jsonl").is_file()
    assert (analysis_root / "context/analysis-context.json").is_file()


def test_analysis_rejects_provider_configuration_before_creating_a_run(
    cli_harness: tuple[CliRunner, Path],
) -> None:
    runner, instructions = cli_harness
    result = runner.invoke(
        app, ["analysis", "--instructions", str(instructions), "--provider", "unknown"]
    )

    assert result.exit_code == 1
    assert "unknown provider 'unknown'" in result.stderr
    assert not (instructions.parent / "runs").exists()


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
