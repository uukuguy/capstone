from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest
import capability_agent.application.runner as runner_module

from capability_agent.application.output import (
    BindingIdentity,
    CoreRunResult,
    FrameworkOutputComposer,
    ValidatedDomainOutput,
)
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.projector import ApplicationInvocationProjector
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.application.turns import TurnController
from capability_agent.domain.answer_admission import AnswerAdmissionDecision
from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.tools.catalog import CompositeToolCatalog


@dataclass
class FakeTransport:
    events: list[str]
    answers: list[str] = field(default_factory=lambda: ["one", "two"])
    prompt_kwargs: list[dict[str, object]] = field(default_factory=list)

    def start(self) -> None:
        self.events.append("provider.start")

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        self.events.append(f"question:{question}")
        self.prompt_kwargs.append(kwargs)
        return self.answers.pop(0)

    def stop(self) -> None:
        self.events.append("provider.stop")


@dataclass
class FakeController:
    events: list[str]
    answers: list[object] = field(default_factory=list)
    failed: list[tuple[object, dict[str, object]]] = field(default_factory=list)
    submissions: list[dict[str, object]] = field(default_factory=list)

    def start(self, ordinal: int, instruction: str) -> object:
        self.events.append(f"turn.start:{ordinal}")
        return SimpleNamespace(turn_id=f"turn-{ordinal}", started_monotonic=0.0)

    def submit(self, handle: object, **kwargs: object) -> object:
        self.events.append(f"turn.submit:{handle.turn_id}")
        self.submissions.append(kwargs)
        answer = SimpleNamespace(
            answer_ref=f"answer:{handle.turn_id}",
            answer_output=kwargs["answer_output"],
            referenced_bindings=("alpha",),
            result_refs=(),
            evidence_refs=(),
            status="success",
            error=None,
        )
        self.answers.append(answer)
        return answer

    def fail(self, handle: object, **kwargs: object) -> object:
        self.events.append(f"turn.fail:{handle.turn_id}")
        self.failed.append((handle, kwargs))
        return SimpleNamespace(status="failed", error=kwargs.get("error"))


def _valid_binding(*, endpoint: object | None = None) -> object:
    values = {
        "binding_id": "alpha",
        "profile": SimpleNamespace(
            policy_provider=SimpleNamespace(load=lambda: None),
            guide_provider=SimpleNamespace(load=lambda: ()),
            validate_answer_admission_declaration=lambda: None,
            create_answer_admission_policy=lambda _authority: SimpleNamespace(admit=lambda _request: None),
        ),
        "runtime": SimpleNamespace(authority=object()),
    }
    if endpoint is not None:
        values["endpoint"] = endpoint
    return SimpleNamespace(**values)


def test_runner_builds_default_invocation_projector_for_real_run_state(
    tmp_path: Path,
) -> None:
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="projector-run", binding_ids=()
    )
    store = ApplicationContextStore.initialize(workspace)
    catalog = CompositeToolCatalog(core_tools=(), domain_tools=())
    application = AgentApplication(
        profile=SimpleNamespace(manifest=SimpleNamespace(application_id="fixture-app"))
    )

    projector = application._ensure_projector(store, catalog, {})

    assert isinstance(projector, ApplicationInvocationProjector)
    assert projector.store is store


def test_runner_preserves_explicit_projector() -> None:
    explicit = object()
    application = AgentApplication(
        profile=SimpleNamespace(manifest=SimpleNamespace(application_id="fixture-app")),
        projector=explicit,
    )

    assert application._ensure_projector(None, None, {}) is explicit


def test_runner_binds_current_prompt_projection_references_to_answer(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    result_ref = "result:sha256:" + "a" * 64
    evidence_ref = "evidence:sha256:" + "b" * 64

    class ProjectingTransport(FakeTransport):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            callback = kwargs["on_semantic_event"]
            callback({"type": "tool_result"}, 1)
            return "grounded answer"

    class Projector:
        def observe(self, *_args: object, **_kwargs: object) -> object:
            return SimpleNamespace(
                binding_id="alpha",
                result_refs=(result_ref,),
                evidence_refs=(evidence_ref,),
            )

    transport = ProjectingTransport(events, answers=[])
    controller = FakeController(events)
    binding = SimpleNamespace(
        binding_id="alpha",
        profile=SimpleNamespace(
            policy_provider=SimpleNamespace(load=lambda: None),
            guide_provider=SimpleNamespace(load=lambda: ()),
            validate_answer_admission_declaration=lambda: None,
            create_answer_admission_policy=lambda _authority: SimpleNamespace(admit=lambda _request: None),
        ),
        runtime=SimpleNamespace(authority=object()),
    )
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={"alpha": binding}),
        catalog=object(),
        provider=transport,
        workspace_root=tmp_path,
        turn_controller=controller,
        projector=Projector(),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(
                binding_id="alpha", domain_id="alpha", domain_version="1.0"
            ),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert controller.submissions[0]["referenced_bindings"] == ("alpha",)
    assert controller.submissions[0]["result_refs"] == (result_ref,)
    assert controller.submissions[0]["evidence_refs"] == (evidence_ref,)


