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
from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.projector import ApplicationInvocationProjector
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.application.turns import (
    ActiveTurnHandle,
    FinalizedTurn,
    TurnController,
)
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
    answers: list[FinalizedTurn] = field(default_factory=list)
    failed: list[tuple[ActiveTurnHandle, dict[str, object]]] = field(default_factory=list)
    submissions: list[dict[str, object]] = field(default_factory=list)

    def start(self, ordinal: int, instruction: str) -> ActiveTurnHandle:
        self.events.append(f"turn.start:{ordinal}")
        return ActiveTurnHandle(
            ordinal=ordinal,
            turn_id=f"turn-{ordinal}",
            instruction=instruction,
            instruction_sha256="a" * 64,
            turn_nonce=f"nonce-{ordinal}",
            started_monotonic=0.0,
        )

    def submit(self, handle: ActiveTurnHandle, **kwargs: object) -> FinalizedTurn:
        self.events.append(f"turn.submit:{handle.turn_id}")
        self.submissions.append(kwargs)
        answer = FinalizedTurn(
            turn_id=handle.turn_id,
            status="success",
            answer_ref=f"answer:{handle.turn_id}",
            answer_output=kwargs["answer_output"],
            answer_path=None,
            admission_ref=None,
            referenced_bindings=("alpha",),
            result_refs=(),
            evidence_refs=(),
            submission=None,
            audit_diagnostics=(),
            admission=None,
            error=None,
        )
        self.answers.append(answer)
        return answer

    def fail(self, handle: ActiveTurnHandle, **kwargs: object) -> FinalizedTurn:
        self.events.append(f"turn.fail:{handle.turn_id}")
        self.failed.append((handle, kwargs))
        return FinalizedTurn(
            turn_id=handle.turn_id,
            status="failed",
            answer_output="",
            answer_path=None,
            answer_ref=None,
            admission_ref=None,
            referenced_bindings=(),
            result_refs=(),
            evidence_refs=(),
            submission=None,
            audit_diagnostics=(),
            admission=None,
            error=kwargs.get("error") if isinstance(kwargs.get("error"), str) else None,
        )


def test_runner_rejects_controller_signature_at_construction() -> None:
    events: list[str] = []
    bad_controller = SimpleNamespace(
        start=lambda _ordinal: object(),
        submit=lambda _handle, **_kwargs: object(),
        fail=lambda _handle, **_kwargs: object(),
    )

    with pytest.raises(ApplicationConfigurationError, match="turn controller start"):
        AgentApplication(
            profile=SimpleNamespace(),
            provider=FakeTransport(events),
            turn_controller=bad_controller,
        )

    assert events == []


def test_turn_controller_adapter_rejects_invalid_return_values() -> None:
    from capability_agent.application.runner import _prepare_turn_controller

    handle = ActiveTurnHandle(
        ordinal=1,
        turn_id="turn-1",
        instruction="q",
        instruction_sha256="a" * 64,
        turn_nonce="nonce",
        started_monotonic=0.0,
    )
    bad_controller = SimpleNamespace(
        start=lambda _ordinal, _instruction: handle,
        submit=lambda _handle, **_kwargs: object(),
        fail=lambda _handle, **_kwargs: object(),
    )
    controller = _prepare_turn_controller(bad_controller)

    assert controller.start(1, "q") is handle
    with pytest.raises(ApplicationConfigurationError, match="finalized turn"):
        controller.submit(
            handle,
            answer_output="answer",
            referenced_bindings=(),
            result_refs=(),
            evidence_refs=(),
            duration_seconds=0.0,
        )


@pytest.mark.parametrize(
    "transport",
    (
        SimpleNamespace(
            start=lambda: None,
            stop=lambda: None,
            prompt_and_wait=lambda _question, *, correlation_id: "answer",
        ),
        SimpleNamespace(
            start=lambda: None,
            stop=lambda: None,
            prompt_and_wait=lambda _question, *, on_semantic_event: "answer",
        ),
        SimpleNamespace(
            start=lambda: None,
            stop=lambda: None,
            prompt_and_wait=lambda _question, *, on_semantic_event, correlation_id: "answer",
        ),
    ),
)
def test_runner_rejects_static_transport_missing_projection_or_correlation_before_start(
    transport: object,
) -> None:
    """A configured session cannot silently discard primary prompt metadata."""

    with pytest.raises(ApplicationConfigurationError, match="provider session"):
        AgentApplication(
            profile=SimpleNamespace(manifest=SimpleNamespace(application_id="fixture-app")),
            provider=transport,
        )


