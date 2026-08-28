from collections.abc import Mapping
from pathlib import Path

from capability_agent.domain.contracts import FilesystemCapabilityContractSource
from capability_agent.tools.catalog import (
    ToolCatalog,
    ToolCatalogError,
    ToolDocument,
    _description as _neutral_description,
)


__all__ = [
    "ToolCatalog",
    "ToolCatalogError",
    "ToolDocument",
    "build_grid_tool_description",
    "load_packaged_capability_documents",
]


def build_grid_tool_description(document: dict[str, object]) -> str:
    """Add the product's localized presentation to a neutral tool description."""
    compatible_document = dict(document)
    not_for = list(_strings(document.get("not_for")))
    limitations = _extension_limitations(document)
    if any(
        "flow direction" in item or "power-flow direction" in item
        for item in (*not_for, *limitations)
    ) and "不表示实时功率方向" not in not_for:
        not_for.append("不表示实时功率方向")
    compatible_document["not_for"] = not_for
    return _neutral_description(compatible_document)


def load_packaged_capability_documents(
    repository_root: Path,
) -> tuple[dict[str, object], ...]:
    root = (
        Path(repository_root)
        / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
    )
    return FilesystemCapabilityContractSource(root).load()


def _extension_limitations(value: object) -> tuple[str, ...]:
    limitations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "limitations":
                limitations.extend(_strings(child))
            elif isinstance(child, (Mapping, list, tuple)):
                limitations.extend(_extension_limitations(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            limitations.extend(_extension_limitations(child))
    return tuple(limitations)


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