def test_runner_checkpoints_mutable_report_after_each_finalized_answer(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    rendered: list[dict[str, object]] = []

    def render(**kwargs: object) -> str:
        rendered.append(dict(kwargs))
        return f"report-{len(rendered)}"

    transport = FakeTransport(events)
    controller = FakeController(events)
    binding = SimpleNamespace(
        binding_id="alpha",
        profile=SimpleNamespace(
            policy_provider=SimpleNamespace(load=lambda: None),
            guide_provider=SimpleNamespace(load=lambda: ()),
            validate_answer_admission_declaration=lambda: None,
            create_answer_admission_policy=lambda _authority: SimpleNamespace(admit=lambda _request: None),
        ),
        runtime=SimpleNamespace(authority=object()),
    )
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(render=render),
    )
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="checkpoint-run", binding_ids=("alpha",)
    )

    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={"alpha": binding}),
        catalog=object(),
        provider=transport,
        workspace=workspace,
        turn_controller=controller,
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("first", "second")))

    assert outcome.status == "completed"
    assert [call["answers"] for call in rendered] == [
        ("one",),
        ("one", "two"),
        ("one", "two"),
    ]
    assert [call["core"]["report_ref"] for call in rendered] == [None, None, None]
    assert workspace.output_path.joinpath("report.md").read_text(encoding="utf-8") == "report-3"


def test_report_marks_fabricated_answer_sidecar_unknown_without_durable_submission_event(
    tmp_path: Path,
) -> None:
    source_workspace = ApplicationWorkspace.create(
        tmp_path / "source", run_id="source-run", binding_ids=("grid",)
    )
    source_store = ApplicationContextStore.initialize(
        source_workspace, domains={"grid": "grid-state/1.0"}
    )
    authority = SimpleNamespace(
        authority_id="grid", workspace_root=source_workspace.domain_roots["grid"],
        verify_result=lambda _ref: object(), verify_evidence=lambda _ref: object(),
    )
    admission = SimpleNamespace(admit=lambda request: __import__(
        "capability_agent.domain.answer_admission", fromlist=["AnswerAdmissionDecision"]
    ).AnswerAdmissionDecision("limited", "limited", request.answer_output, ()))
    binding = SimpleNamespace(
        binding_id="grid",
        profile=SimpleNamespace(
            manifest=SimpleNamespace(authority_id="grid"), answer_policy=SimpleNamespace(
                validate_submission=lambda _submission: None
            ),
            create_answer_admission_policy=lambda _authority: admission,
            answer_admission_capabilities=frozenset({"authority_backed", "limited"}),
        ),
    )
    prepared = SimpleNamespace(binding=binding, runtime=SimpleNamespace(authority=authority))
    source_controller = TurnController(
        store=source_store, workspace=source_workspace, bindings={"grid": prepared}
    )
    committed = source_controller.submit(
        source_controller.start(1, "question"), answer_output="answer", duration_seconds=0.1
    )
    target_workspace = ApplicationWorkspace.create(
        tmp_path / "target", run_id="target-run", binding_ids=("grid",)
    )
    target_store = ApplicationContextStore.initialize(
        target_workspace, domains={"grid": "grid-state/1.0"}
    )
    target_turn = target_workspace.turns_path / committed.turn_id
    target_turn.mkdir()
    assert committed.answer_path is not None
    shutil.copy2(committed.answer_path, target_turn / "answer.json")
    shutil.copy2(
        committed.answer_path.with_name("answer-admission.json"),
        target_turn / "answer-admission.json",
    )
    rendered: list[dict[str, object]] = []
    application = AgentApplication(
        profile=SimpleNamespace(manifest=SimpleNamespace(application_id="fixture", version="1")),
        prepared_application=SimpleNamespace(bindings={"grid": prepared}),
        report_shell=SimpleNamespace(render=lambda **kwargs: rendered.append(kwargs) or "report"),
    )
    fake_answer = SimpleNamespace(
        turn_id=committed.turn_id, answer_output="answer", answer_ref=committed.answer_ref,
        admission_ref=committed.admission_ref, answer_path=target_turn / "answer.json", result_refs=(),
    )

    application._render_report(
        request=ApplicationRequest(application_id="fixture", questions=("question",)),
        workspace=target_workspace, store=target_store,
        core=CoreRunResult(application_id="fixture", application_version="1", run_id="target-run", status="completed", answer_refs=(), report_ref=None, diagnostic_refs=()),
        completed_answers=(fake_answer,),
    )

    assert rendered[-1]["assurances"] == ("unknown",)