def test_runner_rejects_static_factory_and_preparer_missing_required_keywords() -> None:
    """Injection signatures are configuration, not a per-run reflection fallback."""

    def incomplete_factory(*, request: object) -> object:
        return object()

    def incomplete_preparer(*, profile: object, request: object) -> object:
        return object()

    profile = SimpleNamespace(manifest=SimpleNamespace(application_id="fixture-app"))
    with pytest.raises(ApplicationConfigurationError, match="provider factory"):
        AgentApplication(profile=profile, provider_factory=incomplete_factory)
    with pytest.raises(ApplicationConfigurationError, match="application preparer"):
        AgentApplication(profile=profile, application_preparer=incomplete_preparer)


def test_runner_passes_only_established_keywords_to_provider_factory(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    received: dict[str, object] = {}
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )

    def make_provider(**kwargs: object) -> FakeTransport:
        received.update(kwargs)
        return FakeTransport(events, answers=["answer"])

    prepared = SimpleNamespace(
        bindings={"alpha": binding},
        profile=SimpleNamespace(identity="prepared-profile"),
    )
    outcome = AgentApplication(
        profile=profile,
        prepared_application=prepared,
        catalog=object(),
        provider_factory=make_provider,
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert set(received) == {
        "request",
        "profile",
        "prepared_application",
        "bindings",
        "catalog",
    }
    assert received["prepared_application"] is prepared
    assert received["prepared_application"].profile.identity == "prepared-profile"


def test_runner_passes_all_established_keywords_to_application_preparer(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    received: dict[str, object] = {}
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="preparer-run", binding_ids=("alpha",)
    )
    registry = object()
    credentials = object()

    def prepare(**kwargs: object) -> object:
        received.update(kwargs)
        return SimpleNamespace(bindings={"alpha": binding})

    outcome = AgentApplication(
        profile=profile,
        application_preparer=prepare,
        catalog=object(),
        provider=FakeTransport(events, answers=["answer"]),
        workspace=workspace,
        registry=registry,
        credentials=credentials,
        turn_controller=FakeController(events),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert set(received) == {
        "profile",
        "request",
        "workspace",
        "registry",
        "credentials",
    }
    assert received["workspace"] is workspace
    assert received["registry"] is registry
    assert received["credentials"] is credentials


def test_runner_rejects_dynamic_transport_before_its_start(tmp_path: Path) -> None:
    events: list[str] = []
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    incompatible = SimpleNamespace(
        start=lambda: events.append("provider.start"),
        stop=lambda: events.append("provider.stop"),
        prompt_and_wait=lambda _question, *, correlation_id: "answer",
    )

    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={"alpha": binding}),
        catalog=object(),
        provider_factory=lambda **_: incompatible,
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert events == []


def test_runner_rejects_default_transport_before_its_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    provider_catalog = ProviderCatalog.from_mapping(
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
    incompatible = SimpleNamespace(
        start=lambda: events.append("provider.start"),
        stop=lambda: events.append("provider.stop"),
        prompt_and_wait=lambda _question, *, correlation_id: "answer",
    )
    application = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={"alpha": binding}),
        catalog=object(),
        provider_catalog=provider_catalog,
        environment={"ALPHA_KEY": "fixture-secret"},
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    )
    monkeypatch.setattr(
        application,
        "_default_pi_transport",
        lambda *_args, **_kwargs: incompatible,
    )

    outcome = application.run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert events == []


@pytest.mark.parametrize("missing_method", ("start", "submit", "fail"))
def test_runner_rejects_controller_missing_required_method_before_provider_start(
    tmp_path: Path, missing_method: str
) -> None:
    events: list[str] = []
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )
    methods = {
        "start": lambda ordinal, question: SimpleNamespace(
            turn_id=f"turn-{ordinal}", instruction=question
        ),
        "submit": lambda _handle, **_kwargs: None,
        "fail": lambda _handle, *, error, duration_seconds: None,
    }
    del methods[missing_method]
    controller = SimpleNamespace(**methods)

    with pytest.raises(ApplicationConfigurationError, match="turn controller"):
        AgentApplication(
            profile=profile,
            prepared_application=SimpleNamespace(bindings={"alpha": binding}),
            catalog=object(),
            provider=FakeTransport(events, answers=["answer"]),
            workspace_root=tmp_path,
            turn_controller=controller,
            domain_output_builder=lambda **_: ValidatedDomainOutput(
                schema="alpha-output/1.0", status="completed", payload={"ok": True}
            ),
            binding_identities=(
                BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
            ),
        )

    assert events == []


