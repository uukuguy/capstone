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
from pandapower_domain.authority import SimulatorIntegrityError, VerifiedArtifact
from pandapower_domain.network_annotations import project_scene_annotations, select_contingency_scene, project_base_disconnections
from capstone_agent.thread_service import AttemptClaim

from .network_view import NetworkExecutor


_BRANCH_ASSET = re.compile(r"^asset:(line|trafo|trafo3w):sha256:[0-9a-f]{64}$")
_ENDPOINT_CAPABILITY = "topology.branch.endpoints.get"


class EvidenceAuthority(Protocol):
    def verify_evidence(self, reference: str) -> object: ...
    def verify_result(self, reference: str) -> VerifiedArtifact: ...
    def verify_linked_result(self, reference: str, parent_ref: str) -> VerifiedArtifact: ...
    def verify_context_descendant(self, reference: str, ancestor_ref: str) -> VerifiedArtifact: ...


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
        self._scene_cache: dict[str, dict[str, object]] = {}
        self._observed_topology: dict[str, dict[str, object]] = {}

    def observe_runtime_event(self, event: Mapping[str, object]) -> None:
        """Retain only bounded query metadata; the authority rechecks the rows."""
        if event.get("type") not in {"tool_execution_end", "tool_result"}:
            return
        raw = event.get("result")
        details = event if event.get("event") == "tool_result" else (
            raw.get("details") if isinstance(raw, Mapping) else event.get("details")
        )
        if not isinstance(details, Mapping) or details.get("ok") is not True:
            return
        owner = details.get("capability_key")
        result = details.get("result")
        if (details.get("capability") == "topology.components.get" and isinstance(owner, Mapping)
                and owner.get("binding_id") == self._binding.binding_id and isinstance(result, Mapping)):
            reference = result.get("context_ref")
            components = result.get("components")
            if (isinstance(reference, str) and re.fullmatch(r"context:sha256:[0-9a-f]{64}", reference)
                    and isinstance(result.get("revision_ref"), str) and isinstance(components, list)
                    and len(components) <= 10_000):
                self._observed_topology[reference] = dict(result)
                if len(self._observed_topology) > 16:
                    del self._observed_topology[next(iter(self._observed_topology))]
            return
        if details.get("capability") != "result.branches.rank":
            return
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
        annotations = self._scene_annotations(topology, result_refs, tool_events)
        scene = annotations.get("scene") if annotations is not None else None
        scene_ref = scene.get("source_ref") if isinstance(scene, Mapping) else None
        ranking = self._ranking_layer(topology, result_refs, tool_events, scene_ref)
        layer = ranking or {"focus_ids": focus, "next_focus_ids": [], "overlay": None}
        if annotations is not None:
            layer["annotations"] = annotations
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
                "disconnections": project_base_disconnections(topology),
            },
            "layer": layer,
        }

    def _scene_annotations(
        self, diagram: Mapping[str, object], admitted: tuple[str, ...],
        events: tuple[Mapping[str, object], ...],
    ) -> dict[str, object] | None:
        roots: list[tuple[str, Mapping[str, object]]] = []
        for reference in admitted:
            try:
                document = self._authority.verify_result(reference).document
                context = document.get("context_ref")
                if not isinstance(context, str):
                    continue
                verified = self._authority.verify_context_descendant(context, self._binding.context_ref)
                if verified.document.get("revision_ref") == document.get("revision_ref"):
                    roots.append((reference, document))
            except (SimulatorIntegrityError, ValueError):
                continue
        selected = select_contingency_scene(roots)
        linked_cases = {
            reference: selection[1] for reference, document in roots
            if (selection := select_contingency_scene([(reference, document)])) is not None
        }
        # Admission order records first appearance. Completed calculations and
        # later reads both select a scene in this attempt's actual event order.
        interacted: list[str] = []
        for event in reversed(events):
            if event.get("binding_id") != self._binding.binding_id or event.get("ok") is not True:
                continue
            capability = event.get("capability")
            event_refs = event.get("result_refs")
            if not isinstance(event_refs, (list, tuple)):
                continue
            if isinstance(capability, str) and capability.startswith("analysis."):
                interacted.extend(ref for ref in reversed(event_refs) if isinstance(ref, str) and ref in admitted)
                continue
            if capability not in {"result.aggregate", "result.dataset.query", "result.branches.rank"}:
                continue
            arguments = event.get("request_parameters")
            if not isinstance(arguments, Mapping) and capability == "result.branches.rank":
                query = self._rank_queries.get(str(event.get("tool_call_id")))
                arguments = query.get("arguments") if query is not None else None
            reference = arguments.get("result_ref") if isinstance(arguments, Mapping) else None
            if isinstance(reference, str) and reference in admitted and reference in event_refs:
                interacted.append(reference)
        candidates = interacted + ([selected[0]] if selected else []) + list(reversed(admitted))
        for reference in dict.fromkeys(candidates):
            if reference in self._scene_cache:
                return self._scene_cache[reference]
            try:
                case_ref = linked_cases.get(reference)
                result = (self._authority.verify_linked_result(case_ref, reference).document
                          if case_ref else self._authority.verify_result(reference).document)
                datasets = result.get("datasets")
                if not isinstance(datasets, Mapping) or "result.res_bus" not in datasets:
                    continue
                context_ref = result.get("context_ref")
                revision = result.get("revision_ref")
                if not isinstance(context_ref, str) or not isinstance(revision, str):
                    continue
                verified = self._authority.verify_context_descendant(context_ref, self._binding.context_ref)
                if verified.document.get("revision_ref") != revision:
                    continue
                scene_diagram = diagram
                if context_ref != self._binding.context_ref:
                    scene_diagram = self._executor.invoke("operator.diagram.get", {"context_ref": context_ref})
                    def geometry_identity(value: Mapping[str, object]) -> tuple[set[str], set[tuple[str, ...]]]:
                        buses = value.get("buses")
                        branches = value.get("branches")
                        if not isinstance(buses, list) or not isinstance(branches, list):
                            raise ValueError("scene geometry is invalid")
                        return ({str(row["id"]) for row in buses}, {
                            tuple(str(row[key]) for key in ("id", "kind", "from_bus", "to_bus")) for row in branches})
                    if (scene_diagram.get("context_ref") != context_ref or scene_diagram.get("revision_ref") != revision
                            or geometry_identity(scene_diagram) != geometry_identity(diagram)):
                        raise NetworkProjectionUnavailable("projection_model_mismatch")
                topology = ({"context_ref": context_ref, "revision_ref": revision, "components": []}
                            if isinstance(result.get("outage"), Mapping) else self._observed_topology.get(context_ref))
                if topology is None or topology.get("revision_ref") != revision:
                    topology = dict(self._executor.invoke("topology.components.get", {"context_ref": context_ref}))
                state_facts: dict[str, object] = {"context_ref": context_ref, "revision_ref": revision}
                if isinstance(scene_diagram.get("branch_states"), list):
                    state_facts["branch_states"] = scene_diagram["branch_states"]
                else:
                    rows: list[object] = []
                    offset = 0
                    while True:
                        page = self._executor.invoke("model.dataset.query", {
                            "context_ref": context_ref, "dataset": "network.line", "select": ["index", "in_service"],
                            "where": {"in_service": False}, "limit": 50, "offset": offset,
                        })
                        page_rows = page.get("rows")
                        if not isinstance(page_rows, list) or page.get("context_ref") != context_ref or page.get("revision_ref") != revision:
                            raise ValueError("scene model facts do not match the result")
                        rows.extend(page_rows)
                        next_offset = page.get("next_offset")
                        if next_offset is None:
                            break
                        if type(next_offset) is not int or next_offset <= offset or len(rows) > 20_000:
                            raise ValueError("scene model pagination is invalid")
                        offset = next_offset
                    state_facts["rows"] = rows
                annotations = project_scene_annotations(diagram, result, topology, state_facts, source_ref=reference)
                if case_ref:
                    scene = cast(dict[str, object], annotations["scene"])
                    scene["case_ref"] = case_ref
                    scene["label"] = f"N−1 最高线路负载率场景 · {scene['label']}"
                self._scene_cache[reference] = annotations
                if len(self._scene_cache) > 16:
                    del self._scene_cache[next(iter(self._scene_cache))]
                return annotations
            except (SimulatorIntegrityError, SimulatorCapabilityError, ValueError):
                continue
        return None

    def _ranking_layer(
        self, topology: Mapping[str, object], admitted: tuple[str, ...],
        events: tuple[Mapping[str, object], ...], scene_ref: object = None,
    ) -> dict[str, object] | None:
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
            if scene_ref is not None and reference != scene_ref:
                continue
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
