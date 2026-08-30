from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from capability_agent.application.output import (
    BindingIdentity,
    CoreRunResult,
    FrameworkOutputComposer,
    ValidatedDomainOutput,
)
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.workspace import ApplicationWorkspace


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

    def start(self, ordinal: int, instruction: str) -> object:
        self.events.append(f"turn.start:{ordinal}")
        return SimpleNamespace(turn_id=f"turn-{ordinal}", started_monotonic=0.0)

    def submit(self, handle: object, **kwargs: object) -> object:
        self.events.append(f"turn.submit:{handle.turn_id}")
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


def test_runner_processes_questions_in_order_and_preserves_two_output_layers(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    transport = FakeTransport(events)
    controller = FakeController(events)
    binding = SimpleNamespace(binding_id="alpha")
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
    )
    binding = SimpleNamespace(binding_id="alpha", profile=binding_profile)
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
    binding = SimpleNamespace(binding_id="alpha")
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
    binding = SimpleNamespace(binding_id="alpha")
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
    binding = SimpleNamespace(binding_id="alpha", endpoint=InterruptEndpoint())
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
    binding = SimpleNamespace(binding_id="alpha", endpoint=InterruptEndpoint())
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
    binding = SimpleNamespace(binding_id="alpha", endpoint=InterruptEndpoint())
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
    binding = SimpleNamespace(binding_id="alpha")
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
    binding = SimpleNamespace(binding_id="alpha")
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

    assert outcome.status == "failed"
    assert report_path.is_symlink()
    assert outside.read_text(encoding="utf-8") == "outside-original"