def test_runner_rejects_output_builder_missing_report_reference_before_provider_start(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    binding = _valid_binding()
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(),
    )

    def incomplete_builder(
        *,
        binding_id: str,
        binding: object,
        context: object,
        committed_answers: tuple[object, ...],
    ) -> ValidatedDomainOutput:
        del binding_id, binding, context, committed_answers
        raise AssertionError("must be rejected before invocation")

    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={"alpha": binding}),
        catalog=object(),
        provider=FakeTransport(events, answers=["answer"]),
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        domain_output_builder=incomplete_builder,
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert events == []


@pytest.mark.parametrize("invalid_seam", ("state_adapter", "build", "validator"))
def test_runner_rejects_invalid_default_output_seam_before_provider_start(
    tmp_path: Path, invalid_seam: str
) -> None:
    events: list[str] = []

    contract_values: dict[str, object] = {
        "build": lambda *, binding_id, context, committed_answers: {"ok": True},
        "validate": lambda _payload: None,
    }
    profile_values: dict[str, object] = {
        "policy_provider": SimpleNamespace(load=lambda: None),
        "guide_provider": SimpleNamespace(load=lambda: ()),
        "validate_answer_admission_declaration": lambda: None,
        "create_answer_admission_policy": lambda _authority: SimpleNamespace(
            admit=lambda _request: None
        ),
    }
    if invalid_seam == "state_adapter":
        profile_values["state_adapter"] = SimpleNamespace(
            build_context=lambda *, binding_id: {"binding_id": binding_id}
        )
    elif invalid_seam == "build":
        contract_values["build"] = lambda *, binding_id, context: {"ok": True}
    else:
        del contract_values["validate"]
        contract_values["validate_with_context"] = lambda _payload: None
    profile_values["output_contract"] = SimpleNamespace(**contract_values)

    binding = SimpleNamespace(
        binding_id="alpha",
        profile=SimpleNamespace(**profile_values),
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
        provider=FakeTransport(events, answers=["answer"]),
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert events == []


def test_runner_keeps_provider_implementation_typeerror_as_execution_failure(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    class TypeErrorTransport(FakeTransport):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            del question, kwargs
            raise TypeError("provider implementation error")

    binding = _valid_binding()
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
        provider=TypeErrorTransport(events),
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={"ok": True}
        ),
        binding_identities=(
            BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0"),
        ),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "failed"
    assert outcome.error == "TypeError: application execution failed"
    assert "provider.start" in events


def test_legacy_prompt_method_forwards_complete_callback_contract() -> None:
    from capability_agent.application.runner import _call_prompt

    received: dict[str, object] = {}

    class LegacyTransport:
        def prompt(
            self,
            _question: str,
            *,
            on_semantic_event: object,
            correlation_id: str | None,
            on_heartbeat: object,
        ) -> str:
            received.update(
                on_semantic_event=on_semantic_event,
                correlation_id=correlation_id,
                on_heartbeat=on_heartbeat,
            )
            return "answer"

    answer, projections = _call_prompt(
        LegacyTransport(), "question", projector=None, turn_id="turn-1"
    )

    assert answer == "answer"
    assert projections == ()
    assert received["correlation_id"] == "turn-1"
    assert callable(received["on_semantic_event"])
    assert callable(received["on_heartbeat"])


def test_legacy_output_validator_receives_scoped_admitted_references() -> None:
    from capability_agent.application.runner import _prepare_output_validator

    reference = "artifact:sha256:" + "a" * 64

    class Contract:
        allowed_references: frozenset[str] | None = None

        def validate(self, payload: object) -> None:
            assert payload == {"answer": "text"}
            assert self.allowed_references == frozenset((reference,))

    _prepare_output_validator(Contract(), "alpha").validate(
        {"answer": "text"},
        context={"admitted_artifact_refs": (reference,)},
    )


def test_context_aware_output_validator_receives_named_context() -> None:
    from capability_agent.application.runner import _prepare_output_validator

    context = {"admitted_refs": ("artifact:sha256:" + "b" * 64,)}
    received: dict[str, object] = {}

    class Contract:
        def validate_with_context(self, payload: object, *, context: object) -> None:
            received["payload"] = payload
            received["context"] = context

    _prepare_output_validator(Contract(), "alpha").validate(
        {"answer": "text"}, context=context
    )

    assert received == {"payload": {"answer": "text"}, "context": context}


def test_call_factory_does_not_silently_filter_named_inputs() -> None:
    from capability_agent.application.runner import _call_factory

    with pytest.raises(TypeError):
        _call_factory(lambda value: value, value="answer", context="discarded")


def test_runner_default_generic_report_shell_stays_compatible_with_strict_calls(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=GenericReportShell(),
    )

    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={}),
        catalog=object(),
        provider=FakeTransport(events, answers=["answer"]),
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        binding_identities=(),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert outcome.report_path is not None
    assert "# Application report" in outcome.report_path.read_text(encoding="utf-8")


