"""Application-private bridge from prepared Kernel profiles to Harness Pi."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from capability_agent.domain.answer_admission import (
    AnswerAdmissionInput,
    AnswerAdmissionPolicy,
    aggregate_answer_admission,
)
from capability_agent.runtime.descriptor import (
    CompositeRuntimeDescriptor,
    descriptor_from_endpoint,
    write_runtime_descriptor,
)
from capability_agent.runtime.environment import RuntimeHost, RuntimePaths, build_pi_launch
from capability_agent.runtime.models import ResolvedLLM
from capability_agent.runtime.rpc import PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter

from .harness import AdmittedAttemptAnswer, PiPromptSession
from .kernel_capability_preparation import PreparedKernelApplicationProfile
from .model_capability_context import PreparedModelCapabilityContext
from .thread_protocol import ModelContextSnapshot
from .thread_service import AttemptClaim
from .result_projection import normalize_result_projection


PreparedKernelSessionBuilder = Callable[
    [AttemptClaim, PreparedModelCapabilityContext,
     tuple[PreparedKernelApplicationProfile, ...]],
    PiPromptSession,
]


class PreparedKernelPiSessionFactory:
    """Validate prepared Kernel contributions before constructing a Pi session."""

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
    """Materialize a checked runtime descriptor and Pi RPC client."""

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
                descriptor = descriptor_from_endpoint(
                    binding_id=binding_id,
                    workspace=workspace.domain_path(binding_id),
                    application_workspace_path=workspace.root,
                    endpoint=getattr(binding, "endpoint", None),
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
                binding_runtimes.append((binding_id, runtime, getattr(binding, "endpoint", None)))
        binding_ids = [binding_id for binding_id, _, _ in binding_runtimes]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("prepared Kernel profiles contain duplicate binding IDs")
        descriptor_path = workspace.core_path / "pi" / "runtime-descriptor.json"
        descriptor_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = descriptors[0] if len(descriptors) == 1 else CompositeRuntimeDescriptor(tuple(descriptors))
        write_runtime_descriptor(descriptor_path, descriptor)
        search_paths = tuple(
            dict.fromkeys(Path(path) for item in descriptors for path in item.search_path)
        )
        single = len(binding_runtimes) == 1
        single_runtime = binding_runtimes[0][1] if single else None
        ordinary = claim.turn_plan is not None and claim.turn_plan.route == "ordinary"
        system_policy_path = self._runtime_host.system_policy_path
        if ordinary:
            system_policy_path = _compose_conversation_policy(
                workspace.core_path / "pi" / "attempts" / claim.attempt.attempt_id,
                self._runtime_host.system_policy_path,
            )
        paths = RuntimePaths(
            command=self._runtime_host.command,
            project_pi_dir=self._runtime_host.project_pi_dir,
            session_dir=workspace.core_path / "pi" / "attempts" / claim.attempt.attempt_id / "session",
            workspace=workspace.root,
            domain_search_paths=search_paths,
            extension_path=self._runtime_host.extension_path,
            tool_catalog_path=getattr(single_runtime, "tool_catalog_path", None) if single_runtime else None,
            guide_index_path=getattr(single_runtime, "guide_index_path", None) if single_runtime else None,
            system_policy_path=system_policy_path,
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
            client, trace, admission=_build_kernel_admission(profiles),
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


def _compose_conversation_policy(directory: Path, domain_policy: Path | None) -> Path:
    """Keep generic Pi behavior while retaining the selected Domain Pack policy."""

    generic = Path(__file__).parent / "resources" / "conversation-policy.md"
    generic_text = generic.read_text(encoding="utf-8")
    domain_text = ""
    if domain_policy is not None:
        domain_text = domain_policy.read_text(encoding="utf-8")
    if len(generic_text) + len(domain_text) > 128_000:
        raise RuntimeError("combined runtime policy is too large")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / "system-policy.md"
    path.write_text(generic_text + "\n\n" + domain_text, encoding="utf-8")
    path.chmod(0o600)
    return path


class _RpcWorkspace:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path


class _KernelPiPromptSession:
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
        return self._admission(claim, answer, result_refs, evidence_refs, tool_events)

    def stop(self) -> None:
        try:
            self._client.stop()
        finally:
            self._trace.close()


def _build_kernel_admission(profiles: tuple[PreparedKernelApplicationProfile, ...]):
    def admit(claim, answer, result_refs, evidence_refs, tool_events):
        if (claim.turn_plan is not None and claim.turn_plan.route == "ordinary"
            and not result_refs and not evidence_refs and not tool_events):
            return AdmittedAttemptAnswer(answer, "offline_information", "general_knowledge")
        binding_map: dict[str, object] = {}
        for profile in profiles:
            bindings = getattr(profile.prepared_application, "bindings", None)
            if not isinstance(bindings, Mapping):
                raise ValueError("prepared bindings are unavailable")
            for binding_id, binding in bindings.items():
                if binding_id in binding_map:
                    raise ValueError("duplicate prepared binding ID")
                binding_map[binding_id] = binding
        owners: dict[str, str] = {}
        for event in tool_events:
            binding_id = event.get("binding_id")
            if binding_id is None and len(binding_map) == 1:
                binding_id = next(iter(binding_map))
            if not isinstance(binding_id, str) or binding_id not in binding_map:
                raise ValueError("tool provenance has no prepared binding owner")
            for field in ("result_refs", "evidence_refs"):
                refs = event.get(field)
                if not isinstance(refs, (list, tuple)):
                    continue
                for reference in refs:
                    if not isinstance(reference, str) or not reference:
                        continue
                    previous = owners.setdefault(reference, binding_id)
                    if previous != binding_id:
                        raise ValueError("runtime reference has conflicting binding owners")
        if set(result_refs) - set(owners) or set(evidence_refs) - set(owners):
            raise ValueError("admitted reference has no tool provenance owner")
        decisions = []
        for binding_id, binding in binding_map.items():
            runtime = getattr(binding, "runtime", None)
            domain_profile = getattr(runtime, "profile", None)
            create_policy = getattr(domain_profile, "create_answer_admission_policy", None)
            if not callable(create_policy):
                raise ValueError("Domain Pack answer admission policy is unavailable")
            policy = cast(AnswerAdmissionPolicy, create_policy(getattr(runtime, "authority", None)))
            decision = policy.admit(AnswerAdmissionInput(
                question=claim.instruction,
                answer_output=answer,
                result_refs=tuple(ref for ref in result_refs if owners.get(ref) == binding_id),
                evidence_refs=tuple(ref for ref in evidence_refs if owners.get(ref) == binding_id),
                authority_attempted=any(
                    event.get("binding_id", binding_id) == binding_id
                    for event in tool_events
                ),
            ))
            if decision.answer_output != answer:
                raise ValueError("Domain Pack admission changed the answer text")
            allowed = getattr(domain_profile, "answer_admission_capabilities", None)
            if not isinstance(allowed, frozenset) or decision.mode not in allowed:
                raise ValueError("Domain Pack admission mode is not declared")
            decisions.append(decision)
        if not decisions:
            raise ValueError("no prepared Domain Pack admission policy")
        decision = aggregate_answer_admission(tuple(decisions), answer)
        result_projections = _build_result_projections(
            claim, profiles, binding_map, result_refs, evidence_refs, tool_events,
        )
        return AdmittedAttemptAnswer(
            decision.answer_output, decision.mode, decision.assurance,
            tuple(result_refs), tuple(evidence_refs), tuple(decision.diagnostic_codes),
            result_projections=result_projections,
        )
    return admit


def _build_result_projections(
    claim: AttemptClaim,
    profiles: tuple[PreparedKernelApplicationProfile, ...],
    bindings: Mapping[str, object],
    result_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    tool_events: tuple[Mapping[str, object], ...],
) -> tuple[Mapping[str, object], ...]:
    """Ask a selected Domain Pack to project admitted authority results.

    The application owns admission and normalization.  A Domain Pack owns the
    business labels and table semantics; it receives verified documents and a
    bounded diagram, never a raw authority object.
    """

    projections: list[Mapping[str, object]] = []
    owners: dict[str, str] = {}
    sole_binding = next(iter(bindings), None) if len(bindings) == 1 else None
    for event in tool_events:
        binding_id = event.get("binding_id")
        if binding_id is None:
            binding_id = sole_binding
        if not isinstance(binding_id, str) or binding_id not in bindings:
            continue
        for field in ("result_refs", "evidence_refs"):
            refs = event.get(field)
            if not isinstance(refs, (list, tuple)):
                continue
            for reference in refs:
                if not isinstance(reference, str):
                    continue
                previous = owners.setdefault(reference, binding_id)
                if previous != binding_id:
                    raise ValueError("runtime reference has conflicting binding owners")

    for profile in profiles:
        prepared_bindings = getattr(profile.prepared_application, "bindings", None)
        if not isinstance(prepared_bindings, Mapping):
            continue
        for binding_id, binding in prepared_bindings.items():
            runtime = getattr(binding, "runtime", None)
            domain_profile = getattr(runtime, "profile", None)
            registry = getattr(domain_profile, "projector_registry", None)
            projector = getattr(registry, "result_projector", None)
            project = getattr(projector, "project", None)
            if not callable(project):
                continue
            authority = getattr(runtime, "authority", None)
            verify_context = getattr(authority, "verify_context", None)
            verify_result = getattr(authority, "verify_result", None)
            invoke = getattr(getattr(runtime, "executor", None), "invoke", None)
            if not callable(verify_context) or not callable(verify_result) or not callable(invoke):
                raise ValueError("Domain Pack result projection authority is unavailable")
            context_ref = profile.model_binding.context_ref
            context_artifact = verify_context(context_ref)
            context_document = getattr(context_artifact, "document", None)
            if not isinstance(context_document, Mapping):
                raise ValueError("Domain Pack context projection is invalid")
            context_input = {
                **dict(context_document),
                "model_context_id": claim.model_context.id,
                "counts": dict(context_document.get("counts", {}))
                if isinstance(context_document.get("counts"), Mapping) else {},
            }
            diagram = invoke("operator.diagram.get", {"context_ref": context_ref})
            if not isinstance(diagram, Mapping):
                raise ValueError("Domain Pack diagram projection is invalid")
            for result_ref in result_refs:
                if owners.get(result_ref) != binding_id:
                    continue
                artifact = verify_result(result_ref)
                calculation = getattr(artifact, "document", None)
                if not isinstance(calculation, Mapping):
                    raise ValueError("Domain Pack result projection is invalid")
                if "evidence_refs" not in calculation:
                    calculation = {**dict(calculation), "evidence_refs": list(evidence_refs)}
                raw_projection = project(
                    context_input, calculation,
                    thread_id=claim.thread_id, run_id=claim.run_id,
                    turn_id=claim.attempt.turn_id, attempt_id=claim.attempt.attempt_id,
                    admitted_refs=(*result_refs, *evidence_refs), diagram=diagram,
                )
                projections.append(normalize_result_projection(
                    raw_projection,
                    admitted_refs=(*result_refs, *evidence_refs),
                    expected_model_revision=claim.model_context.model_revision,
                ))
    return tuple(projections)


__all__ = [
    "PreparedKernelPiRpcSessionBuilder",
    "PreparedKernelPiSessionFactory",
    "PreparedKernelSessionBuilder",
]
