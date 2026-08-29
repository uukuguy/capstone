from __future__ import annotations

from capability_agent.domain.contracts import FilesystemCapabilityContractSource
from capability_agent.tools.catalog import describe_tool_document


def build_inventory_tool_description(document: dict[str, object]) -> str:
    return describe_tool_document(document)


__all__ = [
    "FilesystemCapabilityContractSource",
    "build_inventory_tool_description",
]
