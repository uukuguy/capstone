from __future__ import annotations

from capability_agent.domain import DomainManifest, DomainRuntimeProfile

from inventory_domain.authority import InventoryArtifactAuthority
from inventory_domain.capabilities import (
    FilesystemCapabilityContractSource,
    build_inventory_tool_description,
)
from inventory_domain.execution import InventoryctlExecutor
from inventory_domain.projection import InventoryProjectorRegistry
from inventory_domain.resources import InventoryResourceSet
from inventory_domain.acceptance import InventoryAcceptanceProfile
from inventory_domain.answer_admission import InventoryAnswerAdmissionPolicyFactory
from inventory_domain.answer_policy import InventoryAnswerEvidencePolicy
from inventory_domain.guide import InventoryGuideProvider, InventoryPolicyProvider
from inventory_domain.output import InventoryOutputContract
from inventory_domain.presentation import InventoryPresentationProvider
from inventory_domain.provisioning import InventoryRuntimeProvisioner
from inventory_domain.state import InventoryStateAdapter


def build_inventory_profile() -> DomainRuntimeProfile:
    resources = InventoryResourceSet.load()
    guides = InventoryGuideProvider(resources.guide_root)
    manifest = DomainManifest(
        domain_id="inventory-readonly",
        version="0.1.0",
        display_name="Read-only Inventory",
        protocol="inventory-capability",
        protocol_version="1.0",
        executable_name="inventoryctl",
        tool_name_prefix="inventory_",
        authority_id="inventoryctl",
        capability_contract_root=resources.capability_contract_root,
        system_policy_path=resources.system_policy_path,
        guide_root=resources.guide_root,
    )
    return DomainRuntimeProfile(
        manifest=manifest,
        contract_source=FilesystemCapabilityContractSource(
            resources.capability_contract_root
        ),
        executor_factory=lambda executable, workspace, timeout: InventoryctlExecutor(
            executable=executable,
            workspace=workspace,
            timeout_seconds=timeout,
        ),
        projector_registry=InventoryProjectorRegistry(),
        authority_factory=InventoryArtifactAuthority,
        tool_description_builder=build_inventory_tool_description,
        provisioner=InventoryRuntimeProvisioner(),
        state_adapter=InventoryStateAdapter(),
        answer_policy=InventoryAnswerEvidencePolicy(),
        answer_admission_policy_factory=InventoryAnswerAdmissionPolicyFactory(guides),
        answer_admission_policy_version="answer-admission/1.0",
        answer_admission_capabilities=frozenset({"authority_backed", "offline_information", "limited"}),
        policy_provider=InventoryPolicyProvider(resources.system_policy_path),
        guide_provider=guides,
        presentation_provider=InventoryPresentationProvider(),
        output_contract=InventoryOutputContract(),
        acceptance_profile=InventoryAcceptanceProfile(),
    )
