from collections.abc import Mapping
from pathlib import Path
from typing import cast

from grid_agent.domain.authority import ArtifactAuthority, VerifiedArtifact, VerifiedReferenceSet
from grid_agent.domain.contracts import CapabilityContractSource
from grid_agent.domain.execution import CapabilityExecutor
from grid_agent.domain.manifest import DomainManifest
from grid_agent.domain.profile import DomainRuntimeProfile
from grid_agent.domain.projection import DomainProjector, DomainProjectorRegistry


def manifest(tmp_path: Path) -> DomainManifest:
    return DomainManifest(
        domain_id="inventory-readonly",
        version="1.0.0",
        display_name="Inventory",
        protocol="inventory-capability",
        protocol_version="1.0",
        executable_name="inventoryctl",
        tool_name_prefix="inventory_",
        authority_id="inventory-api",
        capability_contract_root=tmp_path / "contracts",
        system_policy_path=tmp_path / "policy.md",
        guide_root=tmp_path / "guides",
    )


class StubContractSource(CapabilityContractSource):
    def load(self) -> tuple[dict[str, object], ...]:
        return ()


class RecordingExecutor(CapabilityExecutor):
    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        return {}


class StubProjectorRegistry(DomainProjectorRegistry):
    def require(self, projector_id: str) -> DomainProjector:
        return cast(DomainProjector, object())


class RecordingAuthority(ArtifactAuthority):
    authority_id = "inventory-api"

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet:
        return cast(VerifiedReferenceSet, object())

    def verify_result(self, reference: str) -> VerifiedArtifact:
        return cast(VerifiedArtifact, object())

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[object, ...]:
        return ()


def test_profile_factories_create_run_scoped_dependencies(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    authority = RecordingAuthority(tmp_path / "run")
    profile = DomainRuntimeProfile(
        manifest=manifest(tmp_path),
        contract_source=StubContractSource(),
        executor_factory=lambda executable, workspace, timeout: executor,
        projector_registry=StubProjectorRegistry(),
        authority_factory=lambda workspace: authority,
    )

    assert profile.create_executor(
        tmp_path / "inventoryctl", tmp_path / "run", 30
    ) is executor
    assert profile.create_authority(tmp_path / "run") is authority
