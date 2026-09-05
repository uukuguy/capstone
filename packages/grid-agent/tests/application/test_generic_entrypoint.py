from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.output import (
    JsonOutputRenderer,
)
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.domain.answer_admission import AnswerAdmissionInput
from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity

import grid_agent.application.composition as composition_module
from grid_agent.application.composition import (
    build_generic_application,
    run_generic_application,
)
from grid_agent.application.paths import ProjectPaths
from grid_agent.application.profile import build_pandapower_application_profile


@dataclass
class _Provider:
    answers: tuple[str, ...] = ("first", "second")
    started: bool = False
    stopped: bool = False
    index: int = 0

    def start(self) -> None:
        self.started = True

    def prompt_and_wait(self, _question: str, **_kwargs: object) -> str:
        answer = self.answers[self.index]
        self.index += 1
        return answer

    def stop(self) -> None:
        self.stopped = True


@dataclass
class _LegacyProvider:
    answer: str = "legacy answer"
    started: bool = False
    stopped: bool = False
    received: dict[str, object] | None = None

    def start(self) -> None:
        self.started = True

    def prompt(self, _question: str, **kwargs: object) -> str:
        self.received = dict(kwargs)
        return self.answer

    def stop(self) -> None:
        self.stopped = True


class _Renderer:
    def render(self, result: object) -> str:
        return JsonOutputRenderer().render(result)  # type: ignore[arg-type]


OFFLINE_QUESTION = "What is AC power flow"


def _offline_answer(profile: object) -> str:
    binding = profile.domains[0]  # type: ignore[attr-defined]
    policy = binding.profile.create_answer_admission_policy(object())
    return policy.admit(
        AnswerAdmissionInput(OFFLINE_QUESTION, "ignored", (), ())
    ).answer_output


def _prepared(profile: object) -> SimpleNamespace:
    binding = profile.domains[0]  # type: ignore[attr-defined]
    endpoint = SimpleNamespace(close=lambda: None)
    return SimpleNamespace(
        bindings={
            "grid": SimpleNamespace(
                binding=binding,
                endpoint=endpoint,
                runtime=SimpleNamespace(authority=SimpleNamespace(authority_id="gridctl")),
            )
        }
    )


def test_generic_entrypoint_rejects_prepared_runtime_without_bindings() -> None:
    with pytest.raises(ApplicationConfigurationError, match="prepared application"):
        build_generic_application(
            "pandapower-static-analysis",
            prepared_application=SimpleNamespace(),
        )


def test_generic_entrypoint_adapts_legacy_prompt_provider_with_all_callbacks(
    tmp_path: Path,
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="legacy-run", binding_ids=("grid",)
    )
    provider = _LegacyProvider()
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=provider,
        workspace=workspace,
        catalog=object(),
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        (OFFLINE_QUESTION,),
        application=application,
    )

    assert outcome.status == "completed", outcome.error
    assert provider.started is True
    assert provider.stopped is True
    assert provider.received is not None
    assert provider.received["correlation_id"]
    assert callable(provider.received["on_semantic_event"])
    assert callable(provider.received["on_heartbeat"])