def test_report_consumes_only_events_returned_by_its_verified_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="verified-report", binding_ids=("grid",)
    )
    store = ApplicationContextStore.initialize(
        workspace, domains={"grid": "grid-state/1.0"}
    )
    authority = SimpleNamespace(
        authority_id="grid",
        workspace_root=workspace.domain_roots["grid"],
        verify_result=lambda _ref: object(),
        verify_evidence=lambda _ref: object(),
    )
    admission = SimpleNamespace(
        admit=lambda request: AnswerAdmissionDecision(
            "limited", "limited", request.answer_output, ()
        )
    )
    binding = SimpleNamespace(
        binding_id="grid",
        profile=SimpleNamespace(
            manifest=SimpleNamespace(authority_id="grid"),
            answer_policy=SimpleNamespace(validate_submission=lambda _submission: None),
            create_answer_admission_policy=lambda _authority: admission,
            answer_admission_capabilities=frozenset({"authority_backed", "limited"}),
        ),
    )
    prepared = SimpleNamespace(
        binding=binding, runtime=SimpleNamespace(authority=authority)
    )
    controller = TurnController(
        store=store, workspace=workspace, bindings={"grid": prepared}
    )
    committed = controller.submit(
        controller.start(1, "question"),
        answer_output="answer",
        duration_seconds=0.1,
    )
    rendered: list[dict[str, object]] = []
    application = AgentApplication(
        profile=SimpleNamespace(
            manifest=SimpleNamespace(application_id="fixture", version="1")
        ),
        prepared_application=SimpleNamespace(bindings={"grid": prepared}),
        report_shell=SimpleNamespace(
            render=lambda **kwargs: rendered.append(kwargs) or "report"
        ),
    )
    real_replay_events = ApplicationContextStore.replay_events

    def replay_then_remove(ledger: object):
        replayed = real_replay_events(ledger)  # type: ignore[arg-type]
        workspace.context_events_path.unlink()
        return replayed

    monkeypatch.setattr(
        runner_module.ApplicationContextStore,
        "replay_events",
        staticmethod(replay_then_remove),
    )

    application._render_report(
        request=ApplicationRequest(
            application_id="fixture", questions=("question",)
        ),
        workspace=workspace,
        store=store,
        core=CoreRunResult(
            application_id="fixture",
            application_version="1",
            run_id="verified-report",
            status="completed",
            answer_refs=(str(committed.answer_ref),),
            report_ref=None,
            diagnostic_refs=(),
        ),
        completed_answers=(committed,),
    )

    assert rendered[-1]["assurances"] == ("limited",)


def test_runner_processes_questions_in_order_and_preserves_two_output_layers(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    transport = FakeTransport(events)
    controller = FakeController(events)
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(
            application_id="fixture-app",
            version="1.0.0",
            result_schema="capability-agent-output/1.0",
        ),
        domains=(binding,),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
        application_policy=SimpleNamespace(load=lambda: events.append("policy") or ""),
        acceptance_profile=SimpleNamespace(),
    )
    prepared = SimpleNamespace(profile=profile, bindings={"alpha": binding})

    application = AgentApplication(
        profile=profile,
        prepared_application=prepared,
        workspace_root=tmp_path,
        provider_catalog=SimpleNamespace(load=lambda: events.append("catalog") or object()),
        catalog=object(),
        provider_factory=lambda **_: transport,
        turn_controller=controller,
        lifecycle_hooks={
            "registration": lambda: events.append("registration"),
            "provisioning": lambda: events.append("provisioning"),
            "guide_validation": lambda: events.append("guide"),
            "catalog_validation": lambda: events.append("catalog.validate"),
        },
        output_composer=FrameworkOutputComposer(),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0",
            status="completed",
            payload={"completed_count": 2},
        ),
        binding_identities=(
            BindingIdentity(
                binding_id="alpha", domain_id="alpha-domain", domain_version="1.0.0"
            ),
        ),
    )

    outcome = application.run(
        ApplicationRequest(application_id="fixture-app", questions=("q1", "q2"))
    )

    assert outcome.result.schema == "capability-agent-output/1.0"
    assert outcome.result.core.status == "completed"
    assert tuple(outcome.result.domains) == ("alpha",)
    assert outcome.result.domains["alpha"].payload["completed_count"] == 2
    assert events.index("provider.start") > events.index("catalog.validate")
    assert events.index("provider.start") > events.index("guide")
    assert events.index("question:q1") < events.index("question:q2")
    assert [kwargs.get("correlation_id") for kwargs in transport.prompt_kwargs] == [
        "turn-1",
        "turn-2",
    ]


def test_runner_performs_all_preflight_steps_before_provider_start(tmp_path: Path) -> None:
    events: list[str] = []
    transport = FakeTransport(events)
    binding_profile = SimpleNamespace(
        policy_provider=SimpleNamespace(load=lambda: events.append("domain.policy")),
        guide_provider=SimpleNamespace(
            load=lambda: events.append("domain.guides") or ({"name": "guide"},)
        ),
        validate_answer_admission_declaration=lambda: events.append("domain.admission"),
        create_answer_admission_policy=lambda authority: SimpleNamespace(admit=lambda request: request),
    )
    binding = SimpleNamespace(
        binding_id="alpha", profile=binding_profile,
        runtime=SimpleNamespace(authority=object()),
    )
    profile = SimpleNamespace(
        manifest=SimpleNamespace(
            application_id="fixture-app", version="1.0.0", result_schema="capability-agent-output/1.0"
        ),
        application_policy=SimpleNamespace(load=lambda: events.append("application.policy")),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"alpha": binding})

    def make_provider(**_: object) -> FakeTransport:
        events.append("provider.factory")
        return transport

    outcome = AgentApplication(
        profile=profile,
        prepared_application=prepared,
        workspace_root=tmp_path,
        catalog=object(),
        provider_factory=make_provider,
        turn_controller=FakeController(events),
        lifecycle_hooks={
            "registration": lambda: events.append("registration"),
            "provisioning": lambda: events.append("provisioning"),
            "policy_composition": lambda: events.append("policy.composed"),
            "guide_validation": lambda: events.append("guides.validated"),
            "catalog_validation": lambda: events.append("catalog.validated"),
        },
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert events.index("provider.start") > events.index("registration")
    assert events.index("provider.start") > events.index("provisioning")
    assert events.index("provider.start") > events.index("application.policy")
    assert events.index("provider.start") > events.index("domain.policy")
    assert events.index("provider.start") > events.index("domain.guides")
    assert events.index("provider.start") > events.index("policy.composed")
    assert events.index("provider.start") > events.index("guides.validated")
    assert events.index("provider.start") > events.index("catalog.validated")


@pytest.mark.parametrize(
    "factory",
    (
        None,
        lambda _authority: object(),
        lambda _authority: (_ for _ in ()).throw(RuntimeError("factory exploded")),
    ),
)
def test_runner_rejects_invalid_answer_admission_factory_before_provider_creation(
    tmp_path: Path, factory: object
) -> None:
    """A prepared binding must have a usable policy before any provider exists."""
    events: list[str] = []
    provider_calls: list[str] = []
    binding = SimpleNamespace(
        binding_id="alpha",
        profile=SimpleNamespace(
            policy_provider=SimpleNamespace(load=lambda: events.append("domain.policy")),
            guide_provider=SimpleNamespace(load=lambda: ()),
            validate_answer_admission_declaration=lambda: None,
            create_answer_admission_policy=factory,
        ),
        runtime=SimpleNamespace(authority=object()),
    )
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: events.append("application.policy")),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )

    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={"alpha": binding}),
        provider_factory=lambda **_: provider_calls.append("factory"),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert outcome.error is not None
    assert provider_calls == []
    assert "provider.start" not in events


