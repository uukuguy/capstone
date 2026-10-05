"""Operator topology for the exact prepared pandapower Thread model."""

from __future__ import annotations

from collections.abc import Mapping
import math
import re
from typing import Protocol, cast

from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.model_capability_context import PreparedModelCapabilityContext
from capstone_agent.thread_network import ThreadNetworkProjectionProvider, NetworkProjectionUnavailable
from pandapower_domain.execution import SimulatorCapabilityError
from capstone_agent.thread_service import AttemptClaim

from .network_view import NetworkExecutor


_BRANCH_ASSET = re.compile(r"^asset:(line|trafo|trafo3w):sha256:[0-9a-f]{64}$")
_ENDPOINT_CAPABILITY = "topology.branch.endpoints.get"


class EvidenceAuthority(Protocol):
    def verify_evidence(self, reference: str) -> object: ...


class PandapowerThreadNetworkProjectionProvider:
    """Read an operator diagram through a context-scoped prepared endpoint."""

    def __init__(
        self,
        context: PreparedModelCapabilityContext,
        binding: AuthorityModelBinding,
        executor: NetworkExecutor,
        authority: EvidenceAuthority,
    ) -> None:
        self._context = context
        self._binding = binding
        self._executor = executor
        self._authority = authority
        self._rank_queries: dict[str, dict[str, object]] = {}

    def observe_runtime_event(self, event: Mapping[str, object]) -> None:
        """Retain only bounded query metadata; the authority rechecks the rows."""
        if event.get("type") not in {"tool_execution_end", "tool_result"}:
            return
        raw = event.get("result")
        details = event if event.get("event") == "tool_result" else (
            raw.get("details") if isinstance(raw, Mapping) else event.get("details")
        )
        if not isinstance(details, Mapping) or details.get("ok") is not True or details.get("capability") != "result.branches.rank":
            return
        owner = details.get("capability_key")
        result = details.get("result")
        call_id = event.get("tool_call_id", event.get("toolCallId"))
        if (not isinstance(owner, Mapping) or owner.get("binding_id") != self._binding.binding_id
                or not isinstance(result, Mapping) or not isinstance(call_id, str) or not 0 < len(call_id) <= 256
                or result.get("context_ref") != self._binding.context_ref
                or result.get("revision_ref") != self._binding.model_revision):
            return
        rows = result.get("branches")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
            return
        refs = [row.get("branch_ref") for row in rows if isinstance(row, Mapping)]
        kinds = {row.get("element_kind") for row in rows if isinstance(row, Mapping) and isinstance(row.get("element_kind"), str)}
        if len(refs) != len(rows) or any(not isinstance(ref, str) or not _BRANCH_ASSET.fullmatch(ref) for ref in refs):
            return
        reference, metric, direction = result.get("result_ref"), result.get("metric"), result.get("direction")
        if (not isinstance(reference, str) or not re.fullmatch(r"result:sha256:[0-9a-f]{64}", reference)
                or metric not in {"loading_percent", "p_from_mw", "p_to_mw", "pl_mw"}
                or direction not in {"ascending", "descending"}):
            return
        arguments: dict[str, object] = {"result_ref": reference, "metric": metric, "direction": direction, "limit": len(rows)}
        if len(kinds) == 1 and kinds <= {"line", "trafo", "trafo3w"}:
            arguments["element_kind"] = next(iter(kinds))
        self._rank_queries[call_id] = {"arguments": arguments, "branch_refs": tuple(refs)}
        if len(self._rank_queries) > 16:
            del self._rank_queries[next(iter(self._rank_queries))]

    def project(
        self,
        claim: AttemptClaim,
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        tool_events: tuple[Mapping[str, object], ...],
    ) -> Mapping[str, object]:
        if (
            claim.thread_id != self._context.thread_id
            or claim.run_id != self._context.run_id
            or claim.model_context != self._context.model_context
        ):
            raise NetworkProjectionUnavailable("projection_model_mismatch")
        try:
            topology = self._executor.invoke(
                "operator.diagram.get", {"context_ref": self._binding.context_ref},
            )
        except SimulatorCapabilityError as error:
            code = "diagram_limit" if error.error.get("code") == "diagram_too_large" else "projection_source_unavailable"
            raise NetworkProjectionUnavailable(code) from error
        if not isinstance(topology, Mapping) or (
            topology.get("context_ref") != self._binding.context_ref
            or topology.get("revision_ref") != self._binding.model_revision
        ):
            raise NetworkProjectionUnavailable("projection_model_mismatch")
        focus = self._endpoint_focus(topology, evidence_refs, tool_events)
        ranking = self._ranking_layer(topology, result_refs, tool_events)
        return {
            "schema": "capstone-network-view/2.0", "ordinal": 1,
            "diagram": {
                "schema": "capstone-network-diagram/1.0",
                "model": {
                    "id": self._binding.model_id,
                    "revision": self._binding.model_revision,
                    "source": "gridctl",
                },
                "coordinate_system": topology.get("coordinate_system"),
                "buses": topology.get("buses"),
                "branches": topology.get("branches"),
            },
            "layer": ranking or {"focus_ids": focus, "next_focus_ids": [], "overlay": None},
        }

    def _ranking_layer(self, topology: Mapping[str, object], admitted: tuple[str, ...], events: tuple[Mapping[str, object], ...]) -> dict[str, object] | None:
        branches = topology.get("branches")
        known = {row["id"] for row in branches if isinstance(row, Mapping) and isinstance(row.get("id"), str)} if isinstance(branches, list) else set()
        for event in reversed(events):
            if event.get("binding_id") != self._binding.binding_id or event.get("capability") != "result.branches.rank" or event.get("ok") is not True:
                continue
            query = self._rank_queries.get(str(event.get("tool_call_id")))
            if query is None:
                continue
            arguments = cast(dict[str, object], query["arguments"])
            reference = arguments["result_ref"]
            event_refs = event.get("result_refs")
            if reference not in admitted or not isinstance(event_refs, (list, tuple)) or reference not in event_refs:
                continue
            ranked = self._executor.invoke("result.branches.rank", arguments)
            rows = ranked.get("branches")
            if (ranked.get("context_ref") != self._binding.context_ref or ranked.get("revision_ref") != self._binding.model_revision
                    or ranked.get("result_ref") != reference or not isinstance(rows, list)
                    or ranked.get("metric") != arguments["metric"] or ranked.get("direction") != arguments["direction"]
                    or tuple(row.get("branch_ref") for row in rows if isinstance(row, Mapping)) != query["branch_refs"]):
                continue
            focus: list[str] = []
            values: list[dict[str, object]] = []
            for row in rows:
                if not isinstance(row, Mapping) or type(row.get("pandapower_index")) is not int:
                    continue
                identifier = f"{row.get('element_kind')}:{row['pandapower_index']}"
                ids = [identifier + ":mv", identifier + ":lv"] if row.get("element_kind") == "trafo3w" else [identifier]
                for identifier in ids:
                    if identifier not in known or identifier in focus or len(focus) >= 20:
                        continue
                    focus.append(identifier)
                    value = row.get("loading_percent")
                    if identifier.startswith("line:") and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                        values.append({"id": identifier, "value": float(value)})
            if focus:
                overlay = {"metric": "loading_percent", "unit": "%", "source_ref": reference, "values": values} if values else None
                return {"focus_ids": list(dict.fromkeys(focus)), "next_focus_ids": [], "overlay": overlay}
        return None

    def _endpoint_focus(
        self,
        topology: Mapping[str, object],
        evidence_refs: tuple[str, ...],
        tool_events: tuple[Mapping[str, object], ...],
    ) -> list[str]:
        successful_refs: set[str] = set()
        for event in tool_events:
            if (event.get("binding_id") != self._binding.binding_id
                    or event.get("capability") != _ENDPOINT_CAPABILITY
                    or event.get("ok") is not True):
                continue
            refs = event.get("evidence_refs")
            if isinstance(refs, (list, tuple)):
                successful_refs.update(ref for ref in refs if isinstance(ref, str))
        branches = topology.get("branches")
        known_ids = {
            branch["id"] for branch in branches
            if isinstance(branch, Mapping) and isinstance(branch.get("id"), str)
        } if isinstance(branches, list) else set()
        focus: list[str] = []
        resolved_assets: set[str] = set()
        for reference in dict.fromkeys(evidence_refs):
            if reference not in successful_refs:
                continue
            artifact = self._authority.verify_evidence(reference)
            document = getattr(artifact, "document", None)
            if not isinstance(document, Mapping) or (
                document.get("evidence_type") != "network_fact"
                or document.get("capability_id") != _ENDPOINT_CAPABILITY
                or document.get("context_ref") != self._binding.context_ref
                or document.get("revision_ref") != self._binding.model_revision
            ):
                continue
            subject = document.get("subject_ref")
            if not isinstance(subject, str):
                continue
            match = _BRANCH_ASSET.fullmatch(subject)
            if match is None or subject in resolved_assets:
                continue
            resolved_assets.add(subject)
            kind = match.group(1)
            resolved = self._executor.invoke("model.element.get", {
                "context_ref": self._binding.context_ref, "kind": kind,
                "namespace": "asset_ref", "identifier": subject,
            })
            element = resolved.get("element")
            if (resolved.get("context_ref") != self._binding.context_ref
                    or resolved.get("revision_ref") != self._binding.model_revision
                    or resolved.get("asset_ref") != subject
                    or not isinstance(element, Mapping)
                    or element.get("asset_ref") != subject
                    or element.get("kind") != kind
                    or type(element.get("index")) is not int):
                continue
            identifier = f"{kind}:{element['index']}"
            candidates = (
                [identifier + ":mv", identifier + ":lv"] if kind == "trafo3w"
                else [identifier]
            )
            for candidate in candidates:
                if candidate in known_ids and candidate not in focus:
                    focus.append(candidate)
                    if len(focus) == 20:
                        return focus
        return focus


