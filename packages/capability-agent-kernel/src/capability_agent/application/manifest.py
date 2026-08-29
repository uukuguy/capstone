"""Application identity and schema declarations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplicationManifest:
    application_id: str
    version: str
    display_name: str
    context_schema: str
    result_schema: str
    artifact_schema: str
    core_tool_namespace: str


__all__ = ["ApplicationManifest"]
