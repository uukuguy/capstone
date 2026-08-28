from pathlib import Path

from capability_agent.domain.contracts import FilesystemCapabilityContractSource
from capability_agent.tools.catalog import ToolCatalog, ToolCatalogError, ToolDocument


__all__ = [
    "ToolCatalog",
    "ToolCatalogError",
    "ToolDocument",
    "load_packaged_capability_documents",
]


def load_packaged_capability_documents(
    repository_root: Path,
) -> tuple[dict[str, object], ...]:
    root = (
        Path(repository_root)
        / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
    )
    return FilesystemCapabilityContractSource(root).load()
