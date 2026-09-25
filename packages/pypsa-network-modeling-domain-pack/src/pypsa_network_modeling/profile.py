"""Complete public Kernel SPI for PyPSA Network modeling."""

from __future__ import annotations

from capability_agent.domain import DomainManifest, DomainRuntimeProfile
from capability_agent.domain.contracts import FilesystemCapabilityContractSource
from capability_agent.tools.catalog import describe_tool_document

from pypsa_network_modeling.acceptance import ModelAcceptanceProfile
from pypsa_network_modeling.authority import PypsaModelArtifactAuthority
from pypsa_network_modeling.execution import ModelctlExecutor
from pypsa_network_modeling.output import ModelOutputContract, ModelPresentationProvider
from pypsa_network_modeling.policy import ModelAnswerAdmissionPolicy, ModelAnswerEvidencePolicy
from pypsa_network_modeling.projection import ModelProjectorRegistry
from pypsa_network_modeling.provisioning import ModelRuntimeProvisioner
from pypsa_network_modeling.resources import (
    CONTRACT_ROOT, GUIDE_ROOT, POLICY_PATH, ModelGuideProvider,
    ModelPolicyProvider,
)
from pypsa_network_modeling.state import ModelStateAdapter


def build_pypsa_network_modeling_profile() -> DomainRuntimeProfile:
    manifest = DomainManifest(
        domain_id="pypsa-network-modeling", version="0.1.0",
        display_name="PyPSA Network Modeling",
        protocol="pypsa-model-capability", protocol_version="1.0",
        executable_name="pypsamodelctl", tool_name_prefix="pypsa_model_",
        authority_id="pypsamodelctl", capability_contract_root=CONTRACT_ROOT,
        system_policy_path=POLICY_PATH, guide_root=GUIDE_ROOT,
    )
    return DomainRuntimeProfile(
        manifest=manifest,
        contract_source=FilesystemCapabilityContractSource(CONTRACT_ROOT),
        executor_factory=lambda executable, workspace, timeout: ModelctlExecutor(
            executable=executable, workspace=workspace, timeout_seconds=timeout,
        ),
        projector_registry=ModelProjectorRegistry(),
        authority_factory=PypsaModelArtifactAuthority,
        answer_admission_policy_factory=ModelAnswerAdmissionPolicy,
        answer_admission_policy_version="answer-admission/1.0",
        answer_admission_capabilities=frozenset({"authority_backed", "limited"}),
        tool_description_builder=describe_tool_document,
        provisioner=ModelRuntimeProvisioner(),
        state_adapter=ModelStateAdapter(),
        answer_policy=ModelAnswerEvidencePolicy(),
        policy_provider=ModelPolicyProvider(),
        guide_provider=ModelGuideProvider(),
        presentation_provider=ModelPresentationProvider(),
        output_contract=ModelOutputContract(),
        acceptance_profile=ModelAcceptanceProfile(),
    )
