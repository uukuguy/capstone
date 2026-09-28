"""Validated, cumulative topology snapshots produced after a run completes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from capstone_agent.network_diagram import normalize_network_diagram, normalize_network_layer


SCHEMA = "capstone-network-story/1.0"
MODE = "cumulative-snapshots"
STEP_SCHEMA = "capstone-network-story-step/1.0"
PLAN_SCHEMA = "capstone-topology-plan/1.0"
PRESENTATIONS = frozenset({"highlight", "context", "compare"})
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
        "schema": PLAN_SCHEMA,
        "plan_source": "fallback",
        "steps": [
            {"ordinal": ordinal, "focus_candidate_keys": list(keys)[:3],
             "primary_candidate_key": next(iter(keys), ""), "presentation": "highlight"}
            for ordinal, keys in sorted(candidate_directory_by_step.items())
        ],
    }


def _plan_selection(
    value: object, candidate_directory: Mapping[int, Mapping[str, str]],
) -> tuple[str, dict[int, tuple[str, ...]]] | None:
    if not isinstance(value, Mapping) or set(value) != {"schema", "plan_source", "steps"}:
        return None
    if value.get("schema") != PLAN_SCHEMA:
        return None
    source = value.get("plan_source")
    raw_steps = value.get("steps")
    if not isinstance(source, str) or source not in {"llm", "fallback"} or not isinstance(raw_steps, list):
        return None
    selections: dict[int, tuple[str, ...]] = {}
    for raw in raw_steps:
        if not isinstance(raw, Mapping) or set(raw) != {
            "ordinal", "focus_candidate_keys", "primary_candidate_key", "presentation",
        }:
            return None
        ordinal = raw.get("ordinal")
        keys = raw.get("focus_candidate_keys")
        primary = raw.get("primary_candidate_key")
        presentation = raw.get("presentation")
        if (type(ordinal) is not int or not isinstance(keys, list) or not 1 <= len(keys) <= 3
                or any(not isinstance(key, str) for key in keys)
                or len(set(keys)) != len(keys) or not isinstance(primary, str)
                or primary not in keys or not isinstance(presentation, str)
                or presentation not in PRESENTATIONS or ordinal not in candidate_directory
                or any(key not in candidate_directory[ordinal] for key in keys)
                or ordinal in selections):
            return None
        selections[ordinal] = tuple(keys)
    if set(selections) != set(candidate_directory):
        return None
    return source, selections


def build_cumulative_story(
    diagram: Mapping[str, Any],
    step_inputs: Sequence[Mapping[str, object]],
    plan: Mapping[str, object] | None,
) -> dict[str, Any]:
    normalized_diagram = normalize_network_diagram(diagram)
    if not 1 <= len(step_inputs) <= MAX_STEPS:
        raise ValueError("network story step count is invalid")
    candidate_directory: dict[int, dict[str, str]] = {}
    raw_by_ordinal: dict[int, Mapping[str, object]] = {}
    for raw in step_inputs:
        ordinal = raw.get("ordinal")
        candidates = raw.get("candidate_keys")
        if type(ordinal) is not int or not 1 <= ordinal <= MAX_STEPS or not isinstance(candidates, Mapping):
            raise ValueError("network story step candidates are invalid")
        if ordinal in candidate_directory:
            raise ValueError("network story ordinals are invalid")
        raw_by_ordinal[ordinal] = raw
        candidate_directory[ordinal] = {
            key: value for key, value in candidates.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    if set(candidate_directory) != set(range(1, len(step_inputs) + 1)):
        raise ValueError("network story ordinals are invalid")
    fallback = build_fallback_plan({ordinal: tuple(candidates) for ordinal, candidates in candidate_directory.items()})
    selected = _plan_selection(plan, candidate_directory) or _plan_selection(fallback, candidate_directory)
    if selected is None:
        raise ValueError("fallback topology plan is invalid")
    source, plan_by_ordinal = selected

    steps: list[dict[str, Any]] = []
    history: list[str] = []
    prior_overlay: dict[str, Any] | None = None
    for ordinal in range(1, len(step_inputs) + 1):
        raw = raw_by_ordinal[ordinal]
        candidates = candidate_directory[ordinal]
        current = []
        for key in plan_by_ordinal[ordinal]:
            candidate = candidates[key]
            if candidate not in current:
                current.append(candidate)
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
        layer = normalize_network_layer(
            {"focus_ids": current, "next_focus_ids": [], "overlay": overlay},
            normalized_diagram, ordinal, admitted_refs=None,
        )
        steps.append({
            "schema": STEP_SCHEMA,
            "ordinal": ordinal,
            "diagram_ref": normalized_diagram["ref"],
            "model_revision": normalized_diagram["model"]["revision"],
            "current_focus_ids": layer["focus_ids"],
            "history_focus_ids": history[:MAX_FOCUS_IDS],
            "overlay": layer["overlay"],
            "plan_source": source,
        })
        history.extend(identifier for identifier in current if identifier not in history)
    return {"schema": SCHEMA, "mode": MODE, "story_status": "complete",
            "plan_source": source, "diagram": normalized_diagram, "steps": steps}


def _admitted_refs(source: Mapping[int, Sequence[str]], ordinal: int) -> tuple[str, ...]:
    refs: list[str] = []
    for step in range(1, ordinal + 1):
        values = source.get(step, ())
        if isinstance(values, (str, bytes)):
            raise ValueError("admitted result references are invalid")
        try:
            for ref in values:
                if not isinstance(ref, str):
                    raise ValueError("admitted result references are invalid")
                if ref not in refs:
                    refs.append(ref)
        except TypeError:
            raise ValueError("admitted result references are invalid") from None
    return tuple(refs)


def normalize_network_story(
    value: object, *, admitted_refs_by_ordinal: Mapping[int, Sequence[str]],
) -> dict[str, Any]:
    source = _mapping(value, "network story is invalid")
    if set(source) != {"schema", "mode", "story_status", "plan_source", "diagram", "steps"}:
        raise ValueError("network story schema is invalid")
    if source.get("schema") != SCHEMA or source.get("mode") != MODE:
        raise ValueError("network story schema is invalid")
    story_status = source.get("story_status")
    plan_source = source.get("plan_source")
    if story_status not in {"complete", "partial"}:
        raise ValueError("network story status is invalid")
    if not isinstance(plan_source, str) or plan_source not in {"llm", "fallback"}:
        raise ValueError("network story plan source is invalid")
    diagram = normalize_network_diagram(source.get("diagram"))
    raw_steps = source.get("steps")
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_STEPS:
        raise ValueError("network story steps are invalid")
    normalized_steps: list[dict[str, Any]] = []
    prior: list[str] = []
    for expected, raw in enumerate(raw_steps, start=1):
        step = _mapping(raw, "network story step is invalid")
        required = {"schema", "ordinal", "diagram_ref", "model_revision", "current_focus_ids", "history_focus_ids", "overlay", "plan_source"}
        if set(step) != required or step.get("schema") != STEP_SCHEMA or step.get("ordinal") != expected:
            raise ValueError("network story step identity is invalid")
        step_source = step.get("plan_source")
        if not isinstance(step_source, str) or step_source not in {"llm", "fallback"}:
            raise ValueError("network story step plan source is invalid")
        if step.get("diagram_ref") != diagram["ref"] or step.get("model_revision") != diagram["model"]["revision"]:
            raise ValueError("network story step revision is invalid")
        admitted_refs = _admitted_refs(admitted_refs_by_ordinal, expected)
        if step.get("overlay") is not None:
            overlay = _mapping(step["overlay"], "network overlay is invalid")
            source_ref = overlay.get("source_ref")
            if not isinstance(source_ref, str) or source_ref not in admitted_refs:
                raise ValueError("network overlay reference is not admitted")
        layer = normalize_network_layer(
            {"schema": "capstone-network-layer/1.0", "ordinal": expected,
             "diagram_ref": diagram["ref"], "model_revision": diagram["model"]["revision"],
             "focus_ids": step.get("current_focus_ids"), "next_focus_ids": [],
             "overlay": step.get("overlay")},
            diagram, expected, admitted_refs=admitted_refs,
        )
        history = step.get("history_focus_ids")
        if (not isinstance(history, list) or len(history) > MAX_FOCUS_IDS
                or any(not isinstance(item, str) for item in history)
                or len(history) != len(set(history)) or history != prior):
            raise ValueError("network story history focus is invalid")
        normalized_steps.append({**step, "current_focus_ids": layer["focus_ids"],
                                 "history_focus_ids": list(history), "overlay": layer["overlay"]})
        prior.extend(identifier for identifier in layer["focus_ids"] if identifier not in prior)
    return {"schema": SCHEMA, "mode": MODE, "story_status": story_status,
            "plan_source": plan_source, "diagram": diagram, "steps": normalized_steps}


__all__ = ["MODE", "PLAN_SCHEMA", "SCHEMA", "STEP_SCHEMA", "TopologyPlan", "TopologyPlanner", "build_cumulative_story", "build_fallback_plan", "normalize_network_story"]
