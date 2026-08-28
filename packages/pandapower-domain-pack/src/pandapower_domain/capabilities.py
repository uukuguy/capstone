from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from capability_agent.tools.catalog import describe_tool_document

from pandapower_domain.resources import PandapowerResourceSet


__all__ = [
    "KNOWN_CONTEXT_PROJECTORS",
    "CapabilityContextError",
    "CapabilityContextSpec",
    "CapabilityContextCatalog",
    "build_pandapower_tool_description",
    "FilesystemCapabilityContractSource",
]


KNOWN_CONTEXT_PROJECTORS = frozenset(
    {
        "artifact-observation-v1",
        "analysis-result-v1",
        "capability-catalog-v1",
        "contingency-n1-v1",
        "model-catalog-v1",
        "model-constraints-v1",
        "model-context-v1",
        "model-observation-v1",
        "powerflow-ac-v1",
        "result-view-v1",
        "topology-observation-v1",
    }
)


class CapabilityContextError(ValueError):
    """Raised when capability context metadata is missing or inconsistent."""


@dataclass(frozen=True, slots=True)
class CapabilityContextSpec:
    capability: str
    availability: str
    requires_state: tuple[str, ...]
    consumes_state: tuple[str, ...]
    produces_state: tuple[str, ...]
    invalidates_state: tuple[str, ...]
    result_kind: str | None
    projector: str


class CapabilityContextCatalog:
    def __init__(self, specs: tuple[CapabilityContextSpec, ...]) -> None:
        capabilities = [spec.capability for spec in specs]
        if len(capabilities) != len(set(capabilities)):
            raise CapabilityContextError("capability context ids must be unique")
        self._by_capability = {spec.capability: spec for spec in specs}

    @classmethod
    def from_documents(
        cls, documents: tuple[dict[str, object], ...] | list[dict[str, object]]
    ) -> CapabilityContextCatalog:
        specs = tuple(_context_spec(document) for document in documents)
        return cls(specs)

    def require(self, capability: str) -> CapabilityContextSpec:
        try:
            return self._by_capability[capability]
        except KeyError as exc:
            raise CapabilityContextError(f"unknown capability context metadata: {capability}") from exc


def _context_spec(document: dict[str, object]) -> CapabilityContextSpec:
    capability = document.get("id")
    availability = document.get("availability")
    effect = document.get("context_effect")
    if not isinstance(capability, str) or not capability:
        raise CapabilityContextError("capability context document requires id")
    if availability != "published":
        raise CapabilityContextError(f"capability context is not published: {capability}")
    if not isinstance(effect, dict):
        raise CapabilityContextError(f"capability context effect is missing: {capability}")
    projector = effect.get("projector")
    if not isinstance(projector, str) or projector not in KNOWN_CONTEXT_PROJECTORS:
        raise CapabilityContextError(f"unknown context projector for {capability}: {projector}")
    result_kind = effect.get("result_kind")
    if result_kind is not None and not isinstance(result_kind, str):
        raise CapabilityContextError(f"invalid result kind for {capability}")
    return CapabilityContextSpec(
        capability=capability,
        availability=str(availability),
        requires_state=_strings(effect, "requires_state", capability),
        consumes_state=_strings(effect, "consumes_state", capability),
        produces_state=_strings(effect, "produces_state", capability),
        invalidates_state=_strings(effect, "invalidates_state", capability),
        result_kind=result_kind,
        projector=projector,
    )


def _strings(effect: dict[str, object], field: str, capability: str) -> tuple[str, ...]:
    value = effect.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CapabilityContextError(f"{capability} {field} must be strings")
    return tuple(value)


def build_pandapower_tool_description(document: dict[str, object]) -> str:
    """Add pandapower's localized presentation to a neutral description."""

    compatible_document = dict(document)
    not_for = list(_strings_from_value(document.get("not_for")))
    limitations = _extension_limitations(document)
    if any(
        "flow direction" in item or "power-flow direction" in item
        for item in (*not_for, *limitations)
    ) and "不表示实时功率方向" not in not_for:
        not_for.append("不表示实时功率方向")
    compatible_document["not_for"] = not_for
    return describe_tool_document(compatible_document)


class FilesystemCapabilityContractSource:
    """Read simulator-owned contracts while retaining the resource owner."""

    def __init__(self, resources: PandapowerResourceSet) -> None:
        self._resources = resources
        self.root = resources.capability_contract_root

    def load(self) -> tuple[dict[str, object], ...]:
        from capability_agent.domain.contracts import (
            FilesystemCapabilityContractSource as _FilesystemCapabilityContractSource,
        )

        return _FilesystemCapabilityContractSource(self.root).load()


def _extension_limitations(value: object) -> tuple[str, ...]:
    limitations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "limitations":
                limitations.extend(_strings_from_value(child))
            elif isinstance(child, (Mapping, list, tuple)):
                limitations.extend(_extension_limitations(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            limitations.extend(_extension_limitations(child))
    return tuple(limitations)


def _strings_from_value(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
