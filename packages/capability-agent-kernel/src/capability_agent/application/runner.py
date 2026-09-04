"""Ordered, domain-neutral application execution."""

from __future__ import annotations

import copy
import hashlib
import inspect
import os
import stat
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Literal, cast

from capability_agent.application.composition import (
    PreparedApplication,
    prepare_application,
)
from capability_agent.application.context_store import ApplicationContextStore
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
from capability_agent.application.profile import ApplicationProfile
from capability_agent.application.projector import ApplicationInvocationProjector
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.turns import TurnController
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.runtime.catalog import ProviderCatalog, ProviderCatalogSource
from capability_agent.runtime.descriptor import descriptor_from_endpoint, write_runtime_descriptor
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
    ArtifactIntegrityError,
    ImmutableArtifactRegistry,
)


ApplicationStatus = Literal["completed", "failed"]


@dataclass(frozen=True, slots=True)
class ApplicationRequest:
    application_id: str
    questions: tuple[str, ...]
    run_id: str | None = None

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

    @property
    def output(self) -> object | None:
        return self.rendered


class ProviderSession:
    """Structural marker for injected provider transports."""


@dataclass(frozen=True, slots=True)
class _RunnerBindings:
    prepared: PreparedApplication | object
    bindings: Mapping[str, object]


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
        prepared_application: PreparedApplication | object | None = None,
        provider_catalog: ProviderCatalogSource | ProviderCatalog | object | None = None,
        provider_factory: Callable[..., object] | None = None,
        transport_factory: Callable[..., object] | None = None,
        provider: object | None = None,
        workspace_root: Path | None = None,
        workspace: ApplicationWorkspace | None = None,
        registry: object | None = None,
        credentials: object | None = None,
        store: ApplicationContextStore | None = None,
        turn_controller: object | None = None,
        projector: ApplicationInvocationProjector | object | None = None,
        catalog: CompositeToolCatalog | object | None = None,
        output_composer: FrameworkOutputComposer | None = None,
        output_renderer: object | None = None,
        report_shell: object | None = None,
        domain_output_builder: Callable[..., ValidatedDomainOutput] | None = None,
        binding_identities: Sequence[BindingIdentity] | None = None,
        lifecycle_hooks: Mapping[str, Callable[[], object]] | None = None,
        application_preparer: Callable[..., object] | None = None,
        cli_options: CliLLMOptions | None = None,
        environment: Mapping[str, str] | None = None,
        runtime_host: RuntimeHost | None = None,
        runtime_paths: RuntimePaths | None = None,
        semantic_event_observer: Callable[[Mapping[str, object]], None] | None = None,
    ) -> None:
        self.profile = profile
        self.prepared_application = prepared_application
        self.provider_catalog = provider_catalog
        self.provider_factory = provider_factory or transport_factory
        self.provider = provider
        self.workspace_root = Path(workspace_root) if workspace_root is not None else None
        self.workspace = workspace
        self.registry = registry
        self.credentials = credentials
        self.store = store
        self.turn_controller = turn_controller
        self.projector = projector
        self.catalog = catalog
        self.output_composer = output_composer or FrameworkOutputComposer()
        self.output_renderer = (
            output_renderer
            or getattr(profile, "output_renderer", None)
            or JsonOutputRenderer()
        )
        self.report_shell = report_shell or getattr(profile, "report_shell", None) or GenericReportShell()
        self.domain_output_builder = domain_output_builder
        self.binding_identities = tuple(binding_identities or ())
        self.lifecycle_hooks = dict(lifecycle_hooks or {})
        self.application_preparer = application_preparer
        self.cli_options = cli_options or CliLLMOptions()
        self.environment = None if environment is None else dict(environment)
        self.runtime_host = runtime_host
        self.runtime_paths = runtime_paths
        self.semantic_event_observer = semantic_event_observer
        self._prepared_for_run = False

    def run(self, request: ApplicationRequest) -> ApplicationOutcome:
        self._validate_request(request)
        prepared: object | None = None
        transport: object | None = self.provider
        completed_answers: list[object] = []
        report_path: Path | None = None
        transport_ready = False
        failure: str | None = None
        workspace = self.workspace
        store = self.store
        controller: object | None = self.turn_controller
        projector: object | None = self.projector
        active_turn: object | None = None
        try:
            self._hook("registration")
            prepared = self._prepare(request)
            self._hook("provisioning")
            bindings = _prepared_bindings(prepared)
            workspace = self._ensure_workspace(request, bindings)
            self._prepare_application_output(request=request, workspace=workspace)
            store = self._ensure_store(request, workspace, bindings)
            controller = self._ensure_controller(store, workspace, bindings)
            catalog = self._validate_before_provider(prepared, bindings)
            self._hook("catalog_validation")
            projector = self._ensure_projector(store, catalog, bindings)
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
            transport_ready = True
            _call_method(transport, "start")
            for ordinal, question in enumerate(request.questions, start=1):
                handle = _call_method(controller, "start", ordinal, question)
                active_turn = handle
                turn_started = time.monotonic()
                try:
                    answer, projections = _call_prompt(
                        transport,
                        question,
                        projector=projector,
                        turn_id=getattr(handle, "turn_id", None),
                        semantic_event_observer=self.semantic_event_observer,
                    )
                    finalized = _call_method(
                        controller,
                        "submit",
                        handle,
                        answer_output=answer,
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
                if getattr(finalized, "status", "success") != "success":
                    raise ApplicationConfigurationError("question did not produce an accepted answer")
                self._write_report_checkpoint(
                    request=request,
                    workspace=workspace,
                    store=store,
                    completed_answers=tuple(completed_answers),
                    prepared=prepared,
                )
                self._observe_semantic_event(
                    {
                        "type": "application_turn_completed",
                        "ordinal": ordinal,
                        "total_questions": len(request.questions),
                        "answer_output": str(getattr(finalized, "answer_output", "")),
                    }
                )
            preliminary_core = self._build_core_result(
                request=request,
                workspace=workspace,
                completed_answers=tuple(completed_answers),
                report_ref=None,
            )
            report_path, report_ref = self._write_report(
                request=request,
                workspace=workspace,
                store=store,
                core=preliminary_core,
                completed_answers=tuple(completed_answers),
                prepared=prepared,
            )
            self._record_report_reference(store, report_ref)
            result = self._build_result(
                request=request,
                workspace=workspace,
                store=store,
                bindings=bindings,
                controller=controller,
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
                            getattr(active_turn, "started_monotonic", time.monotonic())
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

    def _prepare(self, request: ApplicationRequest) -> object:
        if self.prepared_application is not None:
            return self.prepared_application
        if self.application_preparer is not None:
            return _call_factory(
                self.application_preparer,
                profile=self.profile,
                request=request,
                workspace=self.workspace,
                registry=self.registry,
                credentials=self.credentials,
            )
        if self.registry is None or self.credentials is None or self.workspace is None:
            raise ApplicationConfigurationError("prepared application inputs are incomplete")
        return prepare_application(
            self.profile,
            registry=cast(Any, self.registry),
            workspace=self.workspace.root,
            credentials=cast(Any, self.credentials),
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
        method = getattr(self.report_shell, "prepare", None)
        if callable(method):
            _call_factory(method, questions=request.questions, workspace=workspace)

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
    ) -> object:
        if self.turn_controller is not None:
            return self.turn_controller
        if store is None or workspace is None:
            raise ApplicationConfigurationError("turn controller is not configured")
        return TurnController(
            store=store,
            workspace=workspace,
            bindings=bindings,
        )

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

    def _validate_before_provider(
        self, prepared: object, bindings: Mapping[str, object]
    ) -> object | None:
        _call_method(getattr(self.profile, "application_policy", None), "load")
        for binding_id in sorted(bindings):
            binding = bindings[binding_id]
            profile = _binding_profile(binding)
            if profile is not None:
                _call_method(getattr(profile, "policy_provider", None), "load")
                try:
                    _call_method(profile, "validate_answer_admission_declaration")
                except Exception as exc:
                    raise ApplicationConfigurationError(
                        f"binding {binding_id!r} answer admission declaration is invalid"
                    ) from exc
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
                BoundDomainCatalog.from_prepared(bindings[binding_id])
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
        prepared: object,
        bindings: Mapping[str, object],
        catalog: object | None,
        workspace: ApplicationWorkspace | None,
        controller: object,
    ) -> object | None:
        if self.provider is not None:
            return self.provider
        if self.provider_factory is not None:
            return _call_factory(
                self.provider_factory,
                request=request,
                profile=self.profile,
                prepared_application=prepared,
                bindings=bindings,
                catalog=catalog,
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
        return self._default_pi_transport(
            resolved,
            prepared,
            bindings,
            request=request,
            workspace=workspace,
            controller=controller,
        )

    def _default_pi_transport(
        self,
        resolved: ResolvedLLM,
        prepared: object,
        bindings: Mapping[str, object],
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace,
        controller: object,
    ) -> PiRpcClient:
        if self.runtime_paths is None:
            if self.runtime_host is None:
                raise ApplicationConfigurationError(
                    "default Pi transport requires an injected runtime host"
                )
            if len(bindings) != 1:
                raise ApplicationConfigurationError("default Pi transport requires one prepared binding")
            binding_id = next(iter(bindings))
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
            guide_root_path = _runtime_path(runtime, "guide_root_path")
            guide_index_sha256 = _runtime_file_digest(guide_index_path)
            runtime_dir = workspace.domain_runtime_path(binding_id)
            descriptor_path = runtime_dir / "runtime-descriptor.json"
            descriptor = descriptor_from_endpoint(
                binding_id=binding_id,
                workspace=workspace.domain_path(binding_id),
                application_workspace_path=workspace.root,
                endpoint=endpoint,
                protocol=getattr(manifest, "protocol", ""),
                protocol_version=getattr(manifest, "protocol_version", ""),
                authority_id=getattr(getattr(runtime, "authority", None), "authority_id", ""),
                tool_catalog_path=tool_catalog_path,
                guide_index_path=guide_index_path,
                guide_root_path=guide_root_path,
                tool_name_prefix=getattr(manifest, "tool_name_prefix", None),
                guide_index_sha256=guide_index_sha256,
                application_id=request.application_id,
                run_id=workspace.run_id,
                active_turn_path=_runtime_channel_path(
                    controller,
                    "active_turn_path",
                    default=workspace.turns_path / "active-turn.json",
                ),
                context_view_path=_runtime_channel_path(
                    controller,
                    "context_view_path",
                    default=workspace.context_snapshot_path,
                ),
                trajectory_requests_path=_runtime_channel_path(
                    controller, "trajectory_requests_path"
                ),
                trajectory_capture_state_path=_runtime_channel_path(
                    controller, "trajectory_capture_state_path"
                ),
                trajectory_allowed_refs_path=_runtime_channel_path(
                    controller, "trajectory_allowed_refs_path"
                ),
                trajectory_acks_path=_runtime_channel_path(
                    controller, "trajectory_acks_path"
                ),
            )
            write_runtime_descriptor(descriptor_path, descriptor)
            host = self.runtime_host
            self.runtime_paths = RuntimePaths(
                command=host.command,
                project_pi_dir=host.project_pi_dir,
                session_dir=runtime_dir / "session",
                workspace=workspace.root,
                domain_search_paths=tuple(Path(path) for path in descriptor.search_path),
                extension_path=host.extension_path,
                tool_catalog_path=tool_catalog_path,
                guide_index_path=guide_index_path,
                system_policy_path=host.system_policy_path,
                runtime_descriptor_path=descriptor_path,
                binding_id=binding_id,
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
        controller: object,
        completed_answers: tuple[object, ...],
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
        completed_answers: tuple[object, ...],
        report_ref: str | None,
    ) -> CoreRunResult:
        answer_refs = tuple(
            ref
            for answer in completed_answers
            for ref in (_optional_text(getattr(answer, "answer_ref", None)),)
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
            diagnostic_refs=(),
        )

    def _build_domain_output(
        self,
        binding_id: str,
        binding: object | None,
        store: ApplicationContextStore | None,
        completed_answers: tuple[object, ...],
        *,
        report_ref: str | None,
    ) -> ValidatedDomainOutput:
        context = store.snapshot if store is not None else None
        if report_ref is not None:
            context = _with_report_reference(context, report_ref)
        if self.domain_output_builder is not None:
            return _call_factory(
                self.domain_output_builder,
                binding_id=binding_id,
                binding=binding,
                context=context,
                committed_answers=completed_answers,
                report_ref=report_ref,
            )
        profile = getattr(binding, "profile", None)
        profile = profile or getattr(getattr(binding, "binding", None), "profile", None)
        contract = getattr(profile, "output_contract", None)
        if contract is None:
            raise ApplicationConfigurationError("domain output contract is not configured")
        context = None
        if store is not None:
            state = store.snapshot.domains[binding_id].state
            adapter = getattr(profile, "state_adapter", None)
            if adapter is not None:
                context = _call_factory(adapter.build_context, binding_id=binding_id, state=state)
        if report_ref is not None:
            context = _with_report_reference(context, report_ref)
        payload = _call_factory(
            contract.build,
            binding_id=binding_id,
            context=context,
            committed_answers=completed_answers,
        )
        if not isinstance(payload, Mapping):
            raise ApplicationConfigurationError("domain output contract returned a non-object")
        _validate_domain_output(contract, payload, context)
        return ValidatedDomainOutput(
            schema=getattr(contract, "schema_id"),
            status="completed",
            payload=payload,
        )

    def _failed_result(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        bindings: Mapping[str, object],
        completed_answers: tuple[object, ...],
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
                for ref in (_optional_text(getattr(answer, "answer_ref", None)),)
                if ref
            ),
            report_ref=None,
            diagnostic_refs=(),
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
        completed_answers: tuple[object, ...],
        prepared: object | None = None,
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

    def _write_report_checkpoint(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace | None,
        store: ApplicationContextStore | None,
        completed_answers: tuple[object, ...],
        prepared: object | None = None,
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
            observer(event)

    def _render_report(
        self,
        *,
        request: ApplicationRequest,
        workspace: ApplicationWorkspace,
        store: ApplicationContextStore | None,
        core: CoreRunResult,
        completed_answers: tuple[object, ...],
        prepared: object | None = None,
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
        answers = tuple(str(getattr(answer, "answer_output", "")) for answer in completed_answers)
        references = tuple(
            ref
            for answer in completed_answers
            for ref in getattr(answer, "result_refs", ())
        )
        report_method = getattr(self.report_shell, "render", None)
        if not callable(report_method):
            report_method = GenericReportShell().render
        report = _call_factory(
            report_method,
            questions=request.questions,
            answers=answers,
            trajectories=(),
            references=references,
            context=store.snapshot if store is not None else None,
            presentation=presentation,
            core=core.model_dump(mode="json"),
            domains={},
            workspace=workspace,
            runtime={
                "provider": self.cli_options.provider,
                "model": self.cli_options.model,
            },
        )
        if not isinstance(report, str):
            raise PresentationError("report shell must return text")
        return report

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

    def _cleanup(self, prepared: object | None) -> None:
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
        controller: object | None,
        handle: object,
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
            _call_method(
                controller,
                "fail",
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


def _prepared_bindings(prepared: object | None) -> Mapping[str, object]:
    if prepared is None:
        return {}
    bindings = getattr(prepared, "bindings", None)
    if not isinstance(bindings, Mapping):
        raise ApplicationConfigurationError("prepared application bindings are invalid")
    return bindings


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


def _runtime_channel_path(
    controller: object, name: str, *, default: Path | None = None
) -> Path | None:
    value = getattr(controller, name, None)
    if value is None:
        return default
    if not isinstance(value, Path):
        raise ApplicationConfigurationError(
            f"runtime channel {name!r} must be a path"
        )
    return value


def _safe_failure(error: BaseException) -> str:
    if isinstance(error, CapabilityAgentError):
        return f"{type(error).__name__}: application execution failed"
    return f"{type(error).__name__}: application execution failed"


def _domain_output_schema(
    binding: object | None, identity: BindingIdentity
) -> tuple[str, tuple[Any, ...]]:
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
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(*args, **kwargs)
    parameters = signature.parameters
    accepts_kwargs = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    if accepts_kwargs:
        return factory(*args, **kwargs)
    accepted = {
        key: value
        for key, value in kwargs.items()
        if key in parameters
        and parameters[key].kind
        in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    }
    return factory(*args, **accepted)


def _validate_domain_output(
    contract: object,
    payload: Mapping[str, object],
    context: object | None,
) -> None:
    """Validate a domain payload against the same run-scoped context.

    Most domain contracts expose the historical ``validate(payload)`` method,
    while a context-aware contract may opt into ``validate_with_context``.  A
    few existing contracts also expose ``allowed_references`` as a constructor
    option.  For those contracts, validate through a shallow run-local copy so
    the admitted references are available without mutating a profile shared by
    another run.
    """

    context_validator = getattr(contract, "validate_with_context", None)
    if callable(context_validator):
        _call_factory(context_validator, payload, context=context)
        return
    validator = getattr(contract, "validate", None)
    if not callable(validator):
        raise ApplicationConfigurationError("domain output contract validator is unavailable")

    scoped_contract = _scope_output_contract(contract, _context_admitted_references(context))
    _call_factory(getattr(scoped_contract, "validate"), payload, context=context)


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


def _call_prompt(
    transport: object,
    question: str,
    *,
    projector: object | None,
    turn_id: str | None,
    semantic_event_observer: Callable[[Mapping[str, object]], None] | None = None,
) -> str:
    method = getattr(transport, "prompt_and_wait", None)
    if not callable(method):
        method = getattr(transport, "prompt", None)
    if not callable(method):
        raise ApplicationConfigurationError("provider transport cannot process a question")
    kwargs: dict[str, object] = {}
    projections: list[Any] = []
    callback = getattr(projector, "observe", None) if projector is not None else None
    if callable(callback) or semantic_event_observer is not None:
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
                    semantic_event_observer(event)
            kwargs["on_semantic_event"] = on_event
    if turn_id is not None:
        kwargs["correlation_id"] = turn_id
    answer = _call_factory(method, question, **kwargs)
    if not isinstance(answer, str):
        raise ApplicationConfigurationError("provider transport returned non-text answer")
    return answer, tuple(projections)


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


def _write_report_atomically(path: Path, report: str) -> None:
    """Publish a report without following a leaf or parent symlink."""

    target = Path(path)
    parent = target.parent
    _reject_report_symlink_ancestors(parent)
    try:
        if target.is_symlink():
            raise PresentationError("report path must not be a symlink")
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _reject_report_symlink_ancestors(parent)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", dir=parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                descriptor = -1
                stream.write(report)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            directory_fd = os.open(
                parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    except PresentationError:
        raise
    except OSError as exc:
        raise PresentationError("report could not be persisted") from exc


def _reject_report_symlink_ancestors(path: Path) -> None:
    current = Path(path)
    while True:
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            parent = current.parent
            if parent == current:
                return
            current = parent
            continue
        except OSError as exc:
            raise PresentationError("report directory cannot be inspected") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PresentationError("report directory must not contain symlinks")
        if not stat.S_ISDIR(metadata.st_mode):
            raise PresentationError("report directory is not a directory")
        break
    while True:
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise PresentationError("report directory cannot be inspected") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PresentationError("report directory must not contain symlinks")
        parent = current.parent
        if parent == current:
            break
        current = parent


__all__ = [
    "AgentApplication",
    "ApplicationOutcome",
    "ApplicationRequest",
    "ProviderSession",
]
