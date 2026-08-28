from __future__ import annotations

from collections.abc import Callable, Mapping
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
    "load_packaged_capability_documents",
]


_GRID_TOOL_NAME_PREFIX = "grid_"
_GRID_CATALOG_PROTOCOL = "grid-tool-catalog"


def load_packaged_capability_documents(
    repository_root: Path,
) -> tuple[dict[str, object], ...]:
    root = (
        Path(repository_root)
        / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
    )
    return FilesystemCapabilityContractSource(root).load()


def _grid_description(document: dict[str, object]) -> str:
    compatible_document = dict(document)
    not_for = list(_strings(document.get("not_for")))
    not_for.extend(_extension_limitations(document))
    if any(
        "flow direction" in item or "power-flow direction" in item
        for item in not_for
    ):
        not_for.append("不表示实时功率方向")
    compatible_document["not_for"] = not_for
    return _neutral_description(compatible_document)


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


def _compat_prefix(
    documents: tuple[dict[str, object], ...],
    explicit_prefix: str | None,
) -> str | None:
    if explicit_prefix is not None:
        return explicit_prefix
    for document in documents:
        tool_name = document.get("tool_name")
        if isinstance(tool_name, str) and tool_name.startswith(_GRID_TOOL_NAME_PREFIX):
            return _GRID_TOOL_NAME_PREFIX
    return None


_neutral_from_documents = getattr(
    ToolCatalog,
    "_kernel_neutral_from_documents",
    ToolCatalog.from_documents.__func__,
)
_neutral_from_environment = getattr(
    ToolCatalog,
    "_kernel_neutral_from_environment",
    ToolCatalog.from_environment.__func__,
)
if not hasattr(ToolCatalog, "_kernel_neutral_from_documents"):
    setattr(ToolCatalog, "_kernel_neutral_from_documents", _neutral_from_documents)
    setattr(ToolCatalog, "_kernel_neutral_from_environment", _neutral_from_environment)


def _compat_from_documents(
    cls: type[ToolCatalog],
    documents: tuple[dict[str, object], ...] | list[dict[str, object]],
    *,
    tool_name_prefix: str | None = None,
    protocol: str | None = None,
    description_builder: Callable[[dict[str, object]], str] | None = None,
) -> ToolCatalog:
    values = tuple(documents)
    if _compat_prefix(values, tool_name_prefix) == _GRID_TOOL_NAME_PREFIX:
        protocol = _GRID_CATALOG_PROTOCOL if protocol is None else protocol
        description_builder = (
            _grid_description if description_builder is None else description_builder
        )
    return _neutral_from_documents(
        cls,
        values,
        tool_name_prefix=tool_name_prefix,
        protocol=protocol,
        description_builder=description_builder,
    )


def _compat_from_environment(
    cls: type[ToolCatalog],
    documents: tuple[dict[str, object], ...] | list[dict[str, object]],
    environment_description: dict[str, object],
    *,
    tool_name_prefix: str | None = None,
    protocol: str | None = None,
    description_builder: Callable[[dict[str, object]], str] | None = None,
) -> ToolCatalog:
    values = tuple(documents)
    if _compat_prefix(values, tool_name_prefix) == _GRID_TOOL_NAME_PREFIX:
        protocol = _GRID_CATALOG_PROTOCOL if protocol is None else protocol
        description_builder = (
            _grid_description if description_builder is None else description_builder
        )
    return _neutral_from_environment(
        cls,
        values,
        environment_description,
        tool_name_prefix=tool_name_prefix,
        protocol=protocol,
        description_builder=description_builder,
    )


if not getattr(ToolCatalog, "_grid_compatibility_installed", False):
    ToolCatalog.from_documents = classmethod(_compat_from_documents)
    ToolCatalog.from_environment = classmethod(_compat_from_environment)
    setattr(ToolCatalog, "_grid_compatibility_installed", True)
