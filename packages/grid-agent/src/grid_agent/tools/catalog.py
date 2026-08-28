from pathlib import Path

from capability_agent.domain.contracts import FilesystemCapabilityContractSource
from capability_agent.tools.catalog import (
    ToolCatalog,
    ToolCatalogError,
    ToolDocument,
)
from pandapower_domain.capabilities import build_pandapower_tool_description


__all__ = [
    "ToolCatalog",
    "ToolCatalogError",
    "ToolDocument",
    "build_grid_tool_description",
    "load_packaged_capability_documents",
]


def build_grid_tool_description(document: dict[str, object]) -> str:
    """Compatibility alias for the domain-owned localized description."""

    return build_pandapower_tool_description(document)


def load_packaged_capability_documents(
    repository_root: Path,
) -> tuple[dict[str, object], ...]:
    root = (
        Path(repository_root)
        / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
    )
    return FilesystemCapabilityContractSource(root).load()