def build_pandapower_thread_network_provider(
    context: PreparedModelCapabilityContext,
) -> ThreadNetworkProjectionProvider:
    """Use the selected prepared binding; do not reopen or select a model."""

    if not isinstance(context, PreparedModelCapabilityContext):
        raise TypeError("pandapower topology context is invalid")
    for contribution in context.contributions:
        prepared = getattr(contribution, "prepared", None)
        binding = getattr(prepared, "model_binding", None)
        if not isinstance(binding, AuthorityModelBinding) or binding.binding_id != "grid":
            continue
        if (
            binding.model_id != context.model_context.model_id
            or binding.model_revision != context.model_context.model_revision
            or binding.implementation_family != context.model_context.implementation_family
            or binding.implementation_family != "pandapower"
        ):
            raise ValueError("pandapower model binding does not match Thread context")
        application = getattr(prepared, "prepared_application", None)
        bindings = getattr(application, "bindings", None)
        grid = bindings.get("grid") if isinstance(bindings, Mapping) else None
        runtime = getattr(grid, "runtime", None)
        executor = getattr(runtime, "executor", None)
        authority = getattr(runtime, "authority", None)
        if not callable(getattr(executor, "invoke", None)):
            raise RuntimeError("pandapower grid executor is unavailable")
        if not callable(getattr(authority, "verify_evidence", None)):
            raise RuntimeError("pandapower evidence authority is unavailable")
        return PandapowerThreadNetworkProjectionProvider(
            context, binding, cast(NetworkExecutor, executor), cast(EvidenceAuthority, authority),
        )
    raise RuntimeError("pandapower grid model binding is unavailable")
