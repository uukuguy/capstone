"""Trusted PyPSA application worker for Capstone sessions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import json
from pathlib import Path
from typing import Any, cast

from capstone_agent.application import EmptyCredentialBroker
from capstone_agent.prompt_hints import build_case_prompt_decorator
from capstone_agent.runtime import build_runtime_host, load_runtime_environment
from capstone_agent.worker import PreparedWorker, read_verified_reference, serve_application
from capability_agent.application.composition import prepare_application
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.reference_handoff import ReferenceHandoffService
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.runtime_protocols import ProviderFactory
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.runtime.models import CliLLMOptions

from pypsa_agent.registry import build_trusted_application_registry
from pypsa_agent.network_story import ProviderTopologyPlanner, build_pypsa_story
from pypsa_agent.network_view import build_pypsa_network_view


ROOT = Path(__file__).resolve().parents[4]
APPLICATION_ID = "pypsa-business-cases"


def _turn_ordinal(turn_id: object) -> int | None:
    if not isinstance(turn_id, str):
        return None
    try:
        return int(turn_id.rsplit("-t", 1)[1])
    except (IndexError, ValueError):
        return None


def _event_ordinal(event: Mapping[str, object]) -> int | None:
    """Resolve a tool event to its turn for scripted and RPC providers."""

    for key in ("turn_id", "correlation_id", "correlationId"):
        ordinal = _turn_ordinal(event.get(key))
        if ordinal is not None:
            return ordinal
    return None


def _write_handoff_index(
    path: Path, run_id: str, handoffs: Mapping[str, Mapping[str, object]],
) -> None:
    document = {
        "schema": "capability-agent-reference-handoffs/1.0",
        "run_id": run_id,
        "handoffs": [dict(value) for value in handoffs.values()],
    }
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class _ExactCaseApplication:
    def __init__(self, application: AgentApplication, instructions: tuple[str, ...]) -> None:
        self.application = application
        self.instructions = instructions

    def run_stream(self, request: ApplicationRequest, instructions: Iterable[str]):
        def checked():
            count = 0
            for instruction in instructions:
                if count >= len(self.instructions) or instruction != self.instructions[count]:
                    raise ValueError("registered PyPSA case instruction changed")
                count += 1
                yield instruction
            if count != len(self.instructions):
                raise ValueError("registered PyPSA case is incomplete")

        return self.application.run_stream(request, checked())


def _prepare(values: Mapping[str, object], observer) -> PreparedWorker:
    if values.get("application_id") != APPLICATION_ID:
        raise ValueError("PyPSA application is not registered")
    run_id = values.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("PyPSA run ID is invalid")
    profile = build_trusted_application_registry().resolve(APPLICATION_ID)
    registry = DomainRegistry()
    for binding in profile.domains:
        manifest = binding.profile.manifest
        registry.register(
            manifest.domain_id, manifest.version,
            lambda selected=binding.profile: selected,
        )
    workspace = ApplicationWorkspace.create(
        ROOT / "runs" / "capstone-agent" / "pypsa", run_id=run_id,
        binding_ids=("source", "operations"),
    )
    prepared = prepare_application(
        profile, registry=registry, workspace=workspace.root,
        credentials=EmptyCredentialBroker(),
    )
    store = ApplicationContextStore.initialize(
        workspace, core={"input": {"application_id": APPLICATION_ID, "questions": []}},
    )
    mode = values.get("mode")
    network_reader: Callable[[int], dict[str, object] | None] | None = None
    if mode == "scripted-demo":
        from validation.pypsa_cases import CaseProvider, load_cases

        case_id = values.get("case_id")
        case = next((item for item in load_cases()
                     if item["id"] == case_id and item["status"] == "runnable"), None)
        if case is None:
            raise ValueError("PyPSA case is not registered")
        handoff = ReferenceHandoffService(profile, workspace, store, prepared.bindings)
        providers: list[CaseProvider] = []
        committed_refs: dict[int, tuple[str, ...]] = {}
        calls_by_ordinal: dict[int, list[dict[str, object]]] = {}

        def observed(event: Mapping[str, object]) -> None:
            if event.get("type") == "tool_result":
                ordinal = _event_ordinal(event)
                result = event.get("result")
                capability = event.get("capability")
                if ordinal is not None and isinstance(capability, str) and isinstance(result, Mapping):
                    calls_by_ordinal.setdefault(ordinal, []).append({
                        "capability": capability, "result": result,
                    })
            if event.get("type") == "application_turn_completed":
                ordinal = event.get("ordinal")
                refs = event.get("result_refs")
                if type(ordinal) is int and isinstance(refs, list):
                    committed_refs[ordinal] = tuple(ref for ref in refs if isinstance(ref, str))
            observer(event)

        def progress(event: dict[str, object]) -> None:
            observer({"type": event.get("event", "progress"),
                      "message": event.get("message", "")})

        def provider_factory(*, request, prepared_application, catalog, **_):
            provider = CaseProvider(
                case, request, prepared_application, catalog, handoff,
                on_progress=progress, demo=True,
            )
            providers.append(provider)
            return provider

        application = AgentApplication(
            profile=profile, prepared_application=prepared,
            workspace=workspace, store=store,
            provider_factory=cast(ProviderFactory, provider_factory),
            semantic_event_observer=observed,
        )
        def completion_projector(context: Any) -> dict[str, object] | None:
            if not providers:
                return None
            provider = providers[0]
            current = provider.results.get("model.derive_series") or provider.results.get("model.open")
            model_ref = current.get("model_ref") if isinstance(current, Mapping) else None
            if not isinstance(model_ref, str):
                return None
            steps = []
            for answer in context.completed_answers:
                ordinal = _turn_ordinal(getattr(answer, "turn_id", None))
                if ordinal is None:
                    continue
                dispatch = None
                for call in reversed(calls_by_ordinal.get(ordinal, ())):
                    if call.get("capability") == "operations.dispatch":
                        result = call.get("result")
                        if isinstance(result, Mapping):
                            dispatch = result
                            break
                steps.append({
                    "ordinal": ordinal,
                    "result_refs": tuple(answer.result_refs),
                    "dispatch": dispatch,
                    "calls": tuple(calls_by_ordinal.get(ordinal, ())),
                })
            if not steps:
                return None
            planner = (
                ProviderTopologyPlanner(context.provider)
                if context.provider is not None else None
            )
            executor = context.bindings["source"].endpoint.executor
            return build_pypsa_story(
                executor=executor,
                model_ref=model_ref,
                model_id=str(case["model_id"]),
                case_id=str(case["id"]),
                completed_steps=steps,
                planner=planner,
            )
        application.completion_projector = completion_projector
        selected = _ExactCaseApplication(
            application, tuple(case["introduction"]["demo_instructions"]),
        )
        diagram_cache: dict[str, dict[str, object]] = {}

        def read_network(ordinal: int) -> dict[str, object] | None:
            if not providers:
                return None
            provider = providers[0]
            current = provider.results.get("model.derive_series") or provider.results.get("model.open")
            if current is None:
                return None
            model_ref = current.get("model_ref")
            if not isinstance(model_ref, str):
                return None
            dispatch = provider.results.get("operations.dispatch")
            executor = prepared.bindings["source"].endpoint.executor

            class CachedDiagramExecutor:
                def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
                    if capability != "operator.diagram":
                        return executor.invoke(capability, arguments)
                    reference = arguments.get("model_ref")
                    if not isinstance(reference, str):
                        return executor.invoke(capability, arguments)
                    cached = diagram_cache.get(reference)
                    if cached is None:
                        cached = executor.invoke(capability, arguments)
                        diagram_cache[reference] = cached
                    return cached

            return build_pypsa_network_view(
                CachedDiagramExecutor(), model_ref, str(case["model_id"]), ordinal, str(case["id"]),
                dispatch, committed_refs.get(ordinal, ()),
            )
        network_reader = read_network
    elif mode == "provider":
        provider = values.get("provider")
        model = values.get("model")
        provider_case_id = values.get("case_id")
        provider_case: Mapping[str, object] | None = None
        provider_model_id: str | None = None
        if isinstance(provider_case_id, str):
            from validation.pypsa_cases import load_cases

            provider_case = next(
                (item for item in load_cases() if item["id"] == provider_case_id),
                None,
            )
            if isinstance(provider_case, Mapping) and isinstance(provider_case.get("model_id"), str):
                provider_model_id = provider_case["model_id"]
        if provider is not None and not isinstance(provider, str):
            raise ValueError("Provider is invalid")
        if model is not None and not isinstance(model, str):
            raise ValueError("model is invalid")
        runtime_environment = load_runtime_environment(ROOT)

        handoff = ReferenceHandoffService(profile, workspace, store, prepared.bindings)
        handoffs: dict[str, dict[str, object]] = {}
        handoff_index = workspace.core_path / "reference-handoffs.json"
        calls_by_ordinal: dict[int, list[dict[str, object]]] = {}

        def observed(event: Mapping[str, object]) -> None:
            if event.get("type") == "tool_result":
                ordinal = _event_ordinal(event)
                result = event.get("result")
                capability = event.get("capability")
                if ordinal is not None and isinstance(capability, str) and isinstance(result, Mapping):
                    calls_by_ordinal.setdefault(ordinal, []).append({
                        "capability": capability, "result": result,
                    })
            if event.get("type") == "tool_result" and event.get("ok") is True:
                capability = event.get("capability")
                result = event.get("result")
                if (
                    isinstance(capability, str)
                    and capability.startswith("model.")
                    and isinstance(result, Mapping)
                    and isinstance(result.get("model_ref"), str)
                ):
                    model_ref = str(result["model_ref"])
                    if model_ref not in handoffs:
                        try:
                            receipt = handoff.prepare_handoff(
                                source_binding_id="source",
                                target_binding_id="operations",
                                reference=model_ref,
                                reference_kind="model",
                                purpose="operations",
                                capability="operations.dispatch",
                            )
                            handoffs[model_ref] = {
                                "reference": model_ref,
                                "target_binding_id": "operations",
                                "capability_family": "operations",
                                "handoff_ref": receipt.receipt_ref,
                            }
                            _write_handoff_index(handoff_index, run_id, handoffs)
                        except Exception:
                            pass
            observer(event)

        application = AgentApplication(
            profile=profile, prepared_application=prepared,
            workspace=workspace, store=store,
            provider_catalog=ProviderCatalog.load(ROOT / "configs/llm-providers.json"),
            cli_options=CliLLMOptions(provider=provider, model=model),
            environment=runtime_environment,
            runtime_host=build_runtime_host(ROOT, profile, runtime_environment),
            semantic_event_observer=observed,
            prompt_decorator=(
                build_case_prompt_decorator(
                    application_id=APPLICATION_ID,
                    case_id=str(provider_case_id),
                    model_id=provider_model_id or str(provider_case_id),
                    instructions=tuple(provider_case["introduction"]["demo_instructions"]),
                    workflows=tuple(tuple(step for step in workflow) for workflow in provider_case["demo_workflow"]),
                )
                if isinstance(provider_case_id, str) and isinstance(provider_case, Mapping)
                else None
            ),
        )
        def completion_projector(context: Any) -> dict[str, object] | None:
            current = None
            for calls in calls_by_ordinal.values():
                for call in calls:
                    if call.get("capability") not in {"model.open", "model.derive_series"}:
                        continue
                    result = call.get("result")
                    if isinstance(result, Mapping) and isinstance(result.get("model_ref"), str):
                        current = result
            model_ref = current.get("model_ref") if isinstance(current, Mapping) else None
            if not isinstance(model_ref, str):
                return None
            steps = []
            for answer in context.completed_answers:
                ordinal = _turn_ordinal(getattr(answer, "turn_id", None))
                if ordinal is None:
                    continue
                dispatch = None
                for call in reversed(calls_by_ordinal.get(ordinal, ())):
                    if call.get("capability") == "operations.dispatch":
                        result = call.get("result")
                        if isinstance(result, Mapping):
                            dispatch = result
                            break
                steps.append({
                    "ordinal": ordinal,
                    "result_refs": tuple(answer.result_refs),
                    "dispatch": dispatch,
                    "calls": tuple(calls_by_ordinal.get(ordinal, ())),
                })
            if not steps:
                return None
            planner = (
                ProviderTopologyPlanner(context.provider)
                if context.provider is not None else None
            )
            executor = context.bindings["source"].endpoint.executor
            if provider_model_id is None or not isinstance(provider_case_id, str):
                return None
            return build_pypsa_story(
                executor=executor,
                model_ref=model_ref,
                model_id=provider_model_id,
                case_id=provider_case_id,
                completed_steps=steps,
                planner=planner,
            )
        application.completion_projector = completion_projector
        selected = application
    else:
        raise ValueError("PyPSA worker mode is invalid")
    return PreparedWorker(
        selected, run_id, lambda reference: read_verified_reference(prepared, reference),
        network_reader,
    )


def main() -> None:
    serve_application(_prepare)


if __name__ == "__main__":
    main()