def test_runner_preserves_configured_generic_report_shell_instance(tmp_path: Path) -> None:
    events: list[str] = []
    rendered: list[tuple[str, ...]] = []

    class SelectedShell(GenericReportShell):
        def render(self, **kwargs: object) -> str:
            rendered.append(tuple(sorted(kwargs)))
            return "selected shell report"

    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SelectedShell(),
    )
    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={}),
        catalog=object(),
        provider=FakeTransport(events, answers=["answer"]),
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        binding_identities=(),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert len(rendered) == 2
    assert all(call == (
        "answers", "assurances", "context", "core", "domains", "presentation",
        "questions", "references", "trajectories",
    ) for call in rendered)


def test_runner_uses_configured_render_without_prepare(tmp_path: Path) -> None:
    events: list[str] = []
    rendered: list[dict[str, object]] = []

    def render(
        *,
        questions: tuple[str, ...],
        answers: tuple[str, ...],
        assurances: tuple[str, ...],
        trajectories: tuple[str, ...],
        references: tuple[str, ...],
        context: object,
        presentation: object,
        core: dict[str, object],
        domains: dict[str, object],
        workspace: ApplicationWorkspace,
        runtime: dict[str, object],
    ) -> str:
        rendered.append(
            {
                "questions": questions,
                "answers": answers,
                "assurances": assurances,
                "trajectories": trajectories,
                "references": references,
                "context": context,
                "presentation": presentation,
                "core": core,
                "domains": domains,
                "workspace": workspace,
                "runtime": runtime,
            }
        )
        return "configured report"

    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=SimpleNamespace(render=render),
    )
    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={}),
        catalog=object(),
        provider=FakeTransport(events, answers=["answer"]),
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        binding_identities=(),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert len(rendered) == 2
    assert all(set(call) == {
        "questions", "answers", "assurances", "trajectories", "references",
        "context", "presentation", "core", "domains", "workspace", "runtime",
    } for call in rendered)


def test_runner_isolates_report_attribute_discovery_failure(tmp_path: Path) -> None:
    events: list[str] = []

    class BrokenReportShell:
        @property
        def prepare(self) -> object:
            raise RuntimeError("report discovery must remain derived")

        @property
        def render(self) -> object:
            raise RuntimeError("report discovery must remain derived")

    profile = SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture-app", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=BrokenReportShell(),
    )
    outcome = AgentApplication(
        profile=profile,
        prepared_application=SimpleNamespace(bindings={}),
        catalog=object(),
        provider=FakeTransport(events, answers=["answer"]),
        workspace_root=tmp_path,
        turn_controller=FakeController(events),
        binding_identities=(),
    ).run(ApplicationRequest(application_id="fixture-app", questions=("q",)))

    assert outcome.status == "completed"
    assert outcome.result.core.report_ref is None
    assert outcome.report_path is None


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


