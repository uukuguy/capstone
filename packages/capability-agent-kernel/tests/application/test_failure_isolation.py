from __future__ import annotations

from types import SimpleNamespace

import pytest

import capability_agent.application.runner as runner_module
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.trajectory.artifacts import ImmutableArtifactRegistry


class Transport:
    def __init__(self) -> None:
        self.answers = iter(("one", "two"))

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
    def prompt_and_wait(self, _question: str, **kwargs: object) -> str:
        callback = kwargs.get("on_semantic_event")
        if callable(callback):
            callback({"type": "tool_result"})
        return next(self.answers)


class Controller:
    def start(self, ordinal: int, _question: str) -> object:
        return SimpleNamespace(turn_id=f"t-{ordinal}", started_monotonic=0.0)

    def submit(self, handle: object, *, answer_output: str, **_kwargs: object) -> object:
        return SimpleNamespace(answer_ref=f"answer:{handle.turn_id}", answer_output=answer_output, result_refs=(), evidence_refs=(), status="success")

    def fail(self, _handle: object, **_kwargs: object) -> object:
        return SimpleNamespace(status="failed")


def make_application(tmp_path, report_shell, *, workspace=None, store=None, projector=None, observer=None):
    workspace = workspace or ApplicationWorkspace.create(tmp_path / "runs", run_id="isolation-run", binding_ids=())
    profile = SimpleNamespace(manifest=SimpleNamespace(application_id="fixture", version="1"), application_policy=SimpleNamespace(load=lambda: None), output_renderer=SimpleNamespace(render=lambda result: result), report_shell=report_shell)
    return AgentApplication(profile=profile, prepared_application=SimpleNamespace(bindings={}), catalog=object(), provider=Transport(), workspace=workspace, store=store, turn_controller=Controller(), projector=projector, binding_identities=(), semantic_event_observer=observer)


def assert_report_fault_keeps_answers(outcome, *, report_unavailable: bool = True):
    assert outcome.status == "completed"
    assert outcome.completed_questions == 2
    assert len(outcome.result.core.answer_refs) == 2
    if report_unavailable:
        assert outcome.result.core.report_ref is None
    else:
        assert outcome.result.core.report_ref is not None


@pytest.mark.parametrize("shell", [
    SimpleNamespace(prepare=lambda **_: (_ for _ in ()).throw(OSError("prepare")), render=lambda **_: "report"),
    SimpleNamespace(render=lambda **_: (_ for _ in ()).throw(RuntimeError("render"))),
])
def test_report_shell_faults_do_not_revoke_accepted_answers(tmp_path, shell):
    outcome = make_application(tmp_path, shell).run(ApplicationRequest(application_id="fixture", questions=("a", "b")))
    assert_report_fault_keeps_answers(outcome, report_unavailable=not hasattr(shell, "prepare"))


def test_checkpoint_writer_failure_can_recover_for_final_publication(tmp_path, monkeypatch):
    original = runner_module._write_report_atomically
    calls = 0
    def fail_checkpoints(path, report):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise OSError("checkpoint")
        original(path, report)
    monkeypatch.setattr(runner_module, "_write_report_atomically", fail_checkpoints)
    outcome = make_application(tmp_path, SimpleNamespace(render=lambda **_: "report")).run(ApplicationRequest(application_id="fixture", questions=("a", "b")))
    assert_report_fault_keeps_answers(outcome, report_unavailable=False)


def test_final_artifact_admission_failure_does_not_revoke_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(ImmutableArtifactRegistry, "register_existing", lambda *_a, **_k: (_ for _ in ()).throw(OSError("admission")))
    outcome = make_application(tmp_path, SimpleNamespace(render=lambda **_: "report")).run(ApplicationRequest(application_id="fixture", questions=("a", "b")))
    assert_report_fault_keeps_answers(outcome)


def test_report_reference_append_failure_does_not_revoke_answers(tmp_path):
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="isolation-run", binding_ids=())
    base = ApplicationContextStore.initialize(workspace)
    class Store:
        @property
        def snapshot(self): return base.snapshot
        def append(self, draft):
            if draft.event_type == "reference.produced": raise OSError("reference")
            return base.append(draft)
    outcome = make_application(tmp_path, SimpleNamespace(render=lambda **_: "report"), workspace=workspace, store=Store()).run(ApplicationRequest(application_id="fixture", questions=("a", "b")))
    assert_report_fault_keeps_answers(outcome)


def test_required_completion_append_failure_is_fail_closed(tmp_path):
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="isolation-run", binding_ids=())
    base = ApplicationContextStore.initialize(workspace)
    class Store:
        @property
        def snapshot(self): return base.snapshot
        def append(self, draft):
            if draft.event_type == "application.completed": raise OSError("completion")
            return base.append(draft)
    outcome = make_application(tmp_path, SimpleNamespace(render=lambda **_: "report"), workspace=workspace, store=Store()).run(ApplicationRequest(application_id="fixture", questions=("a", "b")))
    assert outcome.status == "failed"


def test_projector_and_control_flow_failures_are_not_isolated(tmp_path):
    class Projector:
        def observe(self, *_a, **_k):
            raise RuntimeError("admission")

    outcome = make_application(tmp_path, SimpleNamespace(render=lambda **_: "report"), projector=Projector()).run(ApplicationRequest(application_id="fixture", questions=("a", "b")))
    assert outcome.status == "failed"


@pytest.mark.parametrize("exception_type", (KeyboardInterrupt, SystemExit))
@pytest.mark.parametrize("source", ("renderer", "observer"))
def test_base_exception_from_renderer_or_observer_propagates(tmp_path, exception_type, source):
    def raise_control_flow(**_kwargs):
        raise exception_type()

    shell = SimpleNamespace(render=raise_control_flow if source == "renderer" else lambda **_: "report")
    observer = (lambda _event: raise_control_flow()) if source == "observer" else None
    application = make_application(tmp_path, shell, observer=observer)

    with pytest.raises(exception_type):
        application.run(ApplicationRequest(application_id="fixture", questions=("a", "b")))
