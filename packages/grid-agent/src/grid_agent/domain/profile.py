from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from grid_agent.domain.authority import ArtifactAuthority
from grid_agent.domain.contracts import CapabilityContractSource
from grid_agent.domain.execution import CapabilityExecutor
from grid_agent.domain.manifest import DomainManifest
from grid_agent.domain.projection import DomainProjectorRegistry


ExecutorFactory = Callable[[Path, Path, float], CapabilityExecutor]
AuthorityFactory = Callable[[Path], ArtifactAuthority]


@dataclass(frozen=True, slots=True)
class DomainRuntimeProfile:
    manifest: DomainManifest
    contract_source: CapabilityContractSource
    executor_factory: ExecutorFactory
    projector_registry: DomainProjectorRegistry
    authority_factory: AuthorityFactory

    def create_executor(
        self, executable: Path, workspace: Path, timeout_seconds: float
    ) -> CapabilityExecutor:
        return self.executor_factory(executable, workspace, timeout_seconds)

    def create_authority(self, workspace: Path) -> ArtifactAuthority:
        return self.authority_factory(workspace)
