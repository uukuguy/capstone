from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from grid_agent.analysis.capabilities import (
    KNOWN_CONTEXT_PROJECTORS,
    CapabilityContextSpec,
)
from grid_agent.analysis.domain_projection import project_domain_result
from grid_agent.analysis.integrity import (
    ContentReferenceVerifier,
    ReferenceDiagnostic,
    VerifiedArtifact,
    VerifiedReferenceSet,
)
from grid_agent.domain.contracts import FilesystemCapabilityContractSource
from grid_agent.domain.manifest import DomainManifest
from grid_agent.domain.profile import DomainRuntimeProfile
from grid_agent.domain.projection import DomainStateDelta, VerifiedInvocation
from grid_agent.simulator.client import GridctlClient
from grid_agent.tools.catalog import build_grid_tool_description


class PandapowerProjectorLookupError(LookupError):
    """The pandapower profile does not register the requested projector."""


class PandapowerArtifactAuthority:
    authority_id = "gridctl"

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self._verifier = ContentReferenceVerifier(workspace_root)

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet:
        return self._verifier.admit_successful_tool_references(
            capability, result, evidence_refs
        )

    def verify_result(self, reference: str) -> VerifiedArtifact:
        return self._verifier.verify_result(reference)

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[ReferenceDiagnostic, ...]:
        return self._verifier.audit_answer_references(
            claim_evidence_refs, result_refs
        )


@dataclass(frozen=True, slots=True)
class _PandapowerProjector:
    projector_id: str

    def project(self, invocation: VerifiedInvocation) -> DomainStateDelta:
        spec = CapabilityContextSpec(
            capability=invocation.capability,
            availability="published",
            requires_state=(),
            consumes_state=(),
            produces_state=(),
            invalidates_state=(),
            result_kind=invocation.result_kind,
            projector=invocation.projector_id,
        )
        return project_domain_result(
            spec,
            result=invocation.result,
            arguments=invocation.arguments,
            turn_id=invocation.turn_id,
            result_paths=invocation.result_paths,
            active_revision_ref=invocation.active_revision_ref,
        )


class PandapowerProjectorRegistry:
    def __init__(self) -> None:
        self._by_id = {
            projector_id: _PandapowerProjector(projector_id)
            for projector_id in KNOWN_CONTEXT_PROJECTORS
        }

    def require(self, projector_id: str) -> _PandapowerProjector:
        try:
            return self._by_id[projector_id]
        except KeyError as exc:
            raise PandapowerProjectorLookupError(
                f"unknown projector: {projector_id}"
            ) from exc


def build_pandapower_profile(repository_root: Path) -> DomainRuntimeProfile:
    root = Path(repository_root).resolve()
    manifest = DomainManifest(
        domain_id="pandapower-static-analysis",
        version="1.0.1",
        display_name="Pandapower Static Analysis",
        protocol="grid-capability",
        protocol_version="1.0",
        executable_name="gridctl",
        tool_name_prefix="grid_",
        authority_id="gridctl",
        capability_contract_root=(
            root
            / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
        ),
        system_policy_path=root / "configs/agent/system-policy.md",
        guide_root=root / "skills/grid-static-analysis",
    )
    return DomainRuntimeProfile(
        manifest=manifest,
        contract_source=FilesystemCapabilityContractSource(
            manifest.capability_contract_root
        ),
        executor_factory=lambda executable, workspace, timeout: GridctlClient(
            executable=executable,
            workspace=workspace,
            timeout_seconds=timeout,
        ),
        projector_registry=PandapowerProjectorRegistry(),
        authority_factory=PandapowerArtifactAuthority,
        tool_description_builder=build_grid_tool_description,
    )