@pytest.mark.parametrize("binding", (SimpleNamespace(binding_id="alpha"), SimpleNamespace(
    binding_id="alpha", profile=SimpleNamespace(
        policy_provider=SimpleNamespace(load=lambda: None),
        guide_provider=SimpleNamespace(load=lambda: ()),
        validate_answer_admission_declaration=lambda: None,
        create_answer_admission_policy=lambda _authority: SimpleNamespace(admit=lambda _request: None),
    ),
    runtime=SimpleNamespace(),
)))
def test_runner_rejects_missing_profile_or_current_run_authority_before_provider_creation(
    tmp_path: Path, binding: object
) -> None:
    events: list[str] = []
    provider_calls: list[str] = []
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )

    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={"alpha": binding}),
        workspace_root=tmp_path,
        catalog=object(),
        provider_factory=lambda **_: provider_calls.append("factory") or FakeTransport(events),
        turn_controller=FakeController(events),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert provider_calls == []
    assert "provider.start" not in events


def test_runner_does_not_start_provider_when_preflight_fails_and_closes_reverse_order(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    class Endpoint:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            events.append(f"close:{self.name}")

    first = SimpleNamespace(binding_id="first", endpoint=Endpoint("first"))
    second = SimpleNamespace(binding_id="second", endpoint=Endpoint("second"))
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: events.append("policy")),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"first": first, "second": second})
    provider_calls: list[str] = []

    def fail_guides() -> tuple[object, ...]:
        raise RuntimeError("provider-secret must never escape")

    first.profile = SimpleNamespace(
        guide_provider=SimpleNamespace(load=fail_guides)
    )

    outcome = AgentApplication(
        profile=profile,
        prepared_application=prepared,
        provider_factory=lambda **_: provider_calls.append("factory"),
        lifecycle_hooks={
            "registration": lambda: events.append("registration"),
            "provisioning": lambda: events.append("provisioning"),
        },
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert outcome.error is not None
    assert "provider-secret" not in outcome.error
    assert provider_calls == []
    assert events[-2:] == ["close:second", "close:first"]


def test_runner_propagates_baseexception_and_still_stops_started_transport(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    class BaseExceptionTransport(FakeTransport):
        def prompt_and_wait(self, question: str, **_: object) -> str:
            events.append(f"question:{question}")
            raise KeyboardInterrupt("secret-provider-detail")

    transport = BaseExceptionTransport(events)
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"alpha": binding})
    controller = FakeController(events)
    with pytest.raises(KeyboardInterrupt, match="secret-provider-detail"):
        AgentApplication(
        profile=profile,
        prepared_application=prepared,
        catalog=object(),
        provider=transport,
        workspace_root=tmp_path,
        turn_controller=controller,
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
        ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert "provider.stop" in events
    assert len(controller.failed) == 1
    assert events.index("turn.fail:turn-1") < events.index("provider.stop")


def test_runner_closes_failed_turn_before_returning_sanitized_failure(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    class FailingTransport(FakeTransport):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            self.prompt_kwargs.append(kwargs)
            self.events.append(f"question:{question}")
            raise RuntimeError("provider secret must not escape")

    transport = FailingTransport(events)
    controller = FakeController(events)
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"alpha": binding})

    outcome = AgentApplication(
        profile=profile,
        prepared_application=prepared,
        catalog=object(),
        provider=transport,
        workspace_root=tmp_path,
        turn_controller=controller,
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert outcome.error == "RuntimeError: application execution failed"
    assert len(controller.failed) == 1
    assert controller.failed[0][1]["error"] == outcome.error
    assert events.index("turn.fail:turn-1") < events.index("provider.stop")


def test_runner_attempts_cleanup_after_stop_baseexception(tmp_path: Path) -> None:
    events: list[str] = []

    class StopInterruptTransport(FakeTransport):
        def stop(self) -> None:
            self.events.append("provider.stop")
            raise KeyboardInterrupt("stop secret")

    class InterruptEndpoint:
        def close(self) -> None:
            events.append("endpoint.close")

    transport = StopInterruptTransport(events)
    binding = _valid_binding(endpoint=InterruptEndpoint())
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"alpha": binding})

    with pytest.raises(KeyboardInterrupt, match="stop secret"):
        AgentApplication(
            profile=profile,
            prepared_application=prepared,
            catalog=object(),
            provider=transport,
            workspace_root=tmp_path,
            turn_controller=FakeController(events),
            domain_output_builder=lambda **_: ValidatedDomainOutput(
                schema="alpha-output/1.0", status="completed", payload={"ok": True}
            ),
            binding_identities=(
                BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
            ),
        ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert events == [
        "provider.start",
        "turn.start:1",
        "question:q",
        "turn.submit:turn-1",
        "provider.stop",
        "endpoint.close",
    ]


def test_runner_propagates_cleanup_baseexception(tmp_path: Path) -> None:
    events: list[str] = []

    class InterruptEndpoint:
        def close(self) -> None:
            events.append("endpoint.close")
            raise KeyboardInterrupt("cleanup secret")

    class CleanTransport(FakeTransport):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            self.prompt_kwargs.append(kwargs)
            self.events.append(f"question:{question}")
            raise RuntimeError("provider detail")

    transport = CleanTransport(events)
    binding = _valid_binding(endpoint=InterruptEndpoint())
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"alpha": binding})

    with pytest.raises(KeyboardInterrupt, match="cleanup secret"):
        AgentApplication(
            profile=profile,
            prepared_application=prepared,
            catalog=object(),
            provider=transport,
            workspace_root=tmp_path,
            turn_controller=FakeController(events),
            domain_output_builder=lambda **_: ValidatedDomainOutput(
                schema="alpha-output/1.0", status="completed", payload={"ok": True}
            ),
            binding_identities=(
                BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
            ),
        ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))


