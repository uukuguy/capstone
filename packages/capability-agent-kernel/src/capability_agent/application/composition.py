from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from capability_agent.domain.authority import ArtifactAuthority
from capability_agent.domain.execution import CapabilityExecutor
from capability_agent.domain.profile import DomainRuntimeProfile
from capability_agent.tools.catalog import ToolCatalog
from capability_agent.tools.guide import GuideIndex


@dataclass(frozen=True, slots=True)
class PreparedDomainRuntime:
    profile: DomainRuntimeProfile
    executor: CapabilityExecutor
    authority: ArtifactAuthority
    environment_description: dict[str, object]
    capability_documents: tuple[dict[str, object], ...]
    tool_catalog_path: Path
    guide_index_path: Path


def prepare_domain_runtime(
    profile: DomainRuntimeProfile,
    *,
    executable: Path,
    workspace: Path,
    tool_catalog_path: Path,
    guide_index_path: Path,
    timeout_seconds: float = 60.0,
) -> PreparedDomainRuntime:
    """Materialize the selected domain profile for one workspace."""
    profile.manifest.assert_resources_present()
    capability_documents = profile.contract_source.load()
    executor = profile.create_executor(executable, workspace, timeout_seconds)
    environment_description = executor.invoke("environment.describe", {})
    profile.manifest.assert_environment_compatible(environment_description)
    ToolCatalog.from_environment(
        capability_documents,
        environment_description,
        tool_name_prefix=profile.manifest.tool_name_prefix,
        protocol=_schema_id_from_prefix(
            profile.manifest.tool_name_prefix, "tool-catalog"
        ),
    ).materialize(tool_catalog_path)
    GuideIndex.load(
        profile.manifest.guide_root,
        protocol=_schema_id_from_protocol(profile.manifest.protocol, "guide-index"),
    ).materialize(guide_index_path)
    authority = profile.create_authority(workspace)
    return PreparedDomainRuntime(
        profile=profile,
        executor=executor,
        authority=authority,
        environment_description=environment_description,
        capability_documents=capability_documents,
        tool_catalog_path=tool_catalog_path,
        guide_index_path=guide_index_path,
    )


def _schema_id_from_prefix(tool_name_prefix: str, suffix: str) -> str:
    namespace = tool_name_prefix.rstrip("_") or "capability"
    return f"{namespace}-{suffix}"


def _schema_id_from_protocol(protocol: str, suffix: str) -> str:
    namespace = protocol.split("-", 1)[0] or "capability"
    return f"{namespace}-{suffix}"
