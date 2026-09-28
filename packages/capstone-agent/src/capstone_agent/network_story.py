"""Validated, cumulative topology snapshots produced after a run completes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from capstone_agent.network_diagram import normalize_network_diagram, normalize_network_layer


SCHEMA = "capstone-network-story/1.0"
MODE = "cumulative-snapshots"
STEP_SCHEMA = "capstone-network-story-step/1.0"
MAX_STEPS = 3
MAX_FOCUS_IDS = 20


class TopologyPlanner(Protocol):
    def plan(self, request: Mapping[str, object]) -> Mapping[str, object]: ...


TopologyPlan = Mapping[str, object]


def _mapping(value: object, message: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(message)
    return value


def build_fallback_plan(candidate_directory_by_step: Mapping[int, Sequence[str]]) -> dict[str, object]:
    return {
        "plan_source": "fallback",
        "steps": [
            {"ordinal": ordinal, "focus_candidate_keys": list(keys)[:3]}
            for ordinal, keys in sorted(candidate_directory_by_step.items())
        ],
    }


def build_cumulative_story(
    diagram: Mapping[str, Any],
    step_inputs: Sequence[Mapping[str, object]],
    plan: Mapping[str, object] | None,
) -> dict[str, Any]:
    normalized_diagram = normalize_network_diagram(diagram)
    if not 1 <= len(step_inputs) <= MAX_STEPS:
        raise ValueError("network story step count is invalid")
    candidate_directory: dict[int, dict[str, str]] = {}
    for raw in step_inputs:
        ordinal = raw.get("ordinal")
        candidates = raw.get("candidate_keys")
        if type(ordinal) is not int or not 1 <= ordinal <= MAX_STEPS or not isinstance(candidates, Mapping):
            raise ValueError("network story step candidates are invalid")
        candidate_directory[ordinal] = {
            str(key): value for key, value in candidates.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    if set(candidate_directory) != set(range(1, len(step_inputs) + 1)):
        raise ValueError("network story ordinals are invalid")
    fallback = build_fallback_plan({ordinal: tuple(candidates) for ordinal, candidates in candidate_directory.items()})
    selected_plan = plan if isinstance(plan, Mapping) else fallback
    source = selected_plan.get("plan_source")
    plan_steps = selected_plan.get("steps")
    if source not in {"llm", "fallback"} or not isinstance(plan_steps, list):
        selected_plan = fallback
    plan_by_ordinal = {
        item.get("ordinal"): item for item in selected_plan.get("steps", [])
        if isinstance(item, Mapping) and type(item.get("ordinal")) is int
    }
    if any(
        not isinstance(item, Mapping)
        or any(key not in candidate_directory.get(item.get("ordinal"), {}) for key in item.get("focus_candidate_keys", ()))
        for item in selected_plan.get("steps", [])
    ):
        selected_plan = fallback
        plan_by_ordinal = {item["ordinal"]: item for item in fallback["steps"]}

    steps: list[dict[str, Any]] = []
    history: list[str] = []
    prior_overlay: dict[str, Any] | None = None
    for raw in sorted(step_inputs, key=lambda item: int(item["ordinal"])):
        ordinal = int(raw["ordinal"])
        candidates = candidate_directory[ordinal]
        planned = plan_by_ordinal.get(ordinal, {})
        keys = planned.get("focus_candidate_keys", ()) if isinstance(planned, Mapping) else ()
        if not isinstance(keys, list | tuple):
            keys = ()
        current = []
        for key in keys:
            candidate = candidates.get(key) if isinstance(key, str) else None
            if candidate is not None and candidate not in current:
                current.append(candidate)
        if not current:
            current = list(candidates.values())[:3]
        current = current[:MAX_FOCUS_IDS]
        overlay = raw.get("overlay")
        requested_metric = raw.get("overlay_metric")
        if requested_metric is not None and requested_metric not in {"loading_percent", "voltage_pu"}:
            raise ValueError("network story overlay metric is invalid")
        if overlay is None and prior_overlay is not None and (
            requested_metric is None or requested_metric == prior_overlay["metric"]
        ):
            overlay = prior_overlay
        elif isinstance(overlay, Mapping):
            overlay = dict(overlay)
            prior_overlay = overlay
        history_ids = [identifier for identifier in history if identifier not in current]
        layer = normalize_network_layer(
            {"focus_ids": current, "next_focus_ids": [], "overlay": overlay},
            normalized_diagram,
            ordinal,
            admitted_refs=None,
        )
        steps.append({
            "schema": STEP_SCHEMA,
            "ordinal": ordinal,
            "diagram_ref": normalized_diagram["ref"],
            "model_revision": normalized_diagram["model"]["revision"],
            "current_focus_ids": layer["focus_ids"],
            "history_focus_ids": history_ids[:MAX_FOCUS_IDS],
            "overlay": layer["overlay"],
            "plan_source": selected_plan.get("plan_source", "fallback"),
        })
        history.extend(identifier for identifier in current if identifier not in history)
    return {"schema": SCHEMA, "mode": MODE, "story_status": "complete",
            "plan_source": selected_plan.get("plan_source", "fallback"),
            "diagram": normalized_diagram, "steps": steps}


def normalize_network_story(
    value: object, *, admitted_refs_by_ordinal: Mapping[int, Sequence[str]],
) -> dict[str, Any]:
    source = _mapping(value, "network story is invalid")
    if set(source) != {"schema", "mode", "story_status", "plan_source", "diagram", "steps"} or source["schema"] != SCHEMA:
        raise ValueError("network story schema is invalid")
    if source["mode"] != MODE or source["story_status"] not in {"complete", "partial"}:
        raise ValueError("network story status is invalid")
    if source["plan_source"] not in {"llm", "fallback"}:
        raise ValueError("network story plan source is invalid")
    diagram = normalize_network_diagram(source["diagram"])
    raw_steps = source["steps"]
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_STEPS:
        raise ValueError("network story steps are invalid")
    normalized_steps: list[dict[str, Any]] = []
    prior: set[str] = set()
    for expected, raw in enumerate(raw_steps, start=1):
        step = _mapping(raw, "network story step is invalid")
        required = {"schema", "ordinal", "diagram_ref", "model_revision", "current_focus_ids", "history_focus_ids", "overlay", "plan_source"}
        if set(step) != required or step["schema"] != STEP_SCHEMA or step["ordinal"] != expected:
            raise ValueError("network story step identity is invalid")
        if step["plan_source"] not in {"llm", "fallback"}:
            raise ValueError("network story step plan source is invalid")
        if step["diagram_ref"] != diagram["ref"] or step["model_revision"] != diagram["model"]["revision"]:
            raise ValueError("network story step revision is invalid")
        if step["overlay"] is not None:
            overlay = _mapping(step["overlay"], "network overlay is invalid")
            source_ref = overlay.get("source_ref")
            admitted_refs = tuple(
                ref for ordinal in range(1, expected + 1)
                for ref in admitted_refs_by_ordinal.get(ordinal, ())
            )
            if admitted_refs is not None and source_ref not in admitted_refs:
                raise ValueError("network overlay reference is not admitted")
        layer = normalize_network_layer(
            {"schema": "capstone-network-layer/1.0", "ordinal": expected,
             "diagram_ref": diagram["ref"], "model_revision": diagram["model"]["revision"],
             "focus_ids": step["current_focus_ids"], "next_focus_ids": [], "overlay": step["overlay"]},
            diagram, expected, admitted_refs=tuple(
                ref for ordinal in range(1, expected + 1)
                for ref in admitted_refs_by_ordinal.get(ordinal, ())
            ),
        )
        history = step["history_focus_ids"]
        if not isinstance(history, list) or len(history) > MAX_FOCUS_IDS or any(item not in prior for item in history):
            raise ValueError("network story history focus is invalid")
        normalized_steps.append({**step, "current_focus_ids": layer["focus_ids"], "history_focus_ids": list(history), "overlay": layer["overlay"]})
        prior.update(layer["focus_ids"])
    return {"schema": SCHEMA, "mode": MODE, "story_status": source["story_status"],
            "plan_source": source["plan_source"], "diagram": diagram, "steps": normalized_steps}


__all__ = ["MODE", "SCHEMA", "STEP_SCHEMA", "TopologyPlan", "TopologyPlanner", "build_cumulative_story", "build_fallback_plan", "normalize_network_story"]
