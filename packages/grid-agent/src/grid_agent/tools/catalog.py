from pathlib import Path

from capability_agent.tools.catalog import (
    ToolCatalog,
    ToolCatalogError,
    ToolDocument,
)
from pandapower_domain.capabilities import build_pandapower_tool_description
from pandapower_domain.capabilities import FilesystemCapabilityContractSource
from pandapower_domain.resources import PandapowerResourceSet


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
    """Load simulator contracts from the installed pandapower resources.

    ``repository_root`` remains accepted for source compatibility, but the
    domain profile owns resource discovery and deliberately ignores it.
    """

    del repository_root
    return FilesystemCapabilityContractSource(PandapowerResourceSet.load()).load()
