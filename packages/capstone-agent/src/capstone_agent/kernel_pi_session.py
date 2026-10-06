"""Application-private bridge from prepared Kernel profiles to Harness Pi."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import os
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
from .kernel_reference_handoff import PreparedKernelReferenceHandoffs
from .model_capability_context import PreparedModelCapabilityContext
from .thread_protocol import ModelContextSnapshot
from .thread_service import AttemptClaim, PriorResultReference
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
        environment = os.environ if base_environment is None else base_environment
        self._timeout_seconds = float(environment.get('CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS', '600'))
        if not 1 <= self._timeout_seconds <= 3600:
            raise ValueError('Thread attempt timeout is invalid')

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
        handoffs = PreparedKernelReferenceHandoffs(profiles)
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
                    reference_handoffs_path=handoffs.path,
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
        if profiles:
            system_policy_path = _compose_attempt_policy(
                workspace.core_path / "pi" / "attempts" / claim.attempt.attempt_id,
                self._runtime_host.system_policy_path,
                include_generic=ordinary,
                application_catalog=claim.application_catalog,
                model_context=claim.model_context,
                profiles=profiles,
                prior_results=claim.prior_results,
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
            timeout_seconds=self._timeout_seconds,
        )
        return _KernelPiPromptSession(
            client, trace, admission=_build_kernel_admission(profiles),
            reference_observer=handoffs.observe,
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


def _compose_attempt_policy(
    directory: Path,
    domain_policy: Path | None,
    *,
    include_generic: bool,
    application_catalog: Mapping[str, object] | None,
    model_context: ModelContextSnapshot | None = None,
    profiles: tuple[PreparedKernelApplicationProfile, ...] = (),
    prior_results: tuple[PriorResultReference, ...] = (),
) -> Path:
    """Compose generic, domain, and application catalog guidance for one Attempt."""

    generic = Path(__file__).parent / "resources" / "conversation-policy.md"
    generic_text = generic.read_text(encoding="utf-8") if include_generic else ""
    domain_text = ""
    if domain_policy is not None:
        domain_text = domain_policy.read_text(encoding="utf-8")
    catalog_text = _render_application_catalog_context(application_catalog)
    model_text = _render_attempt_model_context(model_context, profiles, prior_results=prior_results) if model_context is not None else ""
    if len(generic_text) + len(domain_text) + len(catalog_text) + len(model_text) > 128_000:
        raise RuntimeError("combined runtime policy is too large")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / "system-policy.md"
    path.write_text(
        "\n\n".join(item for item in (generic_text, domain_text, catalog_text, model_text) if item),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _render_attempt_model_context(
    context: ModelContextSnapshot,
    profiles: tuple[PreparedKernelApplicationProfile, ...],
    *, prior_results: tuple[PriorResultReference, ...] = (),
) -> str:
    lines = [
        "## Current application-selected model (immutable for this Attempt)",
        f"Model ID: {context.model_id}; family: {context.implementation_family}",
        f"Model revision: {context.model_revision}; model Context: {context.id}",
        "Use this model for follow-up requests, including requests that do not name a model.",
        "Do not open or analyze a different model. Model changes require the application's explicit switch command.",
        "Opening an authority context is not a Thread model switch. Do not report a different model as active.",
    ]
    for profile in profiles:
        binding = profile.model_binding
        lines.append(f"Binding {binding.binding_id}: authority context/model reference {binding.context_ref}")
    if prior_results:
        lines.extend([
            "## Existing results for this exact model Context (newest first)",
            "These references are retrieval candidates, not pre-admitted evidence for this Attempt.",
            "When the request reuses a result, query it through published read capabilities without rerunning the calculation.",
            "Retrieve its supporting evidence through a published evidence capability before citing it in this Attempt.",
        ])
        for item in prior_results:
            lines.append(f"Source {item.capability_id}, Attempt {item.attempt_id}: {item.result_ref}; evidence: {', '.join(item.evidence_refs)}")
    return "\n".join(lines)


def _render_application_catalog_context(
    catalog: Mapping[str, object] | None,
) -> str:
    """Render bounded application metadata without exposing Authority internals."""

    if catalog is None:
        return ""
    models = catalog.get("models")
    if not isinstance(models, list):
        return ""
    lines = [
        "## Capstone registered model catalog (application-owned metadata)",
        "Use this bounded catalog for model availability questions. It covers all registered implementation families, not only the active Domain Pack.",
        "Do not claim that another family has no models merely because the current model uses a different family. To execute work on another family, the user must select or switch to that model first.",
        "Current tool scope does not determine application-wide availability. Domain tools expose the current binding; their model list or context.open limits do not make other registered models unavailable. Model selection and switching belong to the application, through its model control or an opening instruction.",
        "Do not apply the active binding's unsupported-operation or policy limits to another family. A model catalog lists models, not feature support. Do not add claims that another family's capabilities are absent or unsupported without that family's registered capability contracts.",
        "Only an explicit worker-unavailable catalog entry supports an unavailable-worker claim. If no worker health is supplied, do not infer it from the active model or its tools. Describe the required model switch instead of saying the other family cannot run.",
    ]
    default_model = catalog.get("default_model_id")
    if isinstance(default_model, str) and default_model:
        lines.append(f"Default model: {default_model}")
    lines.append("Registered models:")
    for item in models[:128]:
        if not isinstance(item, Mapping):
            continue
        model_id = item.get("model_id")
        display_name = item.get("display_name")
        family = item.get("implementation_family")
        if not all(isinstance(value, str) and value.strip() for value in (model_id, display_name, family)):
            continue
        availability = "registered"
        if item.get("available") is False:
            availability = "worker unavailable"
        lines.append(f"- {display_name} ({model_id}) · family={family} · {availability}")
    return "\n".join(lines)


class _RpcWorkspace:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path


class _KernelPiPromptSession:
    def __init__(self, client: PiRpcClient, trace: JsonlTraceWriter, *, admission,
                 reference_observer: Callable[[Mapping[str, object]], None] | None = None) -> None:
        self._client = client
        self._trace = trace
        self._admission = admission
        self._reference_observer = reference_observer

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
        def observed(event, _sequence):
            if self._reference_observer is not None:
                self._reference_observer(event)
            on_semantic_event(event)

        return self._client.prompt_and_wait(
            question,
            on_semantic_event=observed,
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
        guide_names = {
            f"{namespace}guide_open"
            for binding in binding_map.values()
            if isinstance(namespace := getattr(getattr(binding, "binding", None), "tool_namespace", None), str)
        }
        authority_events = []
        owners: dict[str, str] = {}
        for event in tool_events:
            # Published guide reads have no authority result or evidence. Their
            # names come from the selected binding, not from a model assertion.
            if (event.get("tool_name") in guide_names
                and not event.get("result_refs") and not event.get("evidence_refs")):
                continue
            binding_id = event.get("binding_id")
            if binding_id is None and len(binding_map) == 1:
                binding_id = next(iter(binding_map))
            if not isinstance(binding_id, str) or binding_id not in binding_map:
                raise ValueError("tool provenance has no prepared binding owner")
            authority_events.append({**event, "binding_id": binding_id})
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
        tool_events = tuple(authority_events)
        _verify_bound_attempt_references(profiles, binding_map, owners, result_refs, evidence_refs, tool_events)
        participating = {event["binding_id"] for event in tool_events}
        decisions = []
        for binding_id, binding in binding_map.items():
            # A selected Pack can remain unused in this Turn. Its lack of a
            # result must not downgrade another Pack's verified observation.
            if participating and binding_id not in participating:
                continue
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
                observed_capabilities=tuple(
                    sorted({
                        str(event["capability"])
                        for event in tool_events
                        if event.get("binding_id") == binding_id
                        and isinstance(event.get("capability"), str)
                    })
                ),
                failed_capabilities=tuple(
                    sorted({
                        str(event["capability"])
                        for event in tool_events
                        if event.get("binding_id") == binding_id
                        and event.get("ok") is not True
                        and isinstance(event.get("capability"), str)
                    })
                ),
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


def _verify_bound_attempt_references(
    profiles: tuple[PreparedKernelApplicationProfile, ...],
    bindings: Mapping[str, object],
    owners: Mapping[str, str],
    result_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    tool_events: tuple[Mapping[str, object], ...],
) -> None:
    """Verify authority artifacts against the immutable application binding."""
    for profile in profiles:
        bound = profile.model_binding
        prepared_bindings = getattr(profile.prepared_application, "bindings", None)
        if not isinstance(prepared_bindings, Mapping):
            raise ValueError("prepared authority bindings are unavailable")
        for binding_id in prepared_bindings:
            runtime = getattr(bindings[binding_id], "runtime", None)
            authority = getattr(runtime, "authority", None)
            events = [event for event in tool_events if (
                event.get("binding_id") == binding_id
                or event.get("binding_id") is None and len(bindings) == 1
            )]
            for event in events:
                if event.get("ok") is not True:
                    continue
                for field, expected in (("model_id", bound.model_id), ("model_revision", bound.model_revision),
                                        ("context_ref", bound.context_ref)):
                    if field in event and event[field] != expected:
                        raise ValueError("tool identity does not match the bound model context")
                if "model_ref" in event:
                    model_ref = event["model_ref"]
                    if not isinstance(model_ref, str) or not bound.accepts_model_reference(model_ref):
                        raise ValueError("tool identity does not match the bound model context")
            results = tuple(ref for ref in result_refs if owners.get(ref) == binding_id)
            evidence = tuple(ref for ref in evidence_refs if owners.get(ref) == binding_id)
            verified: set[tuple[str, str]] = set()

            def verify(kind: str, reference: str) -> None:
                key = (kind, reference)
                if key in verified:
                    return
                method = getattr(authority, "verify_" + kind, None)
                if not callable(method):
                    raise ValueError("bound artifact authority verification is unavailable")
                document = getattr(method(reference), "document", None)
                if not isinstance(document, Mapping):
                    raise ValueError("bound authority artifact is invalid")
                for field, expected in (("context_ref", bound.context_ref),
                                        ("revision_ref", bound.model_revision), ("model_revision", bound.model_revision),
                                        ("model_id", bound.model_id)):
                    if field in document and document[field] != expected:
                        raise ValueError("authority artifact does not match the bound model context")
                model_ref = document.get("model_ref")
                accepted_model_ref = isinstance(model_ref, str) and bound.accepts_model_reference(model_ref)
                if "model_ref" in document and not accepted_model_ref:
                    raise ValueError("authority artifact does not match the bound model context")
                linked_result = document.get("result_ref")
                bound_identity = (
                    document.get("context_ref") == bound.context_ref
                    and document.get("revision_ref") == bound.model_revision
                ) if bound.context_ref.startswith("context:") else accepted_model_ref
                linked_evidence = kind == "evidence" and isinstance(linked_result, str)
                if not bound_identity and not linked_evidence:
                    raise ValueError("authority artifact has incomplete bound model identity")
                verified.add(key)
                if kind == "evidence" and isinstance(linked_result, str):
                    verify("result", linked_result)

            for reference in results:
                verify("result", reference)
            for reference in evidence:
                verify("evidence", reference)
            if results or evidence:
                audit = getattr(authority, "audit_answer_references", None)
                if not callable(audit) or audit(evidence, results):
                    raise ValueError("bound authority references are not linked or verified")


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

    if not result_refs:
        return ()
    projections: list[Mapping[str, object]] = []

    def event_refs(event: Mapping[str, object], name: str) -> tuple[str, ...]:
        raw = event.get(name)
        if not isinstance(raw, (list, tuple)):
            return ()
        return tuple(item for item in raw if isinstance(item, str))

    def unavailable_projection(
        *, result_ref: str, evidence_refs_for_result: tuple[str, ...],
        domain_pack_id: str, capability_id: str, implementation_family: str,
        reason: str,
    ) -> Mapping[str, object]:
        raw: dict[str, object] = {
            "schema": "capstone-result-projection/1.0",
            "result_id": "result_projection_unavailable_" + claim.attempt.attempt_id + "_" + result_ref[-16:],
            "result_ref": result_ref,
            "evidence_refs": list(evidence_refs_for_result),
            "thread_id": claim.thread_id,
            "run_id": claim.run_id,
            "turn_id": claim.attempt.turn_id,
            "attempt_id": claim.attempt.attempt_id,
            "model_context_id": claim.model_context.id,
            "model_id": claim.model_context.model_id,
            "model_revision": claim.model_context.model_revision,
            "source": {
                "capability_id": capability_id,
                "domain_pack_id": domain_pack_id,
                "implementation_family": implementation_family,
            },
            "status": "unavailable",
            "summary": [], "tables": [], "element_refs": [], "overlay": None,
            "unavailable_reason": reason,
        }
        return normalize_result_projection(
            raw,
            admitted_refs=tuple((*result_refs, *evidence_refs_for_result)),
            expected_model_revision=claim.model_context.model_revision,
        )

    owners: dict[str, str] = {}
    result_evidence: dict[str, tuple[str, ...]] = {}
    sole_binding = next(iter(bindings), None) if len(bindings) == 1 else None
    for event in tool_events:
        binding_id = event.get("binding_id")
        if binding_id is None:
            binding_id = sole_binding
        if not isinstance(binding_id, str) or binding_id not in bindings:
            continue
        event_results = event_refs(event, "result_refs")
        event_evidence = event_refs(event, "evidence_refs")
        for reference in (*event_results, *event_evidence):
            previous = owners.setdefault(reference, binding_id)
            if previous != binding_id:
                raise ValueError("runtime reference has conflicting binding owners")
    # A view can return an existing result without producing new evidence.
    # Use only verified artifact links. An aggregate can explicitly cite
    # scenario evidence whose own result link names an unselected child.
    admitted_results = set(result_refs)
    declared_evidence: dict[str, set[str]] = {}
    for result_ref in dict.fromkeys(result_refs):
        binding_id = owners.get(result_ref)
        if binding_id is None or binding_id not in bindings:
            raise ValueError("projection result has no prepared binding owner")
        runtime = getattr(bindings[binding_id], "runtime", None)
        authority = getattr(runtime, "authority", None)
        verify_result = getattr(authority, "verify_result", None)
        if not callable(verify_result):
            raise ValueError("projection result authority verification is unavailable")
        document = getattr(verify_result(result_ref), "document", None)
        if not isinstance(document, Mapping):
            raise ValueError("projection result artifact is invalid")
        references = document.get("evidence_refs")
        declared_evidence[result_ref] = {
            reference for reference in references if isinstance(reference, str)
        } if isinstance(references, (list, tuple)) else set()
    for evidence_ref in dict.fromkeys(evidence_refs):
        binding_id = owners.get(evidence_ref)
        if binding_id is None or binding_id not in bindings:
            raise ValueError("projection evidence has no prepared binding owner")
        runtime = getattr(bindings[binding_id], "runtime", None)
        authority = getattr(runtime, "authority", None)
        verify_evidence = getattr(authority, "verify_evidence", None)
        if not callable(verify_evidence):
            raise ValueError("projection evidence authority verification is unavailable")
        document = getattr(verify_evidence(evidence_ref), "document", None)
        if not isinstance(document, Mapping):
            raise ValueError("projection evidence artifact is invalid")
        linked_result = document.get("result_ref")
        if linked_result is not None and not isinstance(linked_result, str):
            raise ValueError("projection evidence result binding is invalid")
        associated_results = {
            result_ref for result_ref, references in declared_evidence.items()
            if evidence_ref in references
        }
        if isinstance(linked_result, str) and linked_result in admitted_results:
            associated_results.add(linked_result)
        for result_ref in associated_results:
            if owners.get(result_ref) != binding_id:
                raise ValueError("projection evidence result binding is invalid")
            previous_evidence = result_evidence.get(result_ref, ())
            result_evidence[result_ref] = (*previous_evidence, evidence_ref)
        # Standalone facts and evidence for an unselected result stay admitted,
        # but do not acquire a projection association from execution order.

    for profile in profiles:
        prepared_bindings = getattr(profile.prepared_application, "bindings", None)
        if not isinstance(prepared_bindings, Mapping):
            continue
        for binding_id, binding in prepared_bindings.items():
            runtime = getattr(binding, "runtime", None)
            domain_profile = getattr(runtime, "profile", None)
            registry = getattr(domain_profile, "projector_registry", None)
            projector = getattr(registry, "result_projector", None)
            project_admitted = getattr(projector, "project_admitted", None)
            authority = getattr(runtime, "authority", None)
            invoke = getattr(getattr(runtime, "executor", None), "invoke", None)
            context_ref = profile.model_binding.context_ref
            owned_results = tuple(result_ref for result_ref in result_refs if owners.get(result_ref) == binding_id)
            if not owned_results:
                continue
            owned_evidence = {result_ref: result_evidence.get(result_ref, ()) for result_ref in owned_results}
            if not callable(project_admitted):
                # A selected Domain Pack may not have a business projection yet
                # (for example PyPSA during the migration). Keep the result
                # visible as an explicitly unavailable projection rather than
                # silently dropping it or pretending another domain's shape.
                domain_pack_id = str(getattr(domain_profile, "id", binding_id))
                implementation_family = claim.model_context.implementation_family
                capability_id = next(
                    (
                        str(event.get("capability_id"))
                        for event in tool_events
                        if event.get("binding_id", binding_id) == binding_id
                        and isinstance(event.get("capability_id"), str)
                    ),
                    "result.projection",
                )
                for result_ref in owned_results:
                    projections.append(unavailable_projection(
                        result_ref=result_ref,
                        evidence_refs_for_result=owned_evidence.get(result_ref, ()),
                        domain_pack_id=domain_pack_id,
                        capability_id=capability_id,
                        implementation_family=implementation_family,
                        reason="当前 Domain Pack 尚未提供结果展示投影",
                    ))
                continue
            if not callable(invoke):
                raw_projections: object = ()
                projection_error = True
            else:
                try:
                    raw_projections = project_admitted(
                        authority=authority,
                        invoke=invoke,
                        context_ref=context_ref,
                        model_revision=claim.model_context.model_revision,
                        model_context_id=claim.model_context.id,
                        model_id=claim.model_context.model_id,
                        thread_id=claim.thread_id,
                        run_id=claim.run_id,
                        turn_id=claim.attempt.turn_id,
                        attempt_id=claim.attempt.attempt_id,
                        result_refs=owned_results,
                        result_evidence=owned_evidence,
                    )
                    projection_error = False
                except Exception:
                    raw_projections = ()
                    projection_error = True
            domain_pack_id = str(getattr(domain_profile, "id", binding_id))
            implementation_family = claim.model_context.implementation_family
            capability_id = next(
                (
                    str(event.get("capability_id"))
                    for event in tool_events
                    if event.get("binding_id", binding_id) == binding_id
                    and isinstance(event.get("capability_id"), str)
                ),
                "result.projection",
            )
            if projection_error or not isinstance(raw_projections, (list, tuple)):
                for result_ref in owned_results:
                    projections.append(unavailable_projection(
                        result_ref=result_ref,
                        evidence_refs_for_result=owned_evidence.get(result_ref, ()),
                        domain_pack_id=domain_pack_id,
                        capability_id=capability_id,
                        implementation_family=implementation_family,
                        reason="结果展示投影暂不可用",
                    ))
                continue
            seen_results: set[str] = set()
            for raw_projection in raw_projections:
                if not isinstance(raw_projection, Mapping):
                    projection_error = True
                    break
                raw_result_ref = raw_projection.get("result_ref")
                if not isinstance(raw_result_ref, str) or raw_result_ref not in owned_results:
                    projection_error = True
                    break
                seen_results.add(raw_result_ref)
                raw_document = dict(raw_projection)
                raw_diagram_ids = raw_document.pop("_diagram_element_ids", None)
                diagram_ids: list[str] | None = None
                if raw_diagram_ids is not None:
                    if not isinstance(raw_diagram_ids, (list, tuple)) or any(not isinstance(item, str) for item in raw_diagram_ids):
                        projection_error = True
                        break
                    diagram_ids = list(raw_diagram_ids)
                try:
                    normalized = normalize_result_projection(
                        raw_document,
                        admitted_refs=tuple((*owned_results, *owned_evidence.get(raw_result_ref, ()))),
                        diagram_ids=diagram_ids,
                        expected_model_revision=claim.model_context.model_revision,
                    )
                except Exception:
                    projection_error = True
                    break
                if diagram_ids is not None:
                    normalized["_diagram_element_ids"] = diagram_ids
                projections.append(normalized)
            if projection_error or seen_results != set(owned_results):
                projections = [item for item in projections if item.get("result_ref") not in owned_results]
                for result_ref in owned_results:
                    projections.append(unavailable_projection(
                        result_ref=result_ref,
                        evidence_refs_for_result=owned_evidence.get(result_ref, ()),
                        domain_pack_id=domain_pack_id,
                        capability_id=capability_id,
                        implementation_family=implementation_family,
                        reason="结果展示投影暂不可用",
                    ))
    return tuple(projections)


__all__ = [
    "PreparedKernelPiRpcSessionBuilder",
    "PreparedKernelPiSessionFactory",
    "PreparedKernelSessionBuilder",
]
