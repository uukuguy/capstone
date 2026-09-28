"""PyPSA-owned completion projection for cumulative topology stories."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from capstone_agent.network_story import PLAN_SCHEMA, TopologyPlanner, build_cumulative_story

from pypsa_agent.network_view import DiagramExecutor, build_pypsa_network_view


_MAX_CANDIDATES = 20
_CASES = frozenset({"regional-demand-stress", "scigrid-dispatch", "ac-dc-interconnection"})


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(value)
    return ()


def _refs(step: Mapping[str, object]) -> tuple[str, ...]:
    raw = step.get("result_refs", step.get("committed_refs", ()))
    return tuple(ref for ref in _sequence(raw) if isinstance(ref, str))


def _dispatch(step: Mapping[str, object]) -> Mapping[str, object] | None:
    direct = step.get("dispatch")
    if isinstance(direct, Mapping):
        return direct
    calls = step.get("calls", step.get("authority_calls", ()))
    for call in reversed(_sequence(calls)):
        if not isinstance(call, Mapping) or call.get("capability") != "operations.dispatch":
            continue
        result = call.get("result")
        if isinstance(result, Mapping):
            return result
    return None


def _candidate_ids(
    view: Mapping[str, object], diagram: Mapping[str, object],
) -> list[str]:
    layer = view["layer"]
    if not isinstance(layer, Mapping):
        return []
    overlay = layer.get("overlay")
    if isinstance(overlay, Mapping) and isinstance(overlay.get("values"), list):
        return [
            item["id"] for item in overlay["values"]
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        ][: _MAX_CANDIDATES]
    for field in ("focus_ids", "next_focus_ids"):
        raw = layer.get(field)
        if isinstance(raw, list):
            selected = [item for item in raw if isinstance(item, str)]
            if selected:
                return selected[:_MAX_CANDIDATES]
    branches = diagram.get("branches")
    return [
        item["id"] for item in branches
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    ][:_MAX_CANDIDATES] if isinstance(branches, list) else []


def _component_metadata(diagram: Mapping[str, object], identifier: str) -> dict[str, object]:
    for field in ("buses", "branches"):
        components = diagram.get(field)
        if not isinstance(components, list):
            continue
        for item in components:
            if isinstance(item, Mapping) and item.get("id") == identifier:
                return {
                    "id": identifier,
                    "kind": item.get("kind", "bus"),
                    "label": item.get("label", identifier),
                }
    return {"id": identifier, "kind": "element", "label": identifier}


def _safe_plan(
    planner: TopologyPlanner | None,
    request: Mapping[str, object],
) -> Mapping[str, object] | None:
    if planner is None:
        return None
    try:
        proposed = planner.plan(request)
    except Exception:
        return None
    if not isinstance(proposed, Mapping) or proposed.get("plan_source") != "llm":
        return None
    raw_steps = proposed.get("steps")
    if not isinstance(raw_steps, list):
        return None
    requested: dict[int, list[str]] = {}
    raw_request_steps = request.get("steps")
    if isinstance(raw_request_steps, list):
        for raw in raw_request_steps:
            if not isinstance(raw, Mapping) or type(raw.get("ordinal")) is not int:
                return None
            candidates = raw.get("candidates")
            if not isinstance(candidates, list):
                return None
            requested[raw["ordinal"]] = [
                item["candidate_key"] for item in candidates
                if isinstance(item, Mapping) and isinstance(item.get("candidate_key"), str)
            ]
    if not requested:
        return None
    provided: dict[int, Mapping[str, object]] = {
        item["ordinal"]: item for item in raw_steps
        if isinstance(item, Mapping) and type(item.get("ordinal")) is int
    }
    bounded_steps: list[dict[str, object]] = []
    for ordinal in sorted(requested):
        item = provided.get(ordinal, {})
        keys = item.get("focus_candidate_keys", requested[ordinal][:3])
        if not isinstance(keys, list) or len(keys) > _MAX_CANDIDATES:
            return None
        primary = item.get("primary_candidate_key")
        if not isinstance(primary, str):
            primary = keys[0] if keys and isinstance(keys[0], str) else ""
        presentation = item.get("presentation", "highlight")
        if not isinstance(presentation, str):
            presentation = "highlight"
        bounded_steps.append({
            "ordinal": ordinal,
            "focus_candidate_keys": [
                key for key in keys if isinstance(key, str)
            ],
            "primary_candidate_key": primary,
            "presentation": presentation,
        })
    return {"schema": PLAN_SCHEMA, "plan_source": "llm", "steps": bounded_steps}


def build_pypsa_story(
    *,
    executor: DiagramExecutor,
    model_ref: str,
    model_id: str,
    case_id: str,
    completed_steps: Sequence[Mapping[str, object]],
    planner: TopologyPlanner | None,
) -> dict[str, object]:
    """Build one authority-backed story after all turns have committed."""

    if case_id not in _CASES:
        raise ValueError("PyPSA network story case is not registered")
    if not isinstance(model_ref, str) or not model_ref:
        raise ValueError("PyPSA model reference is invalid")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("PyPSA model ID is invalid")
    if not 1 <= len(completed_steps) <= 3:
        raise ValueError("PyPSA story step count is invalid")

    def step_ordinal(step: Mapping[str, object]) -> int:
        value = step.get("ordinal")
        return value if type(value) is int else 0

    ordered = sorted(completed_steps, key=step_ordinal)
    views: list[dict[str, Any]] = []
    for step in ordered:
        ordinal = step.get("ordinal")
        if type(ordinal) is not int:
            raise ValueError("PyPSA story ordinal is invalid")
        views.append(build_pypsa_network_view(
            executor,
            model_ref,
            model_id,
            ordinal,
            case_id,
            _dispatch(step),
            _refs(step),
        ))
    diagram = views[0]["diagram"]

    story_steps: list[dict[str, object]] = []
    planner_steps: list[dict[str, object]] = []
    for step, view in zip(ordered, views, strict=True):
        ordinal_value = step.get("ordinal")
        if type(ordinal_value) is not int:
            raise ValueError("PyPSA story ordinal is invalid")
        ordinal = ordinal_value
        identifiers = _candidate_ids(view, diagram)
        candidates = {
            f"c{index}": identifier
            for index, identifier in enumerate(identifiers, start=1)
        }
        layer = view["layer"]
        if not isinstance(layer, Mapping):
            raise ValueError("PyPSA network layer is invalid")
        overlay = layer.get("overlay")
        story_steps.append({
            "ordinal": ordinal,
            "candidate_keys": candidates,
            "overlay": overlay,
            "overlay_metric": (
                overlay.get("metric")
                if isinstance(overlay, Mapping)
                else None
            ),
        })
        planner_steps.append({
            "ordinal": ordinal,
            "candidates": [
                _component_metadata(diagram, identifier)
                | {"candidate_key": key}
                for key, identifier in candidates.items()
            ],
        })

    plan = _safe_plan(planner, {
        "schema": "capstone-network-story-plan-request/1.0",
        "case_id": case_id,
        "diagram": {
            "id": diagram["model"]["id"],
            "revision": diagram["model"]["revision"],
        },
        "steps": planner_steps,
    })
    return build_cumulative_story(diagram, story_steps, plan)


class ProviderTopologyPlanner:
    """Bounded adapter for providers that can answer a planning prompt."""

    def __init__(self, provider: object, *, timeout_seconds: float = 5.0) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds

    def plan(self, request: Mapping[str, object]) -> Mapping[str, object]:
        method = getattr(self.provider, "plan_topology", None)
        if callable(method):
            try:
                value = method(request, timeout_seconds=self.timeout_seconds)
            except Exception:
                return {}
        else:
            method = getattr(self.provider, "prompt_and_wait", None)
            if not callable(method):
                return {}
            prompt = (
                "Return only a JSON object selecting candidate keys for this "
                "network presentation plan. Do not add topology, values, or refs.\n"
                + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
            )
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(
                method,
                prompt,
                on_semantic_event=lambda *_args, **_kwargs: None,
                correlation_id=None,
                on_heartbeat=lambda: None,
            )
            try:
                value = future.result(timeout=self.timeout_seconds)
            except Exception:
                future.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                return {}
            pool.shutdown(wait=False, cancel_futures=True)
        if isinstance(value, Mapping):
            return value
        if not isinstance(value, str):
            return {}
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return decoded if isinstance(decoded, Mapping) else {}


__all__ = ["ProviderTopologyPlanner", "build_pypsa_story"]