@pytest.mark.parametrize("binding_ids", [("grid",), ("grid", "inventory")])
def test_report_consumes_only_events_returned_by_its_verified_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, binding_ids
) -> None:
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="verified-report", binding_ids=binding_ids
    )
    store = ApplicationContextStore.initialize(
        workspace, domains={key: "state/1.0" for key in binding_ids}
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
    bindings = {"grid": prepared}
    if "inventory" in binding_ids:
        bindings["inventory"] = SimpleNamespace(
            binding=SimpleNamespace(binding_id="inventory", profile=binding.profile),
            runtime=SimpleNamespace(authority=SimpleNamespace(
                authority_id="grid", workspace_root=workspace.domain_roots["inventory"],
            )),
        )
    controller = TurnController(
        store=store, workspace=workspace, bindings=bindings
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
        prepared_application=SimpleNamespace(bindings=bindings),
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
    assert outcome.model_request_capture_status == "unavailable"
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
    "evaluation_failure",
    ("declaration", "missing_factory", "invalid_policy", "factory_exception"),
)
def test_runner_continues_when_answer_admission_preflight_evaluation_is_unavailable(
    tmp_path: Path, evaluation_failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Admission evaluation is diagnostic-only before a provider starts."""
    events: list[str] = []
    provider_calls: list[str] = []
    diagnostic_codes: list[str] = []
    declaration = lambda: None
    factory: object = lambda _authority: SimpleNamespace(admit=lambda _request: None)
    if evaluation_failure == "declaration":
        declaration = lambda: (_ for _ in ()).throw(RuntimeError("declaration exploded"))
    elif evaluation_failure == "missing_factory":
        factory = None
    elif evaluation_failure == "invalid_policy":
        factory = lambda _authority: object()
    else:
        factory = lambda _authority: (_ for _ in ()).throw(RuntimeError("factory exploded"))
    binding = SimpleNamespace(
        binding_id="alpha",
        profile=SimpleNamespace(
            policy_provider=SimpleNamespace(load=lambda: events.append("domain.policy")),
            guide_provider=SimpleNamespace(load=lambda: ()),
            validate_answer_admission_declaration=declaration,
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
    monkeypatch.setattr(
        AgentApplication,
        "_record_diagnostic",
        lambda _self, code: diagnostic_codes.append(code),
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

    assert outcome.status == "completed"
    assert provider_calls == ["factory"]
    assert "provider.start" in events
    assert diagnostic_codes == ["answer_evaluation_unavailable"]


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
    session = FakeTransport([], answers=["answer"])

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
        return session

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

    assert result is not None
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

        def prompt_and_wait(self, _question: str, **_kwargs: object) -> str:
            return "answer"

        def stop(self) -> None:
            pass

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
    handle = ActiveTurnHandle(
        ordinal=1,
        turn_id="turn-1",
        instruction="q",
        instruction_sha256="a" * 64,
        turn_nonce="nonce",
        started_monotonic=0.0,
    )
    finalized = FinalizedTurn(
        turn_id=handle.turn_id,
        status="success",
        answer_output="answer",
        answer_path=None,
        answer_ref=None,
        admission_ref=None,
        referenced_bindings=(),
        result_refs=(),
        evidence_refs=(),
        submission=None,
        audit_diagnostics=(),
        admission=None,
        error=None,
    )
    channels.start = lambda _ordinal, _instruction: handle
    channels.submit = lambda _handle, **_kwargs: finalized
    channels.fail = lambda _handle, **_kwargs: finalized
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

    controller = runner_module._prepare_turn_controller(channels)
    assert controller.start(1, "q") is handle
    assert controller.submit(
        handle,
        answer_output="answer",
        referenced_bindings=(),
        result_refs=(),
        evidence_refs=(),
        duration_seconds=0.0,
    ) is finalized

    result = application._default_pi_transport(
        SimpleNamespace(secret=None),
        SimpleNamespace(bindings={"alpha": binding}),
        {"alpha": binding},
        request=request,
        workspace=workspace,
        controller=controller,
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


def test_model_request_capture_status_distinguishes_configured_missing_and_partial_channels(
    tmp_path: Path,
) -> None:
    complete = SimpleNamespace(
        active_turn_path=tmp_path / "active.json",
        trajectory_requests_path=tmp_path / "requests",
        trajectory_capture_state_path=tmp_path / "state.json",
        trajectory_allowed_refs_path=tmp_path / "refs.json",
        trajectory_acks_path=tmp_path / "acks",
    )
    missing = SimpleNamespace(**{name: None for name in vars(complete)})
    partial = SimpleNamespace(**{**vars(complete), "trajectory_acks_path": None})
    missing_active_turn = SimpleNamespace(**{**vars(complete), "active_turn_path": None})

    assert runner_module._capture_status_for_channels(complete) == "enabled"
    assert runner_module._capture_status_for_channels(missing) == "disabled"
    assert runner_module._capture_status_for_channels(partial) == "unavailable"
    assert runner_module._capture_status_for_channels(missing_active_turn) == "unavailable"


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
    assert paths.binding_id == "alpha"
    assert paths.tool_catalog_path == catalog_path
    assert paths.guide_index_path == guide_index_path
    assert paths.session_dir == workspace.domain_runtime_path("alpha") / "session"
    descriptor_path = workspace.domain_runtime_path("alpha") / "runtime-descriptor.json"
    descriptor_payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    assert descriptor_payload["domains"][0]["workspacePath"] == str(domain_root)
    assert descriptor_payload["core"]["analysisContextViewPath"] == str(
        workspace.context_snapshot_path
    )
    assert client is not None


def test_default_transport_writes_one_composite_descriptor_without_ambient_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from capability_agent.runtime.environment import RuntimeHost, build_pi_environment
    from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity

    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="composite-run", binding_ids=("alpha", "zeta")
    )
    bindings = {}
    for binding_id in ("zeta", "alpha"):
        root = workspace.domain_path(binding_id)
        catalog = root / "tool-catalog.json"
        guide_index = root / "guide-index.json"
        guide_root = root / "guides"
        catalog.write_text("{}\n", encoding="utf-8")
        guide_index.write_text("{}\n", encoding="utf-8")
        guide_root.mkdir()
        manifest = SimpleNamespace(
            protocol=f"{binding_id}-capability", protocol_version="1.0",
            tool_name_prefix=f"{binding_id}_",
        )
        bindings[binding_id] = SimpleNamespace(
            endpoint=SimpleNamespace(metadata={
                "executable": f"{binding_id}ctl",
                "arguments": ("--workspace", str(root)),
                "search_path": (str(tmp_path / f"{binding_id}-bin"),),
            }),
            runtime=SimpleNamespace(
                profile=SimpleNamespace(manifest=manifest),
                authority=SimpleNamespace(authority_id=f"{binding_id}-authority"),
                tool_catalog_path=catalog,
                guide_index_path=guide_index,
                guide_root_path=guide_root,
            ),
        )
    host = RuntimeHost(
        command=PiCommand(
            argv=("node", "/product-owned/pi.js"),
            identity=PiRuntimeIdentity(
                path=Path("/product-owned/pi.js"), source="fixture",
                package_version="1.0.0", lock_sha256="fixture-lock",
            ),
        ),
        project_pi_dir=tmp_path / "product-pi",
        extension_path=tmp_path / "trusted-extension.mjs",
    )
    captured = {}

    def fake_launch(resolved, paths, **kwargs):
        captured["launch_count"] = captured.get("launch_count", 0) + 1
        captured["paths"] = paths
        captured["environment"] = build_pi_environment(
            resolved, paths, base_environment=kwargs["base_environment"]
        )
        return object()

    monkeypatch.setattr(runner_module, "build_pi_launch", fake_launch)
    monkeypatch.setattr(runner_module, "JsonlTraceWriter", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(runner_module, "PiRpcClient", lambda *_args, **_kwargs: "client")
    application = AgentApplication(
        profile=SimpleNamespace(), runtime_host=host, environment={}
    )
    assert application._default_pi_transport(
        SimpleNamespace(config=SimpleNamespace(base_url="https://provider.example"), secret=None),
        SimpleNamespace(bindings=bindings), bindings,
        request=ApplicationRequest(application_id="fixture-app", questions=("q",)),
        workspace=workspace,
        controller=SimpleNamespace(
            active_turn_path=workspace.turns_path / "active-turn.json",
            context_view_path=workspace.context_snapshot_path,
            trajectory_requests_path=None,
            trajectory_capture_state_path=None,
            trajectory_allowed_refs_path=None,
            trajectory_acks_path=None,
        ),
    ) == "client"

    paths = captured["paths"]
    assert captured["launch_count"] == 1
    descriptor_path = workspace.core_path / "runtime" / "runtime-descriptor.json"
    payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "capability-agent-runtime/1.1"
    assert [domain["bindingId"] for domain in payload["domains"]] == ["alpha", "zeta"]
    for domain in payload["domains"]:
        binding = bindings[domain["bindingId"]]
        assert domain["toolCatalogPath"] == str(binding.runtime.tool_catalog_path)
        assert domain["guideIndexPath"] == str(binding.runtime.guide_index_path)
    assert paths.runtime_descriptor_path == descriptor_path
    assert paths.session_dir == workspace.core_path / "runtime" / "session"
    assert paths.domain_search_paths == (
        tmp_path / "alpha-bin", tmp_path / "zeta-bin"
    )
    assert paths.binding_id is None
    assert paths.tool_catalog_path is None
    assert paths.guide_index_path is None
    assert "CAPABILITY_AGENT_BINDING_ID" not in captured["environment"]
    assert "CAPABILITY_AGENT_TOOL_CATALOG" not in captured["environment"]
    assert "CAPABILITY_AGENT_GUIDE_INDEX" not in captured["environment"]
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