def test_runner_preserves_prompt_baseexception_when_cleanup_also_interrupts(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    class InterruptingTransport(FakeTransport):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            self.prompt_kwargs.append(kwargs)
            self.events.append(f"question:{question}")
            raise KeyboardInterrupt("prompt primary")

        def stop(self) -> None:
            self.events.append("provider.stop")
            raise KeyboardInterrupt("stop secondary")

    class InterruptEndpoint:
        def close(self) -> None:
            events.append("endpoint.close")
            raise KeyboardInterrupt("cleanup secondary")

    transport = InterruptingTransport(events)
    controller = FakeController(events)
    binding = _valid_binding(endpoint=InterruptEndpoint())
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"alpha": binding})

    with pytest.raises(KeyboardInterrupt, match="prompt primary"):
        AgentApplication(
            profile=profile,
            prepared_application=prepared,
            catalog=object(),
            provider=transport,
            workspace_root=tmp_path,
            turn_controller=controller,
            domain_output_builder=lambda **_: ValidatedDomainOutput(
                schema="alpha-output/1.0", status="completed", payload={"ok": True}
            ),
            binding_identities=(
                BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
            ),
        ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert len(controller.failed) == 1
    assert events.index("turn.fail:turn-1") < events.index("provider.stop")
    assert events[-2:] == ["provider.stop", "endpoint.close"]


def test_runner_does_not_claim_completed_when_completion_event_persistence_fails(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    class FailingStore:
        snapshot = SimpleNamespace()

        def append(self, _draft: object) -> object:
            events.append("store.append")
            raise OSError("store detail must not escape")

    transport = FakeTransport(events, answers=["answer"])
    controller = FakeController(events)
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"alpha": binding})

    outcome = AgentApplication(
        profile=profile,
        prepared_application=prepared,
        catalog=object(),
        provider=transport,
        workspace_root=tmp_path,
        store=FailingStore(),
        turn_controller=controller,
        report_shell=SimpleNamespace(render=lambda **_: "report"),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert outcome.result.core.status == "failed"
    assert outcome.error == "ApplicationConfigurationError: application execution failed"


def test_runner_report_publication_replaces_leaf_atomically_without_following_symlink(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-1", binding_ids=("alpha",)
    )
    outside = tmp_path / "outside-report.md"
    outside.write_text("outside-original", encoding="utf-8")
    report_path = workspace.output_path / "report.md"
    report_path.symlink_to(outside)
    transport = FakeTransport(events, answers=["answer"])
    controller = FakeController(events)
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    prepared = SimpleNamespace(bindings={"alpha": binding})

    outcome = AgentApplication(
        profile=profile,
        prepared_application=prepared,
        catalog=object(),
        provider=transport,
        workspace=workspace,
        turn_controller=controller,
        report_shell=SimpleNamespace(render=lambda **_: "new-report"),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert outcome.result.core.report_ref is None
    assert len(outcome.result.core.answer_refs) == 1
    assert report_path.is_symlink()
    assert outside.read_text(encoding="utf-8") == "outside-original"


def test_default_provider_uses_resolved_workspace_and_process_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_KEY", "process-secret")
    catalog = ProviderCatalog.from_mapping(
        {
            "schema_version": 1,
            "descriptor_version": "fixture-1",
            "default_provider": "alpha",
            "providers": {
                "alpha": {
                    "default_model": "alpha-model",
                    "base_url": "https://provider.example/v1",
                    "base_url_policy": "fixed",
                    "auth": {"kind": "api_key_env", "default_env": "ALPHA_KEY"},
                    "pi_provider": "alpha",
                    "compatibility_profile": "generic",
                    "supports_tools": True,
                }
            },
        }
    )
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="real-run", binding_ids=("alpha",)
    )
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0")
    )
    application = AgentApplication(profile=profile, provider_catalog=catalog)
    captured: dict[str, object] = {}

    def fake_default(
        resolved: object,
        prepared: object,
        bindings: object,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace,
        controller: object,
    ) -> object:
        captured.update(
            resolved=resolved,
            prepared=prepared,
            bindings=bindings,
            request=request,
            workspace=workspace,
            controller=controller,
        )
        return "transport"

    monkeypatch.setattr(application, "_default_pi_transport", fake_default)
    request = ApplicationRequest(
        application_id="fixture-app", questions=("q",), run_id="real-run"
    )
    controller = object()
    prepared = SimpleNamespace(bindings={"alpha": object()})

    result = application._ensure_provider(
        request=request,
        prepared=prepared,
        bindings=prepared.bindings,
        catalog=object(),
        workspace=workspace,
        controller=controller,
    )

    assert result == "transport"
    assert captured["workspace"] is workspace
    assert captured["request"] is request
    assert captured["controller"] is controller
    assert captured["resolved"].secret.value == "process-secret"