def test_generic_entrypoint_renders_validated_core_and_domain_sections(
    tmp_path: Path,
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    provider = _Provider()
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=provider,
        workspace=workspace,
        catalog=object(),
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        (OFFLINE_QUESTION, OFFLINE_QUESTION),
        application=application,
    )

    assert outcome.status == "completed", outcome.error
    assert provider.started is True
    assert provider.stopped is True
    assert outcome.result.schema == "capability-agent-output/1.0"
    assert outcome.result.core.application_id == "pandapower-static-analysis"
    assert outcome.result.core.report_ref is not None
    assert tuple(outcome.result.domains) == ("grid",)
    domain_payload = outcome.result.domains["grid"].payload
    assert domain_payload == {
        "mode": "continuous-static-analysis",
        "instruction_count": 2,
        "completed_count": 2,
        "failed_count": 0,
        "report_artifact_ref": outcome.result.core.report_ref,
    }
    assert workspace.output_path.joinpath("report.md").is_file()
    report = workspace.output_path.joinpath("report.md").read_text(encoding="utf-8")
    assert report.startswith("# 系统仿真分析报告")
    assert "## 本批次运行环境" in report
    assert f"## 1. {OFFLINE_QUESTION}" in report
    assert "### 回答" in report
    assert "### 仿真环境上下文" in report
    assert "### 智能体分析轨迹" in report
    assert "### 执行状态与证据" in report
    report_digest = sha256(
        workspace.output_path.joinpath("report.md").read_bytes()
    ).hexdigest()
    assert outcome.result.core.report_ref == f"artifact:sha256:{report_digest}"
    assert outcome.result.core.report_ref in workspace.root.joinpath(
        "core/context-events.jsonl"
    ).read_text(encoding="utf-8")
    assert isinstance(outcome.rendered, str)
    rendered = json.loads(outcome.rendered)
    assert set(rendered) == {"schema", "core", "domains"}
    assert set(rendered["core"]) == {
        "application_id",
        "application_version",
        "run_id",
        "status",
        "answer_refs",
        "report_ref",
        "diagnostic_refs",
    }
    assert set(rendered["domains"]["grid"]) == {
        "domain_id",
        "domain_version",
        "schema",
        "status",
        "payload",
    }
    assert rendered["core"]["report_ref"] == rendered["domains"]["grid"][
        "payload"
    ]["report_artifact_ref"]


def test_generic_pandapower_application_checkpoints_standard_submission_answers(
    tmp_path: Path,
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=_Provider(),
        workspace=workspace,
        catalog=object(),
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        (OFFLINE_QUESTION, OFFLINE_QUESTION),
        application=application,
    )

    assert outcome.status == "completed"
    assert [
        json.loads(line)
        for line in (workspace.output_path / "answers.jsonl").read_text().splitlines()
    ] == [
        {"question_id": "run-1-t001", "answer_output": _offline_answer(profile)},
        {"question_id": "run-1-t002", "answer_output": _offline_answer(profile)},
    ]


def test_generic_pandapower_renderer_failure_keeps_accepted_answers_and_submission_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real pandapower report shell is derived output, not answer state."""

    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-1", binding_ids=("grid",)
    )
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=_Provider(),
        workspace=workspace,
        catalog=object(),
    )

    def fail_renderer(**_kwargs: object) -> str:
        raise RuntimeError("renderer credential=secret-path")

    monkeypatch.setattr(
        "grid_agent.compat.v1_0_1_report.render_analysis_report", fail_renderer
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        (OFFLINE_QUESTION, OFFLINE_QUESTION),
        application=application,
    )

    assert outcome.status == "completed", outcome.error
    assert outcome.result.core.report_ref is None
    assert len(outcome.result.core.answer_refs) == 2
    assert [
        json.loads(line)
        for line in (workspace.output_path / "answers.jsonl").read_text().splitlines()
    ] == [
        {"question_id": "run-1-t001", "answer_output": _offline_answer(profile)},
        {"question_id": "run-1-t002", "answer_output": _offline_answer(profile)},
    ]
    assert "renderer credential" not in "\n".join(outcome.result.core.diagnostic_refs)


def test_generic_pandapower_report_symlink_rejection_keeps_accepted_answers(
    tmp_path: Path,
) -> None:
    """A rejected report leaf never follows its symlink or revokes answers."""

    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-1", binding_ids=("grid",)
    )
    outside = tmp_path / "outside-report.md"
    outside.write_text("outside bytes", encoding="utf-8")
    (workspace.output_path / "report.md").symlink_to(outside)
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=_Provider(),
        workspace=workspace,
        catalog=object(),
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        (OFFLINE_QUESTION, OFFLINE_QUESTION),
        application=application,
    )

    assert outcome.status == "completed", outcome.error
    assert outcome.result.core.report_ref is None
    assert len(outcome.result.core.answer_refs) == 2
    assert outside.read_text(encoding="utf-8") == "outside bytes"
    assert (workspace.output_path / "report.md").is_symlink()
    assert [
        json.loads(line)
        for line in (workspace.output_path / "answers.jsonl").read_text().splitlines()
    ] == [
        {"question_id": "run-1-t001", "answer_output": _offline_answer(profile)},
        {"question_id": "run-1-t002", "answer_output": _offline_answer(profile)},
    ]


def test_generic_pandapower_answer_submission_failure_remains_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Required controller persistence is not presentation and must fail closed."""

    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-1", binding_ids=("grid",)
    )
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=_Provider(answers=("accepted",)),
        workspace=workspace,
        catalog=object(),
    )

    def fail_submit(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("authority persistence failed")

    monkeypatch.setattr(
        "capability_agent.application.runner.TurnController.submit", fail_submit
    )

    outcome = run_generic_application(
        "pandapower-static-analysis", (OFFLINE_QUESTION,), application=application
    )

    assert outcome.status == "failed"
    assert outcome.result.core.answer_refs == ()
    assert (workspace.output_path / "answers.jsonl").read_text(encoding="utf-8") == ""


def test_generic_pandapower_application_retains_checkpoint_after_later_failure(
    tmp_path: Path,
) -> None:
    class FailingProvider(_Provider):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            if self.index == 1:
                raise RuntimeError("second question failed")
            return super().prompt_and_wait(question, **kwargs)

    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=FailingProvider(),
        workspace=workspace,
        catalog=object(),
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        (OFFLINE_QUESTION, OFFLINE_QUESTION),
        application=application,
    )

    assert outcome.status == "failed"
    assert [
        json.loads(line)
        for line in (workspace.output_path / "answers.jsonl").read_text().splitlines()
    ] == [{"question_id": "run-1-t001", "answer_output": _offline_answer(profile)}]


