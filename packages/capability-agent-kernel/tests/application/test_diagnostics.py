from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.trajectory.artifacts import ImmutableArtifactRegistry


class _Transport:
    def __init__(self, *, heartbeat: bool = False) -> None:
        self.answers = iter(("one", "two"))
        self.heartbeat = heartbeat

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def prompt_and_wait(self, _question: str, **kwargs: object) -> str:
        if self.heartbeat:
            kwargs["on_heartbeat"]()
        return next(self.answers)


class _Controller:
    def start(self, ordinal: int, _question: str) -> object:
        return SimpleNamespace(turn_id=f"turn-{ordinal}", started_monotonic=0.0)

    def submit(self, handle: object, *, answer_output: str, **_kwargs: object) -> object:
        return SimpleNamespace(
            answer_ref=f"answer:{handle.turn_id}", answer_output=answer_output,
            referenced_bindings=(), result_refs=(), evidence_refs=(), status="success",
        )

    def fail(self, _handle: object, **_kwargs: object) -> object:
        return SimpleNamespace(status="failed")


def _application(tmp_path: Path, *, render, heartbeat: bool = False, observer=None) -> AgentApplication:
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="diagnostic-run", binding_ids=())
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(render=render),
    )
    return AgentApplication(
        profile=profile, prepared_application=SimpleNamespace(bindings={}), catalog=object(),
        provider=_Transport(heartbeat=heartbeat), workspace=workspace, turn_controller=_Controller(),
        binding_identities=(),
        semantic_event_observer=observer,
    )


def _diagnostic_payload(workspace: ApplicationWorkspace, reference: str) -> dict[str, object]:
    digest = reference.removeprefix("artifact:sha256:")
    for path in workspace.core_path.glob("diagnostics/*/diagnostic.json"):
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() == digest:
            return json.loads(payload)
    raise AssertionError("diagnostic artifact matching reference was not found")


def test_report_fault_persists_sanitized_run_scoped_diagnostic(tmp_path: Path) -> None:
    secret = "diagnostic-test-secret"
    application = _application(
        tmp_path, render=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError(secret))
    )

    outcome = application.run(ApplicationRequest(application_id="fixture-app", questions=("one", "two")))

    assert outcome.status == "completed"
    assert outcome.result.core.diagnostic_refs
    workspace = application.workspace
    assert workspace is not None
    payload = next(
        _diagnostic_payload(workspace, reference)
        for reference in outcome.result.core.diagnostic_refs
        if _diagnostic_payload(workspace, reference)["code"] == "report_unavailable"
    )
    assert payload["schema"] == "application-diagnostic/1.0"
    assert payload["run_id"] == "diagnostic-run"
    assert payload["code"] == "report_unavailable"
    assert secret not in json.dumps(payload)


def test_diagnostic_persistence_failure_falls_back_to_sanitized_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        ImmutableArtifactRegistry, "write_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("diagnostic-test-secret"))
    )
    application = _application(
        tmp_path, render=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("renderer-secret"))
    )

    outcome = application.run(ApplicationRequest(application_id="fixture-app", questions=("one", "two")))

    captured = capsys.readouterr()
    assert outcome.status == "completed"
    assert outcome.result.core.diagnostic_refs == ()
    assert captured.out == ""
    assert "report_unavailable" in captured.err
    assert "diagnostic-test-secret" not in captured.err
    assert "renderer-secret" not in captured.err


def test_waiting_observer_failure_persists_sanitized_diagnostic(tmp_path: Path) -> None:
    application = _application(
        tmp_path,
        render=lambda **_kwargs: "report",
        heartbeat=True,
        observer=lambda _event: (_ for _ in ()).throw(RuntimeError("observer-secret")),
    )

    outcome = application.run(ApplicationRequest(application_id="fixture-app", questions=("one", "two")))

    assert outcome.status == "completed"
    workspace = application.workspace
    assert workspace is not None
    assert any(
        _diagnostic_payload(workspace, reference)["code"] == "progress_observer_unavailable"
        for reference in outcome.result.core.diagnostic_refs
    )