def test_default_provider_emits_safe_resolution_before_transport_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_KEY", "test-secret-must-not-observe")
    catalog = ProviderCatalog.from_mapping(
        {
            "schema_version": 1,
            "descriptor_version": "fixture-1",
            "default_provider": "alpha",
            "providers": {
                "alpha": {
                    "default_model": "alpha-model",
                    "base_url": "https://provider.example/v1",
                    "base_url_policy": "fixed",
                    "auth": {"kind": "api_key_env", "default_env": "ALPHA_KEY"},
                    "pi_provider": "alpha",
                    "compatibility_profile": "generic",
                    "supports_tools": True,
                }
            },
        }
    )
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="resolved-run", binding_ids=("alpha",)
    )
    observed: list[dict[str, object]] = []
    application = AgentApplication(
        profile=SimpleNamespace(
            manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0")
        ),
        provider_catalog=catalog,
        semantic_event_observer=lambda event: observed.append(dict(event)),
    )
    started: list[bool] = []

    class Transport:
        def start(self) -> None:
            assert observed
            started.append(True)

    monkeypatch.setattr(application, "_default_pi_transport", lambda *_args, **_kwargs: Transport())
    transport = application._ensure_provider(
        request=ApplicationRequest(
            application_id="fixture-app", questions=("q",), run_id="resolved-run"
        ),
        prepared=SimpleNamespace(),
        bindings={"alpha": object()},
        catalog=object(),
        workspace=workspace,
        controller=object(),
    )
    transport.start()

    assert started == [True]
    assert observed == [
        {
            "type": "application_provider_resolved",
            "run_id": "resolved-run",
            "provider": "alpha",
            "model": "alpha-model",
            "timeout_seconds": 180.0,
            "max_retries": 2,
        }
    ]
    assert "test-secret-must-not-observe" not in repr(observed)


def test_cleanup_continues_reverse_order_after_baseexception() -> None:
    events: list[str] = []

    class Endpoint:
        def __init__(self, name: str, *, interrupt: bool = False) -> None:
            self.name = name
            self.interrupt = interrupt

        def close(self) -> None:
            events.append(self.name)
            if self.interrupt:
                raise KeyboardInterrupt("primary cleanup interrupt")

    prepared = SimpleNamespace(
        bindings={
            "first": SimpleNamespace(endpoint=Endpoint("first")),
            "second": SimpleNamespace(endpoint=Endpoint("second", interrupt=True)),
        }
    )
    application = AgentApplication(profile=SimpleNamespace())

    with pytest.raises(KeyboardInterrupt, match="primary cleanup interrupt"):
        application._cleanup(prepared)

    assert events == ["second", "first"]