def test_generic_pandapower_application_prepares_empty_submission_checkpoint(
    tmp_path: Path,
) -> None:
    class FirstQuestionFails(_Provider):
        def prompt_and_wait(self, _question: str, **_kwargs: object) -> str:
            raise RuntimeError("first question failed")

    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=FirstQuestionFails(),
        workspace=workspace,
        catalog=object(),
    )

    outcome = run_generic_application(
        "pandapower-static-analysis",
        ("first",),
        application=application,
    )

    assert outcome.status == "failed"
    assert (workspace.output_path / "answers.jsonl").read_text(encoding="utf-8") == ""


def test_generic_pandapower_application_continues_after_initial_submission_checkpoint_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=_Provider(answers=("accepted",)),
        workspace=workspace,
        catalog=object(),
    )
    calls = 0

    def fail_initial_checkpoint(**kwargs: object) -> Path:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("credential=secret-path")
        from grid_agent.compat.v1_0_1_submission import write_submission_checkpoint

        return write_submission_checkpoint(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "grid_agent.compat.v1_0_1_report.write_submission_checkpoint",
        fail_initial_checkpoint,
    )

    outcome = run_generic_application(
        "pandapower-static-analysis", (OFFLINE_QUESTION,), application=application
    )

    assert outcome.status == "completed", outcome.error
    assert workspace.output_path.joinpath("report.md").is_file()
    assert "Submission checkpoint unavailable" in workspace.output_path.joinpath(
        "report.md"
    ).read_text(encoding="utf-8")
    assert "secret-path" not in workspace.output_path.joinpath("report.md").read_text(
        encoding="utf-8"
    )


def test_generic_pandapower_application_preserves_prior_submission_checkpoint_after_refresh_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=_Provider(),
        workspace=workspace,
        catalog=object(),
    )
    from grid_agent.compat.v1_0_1_submission import write_submission_checkpoint

    calls = 0

    def fail_refresh_after_first_answer(**kwargs: object) -> Path:
        nonlocal calls
        calls += 1
        if calls >= 3:
            raise OSError("credential=secret-path")
        return write_submission_checkpoint(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "grid_agent.compat.v1_0_1_report.write_submission_checkpoint",
        fail_refresh_after_first_answer,
    )

    outcome = run_generic_application(
        "pandapower-static-analysis", (OFFLINE_QUESTION, OFFLINE_QUESTION), application=application
    )

    assert outcome.status == "completed", outcome.error
    assert [
        json.loads(line)
        for line in (workspace.output_path / "answers.jsonl").read_text().splitlines()
    ] == [{"question_id": "run-1-t001", "answer_output": _offline_answer(profile)}]
    report = workspace.output_path.joinpath("report.md").read_text(encoding="utf-8")
    assert f"## 2. {OFFLINE_QUESTION}" in report
    assert "Submission checkpoint unavailable" in report
    assert "secret-path" not in report


