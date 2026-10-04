"""PyPSA authority-backed operator diagram and admitted step layer."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.model_capability_context import PreparedModelCapabilityContext
from capstone_agent.thread_network import ThreadNetworkProjectionProvider
from capstone_agent.thread_service import AttemptClaim


class DiagramExecutor(Protocol):
    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]: ...


class PyPSAThreadNetworkProjectionProvider:
    """Project topology from one prepared, registered PyPSA model binding."""

    def __init__(
        self,
        executor: DiagramExecutor,
        *,
        model_id: str,
        model_revision: str,
        model_ref: str,
    ) -> None:
        if not callable(getattr(executor, "invoke", None)):
            raise TypeError("PyPSA diagram executor is invalid")
        self._executor = executor
        self._model_id = model_id
        self._model_revision = model_revision
        self._model_ref = model_ref

    def project(
        self,
        claim: AttemptClaim,
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        tool_events: tuple[Mapping[str, object], ...],
    ) -> Mapping[str, object] | None:
        del result_refs, evidence_refs, tool_events
        if (
            claim.model_context.model_id != self._model_id
            or claim.model_context.model_revision != self._model_revision
        ):
            raise ValueError("PyPSA topology context does not match Attempt")
        topology = self._executor.invoke(
            "operator.diagram", {"model_ref": self._model_ref},
        )
        if not isinstance(topology, Mapping) or topology.get("model_ref") != self._model_ref:
            raise ValueError("PyPSA diagram belongs to another revision")
        return {
            "schema": "capstone-network-view/2.0",
            "ordinal": 1,
            "diagram": {
                "schema": "capstone-network-diagram/1.0",
                "model": {
                    "id": self._model_id,
                    "revision": self._model_revision,
                    "source": "pypsamodelctl",
                },
                "coordinate_system": topology.get("coordinate_system"),
                "buses": topology.get("buses"),
                "branches": topology.get("branches"),
            },
            "layer": {"focus_ids": [], "next_focus_ids": [], "overlay": None},
        }


def build_pypsa_thread_network_provider(
    context: PreparedModelCapabilityContext,
) -> ThreadNetworkProjectionProvider:
    """Bind the topology provider to the context-scoped prepared source endpoint."""

    if not isinstance(context, PreparedModelCapabilityContext):
        raise TypeError("PyPSA topology context is invalid")
    for contribution in context.contributions:
        prepared = getattr(contribution, "prepared", None)
        binding = getattr(prepared, "model_binding", None)
        if not isinstance(binding, AuthorityModelBinding) or binding.binding_id != "source":
            continue
        if (
            binding.model_id != context.model_context.model_id
            or binding.model_revision != context.model_context.model_revision
        ):
            raise ValueError("PyPSA model binding does not match Thread context")
        application = getattr(prepared, "prepared_application", None)
        bindings = getattr(application, "bindings", None)
        source = bindings.get("source") if isinstance(bindings, Mapping) else None
        runtime = getattr(source, "runtime", None)
        executor = getattr(runtime, "executor", None)
        if source is None or not callable(getattr(executor, "invoke", None)):
            raise RuntimeError("PyPSA source executor is unavailable")
        return PyPSAThreadNetworkProjectionProvider(
            cast(DiagramExecutor, executor),
            model_id=binding.model_id,
            model_revision=binding.model_revision,
            model_ref=binding.context_ref,
        )
    raise RuntimeError("PyPSA source model binding is unavailable")


def build_pypsa_network_view(
    executor: DiagramExecutor, model_ref: str, model_id: str, ordinal: int,
    case_id: str, dispatch: Mapping[str, object] | None,
    committed_refs: Sequence[str],
) -> dict[str, Any]:
    if case_id not in {"regional-demand-stress", "scigrid-dispatch", "ac-dc-interconnection"}:
        raise ValueError("PyPSA network view case is not registered")
    topology = executor.invoke("operator.diagram", {"model_ref": model_ref})
    if topology.get("model_ref") != model_ref:
        raise ValueError("PyPSA diagram belongs to another revision")
    buses = topology.get("buses")
    branches = topology.get("branches")
    if not isinstance(buses, list) or not isinstance(branches, list):
        raise ValueError("PyPSA diagram is invalid")
    visible_ids = {
        branch["id"] for branch in branches
        if isinstance(branch, Mapping) and isinstance(branch.get("id"), str)
    }
    links = [
        branch["id"] for branch in branches
        if isinstance(branch, Mapping) and branch.get("kind") == "link"
        and isinstance(branch.get("id"), str)
    ]
    focus: list[str] = []
    if case_id == "ac-dc-interconnection" and ordinal == 2:
        focus = links[:20]
    next_focus = links[:20] if case_id == "ac-dc-interconnection" and ordinal == 1 else []
    overlay = None
    if ordinal == 3 and isinstance(dispatch, Mapping):
        ref = dispatch.get("result_ref")
        ranked = dispatch.get("top_line_loading")
        if (dispatch.get("model_ref") == model_ref and isinstance(ref, str)
                and ref in committed_refs and isinstance(ranked, list)):
            values = []
            for item in ranked:
                if not isinstance(item, Mapping):
                    continue
                identifier = f"line:{item.get('line_id')}"
                number = item.get("max_loading_pct")
                if (identifier not in visible_ids
                        or not isinstance(number, (int, float))
                        or isinstance(number, bool)):
                    continue
                numeric = float(number)
                if math.isfinite(numeric):
                    values.append({"id": identifier, "value": numeric})
            if values:
                overlay = {"metric": "loading_percent", "unit": "%",
                           "source_ref": ref, "values": values}
                focus = [item["id"] for item in values[:3]]
    return {
        "schema": "capstone-network-view/2.0", "ordinal": ordinal,
        "diagram": {
            "schema": "capstone-network-diagram/1.0",
            "model": {"id": model_id, "revision": model_ref, "source": "pypsamodelctl"},
            "coordinate_system": topology.get("coordinate_system"),
            "buses": buses, "branches": branches,
        },
        "layer": {"focus_ids": focus, "next_focus_ids": next_focus, "overlay": overlay},
    }