def test_default_runtime_descriptor_uses_controller_owned_run_channels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity

    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="real-run", binding_ids=("alpha",)
    )
    channels = SimpleNamespace(
        active_turn_path=workspace.turns_path / "active-turn.json",
        context_view_path=workspace.context_snapshot_path,
        trajectory_requests_path=workspace.core_path / "requests.jsonl",
        trajectory_capture_state_path=workspace.core_path / "capture.json",
        trajectory_allowed_refs_path=workspace.core_path / "allowed.json",
        trajectory_acks_path=workspace.core_path / "acks",
    )
    captured: dict[str, object] = {}

    def fake_descriptor(**kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(search_path=())

    monkeypatch.setattr(runner_module, "descriptor_from_endpoint", fake_descriptor)
    monkeypatch.setattr(runner_module, "write_runtime_descriptor", lambda *_: None)
    host = RuntimeHost(
        command=PiCommand(
            argv=("node", "/product-owned/pi.js"),
            identity=PiRuntimeIdentity(
                path=Path("/product-owned/pi.js"),
                source="fixture",
                package_version="1.0.0",
                lock_sha256="fixture-lock",
            ),
        ),
        project_pi_dir=tmp_path / "product-pi",
        extension_path=tmp_path / "trusted-extension.mjs",
    )
    monkeypatch.setattr(runner_module, "build_pi_launch", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(runner_module, "JsonlTraceWriter", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(runner_module, "PiRpcClient", lambda *_args, **_kwargs: "client")
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0")
    )
    application = AgentApplication(profile=profile, runtime_host=host, environment={})
    request = ApplicationRequest(
        application_id="fixture-app", questions=("q",), run_id="real-run"
    )
    binding = SimpleNamespace(endpoint=SimpleNamespace(metadata={"executable": "domainctl"}))

    result = application._default_pi_transport(
        SimpleNamespace(secret=None),
        SimpleNamespace(bindings={"alpha": binding}),
        {"alpha": binding},
        request=request,
        workspace=workspace,
        controller=channels,
    )

    assert result == "client"
    assert captured["application_id"] == "fixture-app"
    assert captured["run_id"] == "real-run"
    assert captured["active_turn_path"] == channels.active_turn_path
    assert captured["context_view_path"] == channels.context_view_path
    assert captured["trajectory_requests_path"] == channels.trajectory_requests_path
    assert captured["trajectory_capture_state_path"] == channels.trajectory_capture_state_path
    assert captured["trajectory_allowed_refs_path"] == channels.trajectory_allowed_refs_path
    assert captured["trajectory_acks_path"] == channels.trajectory_acks_path


def test_default_runtime_descriptor_materializes_prepared_domain_resources(
    complete_profile: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise prepare -> default descriptor -> as_json/write without a provider."""

    from dataclasses import replace
    from hashlib import sha256
    import json

    from capability_agent.application import (
        ApplicationWorkspace,
        DomainRegistry,
        prepare_application,
    )

    text = "# Fixture guide\n\nA binding-owned guide snapshot.\n"
    digest = sha256(text.encode("utf-8")).hexdigest()

    class GuideProvider:
        def load(self) -> tuple[dict[str, str], ...]:
            return (
                {"resource_id": "overview", "title": "Fixture guide", "sha256": digest},
            )

        def open(self, resource_id: str) -> dict[str, str]:
            if resource_id != "overview":
                raise KeyError(resource_id)
            return {
                "resource_id": resource_id,
                "title": "Fixture guide",
                "sha256": digest,
                "text": text,
            }

    profile = complete_profile
    binding = profile.domains[0]  # type: ignore[attr-defined]
    domain_profile = replace(binding.profile, guide_provider=GuideProvider())
    profile = replace(profile, domains=(replace(binding, profile=domain_profile),))
    provisioner = domain_profile.provisioner
    assert provisioner is not None
    provisioner.endpoint.metadata = {"executable": "domainctl"}

    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="descriptor-run", binding_ids=("fixture",)
    )
    registry = DomainRegistry()
    registry.register(
        domain_profile.manifest.domain_id,
        domain_profile.manifest.version,
        lambda: domain_profile,
    )
    prepared = prepare_application(
        profile,
        registry=registry,
        workspace=workspace.root,
        credentials=SimpleNamespace(issue=lambda **_: SimpleNamespace(scope_id="isolated", credentials={})),
    )

    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity

    host = RuntimeHost(
        command=PiCommand(
            argv=("node", "/product-owned/pi.js"),
            identity=PiRuntimeIdentity(
                path=Path("/product-owned/pi.js"),
                source="fixture",
                package_version="1.0.0",
                lock_sha256="fixture-lock",
            ),
        ),
        project_pi_dir=tmp_path / "product-pi",
        extension_path=tmp_path / "trusted-extension.mjs",
    )
    monkeypatch.setattr(runner_module, "build_pi_launch", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(runner_module, "JsonlTraceWriter", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(runner_module, "PiRpcClient", lambda *_args, **_kwargs: "client")

    application = AgentApplication(
        profile=prepared.profile,
        prepared_application=prepared,
        workspace=workspace,
        runtime_host=host,
        environment={},
    )
    channels = SimpleNamespace(
        active_turn_path=workspace.turns_path / "active-turn.json",
        context_view_path=workspace.context_snapshot_path,
        trajectory_requests_path=workspace.core_path / "requests.jsonl",
        trajectory_capture_state_path=workspace.core_path / "capture.json",
        trajectory_allowed_refs_path=workspace.core_path / "allowed.json",
        trajectory_acks_path=workspace.core_path / "acks",
    )
    client = application._default_pi_transport(
        SimpleNamespace(secret=None),
        prepared,
        prepared.bindings,
        request=ApplicationRequest(
            application_id="fixture-agent", questions=("question",), run_id="descriptor-run"
        ),
        workspace=workspace,
        controller=channels,
    )

    assert client == "client"
    runtime = prepared.bindings["fixture"].runtime
    assert runtime.guide_root_path.is_dir()
    guide_payload = json.loads(runtime.guide_index_path.read_text(encoding="utf-8"))
    assert guide_payload["root"] == str(runtime.guide_root_path)
    assert guide_payload["resources"] == {
        "overview": str(runtime.guide_root_path / "SKILL.md")
    }
    descriptor_path = workspace.domain_runtime_path("fixture") / "runtime-descriptor.json"
    descriptor_payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor_domain = descriptor_payload["domains"][0]
    assert descriptor_domain["toolCatalogPath"] == str(runtime.tool_catalog_path)
    assert descriptor_domain["guideIndexPath"] == str(runtime.guide_index_path)
    assert descriptor_domain["guideRootPath"] == str(runtime.guide_root_path)
    assert descriptor_domain["guideIndexSha256"] == sha256(
        runtime.guide_index_path.read_bytes()
    ).hexdigest()


def test_default_transport_uses_injected_product_runtime_and_split_workspaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The generic runner must never discover Pi from a binding run directory."""

    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity

    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="runtime-host-run", binding_ids=("alpha",)
    )
    domain_root = workspace.domain_path("alpha")
    catalog_path = domain_root / "tool-catalog.json"
    catalog_path.write_text("{}\n", encoding="utf-8")
    guide_index_path = domain_root / "guide-index.json"
    guide_index_path.write_text("{}\n", encoding="utf-8")
    guide_root_path = domain_root / "guides"
    guide_root_path.mkdir()
    manifest = SimpleNamespace(
        application_id="fixture-app",
        version="1.0.0",
        protocol="alpha-capability",
        protocol_version="1.0",
        tool_name_prefix="alpha_",
    )
    profile = SimpleNamespace(manifest=manifest)
    runtime = SimpleNamespace(
        profile=SimpleNamespace(manifest=manifest),
        authority=SimpleNamespace(authority_id="alpha-authority"),
        tool_catalog_path=catalog_path,
        guide_index_path=guide_index_path,
        guide_root_path=guide_root_path,
    )
    endpoint = SimpleNamespace(
        metadata={
            "executable": "domainctl",
            "arguments": ("--workspace", str(domain_root)),
        }
    )
    binding = SimpleNamespace(
        endpoint=endpoint,
        runtime=runtime,
        binding=SimpleNamespace(profile=SimpleNamespace(manifest=manifest)),
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
    host = RuntimeHost(
        command=command,
        project_pi_dir=tmp_path / "product-pi",
        extension_path=tmp_path / "trusted-extension.mjs",
        system_policy_path=tmp_path / "system-policy.md",
    )
    captured: dict[str, object] = {}

    def fake_launch(_resolved: object, paths: object, **_kwargs: object) -> object:
        captured["paths"] = paths
        return object()

    monkeypatch.setattr(
        runner_module,
        "PiRuntimeLocator",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("per-run Pi locator must not be called")
        ),
        raising=False,
    )
    monkeypatch.setattr(runner_module, "build_pi_launch", fake_launch)
    monkeypatch.setattr(runner_module, "JsonlTraceWriter", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(runner_module, "PiRpcClient", lambda *_args, **_kwargs: "client")

    application = AgentApplication(
        profile=profile,
        runtime_host=host,
        environment={},
    )
    channels = SimpleNamespace(
        active_turn_path=workspace.turns_path / "active-turn.json",
        context_view_path=workspace.context_snapshot_path,
        trajectory_requests_path=workspace.core_path / "requests.jsonl",
        trajectory_capture_state_path=workspace.core_path / "capture.json",
        trajectory_allowed_refs_path=workspace.core_path / "allowed.json",
        trajectory_acks_path=workspace.core_path / "acks",
    )
    client = application._default_pi_transport(
        SimpleNamespace(secret=None),
        SimpleNamespace(bindings={"alpha": binding}),
        {"alpha": binding},
        request=ApplicationRequest(
            application_id="fixture-app",
            questions=("question",),
            run_id="runtime-host-run",
        ),
        workspace=workspace,
        controller=channels,
    )

    assert client == "client"
    paths = captured["paths"]
    assert paths.command == command
    assert paths.project_pi_dir == host.project_pi_dir
    assert paths.extension_path == host.extension_path
    assert paths.system_policy_path == host.system_policy_path
    descriptor_path = workspace.domain_runtime_path("alpha") / "runtime-descriptor.json"
    descriptor_payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    assert descriptor_payload["domains"][0]["workspacePath"] == str(domain_root)
    assert descriptor_payload["core"]["analysisContextViewPath"] == str(
        workspace.context_snapshot_path
    )
    assert client is not None
def test_call_prompt_forwards_transport_heartbeat_to_semantic_observer() -> None:
    from capability_agent.application.runner import _call_prompt

    observed: list[dict[str, object]] = []

    class Transport:
        def prompt_and_wait(self, _question: str, *, on_heartbeat, **_kwargs):
            on_heartbeat()
            return "answer"

    answer, _projections = _call_prompt(
        Transport(), "question", projector=None, turn_id="turn-1",
        semantic_event_observer=lambda event: observed.append(dict(event)),
    )

    assert answer == "answer"
    assert observed == [{"type": "application_waiting"}]


def test_call_prompt_isolates_ordinary_semantic_observer_failures() -> None:
    from capability_agent.application.runner import _call_prompt

    class Transport:
        def prompt_and_wait(self, _question: str, *, on_semantic_event, on_heartbeat, **_kwargs):
            on_semantic_event({"type": "application_provider_resolved"})
            on_heartbeat()
            return "answer"

    answer, projections = _call_prompt(
        Transport(),
        "question",
        projector=None,
        turn_id="turn-1",
        semantic_event_observer=lambda _event: (_ for _ in ()).throw(RuntimeError("observer")),
    )

    assert answer == "answer"
    assert projections == ()


def test_call_prompt_keeps_projector_failure_fail_closed() -> None:
    from capability_agent.application.runner import _call_prompt

    class Projector:
        def observe(self, _event, **_kwargs):
            raise RuntimeError("admission")

    class Transport:
        def prompt_and_wait(self, _question: str, *, on_semantic_event, **_kwargs):
            on_semantic_event({"type": "tool_result"})
            return "answer"

    with pytest.raises(RuntimeError, match="admission"):
        _call_prompt(Transport(), "question", projector=Projector(), turn_id="turn-1")
