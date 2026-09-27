"""Ordered, domain-neutral application execution."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Literal, TypeGuard, cast

from capability_agent.application.composition import (
    CredentialBroker,
    PreparedBinding,
    prepare_application,
)
from capability_agent.application._report_files import write_report_atomically
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.context_models import ContextEventDraft, PORTABLE_ID_PATTERN
from capability_agent.application.errors import (
    ApplicationConfigurationError,
    CapabilityAgentError,
    PresentationError,
)
from capability_agent.application.output import (
    ApplicationResult,
    BindingIdentity,
    CoreRunResult,
    FrameworkOutputComposer,
    JsonOutputRenderer,
    ValidatedDomainOutput,
)
from capability_agent.application.answer_format import (
    ANSWER_BUNDLE_INSTRUCTION,
    AnswerBundle,
    parse_answer_bundle,
)
from capability_agent.application.profile import ApplicationProfile
from capability_agent.application.projector import ApplicationInvocationProjector
from capability_agent.application.reporting import GenericReportShell, ReportPublication
from capability_agent.application.runtime_protocols import (
    ApplicationPreparer,
    DomainPayloadBuilder,
    DomainOutputBuilder,
    LegacyPromptSession,
    OutputValidator,
    PreparedApplicationRuntime,
    ProviderFactory,
    ProviderSession,
    ReportPublisher,
    StateContextAdapter,
    TurnControllerSource,
    TurnControllerSession,
)
from capability_agent.application.turns import ActiveTurnHandle, FinalizedTurn, TurnController
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.domain.answer_admission import read_answer_admission_metadata
from capability_agent.runtime.catalog import ProviderCatalog, ProviderCatalogSource
from capability_agent.runtime.descriptor import (
    CompositeRuntimeDescriptor,
    descriptor_from_endpoint,
    write_runtime_descriptor,
)
from capability_agent.runtime.environment import RuntimeHost, RuntimePaths, build_pi_launch
from capability_agent.runtime.models import CliLLMOptions, ResolvedLLM
from capability_agent.runtime.resolver import resolve_llm
from capability_agent.runtime.rpc import PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter
from capability_agent.tools.catalog import (
    BoundDomainCatalog,
    CompositeToolCatalog,
    CoreToolCatalog,
)
from capability_agent.trajectory.artifacts import (
    ArtifactLayout,
    ArtifactIntegrityError,
    ImmutableArtifactRegistry,
    NeutralArtifactPathPolicy,
)


ApplicationStatus = Literal["completed", "failed"]
ModelRequestCaptureStatus = Literal["enabled", "disabled", "unavailable"]

_PROVIDER_FACTORY_KEYWORDS = (
    "request",
    "profile",
    "prepared_application",
    "bindings",
    "catalog",
)
_APPLICATION_PREPARER_KEYWORDS = (
    "profile",
    "request",
    "workspace",
    "registry",
    "credentials",
)
_PROVIDER_PROMPT_KEYWORDS = (
    "on_semantic_event",
    "correlation_id",
    "on_heartbeat",
)


@dataclass(frozen=True, slots=True)
class ApplicationRequest:
    application_id: str
    questions: tuple[str, ...]
    run_id: str | None = None
    response_mode: Literal["text", "answer_bundle"] = "text"

    def __post_init__(self) -> None:
        if not isinstance(self.application_id, str) or not self.application_id:
            raise ValueError("application_id must be non-empty text")
        if isinstance(self.questions, str):
            raise ValueError("questions must be an ordered sequence")
        try:
            questions = tuple(self.questions)
        except TypeError:
            raise ValueError("questions must be an ordered sequence") from None
        if any(not isinstance(question, str) or not question.strip() for question in questions):
            raise ValueError("questions must contain non-empty text")
        object.__setattr__(self, "questions", questions)
        if self.run_id is not None and (
            not isinstance(self.run_id, str) or not self.run_id
        ):
            raise ValueError("run_id must be non-empty text")
        if self.response_mode not in {"text", "answer_bundle"}:
            raise ValueError("response_mode must be 'text' or 'answer_bundle'")

    @property
    def instructions(self) -> tuple[str, ...]:
        """Compatibility spelling for applications that call prompts instructions."""

        return self.questions


@dataclass(frozen=True, slots=True)
class ApplicationOutcome:
    result: ApplicationResult
    status: ApplicationStatus
    rendered: object | None
    run_id: str | None
    report_path: Path | None
    completed_questions: int
    total_questions: int
    error: str | None = None
    model_request_capture_status: ModelRequestCaptureStatus = "unavailable"

    @property
    def output(self) -> object | None:
        return self.rendered


@dataclass(frozen=True, slots=True)
class _RunnerBindings:
    prepared: PreparedApplicationRuntime
    bindings: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _ProviderSessionAdapter:
    """Bind a checked structural transport to the canonical session surface."""

    source: object

    def start(self) -> None:
        _call_method(self.source, "start")

    def prompt_and_wait(
        self,
        question: str,
        *,
        on_semantic_event: Callable[..., object],
        correlation_id: str | None,
        on_heartbeat: Callable[[], None],
    ) -> str:
        method = _provider_prompt_method(self.source)
        answer = method(
            question,
            on_semantic_event=on_semantic_event,
            correlation_id=correlation_id,
            on_heartbeat=on_heartbeat,
        )
        if not isinstance(answer, str):
            raise ApplicationConfigurationError("provider transport returned non-text answer")
        return answer

    def stop(self) -> None:
        _call_method(self.source, "stop")


@dataclass(frozen=True, slots=True)
class _TurnControllerAdapter:
    source: TurnControllerSource
    active_turn_path: Path | None
    context_view_path: Path | None
    trajectory_requests_path: Path | None
    trajectory_capture_state_path: Path | None
    trajectory_allowed_refs_path: Path | None
    trajectory_acks_path: Path | None

    def start(self, ordinal: int, instruction: str) -> ActiveTurnHandle:
        handle = self.source.start(ordinal, instruction)
        if not isinstance(handle, ActiveTurnHandle):
            raise ApplicationConfigurationError(
                "turn controller returned an invalid active turn handle"
            )
        return handle

    def submit(
        self,
        handle: ActiveTurnHandle,
        *,
        answer_output: str,
        answer_summary: str | None = None,
        referenced_bindings: tuple[str, ...],
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        duration_seconds: float,
    ) -> FinalizedTurn:
        finalized = self.source.submit(
            handle,
            answer_output=answer_output,
            answer_summary=answer_summary,
            referenced_bindings=referenced_bindings,
            result_refs=result_refs,
            evidence_refs=evidence_refs,
            duration_seconds=duration_seconds,
        )
        if not isinstance(finalized, FinalizedTurn):
            raise ApplicationConfigurationError(
                "turn controller returned an invalid finalized turn"
            )
        return finalized

    def fail(
        self, handle: ActiveTurnHandle, *, error: str, duration_seconds: float
    ) -> FinalizedTurn:
        finalized = self.source.fail(
            handle, error=error, duration_seconds=duration_seconds
        )
        if not isinstance(finalized, FinalizedTurn):
            raise ApplicationConfigurationError(
                "turn controller returned an invalid finalized turn"
            )
        return finalized


@dataclass(frozen=True, slots=True)
class _DomainOutputBuilderAdapter:
    source: object

    def __call__(self, *, binding_id: str, binding: object | None, context: object | None,
                 committed_answers: tuple[FinalizedTurn, ...], report_ref: str | None) -> ValidatedDomainOutput:
        if not callable(self.source):
            raise ApplicationConfigurationError("domain output builder is unavailable")
        result = _call_factory(self.source, binding_id=binding_id, binding=binding, context=context,
            committed_answers=committed_answers, report_ref=report_ref)
        if not isinstance(result, ValidatedDomainOutput):
            raise ApplicationConfigurationError("domain output builder returned an invalid output")
        return result


@dataclass(frozen=True, slots=True)
class _SelectedOutputContract:
    schema_id: str
    state_adapter: StateContextAdapter | None
    payload_builder: DomainPayloadBuilder
    validator: OutputValidator


@dataclass(frozen=True, slots=True)
class _StateContextAdapter:
    method: Callable[..., object]

    def build_context(self, *, binding_id: str, state: object) -> object:
        return self.method(binding_id=binding_id, state=state)


@dataclass(frozen=True, slots=True)
class _DomainPayloadBuilder:
    method: Callable[..., object]

    def build(
        self,
        *,
        binding_id: str,
        context: object | None,
        committed_answers: tuple[FinalizedTurn, ...],
    ) -> Mapping[str, object]:
        payload = self.method(
            binding_id=binding_id,
            context=context,
            committed_answers=committed_answers,
        )
        if not isinstance(payload, Mapping):
            raise ApplicationConfigurationError("domain output contract returned a non-object")
        return payload


@dataclass(frozen=True, slots=True)
class _ContextOutputValidator:
    method: Callable[..., object]

    def validate(self, payload: Mapping[str, object], *, context: object | None) -> None:
        self.method(payload, context=context)


@dataclass(frozen=True, slots=True)
class _LegacyOutputValidator:
    source: object
    method: Callable[..., object]

    def validate(self, payload: Mapping[str, object], *, context: object | None) -> None:
        scoped = _scope_output_contract(
            self.source, _context_admitted_references(context)
        )
        method = self.method if scoped is self.source else getattr(scoped, "validate", None)
        if not callable(method):
            raise ApplicationConfigurationError("domain output contract validator is unavailable")
        method(payload)


@dataclass(frozen=True, slots=True)
class _GenericReportPublisherAdapter:
    source: GenericReportShell

    def prepare(
        self, *, questions: tuple[str, ...], workspace: ApplicationWorkspace
    ) -> None:
        method = getattr(self.source, "prepare", None)
        if callable(method):
            method(questions=questions, workspace=workspace)

    def render(
        self,
        *,
        questions: tuple[str, ...],
        answers: tuple[str, ...],
        assurances: tuple[str, ...],
        trajectories: tuple[str, ...],
        references: tuple[str, ...],
        context: object | None,
        presentation: object | None,
        core: Mapping[str, object],
        domains: Mapping[str, object],
        workspace: ApplicationWorkspace,
        runtime: Mapping[str, object],
    ) -> str:
        del workspace, runtime
        return _render_generic_report_shell(
            report_method=self.source.render,
            questions=questions,
            answers=answers,
            assurances=assurances,
            trajectories=trajectories,
            references=references,
            context=context,
            presentation=presentation,
            core=core,
            domains=domains,
        )


@dataclass(frozen=True, slots=True)
class _ConfiguredReportPublisherAdapter:
    source: object

    def prepare(
        self, *, questions: tuple[str, ...], workspace: ApplicationWorkspace
    ) -> None:
        method = getattr(self.source, "prepare", None)
        if callable(method):
            method(questions=questions, workspace=workspace)

    def render(
        self,
        *,
        questions: tuple[str, ...],
        answers: tuple[str, ...],
        assurances: tuple[str, ...],
        trajectories: tuple[str, ...],
        references: tuple[str, ...],
        context: object | None,
        presentation: object | None,
        core: Mapping[str, object],
        domains: Mapping[str, object],
        workspace: ApplicationWorkspace,
        runtime: Mapping[str, object],
    ) -> str:
        method = getattr(self.source, "render", None)
        if not callable(method):
            return _render_generic_report_shell(
                report_method=GenericReportShell().render,
                questions=questions,
                answers=answers,
                assurances=assurances,
                trajectories=trajectories,
                references=references,
                context=context,
                presentation=presentation,
                core=core,
                domains=domains,
            )
        report = method(
            questions=questions,
            answers=answers,
            assurances=assurances,
            trajectories=trajectories,
            references=references,
            context=context,
            presentation=presentation,
            core=core,
            domains=domains,
            workspace=workspace,
            runtime=runtime,
        )
        if not isinstance(report, str):
            raise PresentationError("report shell must return text")
        return report


class AgentApplication:
    """Compose one prepared application and process its questions in order.

    All domain decisions arrive through the prepared binding and its public
    contracts.  The optional injection points make the runner usable by
    offline acceptance fixtures as well as the default Pi transport.
    """

    def __init__(
        self,
        *,
        profile: ApplicationProfile,
        prepared_application: PreparedApplicationRuntime | None = None,
        provider_catalog: ProviderCatalogSource | ProviderCatalog | None = None,
        provider_factory: ProviderFactory | None = None,
        transport_factory: ProviderFactory | None = None,
        provider: ProviderSession | LegacyPromptSession | None = None,
        workspace_root: Path | None = None,
        workspace: ApplicationWorkspace | None = None,
        registry: DomainRegistry | None = None,
        credentials: CredentialBroker | None = None,
        store: ApplicationContextStore | None = None,
        turn_controller: TurnControllerSource | None = None,
        projector: object | None = None,
        catalog: object | None = None,
        output_composer: FrameworkOutputComposer | None = None,
        output_renderer: object | None = None,
        report_shell: object | None = None,
        domain_output_builder: DomainOutputBuilder | None = None,
        binding_identities: Sequence[BindingIdentity] | None = None,
        lifecycle_hooks: Mapping[str, Callable[[], object]] | None = None,
        application_preparer: ApplicationPreparer | None = None,
        cli_options: CliLLMOptions | None = None,
        environment: Mapping[str, str] | None = None,
        runtime_host: RuntimeHost | None = None,
        runtime_paths: RuntimePaths | None = None,
        semantic_event_observer: Callable[[Mapping[str, object]], None] | None = None,
    ) -> None:
        self.profile = profile
        self.prepared_application = (
            _prepare_runtime(prepared_application)
            if prepared_application is not None
            else None
        )
        self.provider_catalog = provider_catalog
        self.provider_factory = provider_factory or transport_factory
        self.provider = _prepare_provider_session(provider) if provider is not None else None
        self.workspace_root = Path(workspace_root) if workspace_root is not None else None
        self.workspace = workspace
        self.registry = registry
        self.credentials = credentials
        self.store = store
        self.turn_controller = (
            _prepare_turn_controller(turn_controller)
            if turn_controller is not None
            else None
        )
        self.projector = projector
        self.catalog = catalog
        self.output_composer = output_composer or FrameworkOutputComposer()
        self.output_renderer = (
            output_renderer
            or getattr(profile, "output_renderer", None)
            or JsonOutputRenderer()
        )
        selected_report_shell = (
            report_shell or getattr(profile, "report_shell", None) or GenericReportShell()
        )
        self.report_publisher = _prepare_report_publisher(selected_report_shell)
        self.domain_output_builder = domain_output_builder
        self.binding_identities = tuple(binding_identities or ())
        self.lifecycle_hooks = dict(lifecycle_hooks or {})
        self.application_preparer = application_preparer
        self.cli_options = cli_options or CliLLMOptions()
        self._resolved_runtime: dict[str, str] | None = None
        self.environment = None if environment is None else dict(environment)
        self.runtime_host = runtime_host
        self.runtime_paths = runtime_paths
        self.semantic_event_observer = semantic_event_observer
        self._prepared_for_run = False
        self._diagnostic_workspace: ApplicationWorkspace | None = None
        self._diagnostic_run_id = "run"
        self._diagnostic_refs: list[str] = []
        self._diagnostic_codes: set[str] = set()
        if self.provider_factory is not None:
            _validate_keyword_callable(
                self.provider_factory,
                label="provider factory",
                names=_PROVIDER_FACTORY_KEYWORDS,
            )
        if self.application_preparer is not None:
            _validate_keyword_callable(
                self.application_preparer,
                label="application preparer",
                names=_APPLICATION_PREPARER_KEYWORDS,
            )

    def run(self, request: ApplicationRequest) -> ApplicationOutcome:
        return self._run(request, request.questions, streaming=False)

    def run_stream(
        self, request: ApplicationRequest, instructions: Iterable[str]
    ) -> ApplicationOutcome:
        """Consume instructions as they arrive in one prepared application run."""

        if request.questions:
            raise ValueError("streaming request must start without questions")
        if isinstance(instructions, str):
            raise ValueError("instructions must be an ordered source")
        return self._run(request, instructions, streaming=True)

    def _run(
        self, request: ApplicationRequest, instructions: Iterable[str], *, streaming: bool
    ) -> ApplicationOutcome:
        self._validate_request(request)
        self._diagnostic_workspace = None
        self._diagnostic_run_id = "run"
        self._diagnostic_refs = []
        self._diagnostic_codes = set()
        prepared: PreparedApplicationRuntime | None = None
        transport: ProviderSession | None = self.provider
        completed_answers: list[FinalizedTurn] = []
        report_path: Path | None = None
        transport_ready = False
        failure: str | None = None
        capture_status: ModelRequestCaptureStatus = "unavailable"
        selected_output_contracts: Mapping[str, _SelectedOutputContract] = {}
        workspace = self.workspace
        store = self.store
        controller: TurnControllerSession | None = None
        projector: object | None = self.projector
        active_turn: ActiveTurnHandle | None = None
        try:
            self._hook("registration")
            prepared = self._prepare(request)
            self._hook("provisioning")
            bindings = _prepared_bindings(prepared)
            workspace = self._ensure_workspace(request, bindings)
            self._diagnostic_workspace = workspace
            self._diagnostic_run_id = getattr(workspace, "run_id", request.run_id) or "run"
            self._run_presentation(
                lambda: self._prepare_application_output(request=request, workspace=workspace),
                code="report_prepare_unavailable",
            )
            store = self._ensure_store(request, workspace, bindings)
            controller = self._ensure_controller(store, workspace, bindings)
            catalog = self._validate_before_provider(prepared, bindings)
            self._hook("catalog_validation")
            projector = self._ensure_projector(store, catalog, bindings)
            selected_output_contracts = self._validate_selected_output_contracts(bindings)
            default_pi = self.provider is None and self.provider_factory is None
            capture_channels = self.runtime_paths if self.runtime_paths is not None else controller
            transport = self._ensure_provider(
                request=request,
                prepared=prepared,
                bindings=bindings,
                catalog=catalog,
                workspace=workspace,
                controller=controller,
            )
            if transport is None:
                raise ApplicationConfigurationError("provider transport is not configured")
            if default_pi:
                capture_status = _capture_status_for_channels(capture_channels)
            transport_ready = True
            transport.start()
            for ordinal, question in enumerate(instructions, start=1):
                if streaming:
                    if not isinstance(question, str) or not question.strip():
                        raise ApplicationConfigurationError("instruction must be non-empty text")
                    if store is not None:
                        store.append(ContextEventDraft(
                            event_type="application.instruction.accepted",
                            payload={"ordinal": ordinal, "instruction": question},
                        ))
                    request = replace(
                        request, questions=(*request.questions, question)
                    )
                handle = controller.start(ordinal, question)
                active_turn = handle
                turn_started = time.monotonic()
                try:
                    answer_value, projections = _call_prompt(
                        transport,
                        question,
                        projector=projector,
                        turn_id=handle.turn_id,
                        response_mode=request.response_mode,
                        semantic_event_observer=(
                            self._observe_semantic_event
                            if self.semantic_event_observer is not None else None
                        ),
                    )
                    if isinstance(answer_value, AnswerBundle):
                        answer = answer_value.answer
                        answer_summary = answer_value.summary
                        for code in answer_value.diagnostic_codes:
                            self._record_diagnostic(code)
                    else:
                        answer = answer_value
                        answer_summary = None
                    finalized = controller.submit(
                        handle,
                        answer_output=answer,
                        answer_summary=answer_summary,
                        referenced_bindings=tuple(
                            dict.fromkeys(
                                outcome.binding_id
                                for outcome in projections
                                if outcome.result_refs or outcome.evidence_refs
                            )
                        ),
                        result_refs=tuple(
                            dict.fromkeys(
                                reference
                                for outcome in projections
                                for reference in outcome.result_refs
                            )
                        ),
                        evidence_refs=tuple(
                            dict.fromkeys(
                                reference
                                for outcome in projections
                                for reference in outcome.evidence_refs
                            )
                        ),
                        duration_seconds=max(0.0, time.monotonic() - turn_started),
                    )
                except Exception as exc:
                    self._fail_active_turn(
                        controller,
                        handle,
                        error=_safe_failure(exc),
                        duration_seconds=max(0.0, time.monotonic() - turn_started),
                    )
                    active_turn = None
                    raise
                except BaseException as exc:
                    try:
                        self._fail_active_turn(
                            controller,
                            handle,
                            error=_safe_failure(exc),
                            duration_seconds=max(
                                0.0, time.monotonic() - turn_started
                            ),
                        )
                    except BaseException as failure_error:
                        # Preserve the control-flow exception that interrupted
                        # the turn while retaining the failure-publication
                        # error as its explicit cause.
                        active_turn = None
                        raise exc from failure_error
                    active_turn = None
                    raise
                completed_answers.append(finalized)
                active_turn = None
                for code in finalized.post_commit_diagnostic_codes:
                    self._record_diagnostic(code)
                # Evidence assurance is not execution status. A committed
                # limited answer remains visible and does not abort later work.
                if finalized.status not in {"success", "limited"}:
                    raise ApplicationConfigurationError("question did not produce an accepted answer")
                self._run_presentation(
                    lambda: self._write_report_checkpoint(
                        request=request,
                        workspace=workspace,
                        store=store,
                        completed_answers=tuple(completed_answers),
                        prepared=prepared,
                    ),
                    code="report_checkpoint_unavailable",
                )
                turn_event: dict[str, object] = {
                    "type": "application_turn_completed",
                    "ordinal": ordinal,
                    "total_questions": len(request.questions),
                    "answer_output": finalized.answer_output,
                    "turn_id": finalized.turn_id,
                    "answer_ref": finalized.answer_ref,
                    "result_refs": list(finalized.result_refs),
                    "evidence_refs": list(finalized.evidence_refs),
                }
                if finalized.answer_summary is not None:
                    turn_event["answer_summary"] = finalized.answer_summary
                self._observe_semantic_event(turn_event)
            preliminary_core = self._build_core_result(
                request=request,
                workspace=workspace,
                completed_answers=tuple(completed_answers),
                report_ref=None,
            )
            publication = self._publish_report(
                request=request, workspace=workspace, store=store,
                core=preliminary_core, completed_answers=tuple(completed_answers), prepared=prepared,
            )
            report_path = publication[0]
            report_ref = publication[1].report_ref
            result = self._build_result(
                request=request,
                workspace=workspace,
                store=store,
                bindings=bindings,
                selected_output_contracts=selected_output_contracts,
                completed_answers=tuple(completed_answers),
                report_ref=report_ref,
            )
            rendered = self._render(result)
            self._mark_completed(store, len(completed_answers), len(request.questions))
            return ApplicationOutcome(
                result=result,
                status="completed",
                rendered=rendered,
                run_id=getattr(workspace, "run_id", request.run_id),
                report_path=report_path,
                completed_questions=len(completed_answers),
                total_questions=len(request.questions),
                model_request_capture_status=capture_status,
            )
        except Exception as exc:
            failure = _safe_failure(exc)
            if active_turn is not None:
                self._fail_active_turn(
                    controller,
                    active_turn,
                    error=failure,
                    duration_seconds=max(
                        0.0,
                        time.monotonic()
                        - float(
                            active_turn.started_monotonic
                        ),
                    ),
                )
            result = self._failed_result(
                request=request,
                workspace=workspace,
                bindings=_prepared_bindings(prepared) if prepared is not None else {},
                completed_answers=tuple(completed_answers),
                error=failure,
            )
            self._mark_failed(store, failure)
            return ApplicationOutcome(
                result=result,
                status="failed",
                rendered=None,
                run_id=getattr(workspace, "run_id", request.run_id),
                report_path=report_path,
                completed_questions=len(completed_answers),
                total_questions=len(request.questions),
                error=failure,
                model_request_capture_status=capture_status,
            )
        finally:
            primary_failure = sys.exc_info()[1]
            cleanup_failure: BaseException | None = None
            if transport_ready and transport is not None:
                try:
                    _call_method(transport, "stop")
                except Exception:
                    pass
                except BaseException as exc:
                    cleanup_failure = exc
            try:
                self._cleanup(prepared)
            except Exception:
                # Cleanup is best effort after the primary result/failure has
                # been recorded.  A broken endpoint must not leak a secret or
                # replace the caller-visible sanitized outcome.
                pass
            except BaseException as exc:
                if cleanup_failure is None:
                    cleanup_failure = exc
            if cleanup_failure is not None and primary_failure is None:
                raise cleanup_failure

    def _validate_request(self, request: ApplicationRequest) -> None:
        application_id = getattr(getattr(self.profile, "manifest", None), "application_id", None)
        if application_id is not None and request.application_id != application_id:
            raise ApplicationConfigurationError("application request identity does not match profile")

    def _prepare(self, request: ApplicationRequest) -> PreparedApplicationRuntime:
        if self.prepared_application is not None:
            return self.prepared_application
        if self.application_preparer is not None:
            return _prepare_runtime(
                self.application_preparer(
                    profile=self.profile,
                    request=request,
                    workspace=self.workspace,
                    registry=self.registry,
                    credentials=self.credentials,
                )
            )
        if self.registry is None or self.credentials is None or self.workspace is None:
            raise ApplicationConfigurationError("prepared application inputs are incomplete")
        return prepare_application(
            self.profile,
            registry=self.registry,
            workspace=self.workspace.root,
            credentials=self.credentials,
        )

    def _ensure_workspace(
        self, request: ApplicationRequest, bindings: Mapping[str, object]
    ) -> ApplicationWorkspace | None:
        if self.workspace is not None:
            return self.workspace
        if self.workspace_root is None:
            return None
        binding_ids = tuple(sorted(bindings))
        return ApplicationWorkspace.create(
            self.workspace_root,
            run_id=request.run_id,
            binding_ids=binding_ids,
        )

    def _prepare_application_output(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
    ) -> None:
        if workspace is None:
            return
        self.report_publisher.prepare(questions=request.questions, workspace=workspace)

    def _ensure_store(
        self,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        bindings: Mapping[str, object],
    ) -> ApplicationContextStore | None:
        if self.store is not None:
            return self.store
        if workspace is None:
            return None
        domains = {
            binding_id: _state_schema(binding)
            for binding_id, binding in bindings.items()
        }
        try:
            return ApplicationContextStore.initialize(
                workspace,
                domains=domains,
                core={
                    "input": {
                        "application_id": request.application_id,
                        "questions": list(request.questions),
                    }
                },
            )
        except Exception as exc:
            raise ApplicationConfigurationError("application context could not be initialized") from exc

    def _ensure_controller(
        self,
        store: ApplicationContextStore | None,
        workspace: ApplicationWorkspace | None,
        bindings: Mapping[str, object],
    ) -> TurnControllerSession:
        if self.turn_controller is not None:
            return self.turn_controller
        if store is None or workspace is None:
            raise ApplicationConfigurationError("turn controller is not configured")
        return _prepare_turn_controller(TurnController(
            store=store,
            workspace=workspace,
            bindings=bindings,
        ))

    def _ensure_projector(
        self,
        store: ApplicationContextStore | None,
        catalog: object | None,
        bindings: Mapping[str, object],
    ) -> object | None:
        """Create the normal invocation projector after run state exists."""

        if self.projector is not None:
            return self.projector
        if not isinstance(store, ApplicationContextStore) or not isinstance(
            catalog, CompositeToolCatalog
        ):
            return None
        return ApplicationInvocationProjector(store, catalog, bindings)

    def _validate_selected_output_contracts(
        self, bindings: Mapping[str, object]
    ) -> Mapping[str, _SelectedOutputContract]:
        """Preflight output seams that are required to complete a run."""

        if self.domain_output_builder is not None:
            self.domain_output_builder = _prepare_domain_output_builder(
                self.domain_output_builder
            )
            return {}
        selected: dict[str, _SelectedOutputContract] = {}
        for binding_id, binding in bindings.items():
            profile = getattr(binding, "profile", None)
            profile = profile or getattr(
                getattr(binding, "binding", None), "profile", None
            )
            contract = getattr(profile, "output_contract", None)
            if contract is None:
                raise ApplicationConfigurationError(
                    f"binding {binding_id!r} output contract is unavailable"
                )
            identity = next(
                (
                    candidate
                    for candidate in self.binding_identities
                    if candidate.binding_id == binding_id
                ),
                BindingIdentity(
                    binding_id=binding_id,
                    domain_id=_domain_id(binding),
                    domain_version=_domain_version(binding),
                ),
            )
            selected[binding_id] = _SelectedOutputContract(
                schema_id=_domain_output_schema(binding, identity),
                state_adapter=_prepare_state_context_adapter(
                    getattr(profile, "state_adapter", None), binding_id
                ),
                payload_builder=_prepare_domain_payload_builder(contract, binding_id),
                validator=_prepare_output_validator(contract, binding_id),
            )
        return selected

    def _validate_before_provider(
        self, prepared: PreparedApplicationRuntime, bindings: Mapping[str, object]
    ) -> object | None:
        _call_method(getattr(self.profile, "application_policy", None), "load")
        for binding_id in sorted(bindings):
            binding = bindings[binding_id]
            profile = _binding_profile(binding)
            if profile is None:
                raise ApplicationConfigurationError(
                    f"binding {binding_id!r} profile is unavailable"
                )
            _call_method(getattr(profile, "policy_provider", None), "load")
            runtime = getattr(binding, "runtime", None)
            authority = getattr(runtime, "authority", None)
            if authority is None:
                raise ApplicationConfigurationError(
                    f"binding {binding_id!r} current-run authority is unavailable"
                )
            try:
                _call_method(profile, "validate_answer_admission_declaration")
                policy = _call_method(
                    profile, "create_answer_admission_policy", authority
                )
                if not callable(getattr(policy, "admit", None)):
                    raise TypeError("answer admission policy is invalid")
            except Exception:
                self._record_diagnostic("answer_evaluation_unavailable")
        self._hook("policy_composition")
        for binding_id in sorted(bindings):
            profile = _binding_profile(bindings[binding_id])
            provider = getattr(profile, "guide_provider", None)
            if provider is None:
                if profile is not None:
                    raise ApplicationConfigurationError(
                        f"binding {binding_id!r} guide provider is unavailable"
                    )
                continue
            guides = _call_method(provider, "load")
            if not isinstance(guides, (tuple, list)) or any(
                not isinstance(guide, Mapping) for guide in guides
            ):
                raise ApplicationConfigurationError(
                    f"binding {binding_id!r} guide index is invalid"
                )
        self._hook("guide_validation")
        if self.catalog is not None:
            return self.catalog
        try:
            domains = tuple(
                BoundDomainCatalog.from_prepared(cast(PreparedBinding, bindings[binding_id]))
                for binding_id in sorted(bindings)
            )
            manifest = getattr(self.profile, "manifest", None)
            namespace = getattr(manifest, "core_tool_namespace", "agent_")
            return CompositeToolCatalog.build(
                core=CoreToolCatalog.default(namespace=namespace),
                domains=domains,
            )
        except Exception as exc:
            raise ApplicationConfigurationError(
                "prepared capability catalog is invalid"
            ) from exc

    def _ensure_provider(
        self,
        *,
        request: ApplicationRequest,
        prepared: PreparedApplicationRuntime,
        bindings: Mapping[str, object],
        catalog: object | None,
        workspace: ApplicationWorkspace | None,
        controller: TurnControllerSession,
    ) -> ProviderSession | None:
        if self.provider is not None:
            return self.provider
        if self.provider_factory is not None:
            return _prepare_provider_session(
                self.provider_factory(
                    request=request,
                    profile=self.profile,
                    prepared_application=prepared,
                    bindings=bindings,
                    catalog=catalog,
                )
            )
        if not isinstance(self.provider_catalog, ProviderCatalog):
            source = self.provider_catalog
            if source is not None and callable(getattr(source, "load", None)):
                source = _call_method(source, "load")
            if not isinstance(source, ProviderCatalog):
                return None
            provider_catalog = source
        else:
            provider_catalog = self.provider_catalog
        resolution_environment = (
            os.environ if self.environment is None else self.environment
        )
        resolved = resolve_llm(
            catalog=provider_catalog,
            cli=self.cli_options,
            environ=resolution_environment,
        )
        if workspace is None:
            raise ApplicationConfigurationError(
                "default Pi transport requires a workspace"
            )
        transport = self._default_pi_transport(
            resolved,
            prepared,
            bindings,
            request=request,
            workspace=workspace,
            controller=controller,
        )
        self._resolved_runtime = {
            "provider": resolved.config.provider,
            "model": resolved.config.model,
        }
        self._observe_semantic_event({
            "type": "application_provider_resolved",
            "run_id": request.run_id or getattr(workspace, "run_id", ""),
            "provider": resolved.config.provider,
            "model": resolved.config.model,
            "timeout_seconds": resolved.config.timeout_seconds,
            "max_retries": resolved.config.max_retries,
        })
        return _prepare_provider_session(transport)

    def _default_pi_transport(
        self,
        resolved: ResolvedLLM,
        prepared: object,
        bindings: Mapping[str, object],
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace,
        controller: TurnControllerSession,
    ) -> PiRpcClient:
        if self.runtime_paths is None:
            if self.runtime_host is None:
                raise ApplicationConfigurationError(
                    "default Pi transport requires an injected runtime host"
                )
            if not bindings:
                raise ApplicationConfigurationError(
                    "default Pi transport requires prepared bindings"
                )
            single_binding = len(bindings) == 1
            runtime_dir = (
                workspace.domain_runtime_path(next(iter(bindings)))
                if single_binding else workspace.core_path / "runtime"
            )
            descriptor_path = runtime_dir / "runtime-descriptor.json"
            handoff_index_path = workspace.core_path / "reference-handoffs.json"
            if not handoff_index_path.exists():
                handoff_index_path.write_text(
                    '{"schema":"capability-agent-reference-handoffs/1.0","run_id":'
                    + json.dumps(workspace.run_id)
                    + ',"handoffs":[]}\n',
                    encoding="utf-8",
                )
            descriptors = []
            for binding_id in sorted(bindings):
                binding = bindings[binding_id]
                endpoint = getattr(binding, "endpoint", None)
                runtime = getattr(binding, "runtime", None)
                binding_profile = getattr(getattr(binding, "binding", None), "profile", None)
                runtime_profile = getattr(runtime, "profile", None)
                manifest = getattr(runtime_profile, "manifest", None) or getattr(
                    binding_profile, "manifest", None
                )
                tool_catalog_path = _runtime_path(runtime, "tool_catalog_path")
                guide_index_path = _runtime_path(runtime, "guide_index_path")
                descriptors.append(
                    descriptor_from_endpoint(
                        binding_id=binding_id,
                        workspace=workspace.domain_path(binding_id),
                        application_workspace_path=workspace.root,
                        endpoint=endpoint,
                        protocol=getattr(manifest, "protocol", ""),
                        protocol_version=getattr(manifest, "protocol_version", ""),
                        authority_id=getattr(
                            getattr(runtime, "authority", None), "authority_id", ""
                        ),
                        tool_catalog_path=tool_catalog_path,
                        guide_index_path=guide_index_path,
                        guide_root_path=_runtime_path(runtime, "guide_root_path"),
                        tool_name_prefix=getattr(manifest, "tool_name_prefix", None),
                        guide_index_sha256=_runtime_file_digest(guide_index_path),
                        application_id=request.application_id,
                        run_id=workspace.run_id,
                        active_turn_path=(
                            controller.active_turn_path
                            or workspace.turns_path / "active-turn.json"
                        ),
                        context_view_path=(
                            controller.context_view_path or workspace.context_snapshot_path
                        ),
                        trajectory_requests_path=controller.trajectory_requests_path,
                        trajectory_capture_state_path=controller.trajectory_capture_state_path,
                        trajectory_allowed_refs_path=controller.trajectory_allowed_refs_path,
                        trajectory_acks_path=controller.trajectory_acks_path,
                        reference_handoffs_path=handoff_index_path,
                    )
                )
            descriptor = (
                descriptors[0]
                if single_binding
                else CompositeRuntimeDescriptor(tuple(descriptors))
            )
            write_runtime_descriptor(descriptor_path, descriptor)
            search_paths = tuple(
                dict.fromkeys(
                    Path(path) for member in descriptors for path in member.search_path
                )
            )
            single_runtime = (
                getattr(bindings[next(iter(bindings))], "runtime", None)
                if single_binding else None
            )
            host = self.runtime_host
            self.runtime_paths = RuntimePaths(
                command=host.command,
                project_pi_dir=host.project_pi_dir,
                session_dir=runtime_dir / "session",
                workspace=workspace.root,
                domain_search_paths=search_paths,
                extension_path=host.extension_path,
                tool_catalog_path=(
                    _runtime_path(single_runtime, "tool_catalog_path")
                    if single_binding else None
                ),
                guide_index_path=(
                    _runtime_path(single_runtime, "guide_index_path")
                    if single_binding else None
                ),
                system_policy_path=host.system_policy_path,
                runtime_descriptor_path=descriptor_path,
                binding_id=next(iter(bindings)) if single_binding else None,
                extra_environment=getattr(host, "extra_environment", {}),
            )
        launch = build_pi_launch(
            resolved,
            self.runtime_paths,
            base_environment=(
                os.environ if self.environment is None else self.environment
            ),
        )
        trace_path = self.runtime_paths.workspace / "core" / "events.jsonl"
        trace = JsonlTraceWriter(trace_path, secret_values={resolved.secret.value} if resolved.secret else set())
        return PiRpcClient(
            launch,
            cast(Any, SimpleNamespace(root_path=self.runtime_paths.workspace)),
            trace,
            secret_values={resolved.secret.value} if resolved.secret else set(),
        )

    def _build_result(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        store: ApplicationContextStore | None,
        bindings: Mapping[str, object],
        selected_output_contracts: Mapping[str, _SelectedOutputContract],
        completed_answers: tuple[FinalizedTurn, ...],
        report_ref: str | None,
    ) -> ApplicationResult:
        identities = self.binding_identities or tuple(
            BindingIdentity(
                binding_id=binding_id,
                domain_id=_domain_id(bindings[binding_id]),
                domain_version=_domain_version(bindings[binding_id]),
            )
            for binding_id in sorted(bindings)
        )
        domain_outputs: dict[str, ValidatedDomainOutput] = {}
        for identity in identities:
            binding = bindings.get(identity.binding_id)
            domain_outputs[identity.binding_id] = self._build_domain_output(
                identity.binding_id,
                binding,
                store,
                completed_answers,
                selected_output_contracts.get(identity.binding_id),
                report_ref=report_ref,
            )
        core = self._build_core_result(
            request=request,
            workspace=workspace,
            completed_answers=completed_answers,
            report_ref=report_ref,
        )
        return self.output_composer.compose(
            core=core,
            bindings=identities,
            domains=domain_outputs,
        )

    def _build_core_result(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        completed_answers: tuple[FinalizedTurn, ...],
        report_ref: str | None,
    ) -> CoreRunResult:
        answer_refs = tuple(
            ref
            for answer in completed_answers
            for ref in (answer.answer_ref,)
            if ref
        )
        manifest = getattr(self.profile, "manifest", None)
        return CoreRunResult(
            application_id=getattr(manifest, "application_id", request.application_id),
            application_version=getattr(manifest, "version", "1.0.0"),
            run_id=getattr(workspace, "run_id", request.run_id or "run"),
            status="completed",
            answer_refs=answer_refs,
            report_ref=report_ref,
            diagnostic_refs=tuple(self._diagnostic_refs),
        )

    def _build_domain_output(
        self,
        binding_id: str,
        binding: object | None,
        store: ApplicationContextStore | None,
        completed_answers: tuple[FinalizedTurn, ...],
        selected_contract: _SelectedOutputContract | None,
        *,
        report_ref: str | None,
    ) -> ValidatedDomainOutput:
        context = store.snapshot if store is not None else None
        if report_ref is not None:
            context = _with_report_reference(context, report_ref)
        if self.domain_output_builder is not None:
            return self.domain_output_builder(
                binding_id=binding_id,
                binding=binding,
                context=context,
                committed_answers=completed_answers,
                report_ref=report_ref,
            )
        if selected_contract is None:
            raise ApplicationConfigurationError("domain output contract is not configured")
        context = None
        if store is not None:
            state = store.snapshot.domains[binding_id].state
            if selected_contract.state_adapter is not None:
                context = selected_contract.state_adapter.build_context(
                    binding_id=binding_id, state=state
                )
        if report_ref is not None:
            context = _with_report_reference(context, report_ref)
        payload = selected_contract.payload_builder.build(
            binding_id=binding_id,
            context=context,
            committed_answers=completed_answers,
        )
        selected_contract.validator.validate(payload, context=context)
        return ValidatedDomainOutput(
            schema=selected_contract.schema_id,
            status="completed",
            payload=payload,
        )

    def _failed_result(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        bindings: Mapping[str, object],
        completed_answers: tuple[FinalizedTurn, ...],
        error: str,
    ) -> ApplicationResult:
        """Build a sanitized framework result without rerunning domain logic."""

        identities = self.binding_identities or tuple(
            BindingIdentity(
                binding_id=binding_id,
                domain_id=_domain_id(binding),
                domain_version=_domain_version(binding),
            )
            for binding_id, binding in bindings.items()
        )
        domains: dict[str, ValidatedDomainOutput] = {}
        for identity in identities:
            binding = bindings.get(identity.binding_id)
            domains[identity.binding_id] = ValidatedDomainOutput(
                schema=_domain_output_schema(binding, identity),
                status="failed",
                payload={"error": error},
            )
        manifest = getattr(self.profile, "manifest", None)
        core = CoreRunResult(
            application_id=getattr(manifest, "application_id", request.application_id),
            application_version=getattr(manifest, "version", "1.0.0"),
            run_id=getattr(workspace, "run_id", request.run_id or "run"),
            status="failed",
            answer_refs=tuple(
                ref
                for answer in completed_answers
                for ref in (answer.answer_ref,)
                if ref
            ),
            report_ref=None,
            diagnostic_refs=tuple(self._diagnostic_refs),
        )
        return self.output_composer.compose(
            core=core,
            bindings=identities,
            domains=domains,
        )

    def _render(self, result: ApplicationResult) -> object:
        renderer = self.output_renderer
        method = getattr(renderer, "render", None)
        if not callable(method):
            raise ApplicationConfigurationError("output renderer is not configured")
        return method(result)

    def _write_report(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        store: ApplicationContextStore | None,
        core: CoreRunResult,
        completed_answers: tuple[FinalizedTurn, ...],
        prepared: PreparedApplicationRuntime | None = None,
        final: bool = False,
    ) -> tuple[Path | None, str | None]:
        if workspace is None:
            return None, None
        report = self._render_report(
            request=request,
            workspace=workspace,
            store=store,
            core=core,
            completed_answers=completed_answers,
            prepared=prepared,
            final=final,
        )
        path = workspace.output_path / "report.md"
        _write_report_atomically(path, report)
        try:
            pointer = ImmutableArtifactRegistry(
                workspace.root,
                path_policy=_ReportArtifactPathPolicy(),
            ).register_existing("report", "report", path)
        except (ArtifactIntegrityError, OSError, ValueError):
            raise PresentationError("report artifact admission failed") from None
        return path, pointer.ref

    def _publish_report(
        self, *, request: ApplicationRequest, workspace: ApplicationWorkspace | None,
        store: ApplicationContextStore | None, core: CoreRunResult,
        completed_answers: tuple[FinalizedTurn, ...], prepared: PreparedApplicationRuntime | None,
    ) -> tuple[Path | None, ReportPublication]:
        try:
            path, report_ref = self._write_report(
                request=request, workspace=workspace, store=store, core=core,
                completed_answers=completed_answers, prepared=prepared, final=True,
            )
            self._record_report_reference(store, report_ref)
            return path, ReportPublication("published", report_ref)
        except Exception:
            self._record_diagnostic("report_unavailable")
            return None, ReportPublication("unavailable", None, ("report_unavailable",))

    def _run_presentation(self, action: Callable[[], object], *, code: str) -> None:
        try:
            action()
        except Exception:
            self._record_diagnostic(code)

    def _record_diagnostic(self, code: str) -> None:
        """Record only fixed diagnostic fields; never re-enter a failing observer."""
        if code in self._diagnostic_codes:
            return
        self._diagnostic_codes.add(code)
        workspace = self._diagnostic_workspace
        run_id = self._diagnostic_run_id
        if not isinstance(run_id, str) or not PORTABLE_ID_PATTERN.fullmatch(run_id):
            run_id = "run"
        if workspace is not None:
            try:
                registry = ImmutableArtifactRegistry(
                    workspace.root,
                    path_policy=NeutralArtifactPathPolicy(layouts={
                        "diagnostic": ArtifactLayout(
                            "core/diagnostics/{identity}", "diagnostic.json"
                        ),
                    }),
                )
                pointer = registry.write_json("diagnostic", code, {
                    "schema": "application-diagnostic/1.0",
                    "run_id": run_id,
                    "code": code,
                })
                self._diagnostic_refs.append(pointer.ref)
                return
            except Exception:
                pass
        _diagnostic_stderr(code, run_id)

    def _write_report_checkpoint(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        store: ApplicationContextStore | None,
        completed_answers: tuple[FinalizedTurn, ...],
        prepared: PreparedApplicationRuntime | None = None,
    ) -> None:
        """Refresh the mutable operator report without admitting an artifact."""
        if workspace is None:
            return
        core = self._build_core_result(
            request=request,
            workspace=workspace,
            completed_answers=completed_answers,
            report_ref=None,
        )
        report = self._render_report(
            request=request,
            workspace=workspace,
            store=store,
            core=core,
            completed_answers=completed_answers,
            prepared=prepared,
        )
        _write_report_atomically(workspace.output_path / "report.md", report)
        self._observe_semantic_event(
            {
                "type": "application_report_checkpoint",
                "completed_questions": len(completed_answers),
                "total_questions": len(request.questions),
                "report_path": str(workspace.output_path / "report.md"),
            }
        )

    def _observe_semantic_event(self, event: Mapping[str, object]) -> None:
        observer = self.semantic_event_observer
        if observer is not None:
            try:
                observer(event)
            except Exception:
                self._record_diagnostic("progress_observer_unavailable")

    def _render_report(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace,
        store: ApplicationContextStore | None,
        core: CoreRunResult,
        completed_answers: tuple[FinalizedTurn, ...],
        prepared: PreparedApplicationRuntime | None = None,
        final: bool = False,
    ) -> str:
        presentation = None
        bindings = _prepared_bindings(
            self.prepared_application if prepared is None else prepared
        )
        if len(bindings) == 1:
            binding = next(iter(bindings.values()))
            profile = getattr(binding, "profile", None) or getattr(
                getattr(binding, "binding", None), "profile", None
            )
            presentation = getattr(profile, "presentation_provider", None)
        answers = tuple(answer.answer_output for answer in completed_answers)
        assurances = _persisted_answer_assurances(completed_answers, workspace)
        references = tuple(
            ref
            for answer in completed_answers
            for ref in (*answer.result_refs, *getattr(answer, "evidence_refs", ()))
        )
        runtime = dict(self._resolved_runtime or {
            "provider": self.cli_options.provider,
            "model": self.cli_options.model,
        })
        if final:
            runtime["report_status"] = "completed"
        return self.report_publisher.render(
            questions=request.questions,
            answers=answers,
            assurances=assurances,
            trajectories=(),
            references=references,
            context=store.snapshot if store is not None else None,
            presentation=presentation,
            core=core.model_dump(mode="json"),
            domains={},
            workspace=workspace,
            runtime=runtime,
        )

    def _record_report_reference(
        self, store: ApplicationContextStore | None, report_ref: str | None
    ) -> None:
        if store is None or report_ref is None:
            return
        snapshot = getattr(store, "snapshot", None)
        core = getattr(snapshot, "core", None)
        produced_refs = getattr(core, "produced_refs", ())
        if report_ref in produced_refs:
            return
        from capability_agent.application.context_models import ContextEventDraft

        try:
            store.append(
                ContextEventDraft(
                    event_type="reference.produced",
                    payload={"ref": report_ref},
                )
            )
        except Exception as exc:
            raise ApplicationConfigurationError(
                "report reference could not be persisted"
            ) from exc

    def _mark_completed(
        self, store: ApplicationContextStore | None, completed: int, total: int
    ) -> None:
        if store is None:
            return
        from capability_agent.application.context_models import ContextEventDraft

        try:
            store.append(
                ContextEventDraft(
                    event_type="application.completed",
                    payload={"completed_questions": completed, "total_questions": total},
                )
            )
        except Exception as exc:
            raise ApplicationConfigurationError(
                "application completion event could not be persisted"
            ) from exc

    def _mark_failed(self, store: ApplicationContextStore | None, error: str) -> None:
        if store is None:
            return
        from capability_agent.application.context_models import ContextEventDraft

        try:
            store.append(
                ContextEventDraft(
                    event_type="application.failed",
                    payload={"error": error},
                )
            )
        except Exception:
            pass

    def _cleanup(self, prepared: PreparedApplicationRuntime | None) -> None:
        bindings = _prepared_bindings(prepared)
        control_failure: BaseException | None = None
        for binding_id in reversed(tuple(bindings)):
            endpoint = getattr(bindings[binding_id], "endpoint", None)
            if endpoint is None:
                continue
            try:
                _call_method(endpoint, "close")
            except Exception:
                continue
            except BaseException as exc:
                if control_failure is None:
                    control_failure = exc
        if control_failure is not None:
            raise control_failure

    def _fail_active_turn(
        self,
        controller: TurnControllerSession | None,
        handle: ActiveTurnHandle,
        *,
        error: str,
        duration_seconds: float,
    ) -> None:
        """Close a turn after an ordinary provider or commit error.

        Failure publication is best effort so that the original execution
        error remains sanitized and stable.  ``BaseException`` is intentionally
        not caught here; interruption and process-control signals must pass
        through the runner's cleanup path.
        """

        try:
            if controller is None:
                return
            controller.fail(
                handle,
                error=error,
                duration_seconds=max(0.0, duration_seconds),
            )
        except Exception:
            pass

    def _hook(self, name: str) -> None:
        callback = self.lifecycle_hooks.get(name)
        if callback is not None:
            _call_factory(callback)


def _prepare_runtime(value: object) -> PreparedApplicationRuntime:
    if not _is_prepared_runtime(value):
        raise ApplicationConfigurationError("prepared application bindings are invalid")
    return value


def _is_prepared_runtime(value: object) -> TypeGuard[PreparedApplicationRuntime]:
    bindings = getattr(value, "bindings", None)
    return isinstance(bindings, Mapping) and all(
        isinstance(binding_id, str) for binding_id in bindings
    )


def _prepare_provider_session(value: object) -> ProviderSession:
    _validate_provider_session(value)
    return _ProviderSessionAdapter(value)


def _prepare_report_publisher(value: object) -> ReportPublisher:
    if isinstance(value, GenericReportShell):
        return _GenericReportPublisherAdapter(value)
    return _ConfiguredReportPublisherAdapter(value)


def _prepare_turn_controller(value: object) -> TurnControllerSession:
    _validate_turn_controller(value)
    if not _is_turn_controller_source(value):
        raise ApplicationConfigurationError("turn controller is unavailable")
    return _TurnControllerAdapter(
        source=value,
        active_turn_path=_controller_channel_path(value, "active_turn_path"),
        context_view_path=_controller_channel_path(value, "context_view_path"),
        trajectory_requests_path=_controller_channel_path(
            value, "trajectory_requests_path"
        ),
        trajectory_capture_state_path=_controller_channel_path(
            value, "trajectory_capture_state_path"
        ),
        trajectory_allowed_refs_path=_controller_channel_path(
            value, "trajectory_allowed_refs_path"
        ),
        trajectory_acks_path=_controller_channel_path(value, "trajectory_acks_path"),
    )


def _is_turn_controller_source(value: object) -> TypeGuard[TurnControllerSource]:
    return all(callable(getattr(value, name, None)) for name in ("start", "submit", "fail"))


def _controller_channel_path(value: object, name: str) -> Path | None:
    channel = getattr(value, name, None)
    if channel is None:
        return None
    if isinstance(channel, Path):
        return channel
    raise ApplicationConfigurationError(f"runtime channel {name!r} must be a path")


def _capture_status_for_channels(value: object) -> ModelRequestCaptureStatus:
    """Describe configured capture channels, not successful Provider I/O."""
    channels = tuple(
        getattr(value, name, None)
        for name in (
            "trajectory_requests_path",
            "trajectory_capture_state_path",
            "trajectory_allowed_refs_path",
            "trajectory_acks_path",
        )
    )
    if all(isinstance(channel, Path) for channel in channels) and isinstance(
        getattr(value, "active_turn_path", None), Path
    ):
        return "enabled"
    if all(channel is None for channel in channels):
        return "disabled"
    return "unavailable"


def _prepare_domain_output_builder(value: object) -> DomainOutputBuilder:
    _validate_keyword_callable(
        value,
        label="domain output builder",
        names=("binding_id", "binding", "context", "committed_answers", "report_ref"),
    )
    return _DomainOutputBuilderAdapter(value)


def _prepared_bindings(
    prepared: PreparedApplicationRuntime | None,
) -> Mapping[str, object]:
    if prepared is None:
        return {}
    return prepared.bindings


def _state_schema(binding: object) -> str:
    profile = _binding_profile(binding)
    manifest = getattr(profile, "manifest", None)
    value = getattr(manifest, "state_schema", None)
    if isinstance(value, str) and value:
        return value
    domain_id = _domain_id(binding)
    return f"{domain_id}-state/1.0"


def _domain_id(binding: object) -> str:
    profile = _binding_profile(binding)
    manifest = getattr(profile, "manifest", None)
    return str(getattr(manifest, "domain_id", "domain"))


def _domain_version(binding: object) -> str:
    profile = _binding_profile(binding)
    manifest = getattr(profile, "manifest", None)
    return str(getattr(manifest, "version", "1.0.0"))


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _runtime_path(runtime: object | None, name: str) -> Path | None:
    value = getattr(runtime, name, None) if runtime is not None else None
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value:
        return Path(value)
    raise ApplicationConfigurationError(f"prepared runtime {name!r} must be a path")


def _runtime_file_digest(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ApplicationConfigurationError(
            "prepared runtime guide index could not be read"
        ) from exc


def _binding_profile(binding: object | None) -> object | None:
    if binding is None:
        return None
    return getattr(binding, "profile", None) or getattr(
        getattr(binding, "binding", None), "profile", None
    )


def _safe_failure(error: BaseException) -> str:
    if isinstance(error, CapabilityAgentError):
        return f"{type(error).__name__}: application execution failed"
    return f"{type(error).__name__}: application execution failed"


def _domain_output_schema(
    binding: object | None, identity: BindingIdentity
) -> str:
    profile = getattr(binding, "profile", None) if binding is not None else None
    profile = profile or getattr(getattr(binding, "binding", None), "profile", None)
    contract = getattr(profile, "output_contract", None)
    schema_id = getattr(contract, "schema_id", None)
    if isinstance(schema_id, str) and schema_id:
        return schema_id
    return f"{identity.domain_id}-output/1.0"


def _call_method(
    target: object | None,
    name: str,
    *args: object,
    optional: bool = False,
    **kwargs: object,
) -> object:
    method = getattr(target, name, None) if target is not None else None
    if not callable(method):
        if optional:
            return None
        raise ApplicationConfigurationError(f"required runtime method {name!r} is unavailable")
    return _call_factory(method, *args, **kwargs)


def _call_factory(factory: Callable[..., Any], *args: object, **kwargs: object) -> Any:
    if not callable(factory):
        raise ApplicationConfigurationError("runtime factory is unavailable")
    return factory(*args, **kwargs)


def _validate_turn_controller(controller: object) -> None:
    _validate_positional_and_keyword_callable(
        getattr(controller, "start", None),
        label="turn controller start",
        positional=(1, "question"),
        names=(),
    )
    _validate_positional_and_keyword_callable(
        getattr(controller, "submit", None),
        label="turn controller submit",
        positional=(object(),),
        names=(
            "answer_output",
            "referenced_bindings",
            "result_refs",
            "evidence_refs",
            "duration_seconds",
        ),
    )
    _validate_positional_and_keyword_callable(
        getattr(controller, "fail", None),
        label="turn controller fail",
        positional=(object(),),
        names=("error", "duration_seconds"),
    )


def _prepare_state_context_adapter(
    adapter: object | None, binding_id: str
) -> StateContextAdapter | None:
    if adapter is None:
        return None
    method = getattr(adapter, "build_context", None)
    _validate_keyword_callable(
        method,
        label=f"binding {binding_id!r} state adapter",
        names=("binding_id", "state"),
    )
    if not callable(method):
        raise ApplicationConfigurationError("state adapter is unavailable")
    return _StateContextAdapter(method)


def _prepare_domain_payload_builder(
    contract: object, binding_id: str
) -> DomainPayloadBuilder:
    method = getattr(contract, "build", None)
    _validate_keyword_callable(
        method,
        label=f"binding {binding_id!r} output contract build",
        names=("binding_id", "context", "committed_answers"),
    )
    if not callable(method):
        raise ApplicationConfigurationError("domain output contract is unavailable")
    return _DomainPayloadBuilder(method)


def _prepare_output_validator(contract: object, binding_id: str) -> OutputValidator:
    context_validator = getattr(contract, "validate_with_context", None)
    if callable(context_validator):
        _validate_positional_and_keyword_callable(
            context_validator,
            label=f"binding {binding_id!r} context-aware output validator",
            positional=({},),
            names=("context",),
        )
        return _ContextOutputValidator(context_validator)
    validator = getattr(contract, "validate", None)
    _validate_positional_and_keyword_callable(
        validator,
        label=f"binding {binding_id!r} output validator",
        positional=({},),
        names=(),
    )
    if not callable(validator):
        raise ApplicationConfigurationError("domain output contract validator is unavailable")
    return _LegacyOutputValidator(contract, validator)


def _validate_positional_and_keyword_callable(
    factory: object,
    *,
    label: str,
    positional: tuple[object, ...],
    names: tuple[str, ...],
) -> None:
    if not callable(factory):
        raise ApplicationConfigurationError(f"{label} is unavailable")
    signature = _runtime_signature(factory, label=label)
    try:
        signature.bind(*positional, **{name: None for name in names})
    except TypeError as exc:
        raise ApplicationConfigurationError(
            f"{label} does not accept its required invocation inputs"
        ) from exc


def _render_generic_report_shell(
    *,
    report_method: Callable[..., object],
    questions: Sequence[str],
    answers: Sequence[str],
    assurances: Sequence[str],
    trajectories: Sequence[str],
    references: Sequence[str],
    context: object | None,
    presentation: object | None,
    core: Mapping[str, object],
    domains: Mapping[str, object],
) -> str:
    """Adapt the nine-field generic shell without runner-only details."""

    report = report_method(
        questions=questions,
        answers=answers,
        assurances=assurances,
        trajectories=trajectories,
        references=references,
        context=context,
        presentation=presentation,
        core=core,
        domains=domains,
    )
    if not isinstance(report, str):
        raise PresentationError("report shell must return text")
    return report


def _scope_output_contract(contract: object, references: frozenset[str]) -> object:
    """Bind admitted references to an opt-in contract without shared mutation."""

    if not references:
        return contract
    missing = object()
    configured = getattr(contract, "allowed_references", missing)
    if configured is not None or configured is missing:
        return contract
    try:
        scoped_contract = copy.copy(contract)
        setattr(scoped_contract, "allowed_references", references)
    except (AttributeError, TypeError):
        return contract
    return scoped_contract


def _context_admitted_references(context: object | None) -> frozenset[str]:
    """Read only generic admission fields from an opaque context view."""

    if context is None:
        return frozenset()
    raw = _context_mapping(context)
    references: set[str] = set()
    for source in (raw, raw.get("state")):
        if not isinstance(source, Mapping):
            continue
        for key in ("admitted_artifact_refs", "admitted_refs", "allowed_references"):
            values = source.get(key)
            if isinstance(values, str):
                values = (values,)
            if isinstance(values, Sequence):
                references.update(value for value in values if isinstance(value, str))
    return frozenset(references)


def _context_mapping(context: object) -> dict[str, object]:
    dump = getattr(context, "model_dump", None)
    if callable(dump):
        try:
            value = dump(mode="python")
        except TypeError:
            value = dump()
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
    if isinstance(context, Mapping):
        return {str(key): item for key, item in context.items()}
    return {}


def _validate_provider_session(session: object) -> None:
    """Reject a transport that would lose current-turn callbacks before start."""

    _validate_no_argument_method(session, "start", label="provider session")
    _validate_no_argument_method(session, "stop", label="provider session")
    _provider_prompt_method(session, validate=True)


def _provider_prompt_method(
    session: object, *, validate: bool = False
) -> Callable[..., object]:
    """Return the canonical prompt method or a fully-compatible named legacy one."""

    method = getattr(session, "prompt_and_wait", None)
    if not callable(method):
        method = getattr(session, "prompt", None)
    if not callable(method):
        raise ApplicationConfigurationError("provider session cannot process a question")
    if validate:
        _validate_prompt_callable(method)
    return method


def _validate_prompt_callable(method: Callable[..., object]) -> None:
    signature = _runtime_signature(method, label="provider session prompt")
    try:
        signature.bind(
            "question",
            **{name: None for name in _PROVIDER_PROMPT_KEYWORDS},
        )
    except TypeError as exc:
        raise ApplicationConfigurationError(
            "provider session prompt must accept question, projection callback, "
            "correlation id, and heartbeat callback"
        ) from exc


def _validate_no_argument_method(target: object, name: str, *, label: str) -> None:
    method = getattr(target, name, None)
    if not callable(method):
        raise ApplicationConfigurationError(f"{label} method {name!r} is unavailable")
    signature = _runtime_signature(method, label=f"{label} method {name!r}")
    try:
        signature.bind()
    except TypeError as exc:
        raise ApplicationConfigurationError(
            f"{label} method {name!r} must not require arguments"
        ) from exc


def _validate_keyword_callable(
    factory: object,
    *,
    label: str,
    names: tuple[str, ...],
) -> None:
    if not callable(factory):
        raise ApplicationConfigurationError(f"{label} is unavailable")
    signature = _runtime_signature(factory, label=label)
    try:
        signature.bind(**{name: None for name in names})
    except TypeError as exc:
        raise ApplicationConfigurationError(
            f"{label} must accept required keyword inputs: {', '.join(names)}"
        ) from exc


def _runtime_signature(
    callable_object: Callable[..., object], *, label: str
) -> inspect.Signature:
    try:
        return inspect.signature(callable_object)
    except (TypeError, ValueError) as exc:
        raise ApplicationConfigurationError(
            f"{label} signature is unavailable for preflight"
        ) from exc


def _call_prompt(
    transport: object,
    question: str,
    *,
    projector: object | None,
    turn_id: str | None,
    response_mode: Literal["text", "answer_bundle"] = "text",
    semantic_event_observer: Callable[[Mapping[str, object]], None] | None = None,
) -> tuple[str | AnswerBundle, tuple[Any, ...]]:
    method = _provider_prompt_method(transport)
    projections: list[Any] = []
    callback = getattr(projector, "observe", None) if projector is not None else None

    def on_event(
        event: Mapping[str, object],
        sequence: int | None = None,
        **event_kwargs: object,
    ) -> None:
        if callable(callback) and turn_id is not None:
            outcome = callback(
                event,
                turn_id=turn_id,
                trace_sequence=sequence,
                **event_kwargs,
            )
            if outcome is not None:
                projections.append(outcome)
        if semantic_event_observer is not None:
            _observe_nonblocking(semantic_event_observer, event)

    def on_heartbeat() -> None:
        if semantic_event_observer is not None:
            _observe_nonblocking(
                semantic_event_observer,
                {"type": "application_waiting"},
            )

    prompt = question
    if response_mode == "answer_bundle":
        prompt = f"{question}\n\n{ANSWER_BUNDLE_INSTRUCTION}"
    answer = method(
        prompt,
        on_semantic_event=on_event,
        correlation_id=turn_id,
        on_heartbeat=on_heartbeat,
    )
    if not isinstance(answer, str):
        raise ApplicationConfigurationError("provider transport returned non-text answer")
    return (
        parse_answer_bundle(answer) if response_mode == "answer_bundle" else answer,
        tuple(projections),
    )


def _observe_nonblocking(
    observer: Callable[[Mapping[str, object]], None], event: Mapping[str, object]
) -> None:
    try:
        observer(event)
    except Exception:
        _diagnostic_stderr("progress_observer_unavailable", "run")


def _diagnostic_stderr(code: str, run_id: str) -> None:
    try:
        print(f"application diagnostic: {code} run={run_id}", file=sys.stderr)
    except Exception:
        pass


@dataclass(frozen=True, slots=True)
class _ReportArtifactPathPolicy:
    """Bind the generic report artifact to the published report path."""

    def candidate_paths(
        self, run_root: Path, kind: str, identity: str
    ) -> tuple[Path, ...]:
        if kind != "report" or identity != "report":
            raise ArtifactIntegrityError("report artifact identity is invalid")
        return (run_root / "output" / "report.md",)

    def identity_for_path(self, kind: str, relative_path: PurePosixPath) -> str:
        if kind == "report" and relative_path == PurePosixPath("output/report.md"):
            return "report"
        raise ArtifactIntegrityError("report artifact path is invalid")


@dataclass(frozen=True, slots=True)
class _ReportAwareDomainContext:
    """Expose generic report admission alongside an opaque domain context."""

    base: object | None
    report_artifact_ref: str

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        del mode
        values: dict[str, object] = {}
        if self.base is not None:
            dump = getattr(self.base, "model_dump", None)
            if callable(dump):
                try:
                    candidate = dump(mode="python")
                except TypeError:
                    candidate = dump()
                if isinstance(candidate, Mapping):
                    values.update({str(key): value for key, value in candidate.items()})
            elif isinstance(self.base, Mapping):
                values.update({str(key): value for key, value in self.base.items()})
        values["report_artifact_ref"] = self.report_artifact_ref
        values["admitted_artifact_refs"] = (self.report_artifact_ref,)
        return values


def _with_report_reference(
    context: object | None, report_ref: str
) -> _ReportAwareDomainContext:
    return _ReportAwareDomainContext(context, report_ref)


def _persisted_answer_assurances(
    answers: tuple[FinalizedTurn, ...], workspace: ApplicationWorkspace
) -> tuple[str, ...]:
    """Use the verified ledger once, then bind every display to its event."""
    try:
        _state, events = ApplicationContextStore.replay_events(workspace)
    except Exception:
        return tuple("corrupt" for _ in answers)
    declared: dict[tuple[str, str, str, str], int] = {}
    try:
        for event in events:
            if event.event_type != "answer.submitted":
                continue
            payload = event.payload
            turn_id = event.turn_id
            if not isinstance(payload, dict) or not isinstance(turn_id, str):
                continue
            answer_ref = payload.get("answer_ref")
            answer_path = payload.get("answer_path")
            admission_ref = payload.get("admission_ref")
            if not (
                isinstance(answer_ref, str) and answer_ref
                and isinstance(answer_path, str) and answer_path
                and isinstance(admission_ref, str) and admission_ref
            ):
                continue
            key = (turn_id, answer_ref, answer_path, admission_ref)
            declared[key] = declared.get(key, 0) + 1
    except (UnicodeDecodeError, json.JSONDecodeError):
        return tuple("corrupt" for _ in answers)
    return tuple(_persisted_answer_assurance(answer, workspace, declared) for answer in answers)


def _persisted_answer_assurance(
    answer: FinalizedTurn,
    workspace: ApplicationWorkspace,
    declared: Mapping[tuple[str, str, str, str], int],
) -> str:
    path = answer.answer_path
    answer_ref = answer.answer_ref
    admission_ref = answer.admission_ref
    turn_id = answer.turn_id
    if not (
        isinstance(answer_ref, str) and answer_ref
        and isinstance(admission_ref, str) and admission_ref
        and isinstance(turn_id, str) and turn_id
        and isinstance(path, Path)
    ):
        return "unknown"
    try:
        relative_path = str(path.relative_to(workspace.root))
    except ValueError:
        return "unknown"
    if declared.get((turn_id, answer_ref, relative_path, admission_ref)) != 1:
        return "unknown"
    try:
        decision = read_answer_admission_metadata(
            path, expected_admission_ref=admission_ref
        )
    except ValueError:
        return "corrupt"
    if decision is not None and decision.assurance == "guide_access_verified":
        return "guide_access_verified — published guide access verified; answer semantics and numerical claims are not verified"
    return decision.assurance if decision is not None else "unknown"


def _write_report_atomically(path: Path, report: str) -> None:
    write_report_atomically(path, report)


__all__ = [
    "AgentApplication",
    "ApplicationOutcome",
    "ApplicationRequest",
    "ProviderSession",
]
