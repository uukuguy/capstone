"""Pandapower application worker for the neutral Capstone session host."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from capstone_agent.worker import PreparedWorker, read_verified_reference, serve_application
from capability_agent.runtime.catalog import ProviderCatalog

from grid_agent.application.composition import build_generic_application
from grid_agent.network_story import ProviderTopologyPlanner, build_grid_story
from grid_agent.network_view import build_grid_network_view


ROOT = Path(__file__).resolve().parents[4]
APPLICATION_ID = "pandapower-static-analysis"
CASES = frozenset({"pandapower-scripted-task", "pandapower-scripted-test"})


def _turn_ordinal(turn_id: object) -> int | None:
    if not isinstance(turn_id, str):
        return None
    try:
        return int(turn_id.rsplit("-t", 1)[1])
    except (IndexError, ValueError):
        return None


def _scripted_story(execution: Any) -> dict[str, object] | None:
    prepared = getattr(execution, "prepared", None)
    transport = getattr(execution, "transport", None)
    case = getattr(execution, "case", None)
    controller = getattr(execution, "controller", None)
    if prepared is None or transport is None or not isinstance(case, Mapping):
        return None
    case_id = case.get("case_id")
    if not isinstance(case_id, str):
        return None
    calls_by_turn: dict[str, list[Mapping[str, object]]] = {}
    for event in getattr(transport, "semantic_events", ()):
        if not isinstance(event, Mapping) or event.get("type") != "tool_result":
            continue
        turn_id = event.get("turn_id")
        result = event.get("result")
        capability = event.get("capability")
        if isinstance(turn_id, str) and isinstance(capability, str) and isinstance(result, Mapping):
            calls_by_turn.setdefault(turn_id, []).append({
                "capability": capability, "result": result,
            })
    finalized = getattr(controller, "finalized_turns", ())
    steps: list[dict[str, object]] = []
    for answer in finalized:
        ordinal = _turn_ordinal(getattr(answer, "turn_id", None))
        if ordinal is None:
            continue
        steps.append({
            "ordinal": ordinal,
            "result_refs": tuple(getattr(answer, "result_refs", ())),
            "calls": tuple(calls_by_turn.get(getattr(answer, "turn_id", ""), ())),
        })
    if not steps:
        return None
    try:
        executor = prepared.bindings["grid"].endpoint.executor
        return build_grid_story(
            executor=executor,
            context_ref=transport.current_context_ref,
            case_id=case_id,
            completed_steps=steps,
            planner=None,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _provider_network_reader(application: Any, case_id: str):
    """Project a provider run from its committed authority events.

    The generic provider application keeps the live ``gridctl`` executor in
    its prepared binding, while the durable event log carries the current
    context, admitted result references, and capability results.  Combining
    those two existing authority-backed surfaces lets the operator graph use
    the same projection path as the scripted worker without inventing data.
    """
    def network(ordinal: int) -> dict[str, object] | None:
        workspace = getattr(application, "workspace", None)
        root = getattr(workspace, "root", None)
        if not isinstance(root, Path):
            return None
        events_path = root / "core" / "context-events.jsonl"
        if not events_path.is_file():
            return None
        context_ref: str | None = None
        calls: list[dict[str, object]] = []
        refs_by_ordinal: dict[int, tuple[str, ...]] = {}
        try:
            with events_path.open(encoding="utf-8") as stream:
                for raw in stream:
                    event = json.loads(raw)
                    payload = event.get("payload")
                    if not isinstance(payload, Mapping):
                        continue
                    if event.get("event_type") == "tool.observation.recorded":
                        capability = event.get("capability") or payload.get("capability_id")
                        result = payload.get("result")
                        if isinstance(capability, str) and isinstance(result, Mapping):
                            calls.append({"capability": capability, "result": result})
                            candidate = result.get("context_ref")
                            if isinstance(candidate, str):
                                context_ref = candidate
                            for candidate in payload.get("context_refs", ()):
                                if isinstance(candidate, str) and candidate.startswith("context:"):
                                    context_ref = candidate
                    elif event.get("event_type") == "answer.submitted":
                        turn_id = payload.get("turn_id")
                        result_refs = payload.get("result_refs")
                        if isinstance(turn_id, str) and isinstance(result_refs, list):
                            try:
                                turn_ordinal = int(turn_id.rsplit("-t", 1)[1])
                            except (IndexError, ValueError):
                                continue
                            refs_by_ordinal[turn_ordinal] = tuple(
                                ref for ref in result_refs if isinstance(ref, str)
                            )
        except (OSError, ValueError, TypeError):
            return None
        if not context_ref:
            return None
        try:
            executor = application.prepared_application.bindings["grid"].endpoint.executor
            return build_grid_network_view(
                executor, context_ref, ordinal, case_id,
                refs_by_ordinal.get(ordinal, ()), calls,
            )
        except (KeyError, TypeError, ValueError):
            return None
    return network


class _ScriptedCaseApplication:
    def __init__(self, case: dict[str, Any], observer) -> None:
        self.case = case
        self.observer = observer
        self.execution: Any = None
        self.prepared: Any = None
        self.transport: Any = None

    def run_stream(self, request, instructions):
        from validation.run import execute_application_case

        self.case["run_id"] = request.run_id

        def progress(event: dict[str, object]) -> None:
            self.observer({"type": event.get("event", "progress"),
                           "message": event.get("message", "")})

        execution = execute_application_case(
            self.case, runs_root=ROOT / "runs" / "capstone-agent",
            instruction_source=instructions, on_semantic_event=self.observer,
            on_progress=progress,
            on_prepared=lambda prepared: setattr(self, "prepared", prepared),
            on_transport=lambda transport: setattr(self, "transport", transport),
        )
        self.execution = execution
        story = _scripted_story(execution)
        return (
            replace(execution.outcome, completion_projection=story)
            if story is not None else execution.outcome
        )


def _prepare(values: Mapping[str, object], observer) -> PreparedWorker:
    if values.get("application_id") != APPLICATION_ID:
        raise ValueError("pandapower worker application is invalid")
    run_id = values.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("pandapower worker run ID is invalid")
    mode = values.get("mode")
    if mode == "scripted-demo":
        case_id = values.get("case_id")
        if not isinstance(case_id, str) or case_id not in CASES:
            raise ValueError("pandapower case is not registered")
        scripted_case_id = case_id
        document = json.loads(
            (ROOT / "validation" / "application" / f"{scripted_case_id}.json").read_text(encoding="utf-8")
        )
        application = _ScriptedCaseApplication(document, observer)

        def evidence(reference: str) -> object | None:
            prepared = application.prepared
            return (
                read_verified_reference(prepared, reference)
                if prepared is not None else None
            )

        def network(ordinal: int) -> dict[str, object] | None:
            prepared = application.prepared
            transport = application.transport
            if prepared is None or transport is None or transport.current_context_ref is None:
                return None
            executor = prepared.bindings["grid"].endpoint.executor
            return build_grid_network_view(
                executor, transport.current_context_ref, ordinal, case_id,
                transport.current_result_refs, transport.calls,
            )

        return PreparedWorker(application, run_id, evidence, network)
    if mode != "provider":
        raise ValueError("pandapower worker mode is invalid")
    case_id = values.get("case_id")
    if case_id is not None and (not isinstance(case_id, str) or case_id not in CASES):
        raise ValueError("pandapower provider case is not registered")
    provider_case_id = case_id if isinstance(case_id, str) else None
    provider = values.get("provider")
    model = values.get("model")
    if provider is not None and not isinstance(provider, str):
        raise ValueError("Provider is invalid")
    if model is not None and not isinstance(model, str):
        raise ValueError("model is invalid")
    from grid_agent.cli.app import _generic_runtime_environment, _runtime_environment

    application = build_generic_application(
        APPLICATION_ID, provider=provider, model=model,
        provider_catalog=ProviderCatalog.load(ROOT / "configs/llm-providers.json"),
        workspace_root=ROOT / "runs" / "capstone-agent",
        run_id=run_id,
        environment=_generic_runtime_environment(_runtime_environment(ROOT)),
        semantic_event_observer=observer,
    )
    def completion_projector(context: Any) -> dict[str, object] | None:
        if context.workspace is None or provider_case_id is None:
            return None
        events_path = context.workspace.root / "core" / "context-events.jsonl"
        calls_by_turn: dict[str, list[Mapping[str, object]]] = {}
        context_ref: str | None = None
        if not events_path.is_file():
            return None
        try:
            with events_path.open(encoding="utf-8") as stream:
                for raw in stream:
                    event = json.loads(raw)
                    payload = event.get("payload")
                    if event.get("event_type") != "tool.observation.recorded" or not isinstance(payload, Mapping):
                        continue
                    capability = event.get("capability") or payload.get("capability_id")
                    result = payload.get("result")
                    turn_id = event.get("turn_id") or payload.get("turn_id")
                    if isinstance(result, Mapping):
                        candidate = result.get("context_ref")
                        if isinstance(candidate, str):
                            context_ref = candidate
                    if isinstance(capability, str) and isinstance(result, Mapping):
                        calls_by_turn.setdefault(str(turn_id), []).append({
                            "capability": capability, "result": result,
                        })
        except (OSError, TypeError, ValueError):
            return None
        if not context_ref:
            return None
        steps = []
        for answer in context.completed_answers:
            turn_id = getattr(answer, "turn_id", None)
            ordinal = _turn_ordinal(turn_id)
            if ordinal is None:
                continue
            steps.append({
                "ordinal": ordinal,
                "result_refs": tuple(answer.result_refs),
                "calls": tuple(calls_by_turn.get(str(turn_id), ())),
            })
        if not steps:
            return None
        planner = (
            ProviderTopologyPlanner(context.provider)
            if context.provider is not None else None
        )
        executor = context.bindings["grid"].endpoint.executor
        return build_grid_story(
            executor=executor,
            context_ref=context_ref,
            case_id=provider_case_id,
            completed_steps=steps,
            planner=planner,
        )
    application.completion_projector = completion_projector
    return PreparedWorker(
        application, run_id,
        lambda reference: read_verified_reference(application.prepared_application, reference),
        _provider_network_reader(application, provider_case_id)
        if provider_case_id is not None else None,
    )


def main() -> None:
    serve_application(_prepare)


if __name__ == "__main__":
    main()
