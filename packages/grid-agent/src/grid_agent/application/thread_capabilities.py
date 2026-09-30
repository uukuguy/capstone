"""Explicit migration registration for the existing pandapower application.

This module is an application composition hook only.  The compatibility CLI
does not call it implicitly; a future Capstone composition root may opt in.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from capstone_agent.harness import AdmittedAttemptAnswer, PiPromptSession
from capstone_agent.kernel_capability_preparation import (
    AuthorityModelBinding,
    KernelApplicationProfilePreparer,
    PreparedKernelApplicationProfile,
)
from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_agent.model_capability_context import (
    ModelCapabilityContextOwner,
    PreparedModelCapabilityContext,
    register_application_profile,
)
from capstone_model_capability_spi import ModelCapabilityDescriptor
from capstone_model_capability_spi import ModelCapabilityRegistry, ModelCapabilitySelection
from capstone_agent.thread_protocol import ModelContextSnapshot
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_service import AttemptClaim
from capability_agent.runtime.descriptor import (
    CompositeRuntimeDescriptor,
    descriptor_from_endpoint,
    write_runtime_descriptor,
)
from capability_agent.runtime.environment import (
    RuntimeHost,
    RuntimePaths,
    build_pi_launch,
)
from capability_agent.runtime.models import ResolvedLLM
from capability_agent.runtime.rpc import PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter
from capability_agent.domain.answer_admission import AnswerAdmissionInput, AnswerAdmissionPolicy

from .profile import build_pandapower_application_profile


PANDAPOWER_PROFILE_DESCRIPTOR = ModelCapabilityDescriptor(
    "pandapower-static-analysis", "1.0.1",
)
PANDAPOWER_PROFILE_INFO = ModelCapabilityProfileInfo(
    descriptor=PANDAPOWER_PROFILE_DESCRIPTOR,
    display_name="Pandapower Static Analysis",
    implementation_families=("pandapower",),
)


PreparedKernelSessionBuilder = Callable[
    [AttemptClaim, PreparedModelCapabilityContext,
     tuple[PreparedKernelApplicationProfile, ...]],
    PiPromptSession,
]


class PreparedKernelPiSessionFactory:
    """Validate prepared Kernel contributions before constructing a Pi session.

    This adapter belongs to the application composition root.  It is the only
    migration layer that knows the legacy Kernel preparation result shape;
    Thread and Harness receive only the returned Pi-compatible session.  The
    builder can materialize the Kernel runtime descriptor and start Pi using
    the selected binding's tool catalog and Authority endpoint.
    """

    def __init__(self, builder: PreparedKernelSessionBuilder) -> None:
        if not callable(builder):
            raise TypeError("builder must be callable")
        self._builder = builder

    def __call__(
        self,
        claim: AttemptClaim,
        context: PreparedModelCapabilityContext,
    ) -> PiPromptSession:
        if not isinstance(claim, AttemptClaim):
            raise TypeError("claim must be an AttemptClaim")
        if not isinstance(context, PreparedModelCapabilityContext):
            raise TypeError("context must be a PreparedModelCapabilityContext")
        if context.model_context != claim.model_context:
            raise ValueError("prepared Kernel context does not match Attempt snapshot")
        prepared = tuple(
            _require_prepared_kernel_profile(contribution, claim.model_context)
            for contribution in context.contributions
        )
        session = self._builder(claim, context, prepared)
        if not callable(getattr(session, "start", None)) or not callable(
            getattr(session, "prompt_and_wait", None)
        ) or not callable(getattr(session, "stop", None)):
            raise TypeError("prepared Kernel session builder returned an invalid session")
        return session


class PreparedKernelPiRpcSessionBuilder:
    """Materialize one checked Kernel runtime descriptor and Pi RPC client."""

    def __init__(
        self,
        *,
        runtime_host: RuntimeHost,
        resolved_llm: ResolvedLLM,
        base_environment: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(runtime_host, RuntimeHost):
            raise TypeError("runtime_host must be a RuntimeHost")
        if not isinstance(resolved_llm, ResolvedLLM):
            raise TypeError("resolved_llm must be a ResolvedLLM")
        if base_environment is not None and any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in base_environment.items()
        ):
            raise TypeError("base_environment must contain text keys and values")
        self._runtime_host = runtime_host
        self._resolved_llm = resolved_llm
        self._base_environment = None if base_environment is None else dict(base_environment)

    def __call__(
        self,
        claim: AttemptClaim,
        context: PreparedModelCapabilityContext,
        profiles: tuple[PreparedKernelApplicationProfile, ...],
    ) -> PiPromptSession:
        del context
        if not profiles:
            raise RuntimeError("Pi RPC session requires a prepared Domain Pack")
        workspace = profiles[0].workspace
        descriptors = []
        binding_runtimes: list[tuple[str, object, object]] = []
        for profile in profiles:
            if profile.workspace.root != workspace.root:
                raise ValueError("prepared Kernel profiles use different workspaces")
            bindings = getattr(profile.prepared_application, "bindings", None)
            if not isinstance(bindings, Mapping):
                raise TypeError("prepared Kernel application bindings are unavailable")
            for binding_id, binding in sorted(bindings.items()):
                runtime = getattr(binding, "runtime", None)
                manifest = getattr(getattr(runtime, "profile", None), "manifest", None)
                if manifest is None:
                    manifest = getattr(
                        getattr(getattr(binding, "binding", None), "profile", None),
                        "manifest", None,
                    )
                if manifest is None:
                    raise RuntimeError("prepared Domain Pack manifest is unavailable")
                tool_catalog_path = getattr(runtime, "tool_catalog_path", None)
                guide_index_path = getattr(runtime, "guide_index_path", None)
                guide_root_path = getattr(runtime, "guide_root_path", None)
                if not all(
                    isinstance(path, Path) and path.is_file()
                    for path in (tool_catalog_path, guide_index_path)
                ):
                    raise RuntimeError("prepared Pi tool resources are unavailable")
                endpoint = getattr(binding, "endpoint", None)
                descriptor = descriptor_from_endpoint(
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
                    guide_root_path=guide_root_path,
                    tool_name_prefix=getattr(manifest, "tool_name_prefix", None),
                    application_id=profile.profile.manifest.application_id,
                    run_id=claim.run_id,
                )
                descriptors.append(descriptor)
                binding_runtimes.append((binding_id, runtime, endpoint))
        binding_ids = [binding_id for binding_id, _, _ in binding_runtimes]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("prepared Kernel profiles contain duplicate binding IDs")
        descriptor_path = workspace.core_path / "pi" / "runtime-descriptor.json"
        descriptor_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = (
            descriptors[0]
            if len(descriptors) == 1
            else CompositeRuntimeDescriptor(tuple(descriptors))
        )
        write_runtime_descriptor(descriptor_path, descriptor)
        search_paths = tuple(
            dict.fromkeys(Path(path) for item in descriptors for path in item.search_path)
        )
        single = len(binding_runtimes) == 1
        single_runtime = binding_runtimes[0][1] if single else None
        paths = RuntimePaths(
            command=self._runtime_host.command,
            project_pi_dir=self._runtime_host.project_pi_dir,
            session_dir=workspace.core_path / "pi" / "session",
            workspace=workspace.root,
            domain_search_paths=search_paths,
            extension_path=self._runtime_host.extension_path,
            tool_catalog_path=(
                getattr(single_runtime, "tool_catalog_path", None)
                if single_runtime is not None else None
            ),
            guide_index_path=(
                getattr(single_runtime, "guide_index_path", None)
                if single_runtime is not None else None
            ),
            system_policy_path=self._runtime_host.system_policy_path,
            runtime_descriptor_path=descriptor_path,
            binding_id=binding_ids[0] if single else None,
            extra_environment=self._runtime_host.extra_environment,
        )
        launch = build_pi_launch(
            self._resolved_llm, paths, base_environment=self._base_environment,
        )
        trace = JsonlTraceWriter(
            workspace.core_path / "pi-events.jsonl",
            secret_values={self._resolved_llm.secret.value}
            if self._resolved_llm.secret is not None else set(),
        )
        client = PiRpcClient(
            launch,
            _RpcWorkspace(workspace.root),
            trace,
            secret_values={self._resolved_llm.secret.value}
            if self._resolved_llm.secret is not None else set(),
            correlation_id=claim.attempt.attempt_id,
        )
        return _KernelPiPromptSession(
            client,
            trace,
            admission=_build_kernel_admission(profiles),
        )


class _RpcWorkspace:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path


class _KernelPiPromptSession:
    """Adapt the Kernel RPC callback shape to the Harness Pi session contract."""

    def __init__(self, client: PiRpcClient, trace: JsonlTraceWriter, *, admission) -> None:
        self._client = client
        self._trace = trace
        self._admission = admission

    @property
    def command(self) -> object:
        return self._client.command

    def start(self) -> None:
        self._client.start()

    def prompt_and_wait(
        self,
        question: str,
        *,
        on_semantic_event: Callable[[Mapping[str, object]], None],
        correlation_id: str | None,
        on_heartbeat: Callable[[], None],
    ) -> str:
        return self._client.prompt_and_wait(
            question,
            on_semantic_event=lambda event, _sequence: on_semantic_event(event),
            correlation_id=correlation_id,
            on_heartbeat=on_heartbeat,
        )

    def admit_attempt(self, claim, answer, result_refs, evidence_refs, tool_events):
        return self._admission(
            claim, answer, result_refs, evidence_refs, tool_events,
        )

    def stop(self) -> None:
        try:
            self._client.stop()
        finally:
            self._trace.close()


def _build_kernel_admission(
    profiles: tuple[PreparedKernelApplicationProfile, ...],
):
    def admit(claim, answer, result_refs, evidence_refs, tool_events):
        decisions = []
        for profile in profiles:
            bindings = getattr(profile.prepared_application, "bindings", None)
            if not isinstance(bindings, Mapping):
                raise ValueError("prepared bindings are unavailable")
            for binding in bindings.values():
                runtime = getattr(binding, "runtime", None)
                domain_profile = getattr(runtime, "profile", None)
                authority = getattr(runtime, "authority", None)
                create_policy = getattr(domain_profile, "create_answer_admission_policy", None)
                if not callable(create_policy):
                    raise ValueError("Domain Pack answer admission policy is unavailable")
                policy = create_policy(authority)
                decision = cast(AnswerAdmissionPolicy, policy).admit(
                    AnswerAdmissionInput(
                        question=claim.instruction,
                        answer_output=answer,
                        result_refs=tuple(result_refs),
                        evidence_refs=tuple(evidence_refs),
                        authority_attempted=bool(tool_events),
                    )
                )
                decisions.append(decision)
        if len(decisions) != 1:
            raise ValueError("multiple Domain Pack admission aggregation is not enabled")
        decision = decisions[0]
        capabilities = getattr(
            getattr(getattr(profiles[0].prepared_application, "bindings", {}).get("grid"), "runtime", None),
            "profile", None,
        )
        allowed = getattr(capabilities, "answer_admission_capabilities", None)
        if not isinstance(allowed, frozenset) or decision.mode not in allowed:
            raise ValueError("Domain Pack admission mode is not declared")
        return AdmittedAttemptAnswer(
            decision.answer_output,
            decision.mode,
            decision.assurance,
            tuple(result_refs),
            tuple(evidence_refs),
            tuple(decision.diagnostic_codes),
        )

    return admit


def build_pandapower_thread_application(
    *,
    default_model_id: str,
    model_resolver: Callable[[str], Mapping[str, object]],
    workspace_root: Path,
    model_binder: Callable[[object, ModelContextSnapshot], AuthorityModelBinding],
    session_builder: PreparedKernelSessionBuilder,
    default_selection: ModelCapabilitySelection | None = None,
    runtime_mode: str = "capstone",
) -> ThreadApplicationAssembly:
    """Build an opt-in Thread assembly for the existing pandapower profile.

    The compatibility application never calls this helper implicitly.  The
    caller supplies the Authority model resolver/binder and the final Pi
    session builder, so credentials, provider selection, and runtime asset
    locations remain application-owned.  An optional family default keeps the
    empty-profile assembly useful for preparation diagnostics.
    """

    if not isinstance(workspace_root, Path):
        raise TypeError("workspace_root must be a Path")
    if default_selection is not None and not isinstance(
        default_selection, ModelCapabilitySelection
    ):
        raise TypeError("default_selection must be a ModelCapabilitySelection")
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    preparer = KernelApplicationProfilePreparer(
        workspace_root=workspace_root, model_binder=model_binder,
    )
    register_pandapower_capability(
        catalog,
        owner,
        prepare_profile=cast(
            Callable[[object, ModelContextSnapshot], object], preparer,
        ),
    )
    if default_selection is not None:
        catalog.set_family_default("pandapower", default_selection)
    registry.seal()
    owner.seal()
    factory = PreparedKernelPiSessionFactory(session_builder)
    return ThreadApplicationAssembly.from_prepared_authority(
        default_model_id=default_model_id,
        model_resolver=model_resolver,
        capability_catalog=catalog,
        capability_context_owner=owner,
        session_factory=factory,
        runtime_mode=runtime_mode,
    )


def _require_prepared_kernel_profile(
    contribution: object, model_context: ModelContextSnapshot,
) -> PreparedKernelApplicationProfile:
    prepared = getattr(contribution, "prepared", None)
    if not isinstance(prepared, PreparedKernelApplicationProfile):
        raise TypeError("Thread capability contribution is not Kernel-prepared")
    if prepared.closed:
        raise RuntimeError("Kernel-prepared profile is already closed")
    if prepared.model_binding.model_id != model_context.model_id:
        raise ValueError("Kernel-prepared model does not match Thread snapshot")
    if prepared.model_binding.model_revision != model_context.model_revision:
        raise ValueError("Kernel-prepared revision does not match Thread snapshot")
    if prepared.model_binding.implementation_family != model_context.implementation_family:
        raise ValueError("Kernel-prepared family does not match Thread snapshot")
    bindings = getattr(prepared.prepared_application, "bindings", None)
    if not isinstance(bindings, Mapping):
        raise TypeError("Kernel-prepared application bindings are unavailable")
    binding = bindings.get(prepared.model_binding.binding_id)
    if binding is None:
        raise ValueError("Kernel-prepared Authority binding is unavailable")
    runtime = getattr(binding, "runtime", None)
    for name in ("tool_catalog_path", "guide_index_path"):
        path = getattr(runtime, name, None)
        if not isinstance(path, Path) or not path.is_file():
            raise RuntimeError(f"Kernel-prepared {name} is unavailable")
    endpoint = getattr(binding, "endpoint", None)
    if not callable(getattr(getattr(endpoint, "executor", None), "invoke", None)):
        raise RuntimeError("Kernel-prepared Authority endpoint is unavailable")
    return prepared


def register_pandapower_capability(
    catalog: CapstoneModelCapabilityCatalog,
    owner: ModelCapabilityContextOwner,
    *,
    prepare_profile: Callable[[object, ModelContextSnapshot], object] | None = None,
) -> None:
    """Register the current trusted profile for an explicit app assembly."""

    register_application_profile(
        owner,
        catalog,
        PANDAPOWER_PROFILE_INFO,
        build_pandapower_application_profile,
        trust_source="grid-agent-migration-assembly",
        prepare_profile=prepare_profile,
    )


__all__ = [
    "PANDAPOWER_PROFILE_DESCRIPTOR",
    "PANDAPOWER_PROFILE_INFO",
    "PreparedKernelPiRpcSessionBuilder",
    "PreparedKernelPiSessionFactory",
    "build_pandapower_thread_application",
    "register_pandapower_capability",
]