def test_generic_entrypoint_rejects_request_for_a_different_application(
    tmp_path: Path,
) -> None:
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("grid",))
    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider=_Provider(),
        workspace=workspace,
        catalog=object(),
    )

    with pytest.raises(ApplicationConfigurationError, match="identity"):
        run_generic_application("other-application", (), application=application)


def test_generic_composition_injects_product_owned_runtime_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The grid composition root supplies trusted Pi assets to the generic Kernel."""

    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.extension import ExtensionSpec

    monkeypatch.chdir(tmp_path)
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="host-run", binding_ids=("grid",)
    )
    command = PiCommand(
        argv=("node", "/product-owned/pi.js"),
        identity=PiRuntimeIdentity(
            path=Path("/product-owned/pi.js"),
            source="fixture",
            package_version="1.0.0",
            lock_sha256="fixture-lock",
        ),
    )
    lock_calls: dict[str, Path] = {}
    locator_calls: dict[str, object] = {}

    class FakeLock:
        @classmethod
        def load(cls, path: Path) -> object:
            lock_calls["path"] = path
            return cls()

    class FakeRuntimeLocator:
        def __init__(
            self,
            runtime_dir: Path,
            environ: object,
            *,
            runtime_lock: object,
        ) -> None:
            locator_calls.update(
                runtime_dir=runtime_dir,
                environ=environ,
                runtime_lock=runtime_lock,
            )

        def resolve(self) -> PiCommand:
            return command

    class FakeExtensionLocator:
        def __init__(self, project_root: Path, *, spec: ExtensionSpec) -> None:
            locator_calls["extension_root"] = project_root
            locator_calls["extension_spec"] = spec

        def resolve(self) -> Path:
            return tmp_path / "trusted-extension.mjs"

    monkeypatch.setattr(
        composition_module,
        "_runtime_host_dependencies",
        lambda: (FakeExtensionLocator, FakeLock, FakeRuntimeLocator),
    )

    application = build_generic_application(
        "pandapower-static-analysis",
        prepared_application=_prepared(profile),
        provider_catalog=object(),
        workspace=workspace,
        environment={"PATH": "/usr/bin"},
        catalog=object(),
    )

    assert isinstance(application.runtime_host, RuntimeHost)
    assert application.runtime_host.command == command
    assert application.runtime_host.project_pi_dir == ProjectPaths.from_root(
        tmp_path
    ).pi_agent_dir
    assert application.runtime_host.extension_path == tmp_path / "trusted-extension.mjs"
    assert application.runtime_host.system_policy_path == profile.domains[0].profile.manifest.system_policy_path
    assert locator_calls["runtime_dir"] == ProjectPaths.from_root(tmp_path).pi_runtime_dir
    assert lock_calls["path"] == ProjectPaths.from_root(tmp_path).runtime_lock
    assert locator_calls["extension_root"] == tmp_path
    extension_spec = locator_calls["extension_spec"]
    assert isinstance(extension_spec, ExtensionSpec)
    assert extension_spec.package_name == "@capability-agent/pi-tools"
    assert extension_spec.package_version == "0.1.0"
    assert extension_spec.candidates == (Path("packages/pi-capability-tools"),)


def test_generic_host_resolves_domain_neutral_pi_extension() -> None:
    """Generic composition must bind the v1 runtime to generic Pi tools."""

    from capability_agent.runtime.extension import ExtensionSpec

    project_root = Path(__file__).resolve().parents[4]
    extension_locator, _lock, _runtime = composition_module._runtime_host_dependencies()

    assert extension_locator.__module__ == "capability_agent.runtime.extension"
    extension = extension_locator(
        project_root,
        spec=ExtensionSpec(
            package_name="@capability-agent/pi-tools",
            package_version="0.1.0",
            candidates=(Path("packages/pi-capability-tools"),),
        ),
    ).resolve()

    assert extension == project_root / "packages/pi-capability-tools/src/domain-tools.mjs"
    assert "pi-grid-tools" not in extension.parts
